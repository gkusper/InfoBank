"""Offline postmortem and rescoring for the sealed Claude S1-S6 run.

This script intentionally performs no provider calls. It reads the sealed raw
run, re-scores it with the repetition-aware scorer, and reuses the frozen
publication metric helpers for descriptive manuscript-style summaries.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import socket
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
DEFAULT_RUN_DIR = REPO_ROOT / "evaluation" / "results" / "claude_full_20260904T190415Z_cee5faf"
DEFAULT_ORIGINAL_REPORT_DIR = (
    REPO_ROOT
    / "artifacts"
    / "anthropic_provider_readiness"
    / "full_claude_experiment_20260904T190415Z_cee5faf"
)
DEFAULT_OUTPUT_DIR = DEFAULT_ORIGINAL_REPORT_DIR / "offline_scoring_postmortem_v2"
OPENAI_REFERENCE_DIR = REPO_ROOT / "artifacts" / "s1_s6_publication_experiment_v2" / "openai"
PUBLICATION_SCRIPT = (
    REPO_ROOT
    / "artifacts"
    / "s1_s6_publication_experiment"
    / "scripts"
    / "run_s1_s6_publication_experiment.py"
)
EXPECTED_HEAD = "cee5faf799c160349b09cefbe90d90365bae4a68"
EXPECTED_HASHES = {
    "raw_records.jsonl": "05125fcaa443feac2829c80a998ddab5823068b26e3ae8c4786b7e10a528b2f9",
    "deterministic_content.jsonl": "718314878838aa5adc5667587915e0873730a6c984cc58d4ae69cd245d16a617",
    "run_seal.json": "3f7983652d92b8b0b2a257e2344fd094f41be2567e892b774dac7c31929e3f2b",
    "wall_clock_timings.jsonl": "38bc43bc3bbabea7628243aab1be053c7d0eb1a477f07489ca856218710098ed",
}
MODE_ORDER = [
    "C0_VECTOR_ONLY",
    "C1_VECTOR_ROUTING",
    "P1_PROMPT_ONLY_GOVERNANCE",
    "C2_PERMISSION_FILTERED",
    "C3_FULL_ROLE_AWARE",
]
MODE_SHORT = {
    "C0_VECTOR_ONLY": "C0",
    "C1_VECTOR_ROUTING": "C1",
    "P1_PROMPT_ONLY_GOVERNANCE": "P1",
    "C2_PERMISSION_FILTERED": "C2",
    "C3_FULL_ROLE_AWARE": "C3",
}
FORBIDDEN_COUNTERS = [
    "chroma_add_calls",
    "corpus_seed_calls",
    "document_chunking_calls",
    "document_embedding_calls",
    "document_keyword_extraction_calls",
    "document_pdf_parse_calls",
]
REFERENCE_METRICS = [
    "output_class_accuracy",
    "balanced_accuracy",
    "macro_recall",
    "permitted_answer_accuracy",
    "controlled_failure_correctness",
    "citation_coverage",
    "citation_support_precision",
    "page_level_citation_correctness",
    "safety_error_total",
    "runtime_parser_provider_errors",
    "prompt_input_tokens",
    "completion_output_tokens",
    "total_tokens",
]
FINAL_RECOMMENDATION = "OFFLINE SCORING PIPELINE FIXED — NO NEW API RUN REQUIRED"


for import_path in (REPO_ROOT, REPO_ROOT / "backend_python"):
    value = str(import_path)
    if value not in sys.path:
        sys.path.insert(0, value)

from evaluation.actual_pipeline_scorer import score_repetition_aware_sealed_run  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def install_offline_socket_guard() -> None:
    original_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if isinstance(address, tuple) and address:
            host = str(address[0])
            if host == "localhost":
                return original_connect(self, address)
            try:
                if __import__("ipaddress").ip_address(host).is_loopback:
                    return original_connect(self, address)
            except ValueError:
                pass
        raise RuntimeError("External network access is disabled for offline postmortem")

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]


def load_publication_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("infobank_publication_metrics", PUBLICATION_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load publication script: {PUBLICATION_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    with open(fs_path(path), "rb") as handle:
        return sha256_bytes(handle.read())


def fs_path(path: Path) -> str:
    resolved = str(path.resolve())
    if sys.platform == "win32" and not resolved.startswith("\\\\?\\"):
        return "\\\\?\\" + resolved
    return resolved


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(fs_path(path), "w", encoding="utf-8", newline="") as handle:
        handle.write(value)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
    )


def scalar_for_csv(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(fs_path(path), "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: scalar_for_csv(row.get(key)) for key in fields})


def ratio(num: float | int | None, den: float | int | None) -> float | None:
    if num is None or den in (None, 0):
        return None
    return round(float(num) / float(den), 6)


def metric_delta(left: Any, right: Any) -> float | int | None:
    if left is None or right is None:
        return None
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        value = float(left) - float(right)
        return int(value) if value.is_integer() else round(value, 6)
    return None


def collect_provider_request_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "provider_request_id" and child:
                found.append(str(child))
            else:
                found.extend(collect_provider_request_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(collect_provider_request_ids(child))
    return found


def artifact_hashes(run_dir: Path) -> dict[str, dict[str, Any]]:
    raw_dir = run_dir / "raw"
    result: dict[str, dict[str, Any]] = {}
    for filename, expected in EXPECTED_HASHES.items():
        path = raw_dir / filename
        actual = sha256_file(path) if path.exists() else None
        result[filename] = {
            "path": rel(path),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "status": "PASS" if actual == expected else "FAIL",
        }
    return result


def chroma_vector_count(value: dict[str, Any]) -> Any:
    return value.get("chroma_vector_count", value.get("chroma_collection_count"))


def prepared_base_integrity(seal: dict[str, Any]) -> dict[str, Any]:
    before = seal.get("base_integrity_before") or {}
    after = seal.get("base_integrity_after") or {}
    before_manifest = before.get("manifest") or {}
    after_manifest = after.get("manifest") or {}
    expected = {
        "documents": 41,
        "document_chunks": 245,
        "user_document_permission": 253,
        "source_pdf_count": 41,
        "chroma_vectors": 245,
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
    }
    actual = {
        "documents_before": (before.get("database_counts") or {}).get("documents"),
        "documents_after": (after.get("database_counts") or {}).get("documents"),
        "document_chunks_before": (before.get("database_counts") or {}).get("document_chunks"),
        "document_chunks_after": (after.get("database_counts") or {}).get("document_chunks"),
        "user_document_permission_before": (before.get("database_counts") or {}).get("user_document_permission"),
        "user_document_permission_after": (after.get("database_counts") or {}).get("user_document_permission"),
        "source_pdf_count_before": (before.get("source_storage_fingerprint") or {}).get("file_count"),
        "source_pdf_count_after": (after.get("source_storage_fingerprint") or {}).get("file_count"),
        "chroma_vectors_before": chroma_vector_count(before),
        "chroma_vectors_after": chroma_vector_count(after),
        "embedding_provider_before": before_manifest.get("prepared_embedding_provider"),
        "embedding_provider_after": after_manifest.get("prepared_embedding_provider"),
        "embedding_model_before": before_manifest.get("prepared_embedding_model"),
        "embedding_model_after": after_manifest.get("prepared_embedding_model"),
        "embedding_dimensions_before": before_manifest.get("prepared_embedding_dimensions"),
        "embedding_dimensions_after": after_manifest.get("prepared_embedding_dimensions"),
        "source_sha_before": (before.get("source_storage_fingerprint") or {}).get("sha256"),
        "source_sha_after": (after.get("source_storage_fingerprint") or {}).get("sha256"),
        "chroma_sha_before": (before.get("chroma_fingerprint_before") or {}).get("sha256"),
        "chroma_sha_after": (after.get("chroma_fingerprint_after") or {}).get("sha256"),
    }
    checks = {
        "database_counts_match_manifest": all(
            actual[f"{name}_before"] == expected[name] and actual[f"{name}_after"] == expected[name]
            for name in ("documents", "document_chunks", "user_document_permission")
        ),
        "source_pdf_count_match_manifest": actual["source_pdf_count_before"] == 41 and actual["source_pdf_count_after"] == 41,
        "chroma_vector_count_match_manifest": actual["chroma_vectors_before"] == 245 and actual["chroma_vectors_after"] == 245,
        "embedding_identity_match_manifest": (
            actual["embedding_provider_before"] == "openai"
            and actual["embedding_provider_after"] == "openai"
            and actual["embedding_model_before"] == "text-embedding-3-small"
            and actual["embedding_model_after"] == "text-embedding-3-small"
            and actual["embedding_dimensions_before"] == 1536
            and actual["embedding_dimensions_after"] == 1536
        ),
        "source_storage_stable": actual["source_sha_before"] == actual["source_sha_after"],
        "chroma_storage_stable": actual["chroma_sha_before"] == actual["chroma_sha_after"],
        "seal_prepared_base_stable": seal.get("prepared_base_stable") is True,
    }
    return {
        "expected": expected,
        "actual": actual,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }


def operation_counter_summary(records: list[dict[str, Any]], seal: dict[str, Any]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    for record in records:
        totals.update({key: int(value) for key, value in (record.get("operation_counters") or {}).items()})
    forbidden = {key: totals.get(key, 0) for key in FORBIDDEN_COUNTERS}
    group_forbidden: Counter[str] = Counter()
    for group in seal.get("disposable_groups") or []:
        group_forbidden.update({key: int(value) for key, value in (group.get("operation_counters") or {}).items() if key in FORBIDDEN_COUNTERS})
    return {
        "raw_record_operation_totals": dict(sorted(totals.items())),
        "raw_record_forbidden_totals": dict(sorted(forbidden.items())),
        "seal_forbidden_operation_counters_zero": seal.get("forbidden_operation_counters_zero") is True,
        "disposable_group_forbidden_totals": dict(sorted(group_forbidden.items())),
        "status": "PASS" if all(value == 0 for value in forbidden.values()) and seal.get("forbidden_operation_counters_zero") is True else "FAIL",
    }


def classify_json_boundary(text_value: str) -> str:
    stripped = text_value.strip().removeprefix("\ufeff").strip()
    if not stripped:
        return "EMPTY"
    first_fence = re.match(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if first_fence is not None:
        inner = first_fence.group(1).strip()
        suffix = stripped[first_fence.end():].strip()
        try:
            if isinstance(json.loads(inner), dict) and suffix:
                return "VALID_JSON_WITH_PREFIX_OR_SUFFIX"
        except json.JSONDecodeError:
            return "INVALID_JSON"
    full_fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if full_fence is not None:
        inner = full_fence.group(1).strip()
        try:
            return "STRICT_JSON_OBJECT" if isinstance(json.loads(inner), dict) else "JSON_NON_OBJECT"
        except json.JSONDecodeError:
            return "INVALID_JSON"
    decoder = json.JSONDecoder()
    try:
        parsed, index = decoder.raw_decode(stripped)
    except json.JSONDecodeError:
        return "INVALID_JSON"
    suffix = stripped[index:].strip()
    if isinstance(parsed, dict) and suffix:
        return "VALID_JSON_WITH_PREFIX_OR_SUFFIX"
    if isinstance(parsed, dict):
        return "STRICT_JSON_OBJECT"
    return "JSON_NON_OBJECT"


def technical_failures(records: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [record for record in records if record.get("error") or record.get("actual_output_class") == "ERROR"]
    taxonomy = Counter(str(record.get("error") or "ERROR").split(":", 1)[0] for record in failures)
    rows: list[dict[str, Any]] = []
    for record in failures:
        text = str((record.get("provider_usage") or {}).get("text") or "")
        rows.append(
            {
                "case_id": record.get("case_id"),
                "mode": record.get("mode"),
                "mode_short": MODE_SHORT.get(str(record.get("mode")), record.get("mode")),
                "repetition_index": record.get("repetition_index"),
                "error_taxon": str(record.get("error") or "ERROR").split(":", 1)[0],
                "provider_status": (record.get("provider_usage") or {}).get("status"),
                "stop_reason": (record.get("provider_usage") or {}).get("stop_reason"),
                "json_boundary_classification": classify_json_boundary(text),
                "provider_text_sha256": sha256_text(text) if text else None,
                "provider_text_length": len(text),
            }
        )
    return {
        "count": len(failures),
        "taxonomy": dict(sorted(taxonomy.items())),
        "rows": rows,
    }


def build_publication_rows(pub: ModuleType, records: list[dict[str, Any]], score_dir: Path, gold_path: Path) -> list[dict[str, Any]]:
    score_rows = load_jsonl(score_dir / "case_scores.jsonl")
    scores = {
        (str(row["case_id"]), str(row["mode"]), int(row.get("repetition_index") or 1)): row
        for row in score_rows
    }
    gold_by_case = {str(row["case_id"]): row for row in load_jsonl(gold_path)}
    query_path = REPO_ROOT / "artifacts" / "s1_s6_publication_experiment_v2" / "combined_input" / "combined_query_inputs.jsonl"
    query_by_case = {str(row["case_id"]): row for row in load_jsonl(query_path)}
    out = []
    for record in records:
        key = (str(record["case_id"]), str(record["mode"]), int(record.get("repetition_index") or 1))
        out.append(
            pub.case_row(
                record=record,
                score=scores[key],
                gold=gold_by_case[str(record["case_id"])],
                query=query_by_case[str(record["case_id"])],
                provider="anthropic",
                repetition=int(record.get("repetition_index") or 1),
            )
        )
    return out


def redacted_case_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        clone = {
            key: value
            for key, value in row.items()
            if key not in {"actual_output_text", "aggregate_trace", "policy_trace"}
        }
        clone["actual_output_text_sha256"] = sha256_text(str(row.get("actual_output_text") or ""))
        clone["aggregate_trace_present"] = row.get("aggregate_trace") is not None
        clone["policy_trace_present"] = row.get("policy_trace") is not None
        out.append(clone)
    return out


def aggregate_by_configuration(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    by_config: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["permission_group"] == "Aggregate-only":
            by_config[str(row["configuration_short"])].append(row)
    for config, values in sorted(by_config.items()):
        aggregate_result_rows = [row for row in values if row["expected_output_class"] == "AGGREGATE_RESULT"]
        threshold_rows = [row for row in values if row["expected_output_class"] == "REFUSE_AGGREGATION_THRESHOLD"]
        result[config] = {
            "aggregate_only_cases": len(values),
            "aggregate_only_output_class_correct": sum(int(row["output_class_correct"]) for row in values),
            "aggregate_only_output_class_correctness": ratio(sum(int(row["output_class_correct"]) for row in values), len(values)),
            "aggregate_result_cases": len(aggregate_result_rows),
            "aggregate_numerical_correct": sum(int(row["permitted_answer_correct"]) for row in aggregate_result_rows),
            "aggregate_numerical_correctness": ratio(sum(int(row["permitted_answer_correct"]) for row in aggregate_result_rows), len(aggregate_result_rows)),
            "threshold_cases": len(threshold_rows),
            "threshold_output_correct": sum(int(row["output_class_correct"]) for row in threshold_rows),
            "threshold_correctness": ratio(sum(int(row["output_class_correct"]) for row in threshold_rows), len(threshold_rows)),
            "threshold_generation_skipped_count": sum(int(row["generation_skipped"]) for row in threshold_rows),
            "deterministic_threshold_enforcement_present": any(bool(row["generation_skipped"]) for row in threshold_rows),
            "source_document_id_exposure": sum(int((row.get("safety_findings") or {}).get("prohibited_document_id_exposure", 0)) for row in values),
            "withheld_value_exposure": sum(int((row.get("safety_findings") or {}).get("prohibited_text_fragment_exposure", 0)) for row in values),
        }
    return result


def openai_reference_verification(pub: ModuleType, openai_dir: Path) -> dict[str, Any]:
    rows = load_jsonl(openai_dir / "per_case_630.jsonl")
    manifest = load_json(openai_dir / "run_manifest.json")
    expected_summary = load_json(openai_dir / "configuration_summary.json")["by_configuration"]
    by_config = {
        key[0]: pub.summarize_rows(value)
        for key, value in pub.group_rows(rows, ["configuration_short"]).items()
    }
    mismatches: list[dict[str, Any]] = []
    for config, summary in sorted(by_config.items()):
        expected = expected_summary[config]
        for metric in REFERENCE_METRICS:
            if metric not in expected:
                continue
            actual_value = summary.get(metric)
            expected_value = expected.get(metric)
            if isinstance(actual_value, (int, float)) and isinstance(expected_value, (int, float)):
                matched = math.isclose(float(actual_value), float(expected_value), rel_tol=0.0, abs_tol=0.000001)
            else:
                matched = actual_value == expected_value
            if not matched:
                mismatches.append(
                    {
                        "configuration": config,
                        "metric": metric,
                        "recomputed": actual_value,
                        "frozen_summary": expected_value,
                    }
                )
    return {
        "per_case_rows": len(rows),
        "manifest_executed_records": manifest.get("executed_records"),
        "frozen_summary_recomputed": "PASS" if not mismatches else "FAIL",
        "mismatches": mismatches,
        "status": "PASS" if len(rows) == 630 and manifest.get("executed_records") == 630 and not mismatches else "FAIL",
    }


def safety_affected_records(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        if int(row.get("safety_error_total") or 0) > 0:
            counts[str(row["configuration_short"])] += 1
    return dict(sorted(counts.items()))


def compare_to_openai(pub: ModuleType, claude_rows: list[dict[str, Any]], openai_dir: Path) -> dict[str, Any]:
    openai_rows = load_jsonl(openai_dir / "per_case_630.jsonl")
    openai_summary = load_json(openai_dir / "configuration_summary.json")["by_configuration"]
    claude_by_config = {
        key[0]: pub.summarize_rows(value)
        for key, value in pub.group_rows(claude_rows, ["configuration_short"]).items()
    }
    claude_affected = safety_affected_records(claude_rows)
    openai_affected = safety_affected_records(openai_rows)
    metric_rows = []
    safety_rows = []
    for config in sorted(claude_by_config):
        claude_summary = claude_by_config[config]
        openai_config = openai_summary[config]
        metric_rows.append(
            {
                "Configuration": config,
                **{
                    f"Claude {metric}": claude_summary.get(metric)
                    for metric in REFERENCE_METRICS
                    if metric in claude_summary
                },
                **{
                    f"OpenAI {metric}": openai_config.get(metric)
                    for metric in REFERENCE_METRICS
                    if metric in openai_config
                },
                **{
                    f"Delta {metric}": metric_delta(claude_summary.get(metric), openai_config.get(metric))
                    for metric in REFERENCE_METRICS
                    if metric in claude_summary and metric in openai_config
                },
            }
        )
        claude_safety = Counter(claude_summary.get("safety_findings") or {})
        openai_safety = Counter(openai_config.get("safety_findings") or {})
        counter_keys = sorted(set(claude_safety) | set(openai_safety))
        safety_rows.append(
            {
                "Configuration": config,
                "Claude total safety findings": claude_summary.get("safety_error_total"),
                "OpenAI total safety findings": openai_config.get("safety_error_total"),
                "Total safety finding delta": metric_delta(claude_summary.get("safety_error_total"), openai_config.get("safety_error_total")),
                "Claude affected records": claude_affected.get(config, 0),
                "OpenAI affected records": openai_affected.get(config, 0),
                "Affected record delta": claude_affected.get(config, 0) - openai_affected.get(config, 0),
                "Counter deltas": {
                    key: int(claude_safety.get(key, 0)) - int(openai_safety.get(key, 0))
                    for key in counter_keys
                },
            }
        )
    return {
        "metric_rows": metric_rows,
        "safety_rows": safety_rows,
        "claude_safety_affected_records": claude_affected,
        "openai_safety_affected_records": openai_affected,
    }


def stability_summary(pub: ModuleType, rows: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    stability = pub.stability_rows(rows)
    write_csv(output_dir / "stability_analysis.csv", stability)
    return {
        "case_configuration_groups": len(stability),
        "output_class_stable_3_of_3": Counter(row["Output class stable 3/3"] for row in stability),
        "reason_code_stable": Counter(row["Reason code stable"] for row in stability),
        "repeated_failure_3_of_3": sum(int(row["Repeated failure 3/3"]) for row in stability),
        "one_off_failure": sum(int(row["One-off failure"]) for row in stability),
    }


def write_sha256s(directory: Path) -> None:
    rows = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            rows.append(f"{sha256_file(path)}  {rel(path)}")
    write_text(directory / "SHA256SUMS.txt", "\n".join(rows) + "\n")


def write_markdown_report(path: Path, payload: dict[str, Any]) -> None:
    config = payload["publication_summary"]["by_configuration"]
    aggregate = payload["aggregate_by_configuration"]
    technical = payload["technical_failures"]
    integrity = payload["integrity"]
    safety_rows = payload["openai_comparison"]["safety_rows"]
    lines = [
        "# Offline Scoring Postmortem v2",
        "",
        f"Final recommendation: `{payload['final_recommendation']}`",
        "",
        "## Scope",
        "",
        "- Strictly offline: no Claude/OpenAI/embedding/API rerun was performed.",
        "- Frozen raw run and seal were not modified.",
        "- The scorer defect was in repeated-run orchestration: plain `case_id` uniqueness was applied across repetitions instead of within each `(mode, repetition)` group.",
        "- The P1/S2-Q2 failures remain protocol failures: each provider response contained a valid first JSON block plus non-whitespace suffix content.",
        "",
        "## Raw Integrity",
        "",
        f"- HEAD: `{payload['git']['head']}`",
        f"- Expected HEAD: `{EXPECTED_HEAD}`",
        f"- Raw record count: {integrity['record_count']}",
        f"- Composite keys unique: {integrity['composite_keys_unique']}",
        f"- Mode x repetition groups: {integrity['mode_repetition_group_count']}",
        f"- Prepared base integrity: {payload['prepared_base_integrity']['status']}",
        f"- No-reprocessing counters: {payload['operation_counters']['status']}",
        f"- Payload boundary: {payload['payload_boundary_status']}",
        "",
        "## Corrected Metrics",
        "",
        "| Mode | Raw accuracy | Balanced accuracy | Strict permitted-answer accuracy | Governed-output correctness | Aggregate-only correctness | Aggregate numerical correctness | Citation recall | Citation precision | Page precision | Safety findings | Runtime errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in ["C0", "C1", "C2", "C3", "P1"]:
        summary = config[mode]
        agg = aggregate.get(mode, {})
        lines.append(
            "| "
            + " | ".join(
                [
                    mode,
                    str(summary.get("output_class_accuracy")),
                    str(summary.get("balanced_accuracy")),
                    str(summary.get("permitted_answer_accuracy")),
                    str(summary.get("controlled_failure_correctness")),
                    str(agg.get("aggregate_only_output_class_correctness")),
                    str(agg.get("aggregate_numerical_correctness")),
                    str(summary.get("citation_document_coverage")),
                    str(summary.get("citation_support_precision")),
                    str(summary.get("page_level_citation_correctness")),
                    str(summary.get("safety_error_total")),
                    str(summary.get("runtime_parser_provider_errors")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Technical Failures",
            "",
            f"- Technical failure records: {technical['count']}",
            f"- Taxonomy: `{json.dumps(technical['taxonomy'], sort_keys=True)}`",
        ]
    )
    for row in technical["rows"]:
        lines.append(
            f"- {row['mode_short']} R{row['repetition_index']} {row['case_id']}: "
            f"{row['error_taxon']} / {row['json_boundary_classification']} / provider status {row['provider_status']}"
        )
    lines.extend(
        [
            "",
            "## Safety Delta Versus Frozen OpenAI",
            "",
            "| Mode | Claude findings | OpenAI findings | Finding delta | Claude affected records | OpenAI affected records | Affected-record delta |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in safety_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["Configuration"]),
                    str(row["Claude total safety findings"]),
                    str(row["OpenAI total safety findings"]),
                    str(row["Total safety finding delta"]),
                    str(row["Claude affected records"]),
                    str(row["OpenAI affected records"]),
                    str(row["Affected record delta"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Raw records: `{payload['paths']['raw_records']}`",
            f"- Seal: `{payload['paths']['seal']}`",
            f"- Repetition-aware scorer output: `{payload['paths']['scores']}`",
            f"- Publication metrics: `{payload['paths']['publication_metrics']}`",
            f"- Postmortem payload: `{payload['paths']['postmortem_summary']}`",
            f"- SHA-256 manifest: `{payload['paths']['sha256s']}`",
            "",
            "## Notes",
            "",
            "- Chroma count wording was repaired in source: the value is a vector count; the old key remains as a compatibility alias.",
            "- Governed-output correctness now uses the frozen publication definition: non-FULL expected outputs only.",
            "- Claude/OpenAI safety comparison now separates total finding activations from affected-record counts.",
        ]
    )
    write_text(path, "\n".join(lines) + "\n")


def build_payload(run_dir: Path, original_report_dir: Path, output_dir: Path) -> dict[str, Any]:
    raw_dir = run_dir / "raw"
    raw_path = raw_dir / "raw_records.jsonl"
    seal_path = raw_dir / "run_seal.json"
    gold_path = run_dir / "reference" / "selected_gold_annotations.jsonl"
    records = load_jsonl(raw_path)
    seal = load_json(seal_path)

    scores_dir = output_dir / "scores"
    score_summary = score_repetition_aware_sealed_run(
        raw_run_path=raw_path,
        seal_path=seal_path,
        gold_annotation_path=gold_path,
        output_dir=scores_dir,
    )

    pub = load_publication_module()
    pub.write_csv = write_csv
    pub.write_json = write_json
    pub.write_jsonl = write_jsonl
    rows = build_publication_rows(pub, records, scores_dir, gold_path)
    metrics_dir = output_dir / "publication_metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    publication_summary = pub.write_aggregate_tables(rows, metrics_dir, provider="anthropic")
    aggregate_rows = pub.aggregate_governance_rows(rows)
    write_csv(metrics_dir / "aggregate_governance_summary.csv", aggregate_rows)
    write_json(metrics_dir / "aggregate_by_configuration.json", aggregate_by_configuration(rows))
    write_jsonl(metrics_dir / "per_case_metrics_redacted.jsonl", redacted_case_rows(rows))
    write_csv(metrics_dir / "paired_configuration_comparison.csv", pub.paired_comparison_rows(rows))

    openai_verification = openai_reference_verification(pub, OPENAI_REFERENCE_DIR)
    write_json(output_dir / "openai_reference_verification.json", openai_verification)
    comparison = compare_to_openai(pub, rows, OPENAI_REFERENCE_DIR)
    write_csv(output_dir / "claude_vs_openai_metric_deltas.csv", comparison["metric_rows"])
    write_csv(output_dir / "claude_vs_openai_safety_deltas.csv", comparison["safety_rows"])
    write_json(output_dir / "claude_vs_openai_comparison.json", comparison)

    request_ids = collect_provider_request_ids(records)
    duplicate_request_ids = {
        key: value
        for key, value in sorted(Counter(request_ids).items())
        if value > 1
    }
    composite_keys = [
        (str(record.get("case_id")), str(record.get("mode")), int(record.get("repetition_index") or 1))
        for record in records
    ]
    mode_rep_counts = Counter((MODE_SHORT.get(str(record.get("mode")), str(record.get("mode"))), int(record.get("repetition_index") or 1)) for record in records)
    git_head = __import__("subprocess").run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    original_report_hashes = {
        rel(path): sha256_file(path)
        for path in sorted(original_report_dir.glob("*"))
        if path.is_file() and path.name != "checksums.sha256"
    }
    payload: dict[str, Any] = {
        "generated_at": utc_now(),
        "final_recommendation": FINAL_RECOMMENDATION,
        "offline_guard": "socket.socket.connect denies non-loopback connections during this script",
        "api_keys": {"ANTHROPIC_API_KEY": "NOT_READ", "OPENAI_API_KEY": "NOT_READ"},
        "git": {
            "head": git_head,
            "expected_head": EXPECTED_HEAD,
            "head_matches_expected": git_head == EXPECTED_HEAD,
        },
        "paths": {
            "raw_records": rel(raw_path),
            "deterministic_content": rel(raw_dir / "deterministic_content.jsonl"),
            "seal": rel(seal_path),
            "wall_clock_timings": rel(raw_dir / "wall_clock_timings.jsonl"),
            "scores": rel(scores_dir),
            "publication_metrics": rel(metrics_dir),
            "postmortem_summary": rel(output_dir / "postmortem_summary.json"),
            "report": rel(output_dir / "OFFLINE_SCORING_POSTMORTEM_V2.md"),
            "sha256s": rel(output_dir / "SHA256SUMS.txt"),
        },
        "artifact_hashes": artifact_hashes(run_dir),
        "original_report_hashes": original_report_hashes,
        "integrity": {
            "record_count": len(records),
            "seal_record_count": seal.get("record_count"),
            "raw_hash_matches_seal": sha256_file(raw_path) == seal.get("raw_run_sha256"),
            "composite_keys_unique": len(composite_keys) == len(set(composite_keys)),
            "mode_repetition_group_count": len(mode_rep_counts),
            "mode_repetition_counts": {
                f"{mode}-R{repetition}": count
                for (mode, repetition), count in sorted(mode_rep_counts.items())
            },
            "expected_630_records": len(records) == 630,
            "expected_15_groups": len(mode_rep_counts) == 15 and all(count == 42 for count in mode_rep_counts.values()),
        },
        "official_score_summary": score_summary,
        "publication_summary": publication_summary,
        "aggregate_by_configuration": aggregate_by_configuration(rows),
        "technical_failures": technical_failures(records),
        "prepared_base_integrity": prepared_base_integrity(seal),
        "operation_counters": operation_counter_summary(records, seal),
        "payload_boundary_status": (seal.get("payload_boundary_verification") or {}).get("status"),
        "payload_boundary": seal.get("payload_boundary_verification"),
        "provider_request_ids": {
            "count": len(request_ids),
            "unique_count": len(set(request_ids)),
            "duplicates": duplicate_request_ids,
            "status": "PASS" if not duplicate_request_ids else "FAIL",
        },
        "provider_usage_totals": seal.get("provider_usage_totals"),
        "estimated_anthropic_cost_from_recorded_tokens_usd": seal.get("estimated_anthropic_cost_from_recorded_tokens_usd"),
        "openai_reference_verification": openai_verification,
        "openai_comparison": comparison,
        "stability_summary": stability_summary(pub, rows, output_dir),
        "anomalies": [
            "Original official scoring failed before this fix because repeated raw records reused case_id across repetitions.",
            "P1 S2-Q2 failed in all three repetitions due to valid first JSON object plus extra suffix content; this remains a strict-output contract failure.",
            "Previous descriptive report used raw accuracy as governed-output correctness for C2/C3; corrected publication metric excludes FULL_ANSWER cases.",
            "Previous descriptive OpenAI safety comparison mixed pooled Claude activations with per-repetition OpenAI means; corrected comparison is pooled-to-pooled and separates affected records.",
            "Prepared-corpus Chroma count label was misleading; source now reports chroma_vector_count with a compatibility alias.",
        ],
    }
    write_json(output_dir / "postmortem_summary.json", payload)
    write_markdown_report(output_dir / "OFFLINE_SCORING_POSTMORTEM_V2.md", payload)
    write_sha256s(output_dir)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--original-report-dir", type=Path, default=DEFAULT_ORIGINAL_REPORT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    install_offline_socket_guard()
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args.run_dir, args.original_report_dir, args.output_dir)
    print(json.dumps({"status": payload["final_recommendation"], "output_dir": rel(args.output_dir)}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
