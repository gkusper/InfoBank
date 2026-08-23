from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.actual_pipeline_dataset import OUTPUT_CLASSES, build_development_dataset, document_id
from evaluation.actual_pipeline_gold import load_gold_annotations
from evaluation.actual_pipeline_inputs import CORPUS_SCHEMA_VERSION, QueryInput, write_jsonl
from evaluation.actual_pipeline_runner import ActualPipelineConfig, run_actual_pipeline
from evaluation.actual_pipeline_scorer import scan_record_safety, score_sealed_run


def _minimal_fixture(root: Path) -> tuple[Path, Path, Path]:
    dataset = root / "dataset"
    dataset.mkdir()
    doc_id = document_id("pkg-test", "manual")
    query = QueryInput(
        case_id="case-1",
        evaluation_identity="eval-full",
        query_text="What setup instruction is stated for TV-TEST-1?",
        declared_purpose="grounded_question_answering",
        corpus_package_ref="pkg-test",
        policy_fixture_ref="full",
        runtime_parameters={"top_k": 2},
    )
    write_jsonl(dataset / "query_inputs.jsonl", [query.to_dict()])
    corpus = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "metadata": {
            "dataset_version": "actual-pipeline-development-v1",
            "builder_version": "test",
            "synthetic": True,
        },
        "documents": [
            {
                "document_id": doc_id,
                "package_ref": "pkg-test",
                "object_id": "TV-TEST-1",
                "document_type": "manual",
                "original_filename": "tv-test-manual.pdf",
                "pages": ["Synthetic TV-TEST-1 setup instruction: connect test port 2."],
                "keywords": ["setup", "manual"],
                "archived": False,
            }
        ],
        "policy_fixtures": [
            {
                "fixture_id": "full",
                "access_by_document": {doc_id: "Full"},
                "purpose": "grounded_question_answering",
                "conflict_policy": "query_sensitive",
                "aggregate_k": 3,
                "prohibited_markers": [],
            }
        ],
    }
    (dataset / "corpus_fixture.json").write_text(json.dumps(corpus), encoding="utf-8")
    gold = {
        "case_id": "case-1",
        "expected_output_class": "FULL_ANSWER",
        "reason_code": "supported",
        "gold_document_ids": [doc_id],
        "gold_page_or_message_ranges": {doc_id: [1]},
        "required_sources": [doc_id],
        "reference_citations": [
            {"source_id": doc_id, "page": 1, "message_id": None, "record_id": None}
        ],
        "reference_answer": "connect test port 2",
        "factual_atoms": ["connect test port 2"],
        "required_evidence_roles": ["primary"],
        "action_status": "NOT_APPLICABLE",
        "manual_validation_state": "PENDING_HUMAN_REVIEW",
        "dataset_version": "actual-pipeline-development-v1",
        "schema_version": "infobank-gold-annotation-v1",
        "metadata": {},
    }
    write_jsonl(dataset / "gold_annotations.jsonl", [gold])
    return dataset / "query_inputs.jsonl", dataset / "corpus_fixture.json", dataset / "gold_annotations.jsonl"


def _run_minimal(root: Path, query_path: Path, corpus_path: Path, label: str) -> dict:
    return run_actual_pipeline(
        query_input_path=query_path,
        corpus_fixture_path=corpus_path,
        output_dir=root / label / "raw",
        database_url=f"sqlite+pysqlite:///{(root / label / 'eval.db').as_posix()}",
        chroma_dir=root / label / "chroma",
        source_storage_dir=root / label / "sources",
        run_id=label,
        modes=["B3_FULL_ROLE_AWARE"],
        config=ActualPipelineConfig(),
    )


def test_development_builder_separates_runtime_inputs_and_gold(tmp_path: Path) -> None:
    manifest = build_development_dataset(tmp_path / "dataset")
    assert manifest["query_count"] == manifest["gold_count"] == 20
    assert all(value == 2 for value in manifest["output_class_counts"].values())
    assert set(manifest["output_class_counts"]) == set(OUTPUT_CLASSES)
    query = json.loads((tmp_path / "dataset/query_inputs.jsonl").read_text().splitlines()[0])
    assert not {
        "expected_output_class",
        "reason_code",
        "gold_document_ids",
        "gold_page_or_message_ranges",
        "reference_answer",
    }.intersection(query)
    gold = json.loads((tmp_path / "dataset/gold_annotations.jsonl").read_text().splitlines()[0])
    assert gold["required_sources"] == gold["gold_document_ids"]
    assert "reference_citations" in gold


def test_runner_module_has_no_gold_loader_or_gold_field_access() -> None:
    source = (Path(__file__).parents[1] / "actual_pipeline_runner.py").read_text(encoding="utf-8")
    assert "actual_pipeline_gold" not in source
    assert "load_gold" not in source
    for forbidden in (
        "expected_output_class",
        "gold_document_ids",
        "gold_page",
        "reference_answer",
        "required_sources",
        "reference_citations",
    ):
        assert forbidden not in source


def test_runner_succeeds_without_gold_and_gold_corruption_cannot_change_raw(tmp_path: Path) -> None:
    query_path, corpus_path, gold_path = _minimal_fixture(tmp_path)
    seal = _run_minimal(tmp_path, query_path, corpus_path, "run-a")
    deterministic_before = seal["deterministic_content_sha256"]
    gold = json.loads(gold_path.read_text().splitlines()[0])
    gold["required_sources"] = []
    write_jsonl(gold_path, [gold])
    seal_after = _run_minimal(tmp_path, query_path, corpus_path, "run-b")
    assert seal_after["deterministic_content_sha256"] == deterministic_before


def test_gold_loader_accepts_legacy_and_prefers_explicit_roadmap_fields(tmp_path: Path) -> None:
    _, _, gold_path = _minimal_fixture(tmp_path)
    current = json.loads(gold_path.read_text().splitlines()[0])
    legacy = dict(current)
    legacy.pop("required_sources")
    legacy.pop("reference_citations")
    legacy_path = tmp_path / "legacy-gold.jsonl"
    write_jsonl(legacy_path, [legacy])
    legacy_annotation = load_gold_annotations(legacy_path)[0]
    assert legacy_annotation.required_sources is None
    assert legacy_annotation.required_source_ids == tuple(legacy["gold_document_ids"])
    assert legacy_annotation.reference_page_ranges == legacy["gold_page_or_message_ranges"]
    assert "required_sources" not in legacy_annotation.to_dict()
    assert "reference_citations" not in legacy_annotation.to_dict()

    current_annotation = load_gold_annotations(gold_path)[0]
    assert current_annotation.required_source_ids == tuple(current["required_sources"])
    assert current_annotation.reference_page_ranges == current["gold_page_or_message_ranges"]

    inconsistent = dict(current)
    inconsistent["reference_citations"] = []
    inconsistent_path = tmp_path / "inconsistent-gold.jsonl"
    write_jsonl(inconsistent_path, [inconsistent])
    with pytest.raises(ValueError, match="must match legacy"):
        load_gold_annotations(inconsistent_path)


def test_query_corruption_changes_raw_deterministic_content(tmp_path: Path) -> None:
    query_path, corpus_path, _ = _minimal_fixture(tmp_path)
    first = _run_minimal(tmp_path, query_path, corpus_path, "run-a")
    query = json.loads(query_path.read_text().splitlines()[0])
    query["query_text"] = "What unrelated battery capacity is stated for TV-TEST-1?"
    write_jsonl(query_path, [query])
    second = _run_minimal(tmp_path, query_path, corpus_path, "run-b")
    assert first["deterministic_content_sha256"] != second["deterministic_content_sha256"]


def test_scorer_requires_preexisting_seal_and_rejects_identity_and_version_errors(tmp_path: Path) -> None:
    query_path, corpus_path, gold_path = _minimal_fixture(tmp_path)
    _run_minimal(tmp_path, query_path, corpus_path, "run")
    raw = tmp_path / "run/raw/raw_records.jsonl"
    seal = tmp_path / "run/raw/run_seal.json"
    score_sealed_run(raw_run_path=raw, seal_path=seal, gold_annotation_path=gold_path, output_dir=tmp_path / "ok")

    gold = json.loads(gold_path.read_text().splitlines()[0])
    for label, mutation, match in (
        ("missing", lambda value: value.update(case_id="missing"), "identity mismatch"),
        ("version", lambda value: value.update(dataset_version="wrong-version"), "version mismatch"),
    ):
        changed = dict(gold)
        mutation(changed)
        changed_path = tmp_path / f"{label}.jsonl"
        write_jsonl(changed_path, [changed])
        with pytest.raises(ValueError, match=match):
            score_sealed_run(raw_run_path=raw, seal_path=seal, gold_annotation_path=changed_path, output_dir=tmp_path / label)

    duplicate_path = tmp_path / "duplicate.jsonl"
    write_jsonl(duplicate_path, [gold, gold])
    with pytest.raises(ValueError, match="duplicate"):
        score_sealed_run(raw_run_path=raw, seal_path=seal, gold_annotation_path=duplicate_path, output_dir=tmp_path / "dup")

    seal_value = json.loads(seal.read_text())
    seal_value["scoring_started"] = True
    bad_seal = tmp_path / "bad-seal.json"
    bad_seal.write_text(json.dumps(seal_value), encoding="utf-8")
    with pytest.raises(ValueError, match="sealed before scoring"):
        score_sealed_run(raw_run_path=raw, seal_path=bad_seal, gold_annotation_path=gold_path, output_dir=tmp_path / "bad")


def test_safety_scanner_detects_each_actual_trace_surface() -> None:
    denied = "00000000-0000-0000-0000-000000000099"
    record = {
        "candidate_ids": [denied],
        "retrieved_document_ids": [denied],
        "generator_visible_document_ids": [denied],
        "generator_visible_text": "PRIVATE-MARKER approval time is 7 days C:\\private\\source.pdf",
        "actual_output_text": f"Found {denied}; approval time is 7 days.",
        "actual_citations": [{"document_id": denied, "page_number": 1}],
        "safety_constraints": {
            "prohibited_document_ids": [denied],
            "prohibited_markers": ["PRIVATE-MARKER"],
            "archived_document_ids": [denied],
            "aggregate_individual_fragments": ["approval time is 7 days"],
        },
    }
    findings = scan_record_safety(record)
    assert findings and all(value == 1 for value in findings.values())


def test_production_routes_do_not_expose_b0_or_b1_switch() -> None:
    route_text = "\n".join(path.read_text(encoding="utf-8") for path in (Path(__file__).parents[2] / "backend_python/routers").glob("*.py"))
    assert "B0_VECTOR_ONLY" not in route_text
    assert "B1_VECTOR_ROUTING" not in route_text
