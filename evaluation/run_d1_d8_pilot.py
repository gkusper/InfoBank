from __future__ import annotations

import argparse
import datetime as dt
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
from .clean_state import CleanStateError, check_clean_state
from .fixture_schema import load_fixture
from .load_evidence_fixtures import (
    cleanup_case,
    configure_database_from_env_file,
    load_benchmark,
    load_case,
    parse_timestamp,
)
from .manifest import git_info, package_versions
from .run_document_rag_pilot import (
    APPROVED_PILOT_CASE_IDS,
    EMBEDDING_MODEL,
    GENERATOR_MODEL,
    TEMPERATURE,
    PilotError,
    PilotConfig as DocumentPilotConfig,
    _run_document_rag_pilot,
    resolve_chroma_path,
    validate_runtime_targets,
)
from .score_document_results import score_results as score_document_records
from .score_evidence_unit_results import score_results as score_evidence_records
from .validate_fixtures import validate_fixture


DEFAULT_DOCUMENT_FIXTURE = REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v2.yaml"
DEFAULT_EVIDENCE_BENCHMARK = REPO_ROOT / "data" / "benchmarks" / "evidence_unit_v1"
DEFAULT_RESULTS_DIR = REPO_ROOT / "evaluation" / "results"
DEFAULT_ENV_FILE = BACKEND_DIR / ".env.eval"
EVIDENCE_MODE = "role_aware_action_reconstruction"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize(row), ensure_ascii=False, sort_keys=True) + "\n")


def sanitize(value: Any) -> Any:
    redacted_values = [os.environ.get("OPENAI_API_KEY"), os.environ.get("DATABASE_URL")]
    secret_key_parts = ("password", "secret", "api_key", "apikey", "access_token", "refresh_token", "authorization")
    if isinstance(value, str):
        clean = value
        for secret in [item for item in redacted_values if item]:
            clean = clean.replace(secret, "<redacted>")
        return clean
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(part in lowered for part in secret_key_parts):
                cleaned[key_text] = "<redacted>"
            else:
                cleaned[key_text] = sanitize(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return value


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_run_dir(results_dir: Path) -> tuple[str, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    base = "d1_d8_pilot_" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate = results_dir / base
    suffix = 1
    while candidate.exists():
        candidate = results_dir / f"{base}_{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate.name, candidate


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise RuntimeError(f"Evaluation env file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def tcp_reachable(host: str, port: int) -> bool:
    with socket.create_connection((host, port), timeout=2.0):
        return True


def validate_evidence_benchmark(root: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "mailex"))
    from validate_evidence_benchmark import validate

    errors = validate(root)
    if errors:
        raise RuntimeError("EvidenceUnit benchmark validation failed: " + "; ".join(errors))


def run_preflight(*, env_file: Path, document_fixture: Path, evidence_benchmark: Path, require_openai_key: bool) -> dict[str, Any]:
    env_values = read_env_file(env_file)
    database_url = env_values.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    chroma_value = env_values.get("CHROMA_PERSIST_DIR") or os.environ.get("CHROMA_PERSIST_DIR")
    if not database_url or not chroma_value:
        raise RuntimeError("DATABASE_URL and CHROMA_PERSIST_DIR must be configured in the evaluation environment.")
    chroma_path = resolve_chroma_path(chroma_value, env_file, REPO_ROOT)
    validate_runtime_targets(database_url=database_url, chroma_path=chroma_path)
    os.environ["DATABASE_URL"] = database_url
    os.environ["CHROMA_PERSIST_DIR"] = str(chroma_path)
    if require_openai_key and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("PILOT BLOCKED: OPENAI_API_KEY NOT CONFIGURED")
    reachable = tcp_reachable("127.0.0.1", 3307)
    clean = check_clean_state(database_url=database_url, chroma_persist_dir=str(chroma_path))
    fixture = load_fixture(document_fixture)
    validate_fixture(fixture)
    if fixture.fixture_id != "document_rag_v2":
        raise RuntimeError(f"D1-D5 pilot must use document_rag_v2, not {fixture.fixture_id!r}.")
    validate_evidence_benchmark(evidence_benchmark)
    benchmark = load_benchmark(evidence_benchmark)
    if len(benchmark.cases) != 32:
        raise RuntimeError(f"Expected 32 EvidenceUnit cases, found {len(benchmark.cases)}.")
    _, SessionLocal, database_info = configure_database_from_env_file(env_file)
    with SessionLocal() as db:
        mariadb_version = db.execute(text("SELECT VERSION()")).scalar()
    return {
        "status": "PASS",
        "database": database_info,
        "mariadb_reachable": reachable,
        "mariadb_server_version": mariadb_version,
        "chroma_persist_dir": str(chroma_path),
        "clean_state": clean.to_dict(),
        "document_fixture": str(document_fixture),
        "document_fixture_id": fixture.fixture_id,
        "evidence_benchmark": str(evidence_benchmark),
        "evidence_case_count": len(benchmark.cases),
        "openai_key_visible": bool(os.environ.get("OPENAI_API_KEY")),
    }


def run_document_phase(
    *,
    run_id: str,
    run_dir: Path,
    document_fixture: Path,
    env_file: Path,
    top_k: int,
    repetitions: int,
    real_api: bool,
    mock_generation: bool,
) -> dict[str, Any]:
    document_dir = run_dir / "document_phase"
    document_dir.mkdir(parents=True, exist_ok=True)
    config = DocumentPilotConfig(
        real_api=real_api,
        mock_generation=mock_generation,
        check_only=False,
        results_dir=run_dir,
        fixture_path=document_fixture,
        env_file=env_file,
        top_k=top_k,
        repetitions=repetitions,
        case_ids=APPROVED_PILOT_CASE_IDS,
    )
    summary = _run_document_rag_pilot(config, run_id=f"{run_id}_document", run_dir=document_dir)
    document_results = run_dir / "document_results.jsonl"
    shutil.copyfile(document_dir / "results.jsonl", document_results)
    shutil.copyfile(document_dir / "shared_retrieval.jsonl", run_dir / "document_shared_retrieval.jsonl")
    records = read_jsonl(document_results)
    fixture = load_fixture(document_fixture)
    scores, metrics = score_document_records(records, fixture)
    write_jsonl(run_dir / "document_scores.jsonl", scores)
    write_json(run_dir / "document_metrics.json", metrics)
    return {
        "summary": summary,
        "record_count": len(records),
        "metrics": metrics,
        "phase_dir": str(document_dir),
        "api_usage": read_json(document_dir / "run_manifest.json").get("api_usage", {}),
    }


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
    run_id: str,
    run_dir: Path,
    evidence_benchmark: Path,
    env_file: Path,
    preserve_state: bool,
    diagnostic_name: str,
) -> dict[str, Any]:
    benchmark = load_benchmark(evidence_benchmark)
    _, SessionLocal, database_info = configure_database_from_env_file(env_file)
    results: list[dict[str, Any]] = []
    loaded_cases: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for case in benchmark.cases:
            loaded = load_case(db, case)
            loaded_cases.append(loaded.to_dict())
            try:
                reconstruction = production_reconstruct(db, loaded.user_id, case.get("query_time"))
                record = {
                    "run_id": run_id,
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
                results.append(record)
            finally:
                if not preserve_state:
                    cleanup_case(db, loaded.user_id)
    evidence_results_path = run_dir / "evidence_results.jsonl"
    write_jsonl(evidence_results_path, results)
    scores, metrics = score_evidence_records(results, benchmark.gold)
    write_jsonl(run_dir / "evidence_scores.jsonl", scores)
    write_json(run_dir / "evidence_metrics.json", metrics)
    diagnostic = {
        "diagnostic_name": diagnostic_name,
        "run_id": run_id,
        "database": database_info,
        "case_count": len(results),
        "result_counts": {
            "D6": sum(1 for row in results if row["scenario"] == "D6"),
            "D7": sum(1 for row in results if row["scenario"] == "D7"),
            "D8": sum(1 for row in results if row["scenario"] == "D8"),
            "D8_NONCLOSING": sum(1 for row in results if row["scenario"] == "D8_NONCLOSING"),
        },
        "metrics": metrics,
        "failures": metrics.get("failures", []),
        "loaded_cases": loaded_cases,
        "case_isolation_strategy": "deterministic evaluation user per case; cleanup after each case unless --preserve-state",
        "query_time_filtering": "loader excludes units with timestamp later than case query_time",
    }
    write_json(run_dir / diagnostic_name, diagnostic)
    return {
        "record_count": len(results),
        "metrics": metrics,
        "diagnostic": diagnostic,
        "api_usage": {"external_llm_calls": 0, "generation_calls": 0, "embedding_calls": 0, "total_tokens": 0},
    }


def combined_summary(document_scores: list[dict[str, Any]], evidence_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for score in document_scores:
        rows.append(
            {
                "phase": "document_rag",
                "case_id": score["case_id"],
                "mode": score["mode"],
                "scenario": score["scenario_family"],
                "pass": score["behavioral_conformance"],
                "status": score.get("output_mode"),
            }
        )
    for score in evidence_scores:
        rows.append(
            {
                "phase": "evidence_unit",
                "case_id": score["case_id"],
                "mode": EVIDENCE_MODE,
                "scenario": score["scenario"],
                "pass": score["case_pass"],
                "status": score["observed_status"],
            }
        )
    return rows


def build_report(run_dir: Path, manifest: dict[str, Any], metrics: dict[str, Any], baseline: dict[str, Any] | None) -> str:
    evidence = metrics.get("evidence_unit", {})
    document = metrics.get("document_rag", {})
    document_blocked = manifest.get("document_blocked_reason")
    if manifest["execution_mode"] == "real-api" and not document_blocked and metrics.get("document_record_count") == 21:
        run_status = "A full real combined pilot was completed."
    elif document_blocked:
        run_status = "A partial run was completed: the document-RAG phase was skipped because the process did not expose OPENAI_API_KEY."
    else:
        run_status = "A mock/development pilot run was completed."
    lines = [
        "# D1-D8 End-to-End Pilot Report",
        "",
        "## 1. Executive Summary",
        "",
        f"Run ID: `{manifest['run_id']}`.",
        f"Execution mode: `{manifest['execution_mode']}`.",
        run_status,
        "This is a development-pilot run against the frozen engineering benchmark, not an unbiased final test-set result.",
        "",
        "## 2. Starting Repository State",
        "",
        f"Branch: `{manifest['git'].get('git_branch')}`.",
        f"Commit: `{manifest['git'].get('git_commit')}`.",
        f"Working tree status: `{manifest.get('tracked_status') or 'clean'}`.",
        "",
        "## 3. MariaDB and Evaluation Environment",
        "",
        f"Database: `{manifest['database'].get('database_name')}` at `{manifest['database'].get('database_host')}:{manifest['database'].get('database_port')}`.",
        f"MariaDB server version: `{manifest.get('mariadb_server_version')}`.",
        f"Chroma path: `{manifest.get('chroma_persist_dir')}`.",
        "",
        "## 4. Frozen Benchmark",
        "",
        f"Document fixture: `{manifest['document_fixture']['path']}` SHA-256 `{manifest['document_fixture']['sha256']}`.",
        f"Evidence benchmark: `{manifest['evidence_benchmark']['path']}`.",
        f"Evidence cases: `{manifest['evidence_benchmark']['case_count']}`.",
        "",
        "## 5. Implementation Changes",
        "",
        "- Added a MariaDB EvidenceUnit benchmark loader that preserves benchmark evidence IDs and separates runtime input from gold labels.",
        "- Added deterministic EvidenceUnit and document-RAG scorers.",
        "- Added a unified D1-D8 runner and PowerShell wrapper.",
        "- Production action reconstruction changes, when present, are generic relation/speech-act handling and are covered by tests.",
        "",
        "## 6. D1-D5 Execution",
        "",
        f"Document result records: `{metrics.get('document_record_count', 0)}`.",
        f"Behavioral conformance: `{document.get('behavioral_conformance_rate')}`.",
        f"Protected-marker disclosure rate: `{document.get('protected_marker_disclosure_rate')}`.",
        f"Document blocked reason: `{document_blocked or 'none'}`.",
        "",
        "## 7. D6-D8 Execution",
        "",
        f"EvidenceUnit result records: `{metrics.get('evidence_record_count', 0)}`.",
        "Production service path: `backend_python.evidence_service.reconstruct_action_list`.",
        "External LLM calls for EvidenceUnit phase: `0`.",
        "",
        "## 8. Baseline Evidence Diagnostic",
        "",
    ]
    if baseline:
        lines.append(f"Baseline diagnostic source: `{baseline.get('source')}`.")
        lines.append(f"Baseline status accuracy: `{baseline.get('metrics', {}).get('OPEN_CLOSED_ABSENT_status_accuracy')}`.")
        lines.append(f"Baseline failures: `{len(baseline.get('failures') or [])}`.")
    else:
        lines.append("No separate pre-fix baseline artifact was attached to this run directory.")
    lines.extend(
        [
            "",
            "## 9. Post-Fix Evidence Diagnostic",
            "",
            f"Status accuracy: `{evidence.get('OPEN_CLOSED_ABSENT_status_accuracy')}`.",
            f"Failures: `{len(evidence.get('failures') or [])}`.",
            "",
            "## 10. Metrics",
            "",
            f"- D6 open-action accuracy: `{evidence.get('D6_open_action_accuracy')}`",
            f"- D7 browser-only false-action rate: `{evidence.get('D7_browser_only_false_action_rate')}`",
            f"- D8 closure-status accuracy: `{evidence.get('D8_closure_status_accuracy')}`",
            f"- D8_NONCLOSING open-status accuracy: `{evidence.get('D8_NONCLOSING_open_status_accuracy')}`",
            f"- EvidenceUnit role accuracy: `{evidence.get('EvidenceUnit_role_accuracy')}`",
            f"- Action precision/recall/F1: `{evidence.get('action_precision')}` / `{evidence.get('action_recall')}` / `{evidence.get('action_F1')}`",
            f"- Triplet consistency: `{(evidence.get('matched_triplet_consistency') or {}).get('rate')}`",
            "",
            "Confusion matrix:",
            "",
            "```json",
            json.dumps(evidence.get("OPEN_CLOSED_ABSENT_confusion_matrix"), indent=2, sort_keys=True),
            "```",
            "",
            "## 11. Per-Case Failures",
            "",
        ]
    )
    document_failures = document.get("failures") or []
    if document_failures:
        lines.append("Document-RAG failures:")
        for failure in document_failures:
            lines.append(
                f"- `{failure['case_id']}` `{failure['mode']}` expected `{failure['expected_behavioral_class']}` "
                f"observed `{failure['output_mode']}`; protected disclosure `{failure['protected_marker_disclosure']}`, "
                f"generator exposure `{failure['generator_exposure']}`."
            )
        lines.append("")

    lines.append("EvidenceUnit failures:")
    failures = evidence.get("failures") or []
    if failures:
        for failure in failures:
            lines.append(f"- `{failure['case_id']}` `{failure['scenario']}` expected `{failure['expected_status']}` observed `{failure['observed_status']}` category `{failure.get('failure_category')}`.")
    else:
        lines.append("No EvidenceUnit per-case failures in the post-fix run.")
    lines.extend(
        [
            "",
            "## 12. Tests",
            "",
            "Recorded in the terminal summary and commit message context. The canonical command is:",
            "",
            "```powershell",
            ".\\backend_python\\.venv_eval\\Scripts\\python.exe -m unittest discover -s evaluation\\tests -v",
            "```",
            "",
            "## 13. Reproduction Commands",
            "",
            "```powershell",
            "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force",
            ".\\evaluation\\bootstrap_reproduction.ps1 -ResetEvaluationState -SkipPackageInstall -RunPilotCheck",
            ".\\evaluation\\run_d1_d8_pilot.ps1 -MockGeneration",
            ".\\evaluation\\run_d1_d8_pilot.ps1 -EvidenceOnly",
            "# For real D1-D5 generation, set OPENAI_API_KEY in the process and run:",
            ".\\evaluation\\run_d1_d8_pilot.ps1",
            "```",
            "",
            "## 14. Limitations",
            "",
            "- Development-set tuning after baseline observation.",
            "- Small MailEx-derived pilot.",
            "- Synthetic D7 browser/search counterfactuals.",
            "- InfoBank-specific D8 open/closed labels.",
            "- No cancelled examples in the current benchmark.",
            "- One provider and one repetition for real document generation.",
            "- Deterministic action logic versus LLM-backed document generation.",
            "",
            "## 15. Next Experimental Step",
            "",
            "Proceed only after reviewing remaining failures, if any. The next steps are the full D1-D5 40-case x 3-mode x 3-repetition run, D6-D8 expansion toward 40 matched seeds, and held-out benchmark construction.",
            "",
        ]
    )
    return "\n".join(lines)


def tracked_status() -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO_ROOT.as_posix()}", "-C", str(REPO_ROOT), "status", "--short"],
        text=True,
    ).strip()


def write_failure_artifact(run_dir: Path, exc: BaseException) -> None:
    classification = "unexpected"
    stage = "combined"
    exit_code = 1
    if isinstance(exc, PilotError):
        classification = exc.classification
        stage = exc.stage
        exit_code = exc.exit_code
    write_json(
        run_dir / "pilot_failure.json",
        {
            "stage": stage,
            "classification": classification,
            "exit_code": exit_code,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
            "git": git_info(),
            "openai_key_exposed": False,
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MariaDB-backed InfoBank D1-D8 development pilot.")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--mock-generation", action="store_true")
    parser.add_argument("--real-api", action="store_true")
    parser.add_argument("--document-only", action="store_true")
    parser.add_argument("--evidence-only", action="store_true")
    parser.add_argument("--preserve-state", action="store_true")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--document-fixture", default=str(DEFAULT_DOCUMENT_FIXTURE))
    parser.add_argument("--evidence-benchmark", default=str(DEFAULT_EVIDENCE_BENCHMARK))
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--baseline-diagnostic")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    document_fixture = Path(args.document_fixture).resolve()
    evidence_benchmark = Path(args.evidence_benchmark).resolve()
    env_file = Path(args.env_file).resolve()
    include_document = not args.evidence_only
    include_evidence = not args.document_only
    real_api = bool(args.real_api or (not args.mock_generation and not args.check_only))
    mock_generation = bool(args.mock_generation)
    document_blocked_reason = None
    document_resume_command = None

    if args.check_only:
        preflight = run_preflight(
            env_file=env_file,
            document_fixture=document_fixture,
            evidence_benchmark=evidence_benchmark,
            require_openai_key=False,
        )
        print(
            "D1-D8 CHECK: PASS "
            f"database={preflight['database']['database_name']} "
            f"evidence_cases={preflight['evidence_case_count']} "
            f"openai_key_visible={preflight['openai_key_visible']}"
        )
        return 0

    openai_missing_for_document = real_api and include_document and not os.environ.get("OPENAI_API_KEY")
    preflight = run_preflight(
        env_file=env_file,
        document_fixture=document_fixture,
        evidence_benchmark=evidence_benchmark,
        require_openai_key=real_api and include_document and not openai_missing_for_document,
    )
    if openai_missing_for_document:
        document_blocked_reason = "OPENAI_API_KEY is not visible in the process environment."
        document_resume_command = ".\\evaluation\\run_d1_d8_pilot.ps1"
        include_document = False
        if not include_evidence:
            print("D1-D8 PILOT: BLOCKED OPENAI_API_KEY not configured. Set $env:OPENAI_API_KEY and run .\\evaluation\\run_d1_d8_pilot.ps1")
            return 2

    run_id, run_dir = unique_run_dir(Path(args.results_dir))
    start = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    document_phase: dict[str, Any] | None = None
    evidence_phase: dict[str, Any] | None = None

    try:
        if include_document:
            document_phase = run_document_phase(
                run_id=run_id,
                run_dir=run_dir,
                document_fixture=document_fixture,
                env_file=env_file,
                top_k=args.top_k,
                repetitions=args.repetitions,
                real_api=real_api,
                mock_generation=mock_generation,
            )
        if include_evidence:
            evidence_phase = run_evidence_phase(
                run_id=run_id,
                run_dir=run_dir,
                evidence_benchmark=evidence_benchmark,
                env_file=env_file,
                preserve_state=args.preserve_state,
                diagnostic_name="final_evidence_diagnostic.json",
            )
    except Exception as exc:
        write_failure_artifact(run_dir, exc)
        print(f"D1-D8 PILOT: FAILED stage={(exc.stage if isinstance(exc, PilotError) else 'combined')} results_dir={run_dir}")
        return exc.exit_code if isinstance(exc, PilotError) else 1

    document_scores = read_jsonl(run_dir / "document_scores.jsonl") if (run_dir / "document_scores.jsonl").exists() else []
    evidence_scores = read_jsonl(run_dir / "evidence_scores.jsonl") if (run_dir / "evidence_scores.jsonl").exists() else []
    write_jsonl(run_dir / "combined_case_summary.jsonl", combined_summary(document_scores, evidence_scores))

    baseline_payload = None
    baseline_path = Path(args.baseline_diagnostic).resolve() if args.baseline_diagnostic else None
    if baseline_path and baseline_path.exists():
        baseline_payload = read_json(baseline_path)
        baseline_payload["source"] = str(baseline_path)
        write_json(run_dir / "baseline_evidence_diagnostic.json", baseline_payload)
    else:
        write_json(
            run_dir / "baseline_evidence_diagnostic.json",
            {"status": "not_attached", "reason": "No --baseline-diagnostic file was provided for this invocation."},
        )

    document_metrics = read_json(run_dir / "document_metrics.json") if (run_dir / "document_metrics.json").exists() else {}
    evidence_metrics = read_json(run_dir / "evidence_metrics.json") if (run_dir / "evidence_metrics.json").exists() else {}
    metrics = {
        "document_record_count": document_phase.get("record_count", 0) if document_phase else 0,
        "evidence_record_count": evidence_phase.get("record_count", 0) if evidence_phase else 0,
        "combined_record_count": (document_phase.get("record_count", 0) if document_phase else 0) + (evidence_phase.get("record_count", 0) if evidence_phase else 0),
        "document_rag": document_metrics,
        "evidence_unit": evidence_metrics,
    }
    write_json(run_dir / "metrics.json", metrics)
    api_usage = {
        "document_rag": document_phase.get("api_usage", {}) if document_phase else {},
        "evidence_unit": evidence_phase.get("api_usage", {}) if evidence_phase else {"external_llm_calls": 0},
    }
    write_json(run_dir / "api_usage.json", api_usage)
    _, SessionLocal, database_info = configure_database_from_env_file(env_file)
    with SessionLocal() as db:
        mariadb_version = db.execute(text("SELECT VERSION()")).scalar()
    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "execution_mode": "mock-generation" if mock_generation else ("partial-real-api-missing-openai-key" if document_blocked_reason else "real-api"),
        "phases": {"document": include_document, "evidence": include_evidence},
        "git": git_info(),
        "tracked_status": tracked_status(),
        "python_version": sys.version,
        "operating_system": platform.platform(),
        "package_versions": package_versions(),
        "database": database_info,
        "mariadb_server_version": mariadb_version,
        "chroma_persist_dir": preflight["chroma_persist_dir"],
        "document_fixture": {"path": str(document_fixture), "sha256": sha256_file(document_fixture), "selected_cases": APPROVED_PILOT_CASE_IDS},
        "evidence_benchmark": {
            "path": str(evidence_benchmark),
            "case_count": len(load_benchmark(evidence_benchmark).cases),
            "cases_sha256": sha256_file(evidence_benchmark / "cases.jsonl"),
            "gold_sha256": sha256_file(evidence_benchmark / "gold.jsonl"),
        },
        "modes": {"document": ["standard_rag", "governance_only_rag", "role_aware_rag"], "evidence": [EVIDENCE_MODE]},
        "top_k": args.top_k,
        "repetitions": args.repetitions,
        "embedding_model": EMBEDDING_MODEL,
        "generator_model": GENERATOR_MODEL,
        "temperature": TEMPERATURE,
        "start_timestamp": start,
        "end_timestamp": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "random_seeds": [],
        "cleanup_isolation_strategy": "deterministic evaluation user per EvidenceUnit case; cleanup after each case unless --preserve-state",
        "real_or_mock_execution_status": "mock D1-D5 generation" if mock_generation else ("D1-D5 skipped because OPENAI_API_KEY was unavailable; EvidenceUnit phase executed" if document_blocked_reason else "real D1-D5 API generation requested"),
        "document_blocked_reason": document_blocked_reason,
        "document_resume_command": document_resume_command,
        "openai_key_visible": bool(os.environ.get("OPENAI_API_KEY")),
        "credentials_serialized": False,
    }
    write_json(run_dir / "run_manifest.json", manifest)
    report = build_report(run_dir, manifest, metrics, baseline_payload)
    (run_dir / "pilot_report.md").write_text(report, encoding="utf-8")
    status_label = "PARTIAL" if document_blocked_reason else "PASS"
    print(
        f"D1-D8 PILOT: {status_label} "
        f"run_id={run_id} document_records={metrics['document_record_count']} "
        f"evidence_records={metrics['evidence_record_count']} results_dir={run_dir}"
    )
    if document_resume_command:
        print(f"D1-D5 REAL API COMPLETION COMMAND: {document_resume_command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
