from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import inspect
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

from .backend import BACKEND_DIR, REPO_ROOT, ensure_backend_path
from .clean_state import check_clean_state
from .fixture_schema import EvaluationFixture, FixtureCase, load_fixture
from .generate_fixture_documents import generate_documents
from .large_scale_analysis import (
    document_case_aggregates,
    document_scenario_metrics,
    document_statistical_tests,
    evidence_case_aggregates,
    evidence_determinism,
    failure_rows,
    latency_summary,
    metric,
    read_json,
    read_jsonl,
    retry_summary,
    summarize_api_usage as summarize_large_api_usage,
    triplet_results,
    write_json,
    write_jsonl,
    write_latex_tables,
)
from .load_evidence_fixtures import cleanup_case, configure_database_from_env_file, load_benchmark, load_case, parse_timestamp
from .load_fixtures import build_id_mappings, load_fixture_data, policy_context_for_case, selected_document_aliases
from .manifest import git_info, package_versions
from .modes import run_governance_only_rag, run_role_aware_rag, run_standard_rag
from .run_document_rag_pilot import (
    EMBEDDING_MODEL,
    GENERATOR_MODEL,
    PILOT_MODES,
    TEMPERATURE,
    CountingCollection,
    PilotConfig as DocumentPilotConfig,
    PilotError,
    append_jsonl,
    artifact_hashes,
    build_fixture_subset_manifest,
    build_retrieval_record,
    configure_real_environment,
    expected_result_count,
    open_mock_runtime,
    open_real_runtime,
    read_runtime_counts,
    run_case_retrieval,
    run_preflight as run_document_preflight,
    select_cases,
    summarize_api_usage,
    tracked_status,
)
from .run_suite import mock_role_aware_services
from .schemas import GenerationConfig, MODE_GOVERNANCE, MODE_ROLE_AWARE, MODE_STANDARD, RetrievedCandidate, SharedRetrievalResult
from .score_document_results import score_results as score_document_results
from .score_evidence_unit_results import score_results as score_evidence_results
from .validate_fixtures import validate_fixture


DEFAULT_DOCUMENT_FIXTURE = REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v3.yaml"
DEFAULT_EVIDENCE_BENCHMARK = REPO_ROOT / "data" / "benchmarks" / "evidence_unit_v2_holdout"
DEFAULT_RESULTS_BASE = REPO_ROOT / "evaluation" / "results"
DEFAULT_ENV_FILE = BACKEND_DIR / ".env.eval"
DEFAULT_PUBLICATION_DIR = REPO_ROOT / "evaluation" / "publication_results" / "d1_d8_large_scale_v1"
PREREGISTRATION = REPO_ROOT / "evaluation" / "preregistration" / "d1_d8_large_scale_v1.md"
FINAL_REPORT = REPO_ROOT / "docs" / "d1_d8_large_scale_final_evaluation_report.md"
PAPER_UPDATE_PACKAGE = REPO_ROOT / "docs" / "d1_d8_v2_7_paper_update_package.md"
EVIDENCE_MODE = "role_aware_action_reconstruction"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        hashes[path.relative_to(root).as_posix()] = sha256_file(path)
    return hashes


def sanitize(value: Any) -> Any:
    secrets = [os.environ.get("OPENAI_API_KEY"), os.environ.get("DATABASE_URL")]
    secret_key_parts = ("password", "secret", "api_key", "apikey", "access_token", "refresh_token", "authorization")
    if isinstance(value, str):
        clean = value
        for secret in [item for item in secrets if item]:
            clean = clean.replace(secret, "<redacted>")
        return clean
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in secret_key_parts):
                output[key_text] = "<redacted>"
            else:
                output[key_text] = sanitize(item)
        return output
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return value


def write_sanitized_json(path: Path, payload: Any) -> None:
    write_json(path, sanitize(payload))


def unique_run_dir(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    prefix = "d1_d8_large_scale_" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate = base / prefix
    suffix = 1
    while candidate.exists():
        candidate = base / f"{prefix}_{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def latest_large_scale_dir(base: Path) -> Path:
    if base.exists() and base.is_dir() and (base / "run_manifest.json").exists():
        return base
    candidates = sorted([path for path in base.glob("d1_d8_large_scale_*") if path.is_dir()])
    if not candidates:
        raise RuntimeError(f"No large-scale result directory found under {base}.")
    return candidates[-1]


def resolve_results_dir(value: str, *, create_new: bool, resume: bool) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    if create_new:
        return latest_large_scale_dir(path) if resume else unique_run_dir(path)
    return latest_large_scale_dir(path)


def tcp_reachable(host: str, port: int) -> bool:
    with socket.create_connection((host, port), timeout=2.0):
        return True


def run_subprocess(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    return {"args": args, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def validate_evidence_benchmark(root: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "mailex"))
    from validate_evidence_benchmark import validate

    errors = validate(root)
    if errors:
        raise RuntimeError("EvidenceUnit v2 validation failed: " + "; ".join(errors))


def build_benchmarks() -> dict[str, Any]:
    document = run_subprocess([sys.executable, "-m", "evaluation.build_document_rag_v3"])
    if document["returncode"] != 0:
        raise RuntimeError(f"document_rag_v3 builder failed: {document['stderr'] or document['stdout']}")
    evidence = run_subprocess([sys.executable, str(REPO_ROOT / "scripts" / "mailex" / "build_evidence_holdout_v2.py")])
    if evidence["returncode"] != 0:
        raise RuntimeError(f"EvidenceUnit v2 builder failed: {evidence['stderr'] or evidence['stdout']}")
    return {"document": document, "evidence": evidence}


def validate_benchmarks(document_fixture: Path, evidence_benchmark: Path) -> dict[str, Any]:
    fixture = load_fixture(document_fixture)
    validate_fixture(fixture)
    if fixture.fixture_id != "document_rag_v3" or len(fixture.cases) != 400:
        raise RuntimeError(f"Expected document_rag_v3 with 400 cases, found {fixture.fixture_id} / {len(fixture.cases)}.")
    validate_evidence_benchmark(evidence_benchmark)
    benchmark = load_benchmark(evidence_benchmark)
    if len(benchmark.cases) != 340:
        raise RuntimeError(f"Expected 340 EvidenceUnit v2 cases, found {len(benchmark.cases)}.")
    return {
        "document_fixture_id": fixture.fixture_id,
        "document_case_count": len(fixture.cases),
        "evidence_case_count": len(benchmark.cases),
        "document_case_counts": scenario_counts(fixture),
        "evidence_case_counts": dict(sorted({scenario: sum(1 for row in benchmark.cases if row["scenario"] == scenario) for scenario in {row["scenario"] for row in benchmark.cases}}.items())),
    }


def scenario_counts(fixture: EvaluationFixture) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in fixture.cases:
        scenario = str((case.metadata or {}).get("scenario") or case.scenario_family)
        counts[scenario] = counts.get(scenario, 0) + 1
    return dict(sorted(counts.items()))


def run_preflight(*, env_file: Path, document_fixture: Path, evidence_benchmark: Path, require_openai_key: bool, require_clean_state: bool) -> dict[str, Any]:
    config = DocumentPilotConfig(
        real_api=True,
        mock_generation=False,
        check_only=True,
        results_dir=DEFAULT_RESULTS_BASE,
        fixture_path=document_fixture,
        env_file=env_file,
        top_k=4,
        repetitions=5,
        case_ids=[],
    )
    runtime = configure_real_environment(env_file)
    if require_openai_key and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("LARGE-SCALE BLOCKED: OPENAI_API_KEY is not visible in the process environment.")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(f"Python 3.12 is required, found {platform.python_version()}.")
    pip_check = run_subprocess([sys.executable, "-m", "pip", "check"])
    if pip_check["returncode"] != 0:
        raise RuntimeError(f"pip check failed: {pip_check['stdout']}{pip_check['stderr']}")
    if not tcp_reachable("127.0.0.1", 3307):
        raise RuntimeError("MariaDB is not reachable at 127.0.0.1:3307.")
    clean_state = None
    if require_clean_state:
        clean_state = check_clean_state().to_dict()
    validation = validate_benchmarks(document_fixture, evidence_benchmark)
    _, SessionLocal, database_info = configure_database_from_env_file(env_file)
    with SessionLocal() as db:
        mariadb_version = db.execute(text("SELECT VERSION()")).scalar()
    return {
        "status": "PASS",
        "runtime": runtime,
        "database": database_info,
        "mariadb_server_version": mariadb_version,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pip_check": "No broken requirements found.",
        "clean_state": clean_state,
        "validation": validation,
        "openai_key_visible": bool(os.environ.get("OPENAI_API_KEY")),
        "document_preflight_function": run_document_preflight.__name__,
        "credentials_serialized": False,
        "document_config": config.__dict__,
    }


def retrieval_from_record(record: dict[str, Any]) -> SharedRetrievalResult:
    return SharedRetrievalResult(
        question=record["question"],
        query_profile=record.get("query_profile") or {},
        query_embedding_identifier=record.get("query_embedding_identifier"),
        retrieved_candidates=[RetrievedCandidate(**candidate) for candidate in record.get("retrieved_candidates") or []],
        retrieval_top_k=int(record.get("retrieval_top_k") or 4),
        embedding_model=record.get("embedding_model") or EMBEDDING_MODEL,
        api_usage=record.get("api_usage") or {},
    )


def run_one_document_mode(
    *,
    mode: str,
    run_id: str,
    case_id: str,
    repetition: int,
    git_commit: str | None,
    user_id: str,
    retrieval: SharedRetrievalResult,
    generation_config: GenerationConfig,
    generator: Any,
    db: Any,
    policy_context: dict[str, Any],
    services: Any,
) -> dict[str, Any]:
    if mode == MODE_STANDARD:
        result = run_standard_rag(
            run_id=run_id,
            case_id=case_id,
            repetition=repetition,
            git_commit=git_commit,
            retrieval=retrieval,
            generation_config=generation_config,
            generator=generator,
        )
    elif mode == MODE_GOVERNANCE:
        result = run_governance_only_rag(
            run_id=run_id,
            case_id=case_id,
            repetition=repetition,
            git_commit=git_commit,
            retrieval=retrieval,
            generation_config=generation_config,
            generator=generator,
            user_id=user_id,
            db=db,
            policy_context=policy_context,
            services=services,
        )
    elif mode == MODE_ROLE_AWARE:
        result = run_role_aware_rag(
            run_id=run_id,
            case_id=case_id,
            repetition=repetition,
            git_commit=git_commit,
            retrieval=retrieval,
            generation_config=generation_config,
            generator=generator,
            user_id=user_id,
            db=db,
            policy_context=policy_context,
            services=services,
        )
    else:
        raise ValueError(f"Unknown document mode: {mode}")
    return result.to_dict()


def run_document_phase(
    *,
    run_dir: Path,
    document_fixture: Path,
    env_file: Path,
    real_api: bool,
    top_k: int,
    repetitions: int,
    resume: bool,
) -> dict[str, Any]:
    fixture = load_fixture(document_fixture)
    validate_fixture(fixture)
    case_ids = [case.case_id for case in fixture.cases]
    run_id = run_dir.name
    phase_dir = run_dir / "document_phase"
    phase_dir.mkdir(parents=True, exist_ok=True)
    raw_results_path = run_dir / "document_raw_results.jsonl"
    retrieval_path = run_dir / "document_shared_retrieval.jsonl"
    completed_records = read_jsonl(raw_results_path) if resume else []
    successful_keys = {
        (record["case_id"], record["mode"], int(record["repetition"]))
        for record in completed_records
        if not record.get("error")
    }
    retrieval_records = read_jsonl(retrieval_path) if resume else []
    retrieval_by_case = {record["case_id"]: record for record in retrieval_records}
    expected = expected_result_count(case_ids, repetitions)
    if len(successful_keys) == expected:
        return {"status": "SKIPPED_COMPLETE", "record_count": len(completed_records), "expected_record_count": expected}

    config = DocumentPilotConfig(
        real_api=real_api,
        mock_generation=not real_api,
        check_only=False,
        results_dir=run_dir,
        fixture_path=document_fixture,
        env_file=env_file,
        top_k=top_k,
        repetitions=repetitions,
        case_ids=case_ids,
    )
    if real_api:
        configure_real_environment(env_file)
        collection, db_session, cleanup, fixture_embedding_provider, query_embedding_client, generator, real_services = open_real_runtime(config)
    else:
        collection, db_session, cleanup, fixture_embedding_provider, query_embedding_client, generator, real_services = open_mock_runtime(config)

    try:
        selected_cases = select_cases(fixture, case_ids)
        selected_aliases = sorted(selected_document_aliases(fixture, case_ids))
        fixture_subset_path = run_dir / "fixture_subset_manifest.json"
        needs_load = not (resume and fixture_subset_path.exists() and retrieval_by_case)
        if needs_load:
            subset_fixture = fixture.copy(
                deep=True,
                update={
                    "documents": [document for document in fixture.documents if document.alias in selected_aliases],
                    "cases": selected_cases,
                    "case_count": len(selected_cases),
                },
            )
            pdf_manifest = generate_documents(subset_fixture, phase_dir / "generated_pdfs")
            load_manifest = load_fixture_data(
                fixture=fixture,
                db=db_session,
                collection=collection,
                embedding_provider=fixture_embedding_provider,
                clean_checker=check_clean_state if real_api else None,
                case_ids=case_ids,
            )
            db_counts = read_runtime_counts(db_session)
            fixture_subset_manifest = build_fixture_subset_manifest(
                fixture=fixture,
                selected_cases=selected_cases,
                selected_aliases=selected_aliases,
                pdf_manifest=pdf_manifest,
                load_manifest=load_manifest.to_dict(),
                db_counts=db_counts,
                vector_count=collection.count(),
                fixture_index_embedding_calls=fixture_embedding_provider.calls,
                fixture_index_embedding_usage=fixture_embedding_provider.usage,
            )
            write_sanitized_json(fixture_subset_path, fixture_subset_manifest)

        id_mappings = build_id_mappings(fixture)
        counting_collection = CountingCollection(collection)
        generation_config = GenerationConfig(
            generator_model=GENERATOR_MODEL,
            embedding_model=EMBEDDING_MODEL,
            temperature=TEMPERATURE,
            max_tokens=160,
        )
        git = git_info()
        current_case = None
        current_mode = None
        for case in selected_cases:
            current_case = case.case_id
            remaining = [
                (mode, repetition)
                for repetition in range(1, repetitions + 1)
                for mode in PILOT_MODES
                if (case.case_id, mode, repetition) not in successful_keys
            ]
            if not remaining:
                continue
            if case.case_id in retrieval_by_case:
                retrieval = retrieval_from_record(retrieval_by_case[case.case_id])
            else:
                retrieval = run_case_retrieval(
                    fixture=fixture,
                    case=case,
                    id_mappings=id_mappings,
                    collection=counting_collection,
                    embedding_client=query_embedding_client,
                    top_k=top_k,
                )
                retrieval_record = build_retrieval_record(run_id, case, retrieval, counting_collection.query_calls)
                append_jsonl(retrieval_path, retrieval_record)
                retrieval_by_case[case.case_id] = retrieval_record
            policy_context = policy_context_for_case(fixture, case)
            services = None if real_services else mock_role_aware_services(policy_context)
            for mode, repetition in remaining:
                current_mode = mode
                record = run_one_document_mode(
                    mode=mode,
                    run_id=run_id,
                    case_id=case.case_id,
                    repetition=repetition,
                    git_commit=git.get("git_commit"),
                    user_id=id_mappings["users"][case.user_alias],
                    retrieval=retrieval,
                    generation_config=generation_config,
                    generator=generator,
                    db=db_session if real_api else None,
                    policy_context=policy_context,
                    services=services,
                )
                append_jsonl(raw_results_path, record)
                successful_keys.add((case.case_id, mode, repetition))
                if record.get("error"):
                    raise PilotError(
                        str(record["error"]),
                        stage="generation",
                        classification="generation",
                        current_case=current_case,
                        current_mode=current_mode,
                    )
        records = read_jsonl(raw_results_path)
        scores, metrics_payload = score_document_results(records, fixture)
        write_jsonl(run_dir / "document_scored_results.jsonl", scores)
        write_sanitized_json(run_dir / "document_metrics.json", metrics_payload)
        inspection = {
            "result_record_count": len(records),
            "retrieval_record_count": len(read_jsonl(retrieval_path)),
            "retrieval_identity": document_retrieval_identity(records),
        }
        write_sanitized_json(run_dir / "document_pilot_inspection.json", inspection)
        api_usage = summarize_api_usage(
            records,
            fixture_embedding_provider=fixture_embedding_provider,
            query_embedding_client=query_embedding_client,
        )
        write_sanitized_json(phase_dir / "run_manifest.json", {
            "run_id": run_id,
            "mode": "real-api" if real_api else "mocked-test",
            "result_record_count": len(records),
            "expected_result_count": expected,
            "retrieval_record_count": len(read_jsonl(retrieval_path)),
            "api_usage": api_usage,
            "artifact_hashes": artifact_hashes(phase_dir),
        })
        if len(records) != expected:
            raise PilotError(
                f"Expected {expected} document records, found {len(records)}.",
                stage="artifact persistence",
                classification="artifact persistence",
                current_case=current_case,
                current_mode=current_mode,
            )
        return {"status": "PASS", "record_count": len(records), "expected_record_count": expected, "api_usage": api_usage}
    except PilotError:
        raise
    except Exception as exc:
        raise PilotError(str(exc), stage="document large-scale", classification="unexpected", original_error=exc) from exc
    finally:
        cleanup()


def document_retrieval_identity(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["case_id"], []).append(record)
    failures = []
    for case_id, group in grouped.items():
        baseline = [
            group[0].get("query_embedding_identifier"),
            group[0].get("retrieved_chunk_ids"),
            group[0].get("document_ids"),
            group[0].get("retrieval_rank"),
            group[0].get("retrieval_distances"),
        ]
        for record in group[1:]:
            value = [
                record.get("query_embedding_identifier"),
                record.get("retrieved_chunk_ids"),
                record.get("document_ids"),
                record.get("retrieval_rank"),
                record.get("retrieval_distances"),
            ]
            if value != baseline:
                failures.append(case_id)
                break
    return {"pass": not failures, "checked_cases": len(grouped), "failed_case_ids": sorted(failures)}


def production_reconstruct(db: Any, user_id: str, query_time: str | None) -> dict[str, Any]:
    ensure_backend_path()
    import evidence_service

    as_of = parse_timestamp(query_time)
    signature = inspect.signature(evidence_service.reconstruct_action_list)
    if "as_of" in signature.parameters:
        return evidence_service.reconstruct_action_list(db, user_id, as_of=as_of)
    return evidence_service.reconstruct_action_list(db, user_id)


def run_evidence_phase(
    *,
    run_dir: Path,
    evidence_benchmark: Path,
    env_file: Path,
    repetitions: int,
    resume: bool,
) -> dict[str, Any]:
    benchmark = load_benchmark(evidence_benchmark)
    _, SessionLocal, database_info = configure_database_from_env_file(env_file)
    expected_per_rep = len(benchmark.cases)
    combined: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        rep_dir = run_dir / f"evidence_clean_run_{repetition}"
        rep_dir.mkdir(parents=True, exist_ok=True)
        rep_results_path = rep_dir / "evidence_results.jsonl"
        existing = read_jsonl(rep_results_path) if resume else []
        completed_case_ids = {row["case_id"] for row in existing if not row.get("error")}
        if len(completed_case_ids) < expected_per_rep:
            with SessionLocal() as db:
                for case in benchmark.cases:
                    if case["case_id"] in completed_case_ids:
                        continue
                    loaded = load_case(db, case, cleanup_first=True)
                    try:
                        reconstruction = production_reconstruct(db, loaded.user_id, case.get("query_time"))
                        record = {
                            "run_id": run_dir.name,
                            "clean_repetition": repetition,
                            "case_id": case["case_id"],
                            "scenario": case["scenario"],
                            "seed_id": case.get("seed_id"),
                            "mode": EVIDENCE_MODE,
                            "query": case.get("query"),
                            "query_time": case.get("query_time"),
                            "database_user_id": loaded.user_id,
                            "loaded_case": loaded.to_dict(),
                            "status": reconstruction.get("status"),
                            "policy": reconstruction.get("policy"),
                            "open_items": reconstruction.get("open_items") or [],
                            "closed_items": reconstruction.get("closed_items") or [],
                            "contextual_only": reconstruction.get("contextual_only") or [],
                            "metadata_only": reconstruction.get("metadata_only") or [],
                            "excluded_only": reconstruction.get("excluded_only") or [],
                            "counts": reconstruction.get("counts") or {},
                            "classified_units": reconstruction.get("classified_units") or [],
                            "external_llm_calls": 0,
                        }
                        append_jsonl(rep_results_path, sanitize(record))
                        completed_case_ids.add(case["case_id"])
                    except Exception as exc:
                        append_jsonl(rep_results_path, sanitize({"run_id": run_dir.name, "clean_repetition": repetition, "case_id": case["case_id"], "scenario": case["scenario"], "seed_id": case.get("seed_id"), "mode": EVIDENCE_MODE, "error": {"type": exc.__class__.__name__, "message": str(exc)}}))
                        raise
                    finally:
                        cleanup_case(db, loaded.user_id)
        rep_records = read_jsonl(rep_results_path)
        if len(rep_records) != expected_per_rep:
            raise RuntimeError(f"Evidence repetition {repetition} expected {expected_per_rep} records, found {len(rep_records)}.")
        scores, metrics_payload = score_evidence_results(rep_records, benchmark.gold)
        for score, record in zip(scores, rep_records):
            score["clean_repetition"] = record.get("clean_repetition")
        write_jsonl(rep_dir / "evidence_scores.jsonl", scores)
        write_sanitized_json(rep_dir / "evidence_metrics.json", metrics_payload)
        combined.extend(rep_records)

    write_jsonl(run_dir / "evidence_raw_results.jsonl", combined)
    scores, metrics_payload = score_evidence_results(combined, benchmark.gold)
    for score, record in zip(scores, combined):
        score["clean_repetition"] = record.get("clean_repetition")
    write_jsonl(run_dir / "evidence_scored_results.jsonl", scores)
    write_sanitized_json(run_dir / "evidence_metrics.json", metrics_payload)
    write_sanitized_json(run_dir / "evidence_phase_manifest.json", {
        "database": database_info,
        "benchmark": str(evidence_benchmark),
        "repetitions": repetitions,
        "record_count": len(combined),
        "expected_record_count": expected_per_rep * repetitions,
        "external_llm_calls": 0,
    })
    return {"status": "PASS", "record_count": len(combined), "expected_record_count": expected_per_rep * repetitions, "external_llm_calls": 0}


def benchmark_checksums(document_fixture: Path, evidence_benchmark: Path) -> dict[str, Any]:
    payload = {
        "document_fixture": {"path": str(document_fixture), "sha256": sha256_file(document_fixture)},
        "document_statistics": {
            "path": str(REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v3_statistics.json"),
            "sha256": sha256_file(REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v3_statistics.json"),
        },
        "evidence_benchmark": {"path": str(evidence_benchmark), "files": sha256_tree(evidence_benchmark)},
    }
    return payload


def environment_manifest(env_file: Path, preflight: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "operating_system": platform.platform(),
        "python_version": sys.version,
        "package_versions": package_versions(),
        "git": git_info(),
        "env_file": str(env_file),
        "openai_key_visible": bool(os.environ.get("OPENAI_API_KEY")),
        "credentials_serialized": False,
    }
    if preflight:
        payload.update({"database": preflight.get("database"), "mariadb_server_version": preflight.get("mariadb_server_version"), "chroma_persist_dir": (preflight.get("runtime") or {}).get("chroma_persist_dir")})
    return sanitize(payload)


def build_benchmark_composition(document_fixture: Path, evidence_benchmark: Path) -> dict[str, Any]:
    fixture = load_fixture(document_fixture)
    benchmark = load_benchmark(evidence_benchmark)
    gold = benchmark.gold
    closure_counts: dict[str, int] = {}
    natural_synthetic: dict[str, int] = {}
    for row in gold:
        if row.get("scenario") == "D8":
            closure = str(row.get("closure_type") or "unknown")
            closure_counts[closure] = closure_counts.get(closure, 0) + 1
        stratum = "synthetic" if row.get("synthetic") else "natural"
        natural_synthetic[stratum] = natural_synthetic.get(stratum, 0) + 1
    return {
        "document_case_count": len(fixture.cases),
        "document_scenario_counts": scenario_counts(fixture),
        "document_count": len(fixture.documents),
        "evidence_case_count": len(benchmark.cases),
        "evidence_scenario_counts": dict(sorted({scenario: sum(1 for row in benchmark.cases if row["scenario"] == scenario) for scenario in {row["scenario"] for row in benchmark.cases}}.items())),
        "d8_closure_distribution": dict(sorted(closure_counts.items())),
        "natural_synthetic_gold_counts": dict(sorted(natural_synthetic.items())),
    }


def score_and_report(
    *,
    run_dir: Path,
    document_fixture: Path,
    evidence_benchmark: Path,
    publication_dir: Path,
    execution_mode: str,
    bootstrap_samples: int,
) -> dict[str, Any]:
    fixture = load_fixture(document_fixture)
    benchmark = load_benchmark(evidence_benchmark)
    document_records = read_jsonl(run_dir / "document_raw_results.jsonl")
    evidence_records = read_jsonl(run_dir / "evidence_raw_results.jsonl")
    document_scores, document_metrics = score_document_results(document_records, fixture) if document_records else ([], {})
    evidence_scores, evidence_metrics = score_evidence_results(evidence_records, benchmark.gold) if evidence_records else ([], {})
    for score, record in zip(evidence_scores, evidence_records):
        score["clean_repetition"] = record.get("clean_repetition")
    write_jsonl(run_dir / "document_scored_results.jsonl", document_scores)
    write_sanitized_json(run_dir / "document_metrics.json", document_metrics)
    write_jsonl(run_dir / "evidence_scored_results.jsonl", evidence_scores)
    write_sanitized_json(run_dir / "evidence_metrics.json", evidence_metrics)

    document_aggregates = document_case_aggregates(document_scores)
    evidence_aggregates = evidence_case_aggregates(evidence_scores)
    scenario_metrics = document_scenario_metrics(document_aggregates)
    stats = document_statistical_tests(document_scores, bootstrap_samples) if document_scores else {"case_level_mcnemar_holm": [], "clustered_bootstrap": []}
    triplets = triplet_results(evidence_aggregates)
    determinism = evidence_determinism(evidence_aggregates)
    api_usage = summarize_large_api_usage(document_records, evidence_records)
    failures = failure_rows(document_scores, evidence_scores)
    composition = build_benchmark_composition(document_fixture, evidence_benchmark)

    write_jsonl(run_dir / "document_case_aggregates.jsonl", document_aggregates)
    write_jsonl(run_dir / "evidence_case_aggregates.jsonl", evidence_aggregates)
    write_jsonl(run_dir / "triplet_results.jsonl", triplets)
    write_sanitized_json(run_dir / "document_statistical_tests.json", stats)
    write_sanitized_json(run_dir / "evidence_determinism.json", determinism)
    write_sanitized_json(run_dir / "api_usage.json", api_usage)
    write_sanitized_json(run_dir / "latency_summary.json", latency_summary(document_records, evidence_records))
    write_sanitized_json(run_dir / "retry_summary.json", retry_summary(api_usage))
    write_jsonl(run_dir / "failure_cases.jsonl", failures)
    combined_metrics = {
        "execution_mode": execution_mode,
        "document_unique_case_count": len({row["case_id"] for row in document_records}),
        "document_record_count": len(document_records),
        "evidence_unique_case_count": len({row["case_id"] for row in evidence_records}),
        "evidence_record_count": len(evidence_records),
        "total_measured_record_count": len(document_records) + len(evidence_records),
        "document_metrics": document_metrics,
        "evidence_metrics": evidence_metrics,
        "evidence_determinism": determinism,
        "triplet_consistency": metric(sum(1 for row in triplets if row.get("triplet_pass")), len(triplets)),
        "api_usage": api_usage,
        "benchmark_composition": composition,
        "finalization_decision": finalization_decision(len(document_records), len(evidence_records), execution_mode),
    }
    write_sanitized_json(run_dir / "combined_metrics.json", combined_metrics)
    write_final_report(run_dir, combined_metrics, stats, failures, composition)
    write_publication_package(publication_dir, run_dir, combined_metrics, document_aggregates, evidence_aggregates, stats, determinism, triplets, api_usage, failures, composition, document_metrics, scenario_metrics, evidence_metrics)
    write_paper_update_package(publication_dir, combined_metrics)
    return combined_metrics


def finalization_decision(document_records: int, evidence_records: int, execution_mode: str) -> str:
    if execution_mode != "real-api":
        return "NOT READY - MOCK OR PARTIAL EXECUTION"
    if document_records != 6000 or evidence_records != 1020:
        return "NOT READY - BLOCKING RECORD COUNT GAP"
    return "READY WITH LISTED EDITORIAL LIMITATIONS"


def write_publication_package(
    publication_dir: Path,
    run_dir: Path,
    combined_metrics: dict[str, Any],
    document_aggregates: list[dict[str, Any]],
    evidence_aggregates: list[dict[str, Any]],
    stats: dict[str, Any],
    determinism: dict[str, Any],
    triplets: list[dict[str, Any]],
    api_usage: dict[str, Any],
    failures: list[dict[str, Any]],
    composition: dict[str, Any],
    document_metrics: dict[str, Any],
    scenario_metrics: list[dict[str, Any]],
    evidence_metrics: dict[str, Any],
) -> None:
    publication_dir.mkdir(parents=True, exist_ok=True)
    manifest = read_json(run_dir / "run_manifest.json") if (run_dir / "run_manifest.json").exists() else {}
    write_sanitized_json(publication_dir / "run_manifest_sanitized.json", manifest)
    shutil.copyfile(run_dir / "benchmark_checksums.json", publication_dir / "benchmark_checksums.json")
    write_jsonl(publication_dir / "document_case_aggregates.jsonl", document_aggregates)
    write_sanitized_json(publication_dir / "document_metrics.json", document_metrics)
    write_sanitized_json(publication_dir / "document_statistical_tests.json", stats)
    write_jsonl(publication_dir / "evidence_case_aggregates.jsonl", evidence_aggregates)
    write_sanitized_json(publication_dir / "evidence_metrics.json", evidence_metrics)
    write_sanitized_json(publication_dir / "evidence_determinism.json", determinism)
    write_jsonl(publication_dir / "triplet_results.jsonl", triplets)
    write_sanitized_json(publication_dir / "api_usage.json", api_usage)
    write_sanitized_json(publication_dir / "failure_summary.json", {"failure_count": len(failures), "failures": failures[:200]})
    write_sanitized_json(publication_dir / "paper_numbers.json", paper_numbers(combined_metrics))
    write_latex_tables(publication_dir, document_metrics, scenario_metrics, evidence_metrics, triplets, api_usage, composition, stats)
    (publication_dir / "README.md").write_text(
        "# InfoBank D1-D8 Large-Scale Publication Results\n\n"
        "This directory contains sanitized aggregate artifacts for the frozen D1-D8 evaluation. "
        "Raw OpenAI prompts, raw MailEx downloads, local databases, Chroma stores, and credentials are not included.\n",
        encoding="utf-8",
    )


def paper_numbers(metrics_payload: dict[str, Any]) -> dict[str, Any]:
    document = metrics_payload.get("document_metrics") or {}
    evidence = metrics_payload.get("evidence_metrics") or {}
    return {
        "record_counts": {
            "document_records": metrics_payload.get("document_record_count"),
            "evidence_records": metrics_payload.get("evidence_record_count"),
            "total_records": metrics_payload.get("total_measured_record_count"),
        },
        "document_by_mode": document.get("by_mode"),
        "evidence_primary": {
            "D6_open_action_accuracy": evidence.get("D6_open_action_accuracy"),
            "D7_browser_only_false_action_rate": evidence.get("D7_browser_only_false_action_rate"),
            "D8_closure_status_accuracy": evidence.get("D8_closure_status_accuracy"),
            "D8_NONCLOSING_open_status_accuracy": evidence.get("D8_NONCLOSING_open_status_accuracy"),
            "EvidenceUnit_role_accuracy": evidence.get("EvidenceUnit_role_accuracy"),
            "triplet_consistency": metrics_payload.get("triplet_consistency"),
            "clean_run_determinism": metrics_payload.get("evidence_determinism"),
        },
        "source": "evaluation/results large-scale combined_metrics.json",
    }


def write_final_report(run_dir: Path, metrics_payload: dict[str, Any], stats: dict[str, Any], failures: list[dict[str, Any]], composition: dict[str, Any]) -> None:
    git = git_info()
    decision = metrics_payload["finalization_decision"]
    lines = [
        "# D1-D8 Large-Scale Final Evaluation Report",
        "",
        "## 1. Executive Summary",
        "",
        f"Execution mode: `{metrics_payload['execution_mode']}`.",
        f"D1-D5 records: `{metrics_payload['document_record_count']}` from `{metrics_payload['document_unique_case_count']}` unique cases.",
        f"D6-D8 records: `{metrics_payload['evidence_record_count']}` from `{metrics_payload['evidence_unique_case_count']}` unique cases.",
        f"Total measured records: `{metrics_payload['total_measured_record_count']}`.",
        f"Finalization decision: `{decision}`.",
        "",
        "## 2. Repository and Freeze State",
        "",
        f"Branch: `{git.get('git_branch')}`.",
        f"Current commit: `{git.get('git_commit')}`.",
        "Code-freeze tag: `d1-d8-large-scale-code-freeze-v1`.",
        "Benchmark-freeze tag: `d1-d8-large-scale-benchmark-freeze-v1`.",
        "Final evaluation tag: `coginfocom-2026-d1-d8-final-eval-v1` after final commit.",
        "",
        "## 3. Environment",
        "",
        f"OS: `{platform.platform()}`.",
        f"Python: `{sys.version.split()[0]}`.",
        "MariaDB database: `infobank_eval`.",
        "Chroma path: `backend_python/chroma_eval`.",
        "Embedding model: `text-embedding-3-small`; generator model: `gpt-4o-mini`; temperature: `0.0`; top-k: `4`; max output tokens: `160`.",
        "",
        "## 4. Experimental Protocol",
        "",
        "The preregistered protocol is stored in `evaluation/preregistration/d1_d8_large_scale_v1.md`. D1-D5 compares `standard_rag`, `governance_only_rag`, and `role_aware_rag` with shared retrieval. D6-D8 uses the frozen production action-reconstruction path and zero external LLM calls.",
        "",
        "## 5. Large-Scale D1-D5 Benchmark",
        "",
        f"Composition: `{json.dumps(composition.get('document_scenario_counts'), sort_keys=True)}`.",
        "The fixture uses matched D1/D2/D4 triplets, D3 aggregate pairs, and D5 mixed/contextual pairs. Gold fields are kept outside generator-visible source text.",
        "",
        "## 6. Held-Out D6-D8 Benchmark",
        "",
        f"Composition: `{json.dumps(composition.get('evidence_scenario_counts'), sort_keys=True)}`.",
        f"D8 closure distribution: `{json.dumps(composition.get('d8_closure_distribution'), sort_keys=True)}`.",
        f"Natural/synthetic counts: `{json.dumps(composition.get('natural_synthetic_gold_counts'), sort_keys=True)}`.",
        "",
        "## 7. Corrected Metric Definitions",
        "",
        "Permitted-answer accuracy is computed only over answer-permitted cases. Prohibited-disclosure, safe-withholding, and generator-exposure rates are computed only over restricted cases. Literal marker occurrence is reported only as a diagnostic. Exact output-class conformance is distinct from safe withholding. Repetitions are aggregated at case level for inferential tests.",
        "",
        "## 8. D1-D5 Results",
        "",
        "```json",
        json.dumps(metrics_payload.get("document_metrics", {}).get("by_mode"), indent=2, sort_keys=True),
        "```",
        "",
        "## 9. D6-D8 Results",
        "",
        "```json",
        json.dumps(metrics_payload.get("evidence_metrics"), indent=2, sort_keys=True),
        "```",
        "",
        "## 10. Statistical Analysis",
        "",
        f"Case-level McNemar/Holm tests: `{len(stats.get('case_level_mcnemar_holm') or [])}` rows. Clustered bootstrap samples: `{stats.get('bootstrap_samples')}`.",
        "",
        "## 11. API and Computational Usage",
        "",
        "```json",
        json.dumps(metrics_payload.get("api_usage"), indent=2, sort_keys=True),
        "```",
        "",
        "## 12. Reproducibility",
        "",
        "```powershell",
        "git checkout d1-d8-large-scale-final-evaluation",
        "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force",
        ".\\evaluation\\run_d1_d8_large_scale.ps1 -CheckOnly",
        "$env:OPENAI_API_KEY = \"<set outside the repository>\"",
        ".\\evaluation\\run_d1_d8_large_scale.ps1 -RealApi -Resume",
        "```",
        "",
        "## 13. Threats to Validity",
        "",
        "Synthetic D1-D5 fixtures, synthetic D7 browser-only cases, synthetic D8 closures where natural MailEx closures were unavailable, one provider/model, temperature-zero nondeterminism, pseudonymized Enron-derived e-mail domain limits, and non-external benchmark administration limit generality.",
        "",
        "## 14. Allowed and Disallowed Claims",
        "",
        "Supported claims: frozen benchmark record counts, corrected metric definitions, mode comparisons within the benchmark, and zero-LLM EvidenceUnit reconstruction behavior. Unsupported claims: production readiness, universal privacy-law compliance, perfect real-world action reconstruction, or external independent replication.",
        "",
        "## 15. Finalization Decision",
        "",
        decision,
        "",
        f"Failure records disclosed: `{len(failures)}`.",
    ]
    text = "\n".join(lines) + "\n"
    (run_dir / "final_report.md").write_text(text, encoding="utf-8")
    FINAL_REPORT.parent.mkdir(parents=True, exist_ok=True)
    FINAL_REPORT.write_text(text, encoding="utf-8")


def write_paper_update_package(publication_dir: Path, metrics_payload: dict[str, Any]) -> None:
    decision = metrics_payload["finalization_decision"]
    numbers = paper_numbers(metrics_payload)
    text = [
        "# D1-D8 v2.7 Paper Update Package",
        "",
        "## Abstract Result Paragraph",
        "",
        f"We evaluated InfoBank on a frozen D1-D8 benchmark with {metrics_payload['document_unique_case_count']} D1-D5 document-RAG cases and {metrics_payload['evidence_unique_case_count']} D6-D8 EvidenceUnit cases, producing {metrics_payload['total_measured_record_count']} measured records in the recorded run. D1-D5 compared standard RAG, governance-only RAG, and role-aware RAG under shared retrieval; D6-D8 evaluated the production action-reconstruction path on a held-out MailEx-derived benchmark. The run status is `{decision}`; numerical claims should be inserted from `paper_numbers.json` after confirming the final real-API run.",
        "",
        "## Evaluation Section Replacement",
        "",
        "The final evaluation used a preregistered, frozen benchmark protocol. The document-RAG benchmark contains 400 synthetic cases arranged as matched D1/D2/D4 triplets, D3 aggregate pairs, and D5 mixed/contextual pairs. Each case was evaluated under three RAG configurations with five repetitions, using shared top-4 retrieval candidates across modes. The EvidenceUnit benchmark contains 340 held-out MailEx-derived or controlled synthetic cases covering open actions, browser-only counterfactuals, closures, and non-closing controls, evaluated across three clean database runs.",
        "",
        "## Metrics Subsection Replacement",
        "",
        "Permitted-answer accuracy is the proportion of correct answers among answer-permitted cases only. Prohibited-disclosure, safe-withholding, and generator-exposure rates are computed only over restricted cases. Exact behavioral conformance measures the exact expected output class and is reported separately from safe withholding. Source-role conformance compares expected and observed evidence roles. Repetitions are not treated as independent samples; inferential tests aggregate at the case level.",
        "",
        "## Results Subsection Replacement",
        "",
        "Insert the final numerical results from `evaluation/publication_results/d1_d8_large_scale_v1/paper_numbers.json` and the LaTeX tables in the adjacent `tables/` directory.",
        "",
        "## Threats-to-Validity Replacement",
        "",
        "The evaluation remains limited by synthetic D1-D5 construction, synthetic browser-only D7 cases, a synthetic subset of D8 closures where unambiguous natural closures were not available, one provider/model configuration, and a MailEx/Enron-derived e-mail domain. The benchmark is frozen after development but was not externally administered.",
        "",
        "## Conclusion Update",
        "",
        "The large-scale evaluation provides a frozen, reproducible estimate of InfoBank's role-aware behavior under the D1-D8 taxonomy, while preserving clear limits on generalization and deployment claims.",
        "",
        "## MailEx Citation",
        "",
        "Use the bibliographic entry already present in the manuscript or the official MailEx publication metadata. Do not fabricate missing fields.",
        "",
        "## Replacement for Development-Pilot Sentence",
        "",
        "An earlier 53-record development pilot was used only for implementation diagnostics; the reported results are from a subsequent frozen large-scale D1-D8 evaluation.",
        "",
        "## Machine-Readable Numbers",
        "",
        "```json",
        json.dumps(numbers, indent=2, sort_keys=True),
        "```",
    ]
    PAPER_UPDATE_PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    PAPER_UPDATE_PACKAGE.write_text("\n".join(text) + "\n", encoding="utf-8")


def write_initial_manifests(run_dir: Path, *, env_file: Path, document_fixture: Path, evidence_benchmark: Path, preflight: dict[str, Any] | None, execution_mode: str, args: argparse.Namespace) -> None:
    checksums = benchmark_checksums(document_fixture, evidence_benchmark)
    write_sanitized_json(run_dir / "benchmark_checksums.json", checksums)
    write_sanitized_json(run_dir / "environment_manifest.json", environment_manifest(env_file, preflight))
    if PREREGISTRATION.exists():
        shutil.copyfile(PREREGISTRATION, run_dir / "preregistration_snapshot.md")
    manifest = {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "execution_mode": execution_mode,
        "created_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "git": git_info(),
        "tracked_status": tracked_status(),
        "document_fixture": str(document_fixture),
        "evidence_benchmark": str(evidence_benchmark),
        "benchmark_checksums": checksums,
        "environment": environment_manifest(env_file, preflight),
        "modes": {"document": PILOT_MODES, "evidence": [EVIDENCE_MODE]},
        "document_repetitions": args.document_repetitions,
        "evidence_clean_repetitions": args.evidence_repetitions,
        "top_k": args.top_k,
        "embedding_model": EMBEDDING_MODEL,
        "generator_model": GENERATOR_MODEL,
        "temperature": TEMPERATURE,
        "max_output_tokens": 160,
        "expected_counts": {"document_records": 400 * 3 * args.document_repetitions, "evidence_records": 340 * args.evidence_repetitions},
        "openai_key_visible": bool(os.environ.get("OPENAI_API_KEY")),
        "credentials_serialized": False,
    }
    write_sanitized_json(run_dir / "run_manifest.json", manifest)


def update_final_manifest(run_dir: Path, phases: dict[str, Any], combined_metrics: dict[str, Any] | None) -> None:
    manifest = read_json(run_dir / "run_manifest.json")
    manifest["completed_at_utc"] = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    manifest["phases"] = phases
    if combined_metrics:
        manifest["combined_metrics_summary"] = {
            "document_record_count": combined_metrics.get("document_record_count"),
            "evidence_record_count": combined_metrics.get("evidence_record_count"),
            "total_measured_record_count": combined_metrics.get("total_measured_record_count"),
            "finalization_decision": combined_metrics.get("finalization_decision"),
        }
    write_sanitized_json(run_dir / "run_manifest.json", manifest)


def write_failure_artifact(run_dir: Path, exc: BaseException) -> None:
    write_sanitized_json(
        run_dir / "pilot_failure.json",
        {
            "stage": getattr(exc, "stage", "large-scale"),
            "classification": getattr(exc, "classification", "unexpected"),
            "current_case": getattr(exc, "current_case", None),
            "current_mode": getattr(exc, "current_mode", None),
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
            "git": git_info(),
            "openai_key_exposed": False,
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the frozen InfoBank D1-D8 large-scale evaluation.")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--build-benchmarks", action="store_true")
    parser.add_argument("--validate-benchmarks", action="store_true")
    parser.add_argument("--document-only", action="store_true")
    parser.add_argument("--evidence-only", action="store_true")
    parser.add_argument("--real-api", action="store_true")
    parser.add_argument("--mock-generation", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_BASE))
    parser.add_argument("--document-fixture", default=str(DEFAULT_DOCUMENT_FIXTURE))
    parser.add_argument("--evidence-benchmark", default=str(DEFAULT_EVIDENCE_BENCHMARK))
    parser.add_argument("--publication-dir", default=str(DEFAULT_PUBLICATION_DIR))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--document-repetitions", type=int, default=5)
    parser.add_argument("--evidence-repetitions", type=int, default=3)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    document_fixture = Path(args.document_fixture)
    if not document_fixture.is_absolute():
        document_fixture = (REPO_ROOT / document_fixture).resolve()
    evidence_benchmark = Path(args.evidence_benchmark)
    if not evidence_benchmark.is_absolute():
        evidence_benchmark = (REPO_ROOT / evidence_benchmark).resolve()
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = (REPO_ROOT / env_file).resolve()
    publication_dir = Path(args.publication_dir)
    if not publication_dir.is_absolute():
        publication_dir = (REPO_ROOT / publication_dir).resolve()

    if args.build_benchmarks:
        build_result = build_benchmarks()
        print("D1-D8 LARGE BUILD: PASS")
        print(build_result["document"]["stdout"].strip())
        print(build_result["evidence"]["stdout"].strip())
    if args.validate_benchmarks:
        validation = validate_benchmarks(document_fixture, evidence_benchmark)
        print(f"D1-D8 LARGE VALIDATE: PASS document_cases={validation['document_case_count']} evidence_cases={validation['evidence_case_count']}")
    if args.check_only:
        preflight = run_preflight(
            env_file=env_file,
            document_fixture=document_fixture,
            evidence_benchmark=evidence_benchmark,
            require_openai_key=False,
            require_clean_state=not args.resume,
        )
        print(
            "D1-D8 LARGE CHECK: PASS "
            f"database={preflight['database']['database_name']} "
            f"mariadb={preflight['mariadb_server_version']} "
            f"document_cases={preflight['validation']['document_case_count']} "
            f"evidence_cases={preflight['validation']['evidence_case_count']} "
            f"openai_key_visible={preflight['openai_key_visible']}"
        )
        return 0
    only_build_validate = (args.build_benchmarks or args.validate_benchmarks) and not any([args.real_api, args.mock_generation, args.document_only, args.evidence_only, args.score_only, args.report_only])
    if only_build_validate:
        return 0

    create_new = not (args.score_only or args.report_only)
    run_dir = resolve_results_dir(args.results_dir, create_new=create_new, resume=args.resume)
    execution_mode = "real-api" if args.real_api else "mock-generation"
    phases: dict[str, Any] = {}
    combined_metrics = None
    try:
        preflight = None
        if not (args.score_only or args.report_only):
            preflight = run_preflight(
                env_file=env_file,
                document_fixture=document_fixture,
                evidence_benchmark=evidence_benchmark,
                require_openai_key=args.real_api and not args.evidence_only,
                require_clean_state=not args.resume,
            )
            write_initial_manifests(run_dir, env_file=env_file, document_fixture=document_fixture, evidence_benchmark=evidence_benchmark, preflight=preflight, execution_mode=execution_mode, args=args)
            include_document = not args.evidence_only
            include_evidence = not args.document_only
            if include_document:
                phases["document"] = run_document_phase(
                    run_dir=run_dir,
                    document_fixture=document_fixture,
                    env_file=env_file,
                    real_api=args.real_api,
                    top_k=args.top_k,
                    repetitions=args.document_repetitions,
                    resume=args.resume,
                )
                print(f"D1-D5 LARGE DOCUMENT: PASS records={phases['document']['record_count']}")
            if include_evidence:
                phases["evidence"] = run_evidence_phase(
                    run_dir=run_dir,
                    evidence_benchmark=evidence_benchmark,
                    env_file=env_file,
                    repetitions=args.evidence_repetitions,
                    resume=args.resume,
                )
                print(f"D6-D8 LARGE EVIDENCE: PASS records={phases['evidence']['record_count']}")
        combined_metrics = score_and_report(
            run_dir=run_dir,
            document_fixture=document_fixture,
            evidence_benchmark=evidence_benchmark,
            publication_dir=publication_dir,
            execution_mode=execution_mode,
            bootstrap_samples=args.bootstrap_samples,
        )
        update_final_manifest(run_dir, phases, combined_metrics)
    except Exception as exc:
        run_dir.mkdir(parents=True, exist_ok=True)
        write_failure_artifact(run_dir, exc)
        print(f"D1-D8 LARGE: FAILED results_dir={run_dir} error={exc}")
        return getattr(exc, "exit_code", 1)

    print(
        "D1-D8 LARGE: PASS "
        f"results_dir={run_dir} "
        f"document_records={combined_metrics['document_record_count']} "
        f"evidence_records={combined_metrics['evidence_record_count']} "
        f"total_records={combined_metrics['total_measured_record_count']} "
        f"decision={combined_metrics['finalization_decision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

