from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.prepared_corpus_query_only import (
    EXPECTED_DATABASE_NAME,
    FULL_QUERY_ONLY_MODES,
    PROVISIONAL_SCORE_LABEL,
    QueryOnlyOperationCounters,
    _provider_usage_totals,
    _sum_operation_counters,
    _verify_payload_boundaries,
    cleanup_prepared_workspace,
    inspect_prepared_corpus,
    load_prepared_corpus_manifest,
    make_readiness_selection_plan,
    query_only_dry_run_plan,
    run_prepared_query_only,
    safe_rmtree,
    validate_prepared_database_url,
)


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mysql_url(database_name: str) -> str:
    return "mysql+pymysql://" + "user" + ":" + "pass" + f"@127.0.0.1:3307/{database_name}"


def _write_fixture_files(tmp_path: Path, *, query_count: int = 1) -> tuple[Path, Path]:
    corpus = tmp_path / "combined_corpus_fixture.json"
    doc_id = "00000000-0000-5000-8000-000000000001"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "infobank-actual-corpus-v1",
                "metadata": {"dataset_version": "s1-s6-combined-journal-evaluation-v2"},
                "documents": [
                    {
                        "document_id": doc_id,
                        "package_ref": "pkg",
                        "object_id": "OBJ-1",
                        "document_type": "manual",
                        "original_filename": "manual.pdf",
                        "pages": ["safe text"],
                        "keywords": ["safe"],
                    }
                ],
                "policy_fixtures": [
                    {
                        "fixture_id": "fixture",
                        "access_by_document": {doc_id: "Full"},
                        "purpose": "grounded_question_answering",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    queries = tmp_path / "combined_query_inputs.jsonl"
    queries.write_text(
        "".join(
            json.dumps(
                {
                    "case_id": f"Q{i:02d}",
                    "evaluation_identity": "identity",
                    "query_text": f"What is safe fact {i}?",
                    "declared_purpose": "grounded_question_answering",
                    "corpus_package_ref": "pkg",
                    "policy_fixture_ref": "fixture",
                    "runtime_parameters": {"top_k": 1},
                    "schema_version": "infobank-query-input-v1",
                }
            )
            + "\n"
            for i in range(query_count)
        ),
        encoding="utf-8",
    )
    return corpus, queries


def _write_manifest(tmp_path: Path, **overrides) -> Path:
    chroma_dir = tmp_path / "runtime" / "chroma"
    source_dir = tmp_path / "runtime" / "source_storage"
    chroma_dir.mkdir(parents=True)
    source_dir.mkdir(parents=True)
    source_count = int(overrides.pop("source_count", 41))
    for index in range(source_count):
        (source_dir / f"source-{index:02d}.pdf").write_bytes(b"%PDF-1.4\n")
    corpus, queries = _write_fixture_files(tmp_path, query_count=int(overrides.pop("query_count", 1)))
    manifest = {
        "schema_version": "infobank-openai-prepared-corpus-v1",
        "created_at_utc": "2026-09-04T16:36:58.901233+00:00",
        "preparation_status": "READY",
        "purpose": "test prepared corpus",
        "database": {
            "name": EXPECTED_DATABASE_NAME,
            "table_counts": {
                "documents": 41,
                "document_chunks": 245,
                "document_keywords": 1640,
                "keywords": 584,
                "user_document_permission": 253,
                "users": 33,
            },
        },
        "chroma": {
            "persist_dir": str(chroma_dir),
            "total_vector_count": 245,
            "collections": [{"name": "actual_from_manifest", "count": 245, "metadata": {"hnsw:space": "cosine"}}],
        },
        "source_storage": {"dir": str(source_dir), "file_count": 41, "total_bytes": 1},
        "inputs": {
            "dataset_version": "s1-s6-combined-journal-evaluation-v2",
            "document_count": 41,
            "page_count": 202,
            "policy_fixture_count": 32,
            "query_count": 42,
            "corpus_fixture_path": str(corpus),
            "corpus_fixture_sha256": _sha256(corpus),
            "query_input_path": str(queries),
            "query_input_sha256": _sha256(queries),
        },
        "actual_pipeline_config": {
            "config_hash": "002e7aea57218737b16baec95cb819a6b6264d4262581bd54ddb1f603db0e7cf",
            "config_version": "actual-pipeline-development-config-v1",
            "embedding_model": "text-embedding-3-small",
            "generation_model": "infobank-deterministic-extractive-v1",
        },
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "queries_run": 0,
        "generation_calls": 0,
        "keyword_selection_calls": 0,
        "openai_embedding_input_count": 245,
        "openai_embedding_requests_inferred_from_seed_path": 1,
    }
    for dotted_key, value in overrides.items():
        target = manifest
        parts = dotted_key.split("__")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    path = tmp_path / "prepare_manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    return path


def test_prepared_corpus_mode_reads_manifest_and_records_identity(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    prepared = load_prepared_corpus_manifest(manifest_path)
    assert prepared.database_name == EXPECTED_DATABASE_NAME
    assert prepared.chroma_collection_name == "actual_from_manifest"
    assert prepared.embedding_provider == "openai"
    assert prepared.embedding_model == "text-embedding-3-small"
    assert prepared.embedding_dimensions == 1536
    assert len(prepared.manifest_sha256) == 64
    assert prepared.metadata()["prepared_manifest_sha256"] == prepared.manifest_sha256


@pytest.mark.parametrize(
    ("override", "value", "message"),
    [
        ("schema_version", "wrong", "schema/version"),
        ("database__name", "wrong_db", "database name"),
        ("database__name", "infobank_db", "must start with infobank_eval_"),
        ("inputs__document_count", 40, "document count"),
        ("database__table_counts__document_chunks", 244, "chunk count"),
        ("chroma__total_vector_count", 244, "vector count"),
        ("source_storage__file_count", 40, "source PDF count"),
        ("embedding_provider", "anthropic", "embedding provider"),
        ("embedding_model", "other-embedding", "embedding model"),
        ("embedding_dimensions", 24, "embedding dimensions"),
        ("preparation_status", "BUILDING", "preparation status"),
        ("queries_run", 1, "query execution"),
    ],
)
def test_prepared_manifest_rejects_invalid_required_values(tmp_path: Path, override: str, value, message: str) -> None:
    kwargs = {override: value}
    if override == "source_storage__file_count":
        kwargs["source_count"] = value
    manifest_path = _write_manifest(tmp_path, **kwargs)
    with pytest.raises(ValueError, match=message):
        load_prepared_corpus_manifest(manifest_path)


def test_prepared_database_url_must_match_manifest_and_eval_prefix(tmp_path: Path) -> None:
    prepared = load_prepared_corpus_manifest(_write_manifest(tmp_path))
    validate_prepared_database_url(
        prepared,
        _mysql_url("infobank_eval_claude_prepare_20260904"),
    )
    with pytest.raises(ValueError, match="manifest requires"):
        validate_prepared_database_url(prepared, _mysql_url("infobank_eval_other"))
    with pytest.raises(ValueError, match="must start with infobank_eval_"):
        validate_prepared_database_url(prepared, _mysql_url("infobank_db"))


def test_missing_chroma_collection_fails_instead_of_creating_one(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    with pytest.raises(RuntimeError, match="refuses to create collections"):
        inspect_prepared_corpus(prepared_manifest_path=manifest_path, chroma_probe=False)


def test_collection_identity_comes_from_manifest_not_llm_provider(tmp_path: Path) -> None:
    prepared = load_prepared_corpus_manifest(_write_manifest(tmp_path))
    anthropic_metadata = prepared.metadata(cache_namespace_version="anthropic-cache")
    openai_metadata = prepared.metadata(cache_namespace_version="openai-cache")
    assert anthropic_metadata["prepared_chroma_collection_name"] == "actual_from_manifest"
    assert openai_metadata["prepared_chroma_collection_name"] == "actual_from_manifest"
    assert anthropic_metadata["prepared_chroma_collection_name"] != "actual_anthropic_derived"


def test_query_only_guards_raise_on_reprocessing_attempts() -> None:
    from evaluation.actual_pipeline_runner import QueryOnlyChromaCollectionGuard, QueryOnlyDocumentProcessingGuard

    counters = QueryOnlyOperationCounters()

    class WrappedProcessing:
        DEFAULT_PROCESSING_CONFIG = object()

    class WrappedCollection:
        name = "prepared"
        metadata = {}

    processing = QueryOnlyDocumentProcessingGuard(WrappedProcessing(), counters)
    collection = QueryOnlyChromaCollectionGuard(WrappedCollection(), counters)
    with pytest.raises(RuntimeError, match="PDF extraction"):
        processing.extract_pdf_pages(b"x")
    with pytest.raises(RuntimeError, match="chunking"):
        processing.chunk_pages("doc", [])
    with pytest.raises(RuntimeError, match="Chroma vector insertion"):
        collection.add(ids=[])
    assert counters.document_pdf_parse_calls == 1
    assert counters.document_chunking_calls == 1
    assert counters.chroma_add_calls == 1


def test_query_only_run_uses_seed_false_fresh_groups_and_manifest_collection(monkeypatch, tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, query_count=2)
    created_runtime_kwargs = []
    dropped = []

    def fake_inspect(**kwargs):
        del kwargs
        return {
            "database_counts": {"documents": 41, "document_chunks": 245},
            "source_storage_fingerprint": {"sha256": "source"},
            "chroma_vector_count": 245,
            "chroma_collection_count": 245,
            "chroma_fingerprint_before": {"sha256": "chroma"},
        }

    def fake_clone(**kwargs):
        return {
            "source_database_name": EXPECTED_DATABASE_NAME,
            "target_database_name": kwargs["target_url"].rsplit("/", 1)[-1],
            "target_counts": {"documents": 41, "document_chunks": 245, "user_document_permission": 253},
        }

    def fake_copy(prepared, workspace, *, workspace_root):
        del prepared, workspace_root
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "chroma").mkdir()
        (workspace / "source_storage").mkdir()
        return {
            "workspace": workspace,
            "chroma_dir": workspace / "chroma",
            "source_storage_dir": workspace / "source_storage",
            "chroma_fingerprint": {"sha256": "copy-chroma"},
            "source_storage_fingerprint": {"sha256": "copy-source"},
        }

    def fake_drop(**kwargs):
        dropped.append(kwargs["database_url"].rsplit("/", 1)[-1])

    class FakeRuntime:
        def __init__(self, **kwargs):
            created_runtime_kwargs.append(kwargs)
            assert kwargs["seed_corpus"] is False
            assert kwargs["prepared_collection_name"] == "actual_from_manifest"
            assert kwargs["operation_counters"] is not None
            self.counter = kwargs["operation_counters"]

        def run_case(self, query, mode):
            self.counter.query_embedding_calls += 1
            if mode in {"C1_VECTOR_ROUTING", "P1_PROMPT_ONLY_GOVERNANCE", "C3_FULL_ROLE_AWARE"}:
                self.counter.keyword_selection_calls += 1
            self.counter.generation_calls += 1
            return (
                {
                    "schema_version": "infobank-actual-raw-record-v1",
                    "runner_version": "test",
                    "dataset_version": "s1-s6-combined-journal-evaluation-v2",
                    "case_id": query.case_id,
                    "mode": mode,
                    "candidate_ids": [],
                    "retrieved_document_ids": [],
                    "generator_visible_document_ids": [],
                    "generator_visible_text": "",
                    "actual_output_text": "safe",
                    "actual_output_class": "FULL_ANSWER",
                    "actual_citations": [],
                    "routing_trace": {
                        "keyword_provider_trace": {
                            "input_tokens": 2,
                            "output_tokens": 1,
                            "provider_request_id": f"kw-{query.case_id}-{mode}",
                        }
                    },
                    "provider_usage": {
                        "input_tokens": 3,
                        "output_tokens": 2,
                        "total_tokens": 5,
                        "retries": 0,
                        "provider_request_id": f"gen-{query.case_id}-{mode}",
                    },
                    "generation_skipped": False,
                    "safety_constraints": {
                        "prohibited_document_ids": [],
                        "prohibited_markers": [],
                        "archived_document_ids": [],
                    },
                    "operation_counters": self.counter.delta({key: 0 for key in self.counter.snapshot()}),
                    "llm_provider": "anthropic",
                    "llm_model": "claude-haiku-4-5-20251001",
                    "embedding_provider": "openai",
                    "embedding_model": "text-embedding-3-small",
                    "error": None,
                },
                {"total": 1.0},
            )

    monkeypatch.setattr("evaluation.prepared_corpus_query_only.inspect_prepared_corpus", fake_inspect)
    monkeypatch.setattr("evaluation.prepared_corpus_query_only.clone_mysql_database", fake_clone)
    monkeypatch.setattr("evaluation.prepared_corpus_query_only.copy_prepared_workspace", fake_copy)
    monkeypatch.setattr("evaluation.prepared_corpus_query_only.cleanup_prepared_workspace", lambda *a, **k: {"status": "removed"})
    monkeypatch.setattr("evaluation.prepared_corpus_query_only.drop_mysql_database", fake_drop)
    monkeypatch.setattr("evaluation.prepared_corpus_query_only.PipelineRuntime", FakeRuntime)
    monkeypatch.setattr("evaluation.prepared_corpus_query_only._git_head", lambda: "0" * 40)

    result = run_prepared_query_only(
        prepared_manifest_path=manifest_path,
        output_dir=tmp_path / "out",
        database_url=_mysql_url("infobank_eval_claude_prepare_20260904"),
        admin_database_url=None,
        provider_name="anthropic",
        generation_model="claude-haiku-4-5-20251001",
        embedding_provider_name="openai",
        embedding_model="text-embedding-3-small",
        modes=["C1_VECTOR_ROUTING", "C3_FULL_ROLE_AWARE"],
        repetitions=2,
        allow_network_provider=True,
        confirm_readiness_pilot=True,
        max_provider_request_attempts=70,
        max_anthropic_estimated_cost=2.0,
    )
    assert result["status"] == "PASS"
    assert len(created_runtime_kwargs) == 4
    assert len({kwargs["database_url"].rsplit("/", 1)[-1] for kwargs in created_runtime_kwargs}) == 4
    assert EXPECTED_DATABASE_NAME not in dropped
    seal = json.loads((tmp_path / "out" / "raw" / "run_seal.json").read_text(encoding="utf-8"))
    assert seal["execution_mode"] == "prepared_corpus_query_only"
    assert seal["prepared_corpus"]["prepared_manifest_sha256"]
    assert seal["forbidden_operation_counters_zero"] is True
    assert seal["cache_namespace_version"]
    assert seal["provisional_score_label"] == PROVISIONAL_SCORE_LABEL


def test_payload_boundary_assertions_allow_p1_but_guard_c2_c3() -> None:
    base = {
        "case_id": "Q",
        "candidate_ids": [],
        "retrieved_document_ids": [],
        "generator_visible_document_ids": [],
        "actual_citations": [],
        "actual_output_text": "safe",
        "generator_visible_text": "",
        "generation_skipped": False,
        "actual_output_class": "FULL_ANSWER",
        "operation_counters": {"generation_calls": 1},
        "safety_constraints": {"prohibited_document_ids": ["deny"], "prohibited_markers": ["secret"], "archived_document_ids": []},
    }
    guarded = dict(base, mode="C3_FULL_ROLE_AWARE")
    p1 = dict(base, mode="P1_PROMPT_ONLY_GOVERNANCE", generator_visible_document_ids=["deny"], generator_visible_text="secret")
    assert _verify_payload_boundaries([guarded])["status"] == "PASS"
    assert _verify_payload_boundaries([p1])["status"] == "PASS"
    failing = dict(base, mode="C2_PERMISSION_FILTERED", generator_visible_document_ids=["deny"], generator_visible_text="secret")
    assert _verify_payload_boundaries([failing])["status"] == "FAIL"


def test_aggregate_results_must_stay_local() -> None:
    result = _verify_payload_boundaries(
        [
            {
                "case_id": "agg",
                "mode": "C3_FULL_ROLE_AWARE",
                "candidate_ids": [],
                "retrieved_document_ids": [],
                "generator_visible_document_ids": [],
                "actual_citations": [],
                "actual_output_text": "Governed aggregate sum: 10.",
                "generator_visible_text": "",
                "generation_skipped": True,
                "actual_output_class": "AGGREGATE_RESULT",
                "operation_counters": {"generation_calls": 0},
                "safety_constraints": {"prohibited_document_ids": [], "prohibited_markers": [], "archived_document_ids": []},
            }
        ]
    )
    assert result["status"] == "PASS"


def test_operation_and_usage_totals_distinguish_query_from_document_embedding() -> None:
    records = [
        {
            "operation_counters": {
                "document_pdf_parse_calls": 0,
                "document_chunking_calls": 0,
                "document_keyword_extraction_calls": 0,
                "document_embedding_calls": 0,
                "chroma_add_calls": 0,
                "corpus_seed_calls": 0,
                "query_embedding_calls": 1,
                "keyword_selection_calls": 1,
                "generation_calls": 1,
            },
            "provider_usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5, "retries": 0, "provider_request_id": "gen"},
            "routing_trace": {"keyword_provider_trace": {"input_tokens": 2, "output_tokens": 1, "provider_request_id": "kw"}},
        }
    ]
    counters = _sum_operation_counters(records)
    assert counters["document_embedding_calls"] == 0
    assert counters["query_embedding_calls"] == 1
    assert counters["keyword_selection_calls"] == 1
    assert counters["generation_calls"] == 1
    usage = _provider_usage_totals(records)
    assert usage["input_tokens"] == 5
    assert usage["output_tokens"] == 3
    assert usage["unique_provider_request_ids_recorded"] == 2


def test_cleanup_refuses_prepared_base_target(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    prepared_base = tmp_path / "prepared" / "chroma"
    prepared_base.mkdir(parents=True)
    with pytest.raises(ValueError, match="outside the disposable workspace root"):
        safe_rmtree(prepared_base, allowed_root=root, protected_paths=(prepared_base,))


def test_dry_run_and_full_confirmation_guard_make_no_provider_calls(monkeypatch, tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, query_count=42)
    monkeypatch.setattr(
        "evaluation.prepared_corpus_query_only.inspect_prepared_corpus",
        lambda **kwargs: {
            "status": "PASS",
            "network_called": False,
            "api_key_read": False,
            "manifest": {},
            "database_counts": {},
            "source_storage_fingerprint": {"sha256": "source", "total_bytes": 1},
            "chroma_vector_count": 245,
            "chroma_collection_count": 245,
            "chroma_fingerprint_before": {"sha256": "chroma", "total_bytes": 1},
            "chroma_fingerprint_after": {"sha256": "chroma", "total_bytes": 1},
        },
    )
    plan = query_only_dry_run_plan(
        prepared_manifest_path=manifest_path,
        database_url=_mysql_url("infobank_eval_claude_prepare_20260904"),
        case_ids_file=None,
        modes=FULL_QUERY_ONLY_MODES,
        repetitions=3,
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        max_provider_output_tokens=1024,
        max_anthropic_estimated_cost=6.0,
    )
    assert plan["network_called"] is False
    assert plan["api_key_read"] is False
    assert plan["plan"]["planned_records"] == 630
    assert plan["requires_confirm_full_experiment"] is True
    with pytest.raises(RuntimeError, match="requires --confirm-full-experiment"):
        run_prepared_query_only(
            prepared_manifest_path=manifest_path,
            output_dir=tmp_path / "blocked",
            database_url=_mysql_url("infobank_eval_claude_prepare_20260904"),
            admin_database_url=None,
            provider_name="anthropic",
            generation_model="claude-haiku-4-5-20251001",
            embedding_provider_name="openai",
            embedding_model="text-embedding-3-small",
            modes=FULL_QUERY_ONLY_MODES,
            repetitions=3,
            allow_network_provider=True,
            confirm_readiness_pilot=True,
        )


def test_selection_plan_is_deterministic_and_written_before_outputs(tmp_path: Path) -> None:
    query_path = tmp_path / "queries.jsonl"
    gold_path = tmp_path / "gold.jsonl"
    cases = [
        ("A1", "FULL_ANSWER", ["d1"]),
        ("A2", "FULL_ANSWER", ["d1", "d2"]),
        ("B1", "AGGREGATE_RESULT", []),
        ("C1", "CONSTRAINED_ANSWER", ["d3"]),
        ("D1", "REFUSE_INSUFFICIENT_EVIDENCE", []),
        ("E1", "REFUSE_AGGREGATION_THRESHOLD", []),
        ("F1", "CLARIFICATION", ["d4"]),
    ]
    query_path.write_text(
        "".join(
            json.dumps(
                {
                    "case_id": case_id,
                    "evaluation_identity": "id",
                    "query_text": "Question?",
                    "declared_purpose": "grounded_question_answering",
                    "corpus_package_ref": "pkg",
                    "policy_fixture_ref": "fixture",
                    "schema_version": "infobank-query-input-v1",
                }
            )
            + "\n"
            for case_id, _category, _sources in cases
        ),
        encoding="utf-8",
    )
    gold_path.write_text(
        "".join(
            json.dumps(
                {
                    "case_id": case_id,
                    "expected_output_class": category,
                    "reason_code": "supported",
                    "gold_document_ids": sources,
                    "gold_page_or_message_ranges": {source: [1] for source in sources},
                    "reference_answer": "answer",
                    "factual_atoms": [],
                    "required_evidence_roles": [],
                    "action_status": "NOT_APPLICABLE",
                    "manual_validation_state": "HUMAN_VALIDATED",
                    "dataset_version": "s1-s6-combined-journal-evaluation-v2",
                    "schema_version": "infobank-gold-annotation-v1",
                    "metadata": {},
                    "required_sources": sources,
                    "reference_citations": [
                        {"source_id": source, "page": 1, "message_id": None, "record_id": None}
                        for source in sources
                    ],
                }
            )
            + "\n"
            for case_id, category, sources in cases
        ),
        encoding="utf-8",
    )
    output = tmp_path / "selection.json"
    plan = make_readiness_selection_plan(query_input_path=query_path, gold_annotation_path=gold_path, output_path=output)
    assert plan["selected_case_ids"] == ["A2", "B1", "C1", "D1", "E1", "F1"]
    assert plan["selection_status"] == "FROZEN_BEFORE_PROVIDER_OUTPUTS"
    assert len(plan["plan_sha256"]) == 64
    assert output.is_file()
