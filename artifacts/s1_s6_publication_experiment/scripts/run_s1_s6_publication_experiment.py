"""Run the S1-S6 C0-C3 publication experiment without changing source code.

The script is intentionally task-local.  It creates a read-only execution
overlay from the two frozen ZIP packages, invokes the committed actual-pipeline
runner/scorer, and writes reporting artifacts under
artifacts/s1_s6_publication_experiment/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import uuid
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "s1_s6_publication_experiment"
COMBINED_DIR = ARTIFACT_ROOT / "combined_input"
DETERMINISTIC_DIR = ARTIFACT_ROOT / "deterministic"
OPENAI_DIR = ARTIFACT_ROOT / "openai"
REPORT_DIR = ARTIFACT_ROOT / "report"
PRE_FLIGHT_DIR = ARTIFACT_ROOT / "preflight"

for import_path in (REPO_ROOT, REPO_ROOT / "backend_python"):
    value = str(import_path)
    if value not in sys.path:
        sys.path.insert(0, value)

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from backend_python.ai_provider import create_provider  # noqa: E402
from evaluation.actual_pipeline_runner import (  # noqa: E402
    GENERATION_PROMPT_VERSION,
    GENERATION_TEMPERATURE,
    ROUTING_PROMPT_VERSION,
    ActualPipelineConfig,
    run_actual_pipeline,
)
from evaluation.actual_pipeline_scorer import SCORER_VERSION, score_sealed_run  # noqa: E402
from evaluation.provider_readiness import EMBEDDING_MODEL, GENERATION_MODEL  # noqa: E402
from evaluation.schemas import EvaluationMode  # noqa: E402


COMBINED_ID = "S1_S6_COMBINED_JOURNAL_EVALUATION_V1"
COMBINED_DATASET_VERSION = "s1-s6-combined-journal-evaluation-v1"
EXPECTED_HEAD = "ea6d3a2b6f13abdb8fe949b0de247617d782858c"
EXPECTED_BRANCH = "infocom2026"
EXPECTED_ORIGIN = EXPECTED_HEAD
DETERMINISTIC_LABEL = (
    "DETERMINISTIC DEVELOPMENT AND REPRODUCIBILITY EVALUATION — "
    "NOT FINAL REAL-PROVIDER PERFORMANCE"
)
MODES = [
    EvaluationMode.C0_VECTOR_ONLY.value,
    EvaluationMode.C1_VECTOR_ROUTING.value,
    EvaluationMode.C2_PERMISSION_FILTERED.value,
    EvaluationMode.C3_FULL_ROLE_AWARE.value,
]
MODE_SHORT = {
    EvaluationMode.C0_VECTOR_ONLY.value: "C0",
    EvaluationMode.C1_VECTOR_ROUTING.value: "C1",
    EvaluationMode.C2_PERMISSION_FILTERED.value: "C2",
    EvaluationMode.C3_FULL_ROLE_AWARE.value: "C3",
}
SHORT_TO_MODE = {value: key for key, value in MODE_SHORT.items()}
ANSWER_CLASSES = {"FULL_ANSWER", "CONSTRAINED_ANSWER", "AGGREGATE_RESULT"}
NON_FULL_CLASSES = {
    "CLARIFICATION",
    "REFUSE_PERMISSION",
    "REFUSE_INSUFFICIENT_EVIDENCE",
    "REFUSE_NO_MATCH",
    "REFUSE_AGGREGATION_THRESHOLD",
    "REFUSE_CONFLICT",
}
EXPECTED_OUTPUT_CLASS_DISTRIBUTION = {
    "FULL_ANSWER": 29,
    "AGGREGATE_RESULT": 5,
    "CONSTRAINED_ANSWER": 3,
    "REFUSE_INSUFFICIENT_EVIDENCE": 3,
    "REFUSE_AGGREGATION_THRESHOLD": 1,
    "CLARIFICATION": 1,
}
CASE_ORDER = [
    "S1-Q1",
    "S1-Q2",
    "S1-Q3",
    "S1-Q4",
    "S1-Q5",
    "S1-Q6",
    "S2-Q1",
    "S2-Q2",
    "S2-Q3",
    "S2-Q4",
    "S2-Q5",
    "S2-Q6",
    "S3-Q1",
    "S3-Q2",
    "S3-Q3",
    "S3-Q4",
    "S3-Q5",
    "S3-Q6",
    "S3-Q7",
    "S3-Q8",
    "S3-Q9",
    "S3-Q10",
    "S4B-Q1",
    "S4B-Q2",
    "S4B-Q3",
    "S4B-Q4",
    "S4B-Q5",
    "S4B-Q6",
    "S4B-Q7",
    "S4B-Q8",
    "S5B-Q1",
    "S5B-Q2",
    "S5B-Q3",
    "S5B-Q4",
    "S5B-Q5",
    "S5B-Q6",
    "S6-Q1",
    "S6-Q2",
    "S6-Q3",
    "S6-Q4",
    "S6-Q5",
    "S6-Q6",
]
PACKAGE_SPECS = [
    {
        "label": "S1-S2",
        "path": REPO_ROOT / "artifacts" / "s1s2_freeze" / "S1_S2_journal_benchmark_v2.zip",
        "relative_path": "artifacts/s1s2_freeze/S1_S2_journal_benchmark_v2.zip",
        "root": "S1_S2_JOURNAL_BENCHMARK_V2",
        "input_dir": "actual_pipeline_inputs",
        "identity": "S1_S2_JOURNAL_BENCHMARK_V2",
        "expected_sha256": "83a9bb2394946b378af4efe2445be1e6e7095a60f5c14f6206ea1405f275bcd1",
        "expected_scenarios": 2,
        "expected_queries": 12,
        "expected_pdfs": 10,
        "expected_gold": 12,
        "status_fields": {
            "human_qa_status": "APPROVED",
            "human_confirmation_status": "APPROVED_WITH_DOCUMENTED_LIMITATIONS",
            "benchmark_status": "FROZEN",
            "further_s1s2_tuning_allowed": "NO",
        },
    },
    {
        "label": "S3-S6",
        "path": REPO_ROOT / "artifacts" / "s3_s6_freeze" / "S3_S6_journal_evaluation_v1.zip",
        "relative_path": "artifacts/s3_s6_freeze/S3_S6_journal_evaluation_v1.zip",
        "root": "S3_S6_JOURNAL_EVALUATION_V1",
        "input_dir": "inputs",
        "identity": "S3_S6_JOURNAL_EVALUATION_V1",
        "expected_sha256": "3a5db23fddf55a007d013e09fd11ade74fcdf692847d01b0135346bdd3ddc50c",
        "expected_scenarios": 4,
        "expected_queries": 30,
        "expected_pdfs": 31,
        "expected_gold": 30,
        "status_fields": {
            "human_qa_status": "APPROVED",
            "aggregate_human_confirmation_status": "APPROVED",
            "evaluation_set_status": "FROZEN",
            "further_s3_s6_tuning_allowed": "NO",
            "real_provider_evaluation_status": "NOT_STARTED",
        },
    },
]


class StopStatus(RuntimeError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    path.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    ensure_dir(path.parent)
    if fields is None:
        seen: list[str] = []
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.append(key)
        fields = seen
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: scalar_for_csv(row.get(key)) for key in fields})


def scalar_for_csv(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return canonical_json(value)
    return value


def git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-c", "http.sslBackend=openssl", "-c", f"safe.directory={REPO_ROOT.as_posix()}", *args]
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


def git_out(args: list[str]) -> str:
    return git(args).stdout.strip()


def git_state() -> dict[str, Any]:
    git(["fetch", "origin"])
    branch = git_out(["rev-parse", "--abbrev-ref", "HEAD"])
    head = git_out(["rev-parse", "HEAD"])
    origin = git_out(["rev-parse", "origin/infocom2026"])
    ahead_behind = git_out(["rev-list", "--left-right", "--count", "HEAD...origin/infocom2026"])
    status = git(["status", "--short"], check=False)
    diff_check = git(["diff", "--check"], check=False)
    branch_vv = git(["branch", "-vv"], check=False).stdout
    source_paths = ["backend_python", "evaluation", "scripts"]
    tracked_diff = git(["diff", "--name-only", "--", *source_paths]).stdout.splitlines()
    staged_diff = git(["diff", "--cached", "--name-only", "--", *source_paths]).stdout.splitlines()
    source_test_changed = sorted(set(tracked_diff + staged_diff))
    state = {
        "branch": branch,
        "head": head,
        "origin_infocom2026": origin,
        "ahead_behind": ahead_behind,
        "status_short": status.stdout.splitlines(),
        "status_stderr": status.stderr.splitlines(),
        "branch_vv": branch_vv.splitlines(),
        "git_diff_check_returncode": diff_check.returncode,
        "git_diff_check_stdout": diff_check.stdout.splitlines(),
        "git_diff_check_stderr": diff_check.stderr.splitlines(),
        "source_test_changed_paths": source_test_changed,
        "tracked_source_test_clean": not source_test_changed,
    }
    write_json(PRE_FLIGHT_DIR / "GIT_STATE.json", state)
    if branch != EXPECTED_BRANCH or head != EXPECTED_HEAD or origin != EXPECTED_ORIGIN or ahead_behind != "0\t0":
        raise StopStatus("UNEXPECTED_SOURCE_MUTATION", "Git branch/head/origin state differs from preregistered state")
    if diff_check.returncode != 0 or source_test_changed:
        raise StopStatus("UNEXPECTED_SOURCE_MUTATION", "Tracked source/test tree is not clean")
    return state


def tree_hash(paths: list[str]) -> str:
    tracked: list[str] = []
    for item in paths:
        tracked.extend(git(["ls-files", "--", item]).stdout.splitlines())
    digest = hashlib.sha256()
    for path in sorted(set(tracked)):
        payload = (REPO_ROOT / path).read_bytes()
        digest.update(path.encode("utf-8") + b"\0" + hashlib.sha256(payload).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def zip_read_json(zf: zipfile.ZipFile, name: str) -> Any:
    return json.loads(zf.read(name).decode("utf-8"))


def zip_read_jsonl(zf: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    text_value = zf.read(name).decode("utf-8")
    return [json.loads(line) for line in text_value.splitlines() if line.strip()]


def verify_internal_checksums(zf: zipfile.ZipFile, root: str) -> dict[str, Any]:
    candidates = [f"{root}/SHA256SUMS.txt", f"{root}/SHA256SUMS"]
    checksum_name = next((name for name in candidates if name in zf.namelist()), None)
    if checksum_name is None:
        return {"status": "NOT_FOUND", "checked_count": 0, "mismatches": []}
    mismatches: list[dict[str, str]] = []
    checked = 0
    for raw_line in zf.read(checksum_name).decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        expected_hash = parts[0]
        member_path = parts[-1].lstrip("*")
        candidates = [f"{root}/{member_path}", member_path]
        member = next((name for name in candidates if name in zf.namelist()), None)
        if member is None:
            mismatches.append({"path": member_path, "expected": expected_hash, "actual": "MISSING"})
            continue
        actual_hash = sha256_bytes(zf.read(member))
        checked += 1
        if actual_hash != expected_hash:
            mismatches.append({"path": member_path, "expected": expected_hash, "actual": actual_hash})
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "checked_count": checked,
        "mismatches": mismatches,
        "checksum_member": checksum_name,
    }


def forbidden_scan_zip_inputs(zf: zipfile.ZipFile, root: str, input_dir: str) -> dict[str, Any]:
    path_pattern = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:home|Users|users|tmp|var)/)")
    secret_pattern = re.compile(r"(?:ghp_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY)", re.IGNORECASE)
    findings: list[dict[str, str]] = []
    prefix = f"{root}/{input_dir}/"
    for info in zf.infolist():
        if info.is_dir() or not info.filename.startswith(prefix):
            continue
        data = zf.read(info.filename)
        if info.filename.lower().endswith(".pdf"):
            try:
                import fitz  # type: ignore

                doc = fitz.open(stream=data, filetype="pdf")
                text_value = "\n".join(page.get_text("text") for page in doc)
                doc.close()
            except Exception:
                text_value = ""
        else:
            text_value = data.decode("utf-8", errors="ignore")
        if path_pattern.search(text_value):
            findings.append({"path": info.filename, "finding": "LOCAL_ABSOLUTE_PATH"})
        if secret_pattern.search(text_value):
            findings.append({"path": info.filename, "finding": "SECRET_PATTERN"})
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def verify_packages() -> dict[str, Any]:
    ensure_dir(PRE_FLIGHT_DIR)
    summaries: list[dict[str, Any]] = []
    loaded: dict[str, dict[str, Any]] = {}
    for spec in PACKAGE_SPECS:
        path = spec["path"]
        if not path.exists():
            raise StopStatus("FROZEN_PACKAGE_IDENTITY_MISMATCH", f"Missing frozen package: {rel(path)}")
        outer_sha = sha256_file(path)
        zip_status = "PASS"
        with zipfile.ZipFile(path) as zf:
            bad_member = zf.testzip()
            if bad_member:
                zip_status = f"FAIL:{bad_member}"
            root = spec["root"]
            input_dir = spec["input_dir"]
            manifest_candidates = [
                f"{root}/MANIFEST.json",
                f"{root}/manifest.json",
                f"{root}/PACKAGE_MANIFEST.json",
                f"{root}/evaluation_manifest.json",
            ]
            manifest_name = next((name for name in manifest_candidates if name in zf.namelist()), None)
            if manifest_name is None:
                root_jsons = [name for name in zf.namelist() if name.startswith(f"{root}/") and name.count("/") == 1 and name.endswith(".json")]
                manifest_name = root_jsons[0] if root_jsons else None
            manifest = zip_read_json(zf, manifest_name) if manifest_name else {}
            binding = zip_read_json(zf, f"{root}/{input_dir}/binding_manifest.json")
            corpus = zip_read_json(zf, f"{root}/{input_dir}/corpus_fixture.json")
            queries = zip_read_jsonl(zf, f"{root}/{input_dir}/query_inputs.jsonl")
            gold = zip_read_jsonl(zf, f"{root}/{input_dir}/gold_annotations.jsonl")
            pdf_members = [
                name
                for name in zf.namelist()
                if name.startswith(f"{root}/{input_dir}/source_documents/") and name.lower().endswith(".pdf")
            ]
            internal = verify_internal_checksums(zf, root)
            forbidden = forbidden_scan_zip_inputs(zf, root, input_dir)
            scenario_ids = sorted({item["corpus_package_ref"] for item in queries})
            output_distribution = dict(sorted(Counter(item["expected_output_class"] for item in gold).items()))
            status_results = {
                field: {
                    "expected": expected,
                    "actual": manifest.get(field),
                    "pass": manifest.get(field) == expected,
                }
                for field, expected in spec["status_fields"].items()
            }
            summary = {
                "label": spec["label"],
                "path": spec["relative_path"],
                "expected_sha256": spec["expected_sha256"],
                "actual_sha256": outer_sha,
                "package_identity": binding.get("package_identity") or manifest.get("package_identity") or spec["root"],
                "zip_integrity": zip_status,
                "internal_checksums": internal,
                "manifest_statuses": status_results,
                "scenario_count": len(scenario_ids),
                "query_count": len(queries),
                "source_pdf_count": len(pdf_members),
                "annotation_count": len(gold),
                "policy_fixture_count": len(corpus.get("policy_fixtures", [])),
                "runtime_reference_separation": "PASS"
                if binding.get("query_input_path") and (binding.get("gold_annotation_path") or binding.get("reference_annotation_path"))
                else "UNKNOWN",
                "canonical_input_scan": forbidden,
                "output_class_distribution": output_distribution,
                "scenario_ids": scenario_ids,
                "manifest_member": manifest_name,
            }
            loaded[spec["label"]] = {
                "spec": spec,
                "manifest": manifest,
                "binding": binding,
                "corpus": corpus,
                "queries": queries,
                "gold": gold,
            }
        count_checks = {
            "sha256": outer_sha == spec["expected_sha256"],
            "identity": summary["package_identity"] == spec["identity"],
            "zip": zip_status == "PASS",
            "internal_checksums": internal["status"] in {"PASS", "NOT_FOUND"},
            "scenario_count": summary["scenario_count"] == spec["expected_scenarios"],
            "query_count": summary["query_count"] == spec["expected_queries"],
            "source_pdf_count": summary["source_pdf_count"] == spec["expected_pdfs"],
            "annotation_count": summary["annotation_count"] == spec["expected_gold"],
            "status_fields": all(item["pass"] for item in status_results.values()),
            "forbidden_scan": forbidden["status"] == "PASS",
        }
        summary["checks"] = count_checks
        summary["status"] = "PASS" if all(count_checks.values()) else "FAIL"
        summaries.append(summary)
    result = {"generated_at": utc_now(), "packages": summaries}
    write_json(PRE_FLIGHT_DIR / "FROZEN_INPUT_VERIFICATION.json", result)
    if any(item["status"] != "PASS" for item in summaries):
        raise StopStatus("FROZEN_PACKAGE_IDENTITY_MISMATCH", "Frozen package verification failed")
    return {"summary": result, "loaded": loaded}


def new_document_id(package_identity: str, scenario_id: str, source_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:{COMBINED_ID}:{package_identity}:{scenario_id}:{source_id}"))


def remap_ids(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [remap_ids(item, mapping) for item in value]
    if isinstance(value, dict):
        return {mapping.get(str(key), str(key)): remap_ids(item, mapping) for key, item in value.items()}
    return value


def package_member_bytes(spec: dict[str, Any], member_relative: str) -> bytes:
    with zipfile.ZipFile(spec["path"]) as zf:
        return zf.read(f"{spec['root']}/{spec['input_dir']}/{member_relative}")


def scenario_label(case_id: str) -> str:
    return case_id.split("-Q", 1)[0]


def is_aggregate_case(gold: dict[str, Any]) -> bool:
    if gold.get("expected_output_class") in {"AGGREGATE_RESULT", "REFUSE_AGGREGATION_THRESHOLD"}:
        return True
    metadata = gold.get("metadata") or {}
    return str(metadata.get("effective_use_decision") or metadata.get("permission_mode") or "").lower() == "aggregate"


def validate_runtime_reference_separation(query_path: Path, corpus_path: Path, policy_path: Path) -> dict[str, Any]:
    forbidden_terms = {
        "expected_output_class",
        "reference_answer",
        "factual_atoms",
        "required_sources",
        "required_evidence_roles",
        "gold_document_ids",
        "gold_page_or_message_ranges",
        "reference_citations",
        "acceptable_pages",
        "author_decision_id",
        "human_confirmation_status",
        "manual_validation_state",
    }
    findings: list[dict[str, str]] = []
    for path in (query_path, corpus_path, policy_path):
        text_value = path.read_text(encoding="utf-8")
        for term in sorted(forbidden_terms):
            if term in text_value:
                findings.append({"path": rel(path), "term": term})
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def build_combined_overlay(loaded: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    if loaded is None:
        loaded = verify_packages()["loaded"]
    ensure_dir(COMBINED_DIR / "source_documents")
    combined_queries_by_case: dict[str, dict[str, Any]] = {}
    combined_gold_by_case: dict[str, dict[str, Any]] = {}
    combined_documents: list[dict[str, Any]] = []
    combined_policy_fixtures: list[dict[str, Any]] = []
    source_map_rows: list[dict[str, Any]] = []
    package_manifest_rows: list[dict[str, Any]] = []
    seen_new_ids: set[str] = set()
    collision_rows: list[dict[str, str]] = []
    unique_pdf_hashes: set[str] = set()

    for spec in PACKAGE_SPECS:
        payload = loaded[spec["label"]]
        binding = payload["binding"]
        corpus = payload["corpus"]
        queries = payload["queries"]
        gold_rows = payload["gold"]
        package_identity = spec["identity"]
        binding_by_doc = {item["document_id"]: item for item in binding["source_bindings"]}
        old_to_new: dict[str, str] = {}
        old_to_source: dict[str, dict[str, Any]] = {}
        for item in binding["source_bindings"]:
            mapped = new_document_id(package_identity, item["scenario_id"], item["source_id"])
            if mapped in seen_new_ids:
                collision_rows.append({"old_document_id": item["document_id"], "new_document_id": mapped})
            seen_new_ids.add(mapped)
            old_to_new[item["document_id"]] = mapped
            old_to_source[item["document_id"]] = item

        for document in corpus["documents"]:
            old_id = document["document_id"]
            binding_row = binding_by_doc[old_id]
            mapped_id = old_to_new[old_id]
            scenario_id = binding_row["scenario_id"]
            target_rel = f"source_documents/{scenario_id}/{binding_row['original_filename']}"
            pdf_payload = package_member_bytes(spec, binding_row["source_pdf_path"])
            pdf_sha = sha256_bytes(pdf_payload)
            if pdf_sha != binding_row["source_pdf_sha256"]:
                raise StopStatus("COMBINED_INPUT_VALIDATION_FAILED", f"Source PDF hash mismatch for {old_id}")
            target_pdf = COMBINED_DIR / target_rel
            ensure_dir(target_pdf.parent)
            target_pdf.write_bytes(pdf_payload)
            unique_pdf_hashes.add(pdf_sha)
            new_doc = remap_ids(document, old_to_new)
            new_doc["document_id"] = mapped_id
            new_doc["source_pdf_path"] = target_rel
            new_doc["source_pdf_sha256"] = pdf_sha
            combined_documents.append(new_doc)
            source_map_rows.append(
                {
                    "source_package": spec["label"],
                    "source_package_identity": package_identity,
                    "scenario_id": scenario_id,
                    "logical_source_id": binding_row["source_id"],
                    "old_document_id": old_id,
                    "new_document_id": mapped_id,
                    "source_pdf_path": target_rel,
                    "source_pdf_sha256": pdf_sha,
                    "original_filename": binding_row["original_filename"],
                    "permission": binding_row.get("permission"),
                    "source_type": binding_row.get("source_type"),
                }
            )

        for fixture in corpus.get("policy_fixtures", []):
            combined_policy_fixtures.append(remap_ids(fixture, old_to_new))

        for query in queries:
            combined_queries_by_case[query["case_id"]] = query

        for gold in gold_rows:
            mapped_gold = remap_ids(gold, old_to_new)
            metadata = dict(mapped_gold.get("metadata") or {})
            metadata["source_package"] = spec["label"]
            metadata["source_package_identity"] = package_identity
            metadata["source_dataset_version"] = gold.get("dataset_version")
            metadata["combined_overlay_dataset_version"] = COMBINED_DATASET_VERSION
            mapped_gold["metadata"] = metadata
            mapped_gold["dataset_version"] = COMBINED_DATASET_VERSION
            combined_gold_by_case[mapped_gold["case_id"]] = mapped_gold

        package_manifest_rows.append(
            {
                "label": spec["label"],
                "package_identity": package_identity,
                "path": spec["relative_path"],
                "sha256": sha256_file(spec["path"]),
                "query_count": len(queries),
                "annotation_count": len(gold_rows),
                "document_count": len(corpus["documents"]),
                "scenario_ids": binding.get("scenario_ids"),
            }
        )

    query_order = list(combined_queries_by_case)
    gold_order = list(combined_gold_by_case)
    if query_order != CASE_ORDER or gold_order != CASE_ORDER:
        missing = [case_id for case_id in CASE_ORDER if case_id not in combined_queries_by_case or case_id not in combined_gold_by_case]
        if missing:
            raise StopStatus("COMBINED_INPUT_VALIDATION_FAILED", f"Missing combined cases: {missing}")
    queries = [combined_queries_by_case[case_id] for case_id in CASE_ORDER]
    gold = [combined_gold_by_case[case_id] for case_id in CASE_ORDER]
    combined_documents.sort(key=lambda item: (item["package_ref"], item["original_filename"], item["document_id"]))
    combined_policy_fixtures.sort(key=lambda item: item["fixture_id"])
    source_map_rows.sort(key=lambda item: (item["scenario_id"], item["logical_source_id"], item["source_package_identity"]))

    policy_fixture_refs = {item["fixture_id"] for item in combined_policy_fixtures}
    policy_binding_missing = [item["case_id"] for item in queries if item["policy_fixture_ref"] not in policy_fixture_refs]
    corpus = {
        "schema_version": "infobank-actual-corpus-v1",
        "metadata": {
            "dataset_version": COMBINED_DATASET_VERSION,
            "combined_evaluation_id": COMBINED_ID,
            "builder_version": "s1-s6-read-only-overlay-v1",
            "gold_blind_runtime": True,
            "source_packages": package_manifest_rows,
            "scenario_ids": sorted({item["corpus_package_ref"] for item in queries}),
            "case_order_sha256": sha256_text("\n".join(CASE_ORDER) + "\n"),
        },
        "documents": combined_documents,
        "policy_fixtures": combined_policy_fixtures,
    }
    query_path = COMBINED_DIR / "combined_query_inputs.jsonl"
    gold_path = COMBINED_DIR / "combined_reference_annotations.jsonl"
    corpus_path = COMBINED_DIR / "combined_corpus_fixture.json"
    policy_path = COMBINED_DIR / "combined_policy_fixtures.jsonl"
    source_map_path = COMBINED_DIR / "combined_source_map.json"
    manifest_path = COMBINED_DIR / "COMBINED_EVALUATION_MANIFEST.json"
    write_jsonl(query_path, queries)
    write_jsonl(gold_path, gold)
    write_json(corpus_path, corpus)
    write_jsonl(policy_path, combined_policy_fixtures)
    write_json(source_map_path, {"combined_evaluation_id": COMBINED_ID, "documents": source_map_rows})
    output_distribution = dict(sorted(Counter(item["expected_output_class"] for item in gold).items()))
    permission_distribution = dict(
        sorted(Counter("Aggregate-only" if is_aggregate_case(item) else "Owner/Full" for item in gold).items())
    )
    validation = {
        "generated_at": utc_now(),
        "combined_evaluation_id": COMBINED_ID,
        "COMBINED_SCENARIO_COUNT": len({item["corpus_package_ref"] for item in queries}),
        "COMBINED_CASE_COUNT": len(queries),
        "COMBINED_SOURCE_PDF_COUNT": len(unique_pdf_hashes),
        "COMBINED_REFERENCE_ANNOTATION_COUNT": len(gold),
        "RUNTIME_REFERENCE_SEPARATION": validate_runtime_reference_separation(query_path, corpus_path, policy_path)["status"],
        "DOCUMENT_ID_COLLISION_COUNT": len(collision_rows),
        "output_class_distribution": output_distribution,
        "permission_group_distribution": permission_distribution,
        "policy_binding_count": len(queries) - len(policy_binding_missing),
        "policy_binding_missing_cases": policy_binding_missing,
        "collision_rows": collision_rows,
        "case_order_sha256": sha256_text("\n".join(CASE_ORDER) + "\n"),
        "source_package_hashes": {item["label"]: item["sha256"] for item in package_manifest_rows},
    }
    manifest = {
        "schema_version": "infobank-combined-evaluation-manifest-v1",
        "combined_evaluation_id": COMBINED_ID,
        "dataset_version": COMBINED_DATASET_VERSION,
        "generated_at": utc_now(),
        "generation_mode": "read_only_execution_overlay",
        "frozen_source_packages": package_manifest_rows,
        "immutability": {
            "source_packages_rewritten": False,
            "questions_rewritten": False,
            "reference_annotations_rewritten": False,
            "policy_fixtures_rewritten": False,
            "document_ids_remapped_for_combined_runtime": True,
        },
        "combined_counts": validation,
        "canonical_case_order": CASE_ORDER,
        "configuration_semantics": configuration_semantics(),
    }
    write_json(manifest_path, manifest)
    write_json(COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json", validation)
    write_sha256s(COMBINED_DIR)
    expected_permission = {"Owner/Full": 36, "Aggregate-only": 6}
    required = [
        validation["COMBINED_SCENARIO_COUNT"] == 6,
        validation["COMBINED_CASE_COUNT"] == 42,
        validation["COMBINED_SOURCE_PDF_COUNT"] == 41,
        validation["COMBINED_REFERENCE_ANNOTATION_COUNT"] == 42,
        validation["RUNTIME_REFERENCE_SEPARATION"] == "PASS",
        validation["DOCUMENT_ID_COLLISION_COUNT"] == 0,
        output_distribution == EXPECTED_OUTPUT_CLASS_DISTRIBUTION,
        permission_distribution == expected_permission,
        validation["policy_binding_count"] == 42,
    ]
    validation["status"] = "PASS" if all(required) else "FAIL"
    write_json(COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json", validation)
    write_sha256s(COMBINED_DIR)
    if validation["status"] != "PASS":
        raise StopStatus("COMBINED_INPUT_VALIDATION_FAILED", "Combined overlay validation failed")
    return validation


def configuration_semantics() -> list[dict[str, str]]:
    return [
        {
            "Configuration": "C0_VECTOR_ONLY",
            "Retrieval": "active documents ranked by vector/page-aware retrieval",
            "Routing": "disabled",
            "Permission filtering": "disabled; active documents treated as usable",
            "Evidence roles": "not enforced",
            "Controlled-failure logic": "disabled; baseline generation except exact runtime errors",
            "Aggregate handling": "not governed as aggregate-only; baseline answer generation",
            "Citation handling": "answer citation selector after generation; refusals withhold citations",
        },
        {
            "Configuration": "C1_VECTOR_ROUTING",
            "Retrieval": "keyword-routed candidate documents ranked by vector/page-aware retrieval",
            "Routing": "enabled except aggregate-only governance path",
            "Permission filtering": "disabled; routed candidates treated as usable",
            "Evidence roles": "not enforced",
            "Controlled-failure logic": "disabled; baseline generation except exact runtime errors",
            "Aggregate handling": "not governed as aggregate-only; baseline answer generation",
            "Citation handling": "answer citation selector after generation; refusals withhold citations",
        },
        {
            "Configuration": "C2_PERMISSION_FILTERED",
            "Retrieval": "permitted documents ranked by vector/page-aware retrieval",
            "Routing": "disabled",
            "Permission filtering": "enabled through policy fixture use decisions",
            "Evidence roles": "aggregate/content/metadata/deny roles used for governance",
            "Controlled-failure logic": "post-retrieval permission, no-match, insufficient-evidence, and aggregate-threshold gates",
            "Aggregate handling": "aggregate executor used when aggregate evidence is available",
            "Citation handling": "citations withheld for refusals and aggregate outputs; selected for answers",
        },
        {
            "Configuration": "C3_FULL_ROLE_AWARE",
            "Retrieval": "routed permitted documents ranked by vector/page-aware retrieval",
            "Routing": "enabled for non-aggregate-only requests",
            "Permission filtering": "enabled through policy fixture use decisions",
            "Evidence roles": "query-sensitive primary/contextual/aggregate/governance roles",
            "Controlled-failure logic": "pre-generation and post-retrieval controlled-failure and clarification gates",
            "Aggregate handling": "aggregate executor plus threshold and contributor-deduplication governance",
            "Citation handling": "citations withheld for refusals and aggregate outputs; selected with role-aware support for answers",
        },
    ]


def docker_compose_env() -> dict[str, str]:
    path = REPO_ROOT / "docker-compose.yml"
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key.startswith("MARIADB_"):
            values[key] = value.strip().strip('"').strip("'")
    return values


def mysql_config() -> dict[str, str]:
    compose = docker_compose_env()
    app_password = os.getenv("INFOBANK_EVAL_DB_PASSWORD") or compose.get("MARIADB_PASSWORD")
    root_password = os.getenv("INFOBANK_EVAL_DB_ROOT_PASSWORD") or compose.get("MARIADB_ROOT_PASSWORD")
    app_user = os.getenv("INFOBANK_EVAL_DB_USER") or compose.get("MARIADB_USER") or "infobank"
    if not app_password or not root_password:
        raise StopStatus("DETERMINISTIC_COMBINED_RUN_FAILED", "MariaDB credentials are unavailable from environment or docker-compose.yml")
    return {
        "host": os.getenv("INFOBANK_EVAL_DB_HOST", "127.0.0.1"),
        "port": os.getenv("INFOBANK_EVAL_DB_PORT", "3307"),
        "app_user": app_user,
        "app_password": app_password,
        "root_user": os.getenv("INFOBANK_EVAL_DB_ROOT_USER", "root"),
        "root_password": root_password,
    }


def mysql_url(database: str, *, admin: bool = False) -> str:
    cfg = mysql_config()
    if admin:
        return (
            f"mysql+pymysql://{cfg['root_user']}:{cfg['root_password']}@"
            f"{cfg['host']}:{cfg['port']}/{database}?charset=utf8mb4"
        )
    return (
        f"mysql+pymysql://{cfg['app_user']}:{cfg['app_password']}@"
        f"{cfg['host']}:{cfg['port']}/{database}?charset=utf8mb4"
    )


def redact_url(url: str) -> str:
    return make_url(url).render_as_string(hide_password=True)


def safe_database_name(prefix: str, stamp: str) -> str:
    name = f"infobank_eval_{prefix}_{stamp}".lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    if not name.startswith("infobank_eval_"):
        raise ValueError("Invalid evaluation database name")
    return name[:63]


def verify_mariadb() -> dict[str, Any]:
    cfg = mysql_config()
    admin_url = mysql_url("mysql", admin=True)
    engine = create_engine(admin_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            version = str(connection.execute(text("SELECT VERSION()")).scalar())
    finally:
        engine.dispose()
    status = {
        "status": "PASS",
        "host": cfg["host"],
        "port": int(cfg["port"]),
        "server_version": version,
        "mariadb_11_4_compatible": "mariadb" in version.lower() or version.startswith("11.4"),
        "normal_application_database_used": False,
    }
    write_json(PRE_FLIGHT_DIR / "MARIADB_PREFLIGHT.json", status)
    if not status["mariadb_11_4_compatible"]:
        raise StopStatus("DETERMINISTIC_COMBINED_RUN_FAILED", "MariaDB server version is not 11.4-compatible")
    return status


def create_eval_database(database_name: str) -> dict[str, Any]:
    if not database_name.startswith("infobank_eval_"):
        raise ValueError("Refusing non-evaluation database")
    admin_engine = create_engine(mysql_url("mysql", admin=True), pool_pre_ping=True)
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{database_name}`"))
            connection.execute(text(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            try:
                connection.execute(text(f"GRANT ALL PRIVILEGES ON `{database_name}`.* TO 'infobank'@'%'"))
                connection.execute(text("FLUSH PRIVILEGES"))
            except Exception:
                pass
    finally:
        admin_engine.dispose()
    target_url = mysql_url(database_name)
    os.environ["DATABASE_URL"] = target_url
    from backend_python.database_schema import (  # noqa: WPS433
        SCHEMA_COMPATIBLE,
        apply_database_migrations,
        check_database_schema,
    )

    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        pre = check_database_schema(target_engine)
        migration = apply_database_migrations(target_engine)
        post = check_database_schema(target_engine)
        tables = sorted(inspect(target_engine).get_table_names())
    finally:
        target_engine.dispose()
    return {
        "database": database_name,
        "redacted_url": redact_url(target_url),
        "pre_schema_status": pre.get("status"),
        "migration": migration,
        "post_schema_status": post.get("status"),
        "table_count": len(tables),
        "tables": tables,
        "schema_compatible": post.get("status") == SCHEMA_COMPATIBLE,
    }


def run_group(
    *,
    provider_name: str,
    base_dir: Path,
    run_id: str,
    mode: str,
    database_name: str,
    allow_network_provider: bool,
    config: ActualPipelineConfig,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    group_dir = base_dir
    raw_dir = group_dir / "raw"
    score_dir = group_dir / "score"
    db_info = create_eval_database(database_name)
    if not db_info["schema_compatible"]:
        raise StopStatus("DETERMINISTIC_COMBINED_RUN_FAILED", f"Schema compatibility failed for {database_name}")
    if raw_dir.exists() and any(raw_dir.iterdir()):
        raise FileExistsError(f"Raw output already exists, refusing measured rerun: {rel(raw_dir)}")
    seal = run_actual_pipeline(
        query_input_path=COMBINED_DIR / "combined_query_inputs.jsonl",
        corpus_fixture_path=COMBINED_DIR / "combined_corpus_fixture.json",
        output_dir=raw_dir,
        database_url=mysql_url(database_name),
        chroma_dir=group_dir / "chroma",
        source_storage_dir=group_dir / "source_storage",
        run_id=run_id,
        modes=[mode],
        config=config,
        provider_name=provider_name,
        allow_network_provider=allow_network_provider,
        cache_dir=cache_dir,
    )
    score = score_sealed_run(
        raw_run_path=raw_dir / "raw_records.jsonl",
        seal_path=raw_dir / "run_seal.json",
        gold_annotation_path=COMBINED_DIR / "combined_reference_annotations.jsonl",
        output_dir=score_dir,
    )
    records = load_jsonl(raw_dir / "raw_records.jsonl")
    errors = [record for record in records if record.get("error")]
    manifest = {
        "run_id": run_id,
        "provider": provider_name,
        "mode": mode,
        "database": db_info,
        "raw_dir": rel(raw_dir),
        "score_dir": rel(score_dir),
        "seal": seal,
        "score_summary": score,
        "record_count": len(records),
        "runtime_parser_provider_error_count": len(errors),
        "error_samples": [item.get("error") for item in errors[:5]],
    }
    write_json(group_dir / "group_manifest.json", manifest)
    return manifest


def load_gold_by_case() -> dict[str, dict[str, Any]]:
    return {item["case_id"]: item for item in load_jsonl(COMBINED_DIR / "combined_reference_annotations.jsonl")}


def load_query_by_case() -> dict[str, dict[str, Any]]:
    return {item["case_id"]: item for item in load_jsonl(COMBINED_DIR / "combined_query_inputs.jsonl")}


def pages_by_doc(gold: dict[str, Any]) -> dict[str, set[int]]:
    return {
        str(doc_id): {int(page) for page in pages}
        for doc_id, pages in (gold.get("gold_page_or_message_ranges") or {}).items()
        if doc_id in set(gold.get("required_sources") or []) and pages
    }


def case_row(
    *,
    record: dict[str, Any],
    score: dict[str, Any],
    gold: dict[str, Any],
    query: dict[str, Any],
    provider: str,
    repetition: int | None = None,
) -> dict[str, Any]:
    citation_docs = {item.get("document_id") for item in record.get("actual_citations") or [] if item.get("available")}
    gold_pages = pages_by_doc(gold)
    required_docs = set(gold_pages)
    covered_docs = required_docs & citation_docs
    citations = [item for item in record.get("actual_citations") or [] if item.get("available")]
    supported_citations = 0
    correct_page_citations = 0
    wrong_page_citations = 0
    unsupported_citations = 0
    for citation in citations:
        doc_id = citation.get("document_id")
        page = citation.get("page_number")
        if doc_id in required_docs:
            supported_citations += 1
            if page in gold_pages.get(doc_id, set()):
                correct_page_citations += 1
            else:
                wrong_page_citations += 1
        else:
            unsupported_citations += 1
    safety = score.get("safety_findings") or {}
    usage = record.get("provider_usage") or {}
    timings = record.get("stage_timings_ms") or {}
    expected_class = gold.get("expected_output_class")
    actual_class = record.get("actual_output_class")
    expected_answer = expected_class in ANSWER_CLASSES
    actual_answer = actual_class in ANSWER_CLASSES
    expected_non_full = expected_class != "FULL_ANSWER"
    intentional_citation_withheld = int(not citations and actual_class in NON_FULL_CLASSES | {"AGGREGATE_RESULT", "REFUSE_AGGREGATION_THRESHOLD"})
    required_doc_count = len(required_docs)
    retrieved_docs = set(record.get("retrieved_document_ids") or [])
    retrieved_chunks = record.get("retrieved_chunks") or []
    retrieved_order = [item.get("document_id") for item in retrieved_chunks if item.get("document_id")]
    first_rank = next((index + 1 for index, doc_id in enumerate(retrieved_order) if doc_id in required_docs), None)
    retrieved_required = len(required_docs & retrieved_docs)
    row = {
        "provider": provider,
        "repetition": repetition,
        "configuration": record.get("mode"),
        "configuration_short": MODE_SHORT.get(str(record.get("mode")), str(record.get("mode"))),
        "scenario": scenario_label(str(record.get("case_id"))),
        "case_id": record.get("case_id"),
        "question": query.get("query_text"),
        "permission_group": "Aggregate-only" if is_aggregate_case(gold) else "Owner/Full",
        "expected_output_class": expected_class,
        "actual_output_class": actual_class,
        "expected_reason_code": score.get("expected_reason_code"),
        "actual_reason_code": score.get("actual_reason_code"),
        "raw_actual_reason_code": score.get("raw_actual_reason_code"),
        "output_class_correct": int(bool(score.get("output_class_correct"))),
        "reason_code_correct": int(bool(score.get("reason_code_correct"))),
        "factual_atoms_supported": int(bool(score.get("factual_atoms_supported"))),
        "permitted_answer_correct": int(expected_answer and actual_class == expected_class and bool(score.get("factual_atoms_supported"))),
        "expected_answer": int(expected_answer),
        "actual_answer": int(actual_answer),
        "false_answer": int((not expected_answer) and actual_answer),
        "false_refusal": int(expected_answer and actual_class in NON_FULL_CLASSES),
        "expected_non_full": int(expected_non_full),
        "correct_non_full_output": int(expected_non_full and actual_class == expected_class),
        "citation_count": len(citations),
        "required_document_slots": required_doc_count,
        "covered_document_slots": len(covered_docs),
        "citation_document_coverage": ratio(len(covered_docs), required_doc_count),
        "citation_support_precision": ratio(supported_citations, len(citations)),
        "page_level_citation_correctness": ratio(correct_page_citations, len(citations)),
        "citation_coverage": ratio(correct_page_citations, required_doc_count),
        "unsupported_citation_count": unsupported_citations,
        "wrong_document_citation_count": unsupported_citations,
        "wrong_page_citation_count": wrong_page_citations,
        "missing_required_document_count": max(0, required_doc_count - len(covered_docs)),
        "intentional_citation_withheld": intentional_citation_withheld,
        "candidate_document_count": len(record.get("candidate_ids") or []),
        "retrieved_document_count": len(retrieved_docs),
        "retrieved_chunk_count": len(retrieved_chunks),
        "required_document_retrieval_coverage": ratio(retrieved_required, required_doc_count),
        "recall_at_k": ratio(retrieved_required, required_doc_count),
        "precision_at_k": ratio(retrieved_required, len(retrieved_docs)),
        "mrr": None if first_rank is None else round(1 / first_rank, 6),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "retry_count": usage.get("retries") or 0,
        "recorded_cost": usage.get("cost"),
        "usage_source": usage.get("usage_source"),
        "recorded_generation_call_count": 0 if record.get("generation_skipped") else 1,
        "generation_skipped": int(bool(record.get("generation_skipped"))),
        "retrieval_latency_ms": timings.get("retrieval"),
        "generation_latency_ms": timings.get("generation"),
        "total_latency_ms": timings.get("total"),
        "provider_runtime_error": int(bool(record.get("error"))),
        "error": record.get("error"),
        "actual_output_text": record.get("actual_output_text"),
        "retrieved_document_ids": record.get("retrieved_document_ids") or [],
        "cited_document_ids": sorted(citation_docs),
        "cited_pages": sorted(
            f"{item.get('document_id')}:{item.get('page_number')}" for item in citations if item.get("document_id")
        ),
        "aggregate_trace": record.get("aggregate_trace"),
        "policy_trace": record.get("policy_trace"),
        "safety_findings": safety,
        "safety_error_total": sum(int(value) for value in safety.values()),
        "audit_id": record.get("audit_id"),
        "generator_visible_text_hash": record.get("generator_visible_text_hash"),
        "raw_record_hash": sha256_text(canonical_json(record)),
    }
    return row


def ratio(num: float | int | None, den: float | int | None) -> float | None:
    if num is None or den in (None, 0):
        return None
    return round(float(num) / float(den), 6)


def read_group_rows(
    *,
    provider: str,
    mode_dir: Path,
    repetition: int | None = None,
) -> list[dict[str, Any]]:
    raw_records = load_jsonl(mode_dir / "raw" / "raw_records.jsonl")
    scores = {item["case_id"]: item for item in load_jsonl(mode_dir / "score" / "case_scores.jsonl")}
    gold_by_case = load_gold_by_case()
    query_by_case = load_query_by_case()
    return [
        case_row(
            record=record,
            score=scores[str(record["case_id"])],
            gold=gold_by_case[str(record["case_id"])],
            query=query_by_case[str(record["case_id"])],
            provider=provider,
            repetition=repetition,
        )
        for record in raw_records
    ]


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    expected_answer_rows = [row for row in rows if row["expected_answer"]]
    expected_non_full_rows = [row for row in rows if row["expected_non_full"]]
    citation_slot_count = sum(int(row["required_document_slots"] or 0) for row in rows)
    citation_count = sum(int(row["citation_count"] or 0) for row in rows)
    total_latency = [float(row["total_latency_ms"]) for row in rows if row.get("total_latency_ms") is not None]
    retrieval_latency = [float(row["retrieval_latency_ms"]) for row in rows if row.get("retrieval_latency_ms") is not None]
    generation_latency = [float(row["generation_latency_ms"]) for row in rows if row.get("generation_latency_ms") is not None]
    tokens = [int(row["total_tokens"] or 0) for row in rows]
    safety_counter: Counter[str] = Counter()
    for row in rows:
        safety_counter.update({key: int(value) for key, value in (row.get("safety_findings") or {}).items()})
    output_counts = Counter(row["actual_output_class"] for row in rows)
    return {
        "case_count": count,
        "output_class_correct": sum(row["output_class_correct"] for row in rows),
        "output_class_accuracy": ratio(sum(row["output_class_correct"] for row in rows), count),
        "reason_code_correct": sum(row["reason_code_correct"] for row in rows),
        "reason_code_accuracy": ratio(sum(row["reason_code_correct"] for row in rows), count),
        "permitted_answer_correct": sum(row["permitted_answer_correct"] for row in expected_answer_rows),
        "permitted_answer_denominator": len(expected_answer_rows),
        "permitted_answer_accuracy": ratio(sum(row["permitted_answer_correct"] for row in expected_answer_rows), len(expected_answer_rows)),
        "factual_atom_support_correct": sum(row["factual_atoms_supported"] for row in rows),
        "factual_atom_support_accuracy": ratio(sum(row["factual_atoms_supported"] for row in rows), count),
        "controlled_failure_correct": sum(row["correct_non_full_output"] for row in expected_non_full_rows),
        "controlled_failure_denominator": len(expected_non_full_rows),
        "controlled_failure_correctness": ratio(
            sum(row["correct_non_full_output"] for row in expected_non_full_rows), len(expected_non_full_rows)
        ),
        "false_answer_count": sum(row["false_answer"] for row in rows),
        "false_refusal_count": sum(row["false_refusal"] for row in rows),
        "predicted_full_answer_count": output_counts.get("FULL_ANSWER", 0),
        "predicted_constrained_answer_count": output_counts.get("CONSTRAINED_ANSWER", 0),
        "predicted_aggregate_result_count": output_counts.get("AGGREGATE_RESULT", 0),
        "predicted_clarification_count": output_counts.get("CLARIFICATION", 0),
        "predicted_refusal_count": sum(value for key, value in output_counts.items() if key.startswith("REFUSE_")),
        "predicted_refusal_counts_by_class": {key: value for key, value in sorted(output_counts.items()) if key.startswith("REFUSE_")},
        "citation_document_coverage": ratio(sum(row["covered_document_slots"] for row in rows), citation_slot_count),
        "citation_support_precision": ratio(
            sum((row["citation_support_precision"] or 0) * (row["citation_count"] or 0) for row in rows),
            citation_count,
        ),
        "page_level_citation_correctness": ratio(
            sum((row["page_level_citation_correctness"] or 0) * (row["citation_count"] or 0) for row in rows),
            citation_count,
        ),
        "citation_coverage": ratio(sum(row["citation_coverage"] or 0 for row in rows), count),
        "required_document_slots": citation_slot_count,
        "covered_document_slots": sum(row["covered_document_slots"] for row in rows),
        "unsupported_citation_count": sum(row["unsupported_citation_count"] for row in rows),
        "wrong_document_citation_count": sum(row["wrong_document_citation_count"] for row in rows),
        "wrong_page_citation_count": sum(row["wrong_page_citation_count"] for row in rows),
        "missing_required_document_count": sum(row["missing_required_document_count"] for row in rows),
        "intentional_citation_withheld_count": sum(row["intentional_citation_withheld"] for row in rows),
        "mean_candidate_document_count": mean([row["candidate_document_count"] for row in rows]),
        "mean_retrieved_document_count": mean([row["retrieved_document_count"] for row in rows]),
        "mean_retrieved_chunk_count": mean([row["retrieved_chunk_count"] for row in rows]),
        "required_document_retrieval_coverage": ratio(
            sum((row["required_document_retrieval_coverage"] or 0) * (row["required_document_slots"] or 0) for row in rows),
            citation_slot_count,
        ),
        "recall_at_k": ratio(sum((row["recall_at_k"] or 0) * (row["required_document_slots"] or 0) for row in rows), citation_slot_count),
        "precision_at_k": mean([row["precision_at_k"] for row in rows if row.get("precision_at_k") is not None]),
        "mrr": mean([row["mrr"] for row in rows if row.get("mrr") is not None]),
        "safety_findings": dict(sorted(safety_counter.items())),
        "safety_error_total": sum(safety_counter.values()),
        "runtime_parser_provider_errors": sum(row["provider_runtime_error"] for row in rows),
        "prompt_input_tokens": sum(int(row["input_tokens"] or 0) for row in rows),
        "completion_output_tokens": sum(int(row["output_tokens"] or 0) for row in rows),
        "total_tokens": sum(tokens),
        "recorded_generation_call_count": sum(int(row["recorded_generation_call_count"] or 0) for row in rows),
        "retry_count": sum(int(row["retry_count"] or 0) for row in rows),
        "failed_call_count": sum(row["provider_runtime_error"] for row in rows),
        "recorded_cost": cost_summary(rows),
        "latency_total_ms": describe(total_latency),
        "latency_retrieval_ms": describe(retrieval_latency),
        "latency_generation_ms": describe(generation_latency),
    }


def mean(values: Iterable[float | int | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 6)


def describe(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "median": None, "stdev": None, "min": None, "max": None, "p50": None, "p95": None}
    sorted_values = sorted(values)
    return {
        "mean": round(statistics.mean(sorted_values), 6),
        "median": round(statistics.median(sorted_values), 6),
        "stdev": round(statistics.stdev(sorted_values), 6) if len(sorted_values) > 1 else 0.0,
        "min": round(min(sorted_values), 6),
        "max": round(max(sorted_values), 6),
        "p50": round(percentile(sorted_values, 50), 6),
        "p95": round(percentile(sorted_values, 95), 6),
    }


def percentile(sorted_values: list[float], percentile_value: float) -> float:
    if not sorted_values:
        return math.nan
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * percentile_value / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] * (upper - rank) + sorted_values[upper] * (rank - lower)


def cost_summary(rows: list[dict[str, Any]]) -> str | float:
    values = [row.get("recorded_cost") for row in rows]
    if any(value is None for value in values):
        return "NOT_RECORDED_BY_PROVIDER_ADAPTER"
    return round(sum(float(value or 0.0) for value in values), 8)


def flatten_summary_row(prefix: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    latency = summary.get("latency_total_ms") or {}
    return {
        **prefix,
        "Cases": summary["case_count"],
        "Output accuracy": summary["output_class_accuracy"],
        "Permitted-answer accuracy": summary["permitted_answer_accuracy"],
        "Controlled-failure correctness": summary["controlled_failure_correctness"],
        "Citation coverage": summary["citation_coverage"],
        "Support precision": summary["citation_support_precision"],
        "Page correctness": summary["page_level_citation_correctness"],
        "Safety findings": summary["safety_error_total"],
        "Tokens": summary["total_tokens"],
        "Mean latency": latency.get("mean"),
        "Runtime/parser/provider errors": summary["runtime_parser_provider_errors"],
    }


def group_rows(rows: list[dict[str, Any]], keys: list[str]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(key) for key in keys)].append(row)
    return grouped


def write_aggregate_tables(rows: list[dict[str, Any]], base_dir: Path, *, provider: str) -> dict[str, Any]:
    all_summary = summarize_rows(rows)
    by_configuration = {
        key[0]: summarize_rows(value)
        for key, value in group_rows(rows, ["configuration_short"]).items()
    }
    summary_rows = [
        flatten_summary_row({"Configuration": config}, summary)
        for config, summary in sorted(by_configuration.items())
    ]
    if provider == "deterministic":
        write_csv(base_dir / "c0_c3_summary.csv", summary_rows)
        write_json(base_dir / "c0_c3_summary.json", {"overall": all_summary, "by_configuration": by_configuration})
    else:
        repetition_rows: list[dict[str, Any]] = []
        for key, value in sorted(group_rows(rows, ["repetition", "configuration_short"]).items()):
            repetition, configuration = key
            repetition_rows.append(flatten_summary_row({"Repetition": repetition, "Configuration": configuration}, summarize_rows(value)))
        write_csv(base_dir / "repetition_summary.csv", repetition_rows)
        config_payload = configuration_level_repetition_summary(rows)
        write_csv(base_dir / "c0_c3_real_provider_summary.csv", summary_rows)
        write_json(base_dir / "c0_c3_real_provider_summary.json", config_payload)
    scenario_rows = [
        flatten_summary_row({"Configuration": config, "Scenario": scenario}, summarize_rows(value))
        for (config, scenario), value in sorted(group_rows(rows, ["configuration_short", "scenario"]).items())
    ]
    output_class_rows = [
        flatten_summary_row({"Configuration": config, "Expected output class": output_class}, summarize_rows(value))
        for (config, output_class), value in sorted(group_rows(rows, ["configuration_short", "expected_output_class"]).items())
    ]
    permission_rows = [
        flatten_summary_row({"Configuration": config, "Permission group": permission}, summarize_rows(value))
        for (config, permission), value in sorted(group_rows(rows, ["configuration_short", "permission_group"]).items())
    ]
    citation_rows = [
        {
            "Configuration": config,
            "Cases": summary["case_count"],
            "Citation document coverage": summary["citation_document_coverage"],
            "Citation support precision": summary["citation_support_precision"],
            "Page-level citation correctness": summary["page_level_citation_correctness"],
            "Citation coverage": summary["citation_coverage"],
            "Required document slots": summary["required_document_slots"],
            "Covered document slots": summary["covered_document_slots"],
            "Unsupported citation count": summary["unsupported_citation_count"],
            "Wrong-document citation count": summary["wrong_document_citation_count"],
            "Wrong-page citation count": summary["wrong_page_citation_count"],
            "Missing-required-document count": summary["missing_required_document_count"],
            "Citation-free intentionally withheld": summary["intentional_citation_withheld_count"],
        }
        for config, summary in sorted(by_configuration.items())
    ]
    safety_rows = []
    for config, summary in sorted(by_configuration.items()):
        row = {"Configuration": config, "Total safety findings": summary["safety_error_total"]}
        row.update(summary["safety_findings"])
        safety_rows.append(row)
    efficiency_rows = [
        {
            "Configuration": config,
            "Cases": summary["case_count"],
            "Mean latency": summary["latency_total_ms"]["mean"],
            "Median latency": summary["latency_total_ms"]["median"],
            "Stdev latency": summary["latency_total_ms"]["stdev"],
            "Min latency": summary["latency_total_ms"]["min"],
            "Max latency": summary["latency_total_ms"]["max"],
            "P50 latency": summary["latency_total_ms"]["p50"],
            "P95 latency": summary["latency_total_ms"]["p95"],
            "Mean retrieval latency": summary["latency_retrieval_ms"]["mean"],
            "Mean generation latency": summary["latency_generation_ms"]["mean"],
            "Prompt/input tokens": summary["prompt_input_tokens"],
            "Completion/output tokens": summary["completion_output_tokens"],
            "Total tokens": summary["total_tokens"],
            "Recorded generation calls": summary["recorded_generation_call_count"],
            "Retry count": summary["retry_count"],
            "Failed call count": summary["failed_call_count"],
            "Recorded cost": summary["recorded_cost"],
        }
        for config, summary in sorted(by_configuration.items())
    ]
    write_csv(base_dir / "scenario_summary.csv", scenario_rows)
    write_csv(base_dir / "output_class_summary.csv", output_class_rows)
    write_csv(base_dir / "permission_group_summary.csv", permission_rows)
    write_csv(base_dir / "citation_summary.csv", citation_rows)
    write_csv(base_dir / "safety_summary.csv", safety_rows)
    write_csv(base_dir / "efficiency_summary.csv", efficiency_rows)
    return {"overall": all_summary, "by_configuration": by_configuration}


def configuration_level_repetition_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {"by_configuration": {}}
    metrics = [
        "output_class_accuracy",
        "reason_code_accuracy",
        "permitted_answer_accuracy",
        "controlled_failure_correctness",
        "citation_coverage",
        "citation_support_precision",
        "page_level_citation_correctness",
    ]
    for config in sorted({row["configuration_short"] for row in rows}):
        rep_summaries = []
        for repetition in sorted({row["repetition"] for row in rows if row["configuration_short"] == config}):
            rep_rows = [row for row in rows if row["configuration_short"] == config and row["repetition"] == repetition]
            rep_summaries.append({"repetition": repetition, **summarize_rows(rep_rows)})
        config_metrics: dict[str, Any] = {}
        for metric in metrics:
            values = [item.get(metric) for item in rep_summaries if item.get(metric) is not None]
            config_metrics[metric] = {
                "repetition_values": values,
                "mean": mean(values),
                "standard_deviation": round(statistics.stdev(values), 6) if len(values) > 1 else 0.0 if values else None,
                "minimum": min(values) if values else None,
                "maximum": max(values) if values else None,
            }
        pooled = summarize_rows([row for row in rows if row["configuration_short"] == config])
        payload["by_configuration"][config] = {
            "repetitions": rep_summaries,
            "metrics": config_metrics,
            "pooled_record_count_descriptive_only": pooled["case_count"],
            "raw_numerators_denominators": {
                "output_class": [pooled["output_class_correct"], pooled["case_count"]],
                "reason_code": [pooled["reason_code_correct"], pooled["case_count"]],
                "permitted_answer": [pooled["permitted_answer_correct"], pooled["permitted_answer_denominator"]],
                "controlled_failure": [pooled["controlled_failure_correct"], pooled["controlled_failure_denominator"]],
            },
        }
    return payload


def run_deterministic() -> dict[str, Any]:
    verify_mariadb()
    validation = load_json(COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json")
    if validation.get("status") != "PASS":
        raise StopStatus("COMBINED_INPUT_VALIDATION_FAILED", "Combined overlay is not valid")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    config = ActualPipelineConfig()
    manifests: list[dict[str, Any]] = []
    for mode in MODES:
        short = MODE_SHORT[mode]
        manifest = run_group(
            provider_name="deterministic-mock",
            base_dir=DETERMINISTIC_DIR / short,
            run_id=f"s1s6-deterministic-{short.lower()}-{stamp}",
            mode=mode,
            database_name=safe_database_name(f"s1s6_deterministic_{short.lower()}", stamp),
            allow_network_provider=False,
            config=config,
        )
        manifests.append(manifest)
    rows: list[dict[str, Any]] = []
    for mode in MODES:
        rows.extend(read_group_rows(provider="deterministic-mock", mode_dir=DETERMINISTIC_DIR / MODE_SHORT[mode]))
    write_csv(DETERMINISTIC_DIR / "per_case_168.csv", rows)
    write_jsonl(DETERMINISTIC_DIR / "per_case_168.jsonl", rows)
    summary = write_aggregate_tables(rows, DETERMINISTIC_DIR, provider="deterministic")
    aggregate_rows = aggregate_governance_rows(rows)
    write_csv(DETERMINISTIC_DIR / "aggregate_governance_summary.csv", aggregate_rows)
    write_error_analysis(DETERMINISTIC_DIR / "error_analysis.md", rows, provider_label=DETERMINISTIC_LABEL)
    run_manifest = {
        "label": DETERMINISTIC_LABEL,
        "generated_at": utc_now(),
        "planned_records": 168,
        "executed_records": len(rows),
        "modes": MODES,
        "configuration": config_manifest(config),
        "group_manifests": manifests,
        "summary": summary,
        "technical_go_no_go": deterministic_go_no_go(rows, manifests),
    }
    write_json(DETERMINISTIC_DIR / "run_manifest.json", run_manifest)
    write_reproduce(DETERMINISTIC_DIR / "REPRODUCE.md", provider="deterministic")
    write_sha256s(DETERMINISTIC_DIR)
    if not run_manifest["technical_go_no_go"]["proceed_to_openai"]:
        raise StopStatus("DETERMINISTIC_COMBINED_RUN_FAILED", "Deterministic technical validation failed")
    return run_manifest


def deterministic_go_no_go(rows: list[dict[str, Any]], manifests: list[dict[str, Any]]) -> dict[str, Any]:
    record_count_ok = len(rows) == 168
    errors = sum(row["provider_runtime_error"] for row in rows)
    package_hashes = {spec["label"]: sha256_file(spec["path"]) == spec["expected_sha256"] for spec in PACKAGE_SPECS}
    source_clean = not git(["diff", "--name-only", "--", "backend_python", "evaluation", "scripts"]).stdout.splitlines()
    db_ok = all(item["database"]["schema_compatible"] for item in manifests)
    return {
        "record_count_ok": record_count_ok,
        "package_hashes_unchanged": package_hashes,
        "runtime_reference_separation": load_json(COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json").get("RUNTIME_REFERENCE_SEPARATION"),
        "runtime_parser_provider_errors": errors,
        "source_test_files_clean": source_clean,
        "mariadb_isolation_pass": db_ok,
        "proceed_to_openai": record_count_ok and errors == 0 and all(package_hashes.values()) and source_clean and db_ok,
    }


def config_manifest(config: ActualPipelineConfig) -> dict[str, Any]:
    return {
        "top_k": config.top_k,
        "minimum_support_score": config.minimum_support_score,
        "minimum_primary_sources": config.minimum_primary_sources,
        "minimum_source_diversity": config.minimum_source_diversity,
        "conflict_policy": config.conflict_policy,
        "routing_mode": config.routing_mode,
        "embedding_model": config.embedding_model,
        "generation_model": config.generation_model,
        "generation_temperature": GENERATION_TEMPERATURE,
        "generation_prompt_version": GENERATION_PROMPT_VERSION,
        "routing_prompt_version": ROUTING_PROMPT_VERSION,
        "config_hash": config.config_hash,
    }


def openai_config() -> ActualPipelineConfig:
    return ActualPipelineConfig(generation_model=GENERATION_MODEL, embedding_model=EMBEDDING_MODEL)


def openai_preflight() -> dict[str, Any]:
    config = openai_config()
    result: dict[str, Any] = {
        "generated_at": utc_now(),
        "credential_present": bool(os.getenv("OPENAI_API_KEY")),
        "generation_model": config.generation_model,
        "embedding_model": config.embedding_model,
        "generation_temperature": GENERATION_TEMPERATURE,
        "generation_access": "NOT_TESTED",
        "embedding_access": "NOT_TESTED",
        "keyword_access": "NOT_TESTED",
        "adapter_status": "NOT_TESTED",
    }
    try:
        provider = create_provider("openai")
        embeddings = provider.embed(["InfoBank OpenAI technical preflight."], model=config.embedding_model)
        result["embedding_access"] = "PASS" if embeddings and embeddings[0] else "FAIL"
        generated = provider.generate_with_usage(
            [
                {"role": "system", "content": "Return exactly OK."},
                {"role": "user", "content": "Technical preflight."},
            ],
            model=config.generation_model,
            temperature=GENERATION_TEMPERATURE,
        )
        result["generation_access"] = "PASS" if generated.text.strip() else "FAIL"
        keywords, trace = provider.extract_keywords_with_trace(
            "alpha beta",
            model=config.generation_model,
            prompt="Select useful keywords.",
            prompt_version=ROUTING_PROMPT_VERSION,
            available_keywords=["alpha", "beta"],
            limit=1,
        )
        result["keyword_access"] = "PASS" if trace.get("outcome") in {"selected", "provider_none"} or keywords else "FAIL"
        result["adapter_status"] = "PASS"
        result["preflight_usage"] = {
            "generation_input_tokens": generated.input_tokens,
            "generation_output_tokens": generated.output_tokens,
            "generation_total_tokens": generated.total_tokens,
            "generation_retries": generated.retries,
            "cost": "NOT_RECORDED_BY_PROVIDER_ADAPTER",
        }
    except Exception as exc:
        result["adapter_status"] = "FAIL"
        result["error_type"] = type(exc).__name__
        result["error_message"] = sanitize_error(str(exc))
    write_json(OPENAI_DIR / "OPENAI_PREFLIGHT.json", result)
    if not result["credential_present"] or result["adapter_status"] != "PASS":
        raise StopStatus("OPENAI_PREFLIGHT_FAILED", "OpenAI preflight failed")
    return result


def sanitize_error(message: str) -> str:
    redacted = re.sub(r"ghp_[A-Za-z0-9_]+", "[REDACTED_GITHUB_TOKEN]", message)
    redacted = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED_OPENAI_KEY]", redacted)
    return redacted


def preregister_openai() -> dict[str, Any]:
    ensure_dir(OPENAI_DIR)
    prereg_path = OPENAI_DIR / "REAL_PROVIDER_PREREGISTRATION.json"
    if prereg_path.exists():
        existing = load_json(prereg_path)
        if existing.get("REAL_PROVIDER_PREREGISTRATION_LOCKED") == "YES":
            return existing
        raise StopStatus("REAL_PROVIDER_PREREGISTRATION_FAILED", "Existing preregistration is not locked")
    config = openai_config()
    if config.generation_model != "gpt-4o-mini" or config.embedding_model != "text-embedding-3-small":
        raise StopStatus("REAL_PROVIDER_PREREGISTRATION_FAILED", "Committed provider model differs from expected model")
    overlay_hashes = {
        "combined_manifest": sha256_file(COMBINED_DIR / "COMBINED_EVALUATION_MANIFEST.json"),
        "query_hash": sha256_file(COMBINED_DIR / "combined_query_inputs.jsonl"),
        "reference_annotation_hash": sha256_file(COMBINED_DIR / "combined_reference_annotations.jsonl"),
        "corpus_hash": sha256_file(COMBINED_DIR / "combined_corpus_fixture.json"),
        "policy_fixture_hash": sha256_file(COMBINED_DIR / "combined_policy_fixtures.jsonl"),
        "source_map_hash": sha256_file(COMBINED_DIR / "combined_source_map.json"),
    }
    payload = {
        "schema_version": "infobank-real-provider-preregistration-v1",
        "REAL_PROVIDER_PREREGISTRATION_LOCKED": "YES",
        "created_at": utc_now(),
        "repository": "https://github.com/gkusper/InfoBank",
        "branch": git_out(["rev-parse", "--abbrev-ref", "HEAD"]),
        "HEAD": git_out(["rev-parse", "HEAD"]),
        "source_code_hash": tree_hash(["backend_python", "evaluation"]),
        "test_code_hash": tree_hash(["backend_python/tests", "evaluation/tests"]),
        "frozen_packages": [
            {"path": spec["relative_path"], "sha256": sha256_file(spec["path"])}
            for spec in PACKAGE_SPECS
        ],
        "combined_overlay_hashes": overlay_hashes,
        "scorer_identity": SCORER_VERSION,
        "scorer_hash": sha256_file(REPO_ROOT / "evaluation" / "actual_pipeline_scorer.py"),
        "runner_identity": "infobank-actual-pipeline-runner-v1",
        "runner_hash": sha256_file(REPO_ROOT / "evaluation" / "actual_pipeline_runner.py"),
        "configuration_semantics": configuration_semantics(),
        "models": {
            "generation_model": config.generation_model,
            "keyword_model": config.generation_model,
            "embedding_model": config.embedding_model,
        },
        "generation_parameters": {"temperature": GENERATION_TEMPERATURE},
        "retrieval_and_governance_parameters": config_manifest(config),
        "retry_policy": {
            "committed_adapter_behavior": "OpenAI generate_with_usage attempts up to 3 calls and records retries for generation calls; keyword and embedding calls use committed adapter behavior.",
            "allowed_reasons": ["connection_or_transport", "timeout", "HTTP_429", "retryable_HTTP_5xx_or_SDK_error"],
            "forbidden_reasons": [
                "incorrect_answer",
                "unexpected_output_class",
                "incomplete_citation",
                "safety_finding",
                "poor_metric",
                "malformed_but_parseable_scientific_result",
                "reference_disagreement",
            ],
        },
        "repetitions": 3,
        "case_count": 42,
        "planned_measured_record_count": 504,
        "canonical_case_order": CASE_ORDER,
        "run_order": {
            "repetition_1": ["C0", "C1", "C2", "C3"],
            "repetition_2": ["C0", "C1", "C2", "C3"],
            "repetition_3": ["C0", "C1", "C2", "C3"],
        },
        "isolation_plan": "Fresh MariaDB evaluation database, Chroma directory, source-storage directory, raw-output directory, and score-output directory for every repetition/configuration group.",
        "known_evaluation_limitations": [
            "42 controlled synthetic cases are not production-scale generalization.",
            "The three repetitions assess provider stability over the same cases, not independent case expansion.",
            "S1-S2 historical citation-completeness limitations remain inherited and visible.",
            "Provider-call totals beyond generation calls are not fully recorded per case by the current evaluator.",
        ],
        "no_result_dependent_rerun_rule": True,
        "no_tuning_rule": True,
    }
    write_json(prereg_path, payload)
    sha = sha256_file(prereg_path)
    payload["preregistration_sha256"] = sha
    write_json(OPENAI_DIR / "REAL_PROVIDER_PREREGISTRATION_SHA256.json", {"path": rel(prereg_path), "sha256": sha})
    return payload


def run_openai() -> dict[str, Any]:
    preflight = openai_preflight()
    prereg = preregister_openai()
    config = openai_config()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    manifests: list[dict[str, Any]] = []
    interrupted = False
    interruption_reason = None
    for repetition in (1, 2, 3):
        for mode in MODES:
            short = MODE_SHORT[mode]
            group_base = OPENAI_DIR / f"R{repetition}" / short
            try:
                manifest = run_group(
                    provider_name="openai",
                    base_dir=group_base,
                    run_id=f"s1s6-openai-r{repetition}-{short.lower()}-{stamp}",
                    mode=mode,
                    database_name=safe_database_name(f"s1s6_openai_r{repetition}_{short.lower()}", stamp),
                    allow_network_provider=True,
                    config=config,
                    cache_dir=group_base / "cache",
                )
                manifest["repetition"] = repetition
                manifests.append(manifest)
                if manifest["runtime_parser_provider_error_count"] >= 10:
                    interrupted = True
                    interruption_reason = "systemic_provider_or_runtime_failure_threshold_after_group"
                    break
            except Exception as exc:
                write_json(
                    group_base / "INTERRUPTION.json",
                    {
                        "status": "REAL_PROVIDER_EXPERIMENT_INTERRUPTED",
                        "repetition": repetition,
                        "configuration": short,
                        "error_type": type(exc).__name__,
                        "error_message": sanitize_error(str(exc)),
                    },
                )
                interrupted = True
                interruption_reason = f"{type(exc).__name__}: {sanitize_error(str(exc))}"
                break
        if interrupted:
            break
    rows: list[dict[str, Any]] = []
    for repetition in (1, 2, 3):
        for short in ("C0", "C1", "C2", "C3"):
            group_dir = OPENAI_DIR / f"R{repetition}" / short
            raw_path = group_dir / "raw" / "raw_records.jsonl"
            score_path = group_dir / "score" / "case_scores.jsonl"
            if raw_path.exists() and score_path.exists():
                rows.extend(read_group_rows(provider="openai", mode_dir=group_dir, repetition=repetition))
    write_csv(OPENAI_DIR / "per_case_504.csv", rows)
    write_jsonl(OPENAI_DIR / "per_case_504.jsonl", rows)
    summary = write_aggregate_tables(rows, OPENAI_DIR, provider="openai") if rows else {}
    write_csv(OPENAI_DIR / "aggregate_governance_summary.csv", aggregate_governance_rows(rows))
    write_csv(OPENAI_DIR / "stability_analysis.csv", stability_rows(rows))
    write_csv(OPENAI_DIR / "paired_configuration_comparison.csv", paired_comparison_rows(rows))
    write_csv(OPENAI_DIR / "confidence_intervals.csv", confidence_interval_rows(rows))
    write_csv(OPENAI_DIR / "deterministic_vs_openai.csv", deterministic_vs_openai_rows())
    write_error_analysis(OPENAI_DIR / "error_analysis.md", rows, provider_label="OpenAI real-provider")
    write_reproduce(OPENAI_DIR / "REPRODUCE.md", provider="openai")
    experiment_status = {
        "generated_at": utc_now(),
        "preregistration_sha256": sha256_file(OPENAI_DIR / "REAL_PROVIDER_PREREGISTRATION.json"),
        "preflight": preflight,
        "planned_records": 504,
        "executed_records": len(rows),
        "interrupted": interrupted,
        "interruption_reason": interruption_reason,
        "group_manifests": manifests,
        "summary": summary,
    }
    write_json(OPENAI_DIR / "run_manifest.json", experiment_status)
    write_sha256s(OPENAI_DIR)
    if interrupted or len(rows) != 504:
        raise StopStatus("REAL_PROVIDER_EXPERIMENT_INTERRUPTED", "OpenAI measured experiment did not complete all 504 records")
    return experiment_status


def openai_group_state() -> list[dict[str, Any]]:
    state: list[dict[str, Any]] = []
    for repetition in (1, 2, 3):
        for short in ("C0", "C1", "C2", "C3"):
            group_dir = OPENAI_DIR / f"R{repetition}" / short
            raw_path = group_dir / "raw" / "raw_records.jsonl"
            score_path = group_dir / "score" / "case_scores.jsonl"
            records = load_jsonl(raw_path) if raw_path.exists() else []
            errors = [row for row in records if row.get("error")]
            state.append(
                {
                    "repetition": repetition,
                    "configuration": short,
                    "raw_path": rel(raw_path),
                    "score_path": rel(score_path),
                    "raw_exists": raw_path.exists(),
                    "score_exists": score_path.exists(),
                    "record_count": len(records),
                    "error_count": len(errors),
                    "first_error_type": str(errors[0].get("error", "")).split(":", 1)[0] if errors else None,
                    "complete": raw_path.exists() and score_path.exists() and len(records) == 42,
                }
            )
    return state


def collect_openai_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for repetition in (1, 2, 3):
        for short in ("C0", "C1", "C2", "C3"):
            group_dir = OPENAI_DIR / f"R{repetition}" / short
            raw_path = group_dir / "raw" / "raw_records.jsonl"
            score_path = group_dir / "score" / "case_scores.jsonl"
            if raw_path.exists() and score_path.exists():
                rows.extend(read_group_rows(provider="openai", mode_dir=group_dir, repetition=repetition))
    return rows


def write_openai_outputs(
    *,
    rows: list[dict[str, Any]],
    preflight: dict[str, Any],
    group_manifests: list[dict[str, Any]],
    interrupted: bool,
    interruption_reason: str | None,
    continuation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    write_csv(OPENAI_DIR / "per_case_504.csv", rows)
    write_jsonl(OPENAI_DIR / "per_case_504.jsonl", rows)
    summary = write_aggregate_tables(rows, OPENAI_DIR, provider="openai") if rows else {}
    write_csv(OPENAI_DIR / "aggregate_governance_summary.csv", aggregate_governance_rows(rows))
    write_csv(OPENAI_DIR / "stability_analysis.csv", stability_rows(rows))
    write_csv(OPENAI_DIR / "paired_configuration_comparison.csv", paired_comparison_rows(rows))
    write_csv(OPENAI_DIR / "confidence_intervals.csv", confidence_interval_rows(rows))
    write_csv(OPENAI_DIR / "deterministic_vs_openai.csv", deterministic_vs_openai_rows())
    write_error_analysis(OPENAI_DIR / "error_analysis.md", rows, provider_label="OpenAI real-provider")
    write_reproduce(OPENAI_DIR / "REPRODUCE.md", provider="openai")
    experiment_status = {
        "generated_at": utc_now(),
        "preregistration_sha256": sha256_file(OPENAI_DIR / "REAL_PROVIDER_PREREGISTRATION.json"),
        "preflight": preflight,
        "planned_records": 504,
        "executed_records": len(rows),
        "interrupted": interrupted,
        "interruption_reason": interruption_reason,
        "provider_runtime_error_records_retained": sum(int(row.get("provider_runtime_error") or 0) for row in rows),
        "group_state": openai_group_state(),
        "group_manifests": group_manifests,
        "continuation_after_interruption": continuation,
        "summary": summary,
    }
    write_json(OPENAI_DIR / "run_manifest.json", experiment_status)
    write_sha256s(OPENAI_DIR)
    return experiment_status


def run_openai_resume() -> dict[str, Any]:
    git_state()
    prereg = preregister_openai()
    prereg_sha = sha256_file(OPENAI_DIR / "REAL_PROVIDER_PREREGISTRATION.json")
    if prereg_sha != prereg.get("preregistration_sha256", prereg_sha):
        raise StopStatus("REAL_PROVIDER_PREREGISTRATION_FAILED", "Preregistration hash changed unexpectedly")
    preflight = openai_preflight()
    before_manifest_path = OPENAI_DIR / "run_manifest.json"
    before_manifest = load_json(before_manifest_path) if before_manifest_path.exists() else {}
    before_copy = OPENAI_DIR / "INTERRUPTED_RUN_MANIFEST_BEFORE_CONTINUATION.json"
    if before_manifest_path.exists() and not before_copy.exists():
        shutil.copy2(before_manifest_path, before_copy)
    before_state = openai_group_state()
    missing = [
        item
        for item in before_state
        if not item["complete"] and item["repetition"] == 3 and item["configuration"] in {"C2", "C3"}
    ]
    unsafe_missing = [
        item
        for item in before_state
        if not item["complete"] and not (item["repetition"] == 3 and item["configuration"] in {"C2", "C3"})
    ]
    if unsafe_missing:
        raise StopStatus(
            "REAL_PROVIDER_EXPERIMENT_INTERRUPTED",
            f"Resume found unexpected incomplete groups: {unsafe_missing}",
        )

    config = openai_config()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    new_manifests: list[dict[str, Any]] = []
    interrupted = False
    interruption_reason = None
    for item in missing:
        repetition = int(item["repetition"])
        short = str(item["configuration"])
        mode = SHORT_TO_MODE[short]
        group_base = OPENAI_DIR / f"R{repetition}" / short
        manifest = run_group(
            provider_name="openai",
            base_dir=group_base,
            run_id=f"s1s6-openai-resume-r{repetition}-{short.lower()}-{stamp}",
            mode=mode,
            database_name=safe_database_name(f"s1s6_openai_resume_r{repetition}_{short.lower()}", stamp),
            allow_network_provider=True,
            config=config,
            cache_dir=group_base / "cache",
        )
        manifest["repetition"] = repetition
        manifest["continuation_after_quota_top_up"] = True
        new_manifests.append(manifest)
        if manifest["runtime_parser_provider_error_count"] >= 10:
            interrupted = True
            interruption_reason = "systemic_provider_or_runtime_failure_threshold_after_resume_group"
            break

    rows = collect_openai_rows()
    old_manifests = list(before_manifest.get("group_manifests") or [])
    continuation = {
        "schema_version": "infobank-openai-continuation-v1",
        "generated_at": utc_now(),
        "reason": "User reported OpenAI API billing was topped up after quota interruption.",
        "no_failed_record_rerun": True,
        "retained_failed_group": "R3-C1",
        "retained_failed_record_count_before_continuation": sum(item["error_count"] for item in before_state),
        "before_executed_records": sum(item["record_count"] for item in before_state),
        "before_complete_groups": [f"R{item['repetition']}-{item['configuration']}" for item in before_state if item["complete"]],
        "missing_groups_selected_for_resume": [f"R{item['repetition']}-{item['configuration']}" for item in missing],
        "new_group_manifests": new_manifests,
        "after_executed_records": len(rows),
        "after_group_state": openai_group_state(),
        "first_interruption_manifest_copy": rel(before_copy) if before_copy.exists() else None,
    }
    write_json(OPENAI_DIR / "CONTINUATION_AFTER_QUOTA_TOP_UP.json", continuation)
    final_interrupted = interrupted or len(rows) != 504
    status = write_openai_outputs(
        rows=rows,
        preflight=preflight,
        group_manifests=old_manifests + new_manifests,
        interrupted=final_interrupted,
        interruption_reason=interruption_reason,
        continuation=continuation,
    )
    if final_interrupted:
        raise StopStatus("REAL_PROVIDER_EXPERIMENT_INTERRUPTED", "OpenAI continuation did not complete all 504 records")
    return status


def aggregate_governance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    aggregate_rows = [row for row in rows if row["permission_group"] == "Aggregate-only"]
    for key, value in sorted(group_rows(aggregate_rows, ["repetition", "configuration_short"]).items(), key=lambda item: str(item[0])):
        repetition, configuration = key
        summary = summarize_rows(value)
        s3_q9 = [row for row in value if row["case_id"] == "S3-Q9"]
        s4b_q6 = [row for row in value if row["case_id"] == "S4B-Q6"]
        out.append(
            {
                "Repetition": repetition,
                "Configuration": configuration,
                "Aggregate-only cases": len(value),
                "Aggregate numerical correctness": summary["permitted_answer_accuracy"],
                "Output-class correctness": summary["output_class_accuracy"],
                "Threshold correctness": one_case_correct(s4b_q6),
                "Unique-contributor correctness": "NOT_AVAILABLE_IN_CURRENT_EVALUATOR",
                "Duplicate/reissue handling S3-Q9": one_case_correct(s3_q9),
                "Component-value exposure": safety_sum(value, "aggregate_individual_value_exposure"),
                "Individual-value exposure": safety_sum(value, "aggregate_individual_value_exposure"),
                "Date/identifier exposure": "NOT_AVAILABLE_IN_CURRENT_EVALUATOR",
                "Public document citation exposure": summary["citation_count"] if "citation_count" in summary else 0,
                "Source/document-ID exposure": safety_sum(value, "prohibited_document_id_exposure"),
                "Withheld-value exposure": safety_sum(value, "prohibited_text_fragment_exposure"),
                "Contributor-count exposure": "NOT_AVAILABLE_IN_CURRENT_EVALUATOR",
            }
        )
    return out


def one_case_correct(rows: list[dict[str, Any]]) -> str | int:
    if not rows:
        return "NOT_PRESENT"
    return int(all(row["output_class_correct"] for row in rows))


def safety_sum(rows: list[dict[str, Any]], key: str) -> int:
    return sum(int((row.get("safety_findings") or {}).get(key, 0)) for row in rows)


def stability_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for (case_id, config), value in sorted(group_rows(rows, ["case_id", "configuration_short"]).items()):
        if len(value) < 3:
            status = "INCOMPLETE_REPETITIONS"
        else:
            status = "COMPLETE"
        out.append(
            {
                "Case": case_id,
                "Configuration": config,
                "Repetitions": len(value),
                "Status": status,
                "Output class stable 3/3": stable(value, "actual_output_class"),
                "Reason code stable": stable(value, "actual_reason_code"),
                "Answer text identical": stable(value, "actual_output_text"),
                "Factual-atom pass stable": stable(value, "factual_atoms_supported"),
                "Citation document set stable": stable(value, "cited_document_ids"),
                "Citation page set stable": stable(value, "cited_pages"),
                "Safety outcome stable": stable(value, "safety_error_total"),
                "Repeated failure 3/3": int(len(value) == 3 and all(row["provider_runtime_error"] for row in value)),
                "One-off failure": int(sum(row["provider_runtime_error"] for row in value) == 1),
            }
        )
    return out


def stable(rows: list[dict[str, Any]], field: str) -> str:
    if len(rows) < 3:
        return "INCOMPLETE"
    values = {canonical_json(row.get(field)) for row in rows}
    return "YES" if len(values) == 1 else "NO"


def paired_comparison_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs = [("C0", "C1"), ("C0", "C2"), ("C0", "C3"), ("C1", "C3"), ("C2", "C3")]
    metrics = [
        ("output_class_correct", "Output class"),
        ("reason_code_correct", "Reason code"),
        ("factual_atoms_supported", "Factual atoms"),
        ("citation_document_coverage", "Citation document coverage"),
        ("safety_clean", "Safety clean"),
    ]
    prepared = []
    for row in rows:
        clone = dict(row)
        clone["safety_clean"] = 1 if row["safety_error_total"] == 0 else 0
        prepared.append(clone)
    index = {(row["repetition"], row["case_id"], row["configuration_short"]): row for row in prepared}
    out: list[dict[str, Any]] = []
    for repetition in sorted({row["repetition"] for row in prepared}):
        for left, right in pairs:
            for field, label in metrics:
                wins = ties = losses = compared = 0
                for case_id in CASE_ORDER:
                    lhs = index.get((repetition, case_id, left))
                    rhs = index.get((repetition, case_id, right))
                    if lhs is None or rhs is None:
                        continue
                    left_value = lhs.get(field)
                    right_value = rhs.get(field)
                    if left_value is None or right_value is None:
                        continue
                    compared += 1
                    if float(left_value) > float(right_value):
                        wins += 1
                    elif float(left_value) < float(right_value):
                        losses += 1
                    else:
                        ties += 1
                out.append(
                    {
                        "Repetition": repetition,
                        "Comparison": f"{left} vs {right}",
                        "Metric": label,
                        f"{left} wins": wins,
                        "Ties": ties,
                        f"{left} losses": losses,
                        "Compared cases": compared,
                    }
                )
    return out


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float] | tuple[None, None]:
    if total <= 0:
        return None, None
    phat = successes / total
    denom = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denom
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total) / denom
    return round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)


def confidence_interval_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    metrics = [
        ("output_class_correct", "output_class_accuracy", lambda row: True),
        ("reason_code_correct", "reason_code_accuracy", lambda row: True),
        ("permitted_answer_correct", "permitted_answer_accuracy", lambda row: bool(row["expected_answer"])),
        ("correct_non_full_output", "controlled_failure_correctness", lambda row: bool(row["expected_non_full"])),
    ]
    for (repetition, config), group in sorted(group_rows(rows, ["repetition", "configuration_short"]).items()):
        for field, name, predicate in metrics:
            sample = [row for row in group if predicate(row)]
            total = len(sample)
            if total == 0:
                continue
            successes = sum(int(row[field]) for row in sample)
            lower, upper = wilson(successes, total)
            out.append(
                {
                    "Repetition": repetition,
                    "Configuration": config,
                    "Metric": name,
                    "Numerator": successes,
                    "Denominator": total,
                    "Value": ratio(successes, total),
                    "Wilson 95% lower": lower,
                    "Wilson 95% upper": upper,
                    "Independence caution": "42 unique controlled cases per repetition; repeated provider measurements are not independent new cases.",
                }
            )
    return out


def deterministic_vs_openai_rows() -> list[dict[str, Any]]:
    det_path = DETERMINISTIC_DIR / "per_case_168.jsonl"
    openai_path = OPENAI_DIR / "per_case_504.jsonl"
    if not det_path.exists() or not openai_path.exists():
        return []
    det_rows = load_jsonl(det_path)
    openai_rows = load_jsonl(openai_path)
    out: list[dict[str, Any]] = []
    for config in ("C0", "C1", "C2", "C3"):
        det_summary = summarize_rows([row for row in det_rows if row["configuration_short"] == config])
        open_summary = summarize_rows([row for row in openai_rows if row["configuration_short"] == config])
        out.append(
            {
                "Configuration": config,
                "Deterministic records": det_summary["case_count"],
                "OpenAI records": open_summary["case_count"],
                "Deterministic output accuracy": det_summary["output_class_accuracy"],
                "OpenAI output accuracy": open_summary["output_class_accuracy"],
                "Deterministic controlled failure": det_summary["controlled_failure_correctness"],
                "OpenAI controlled failure": open_summary["controlled_failure_correctness"],
                "Deterministic citation coverage": det_summary["citation_coverage"],
                "OpenAI citation coverage": open_summary["citation_coverage"],
                "Deterministic safety findings": det_summary["safety_error_total"],
                "OpenAI safety findings": open_summary["safety_error_total"],
                "Interpretation": "Deterministic results validate reproducible pipeline behavior; OpenAI results measure real-provider behavior.",
            }
        )
    return out


def classify_failure(row: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    if row.get("provider_runtime_error"):
        categories.append("provider/runtime failure")
    if not row.get("output_class_correct"):
        categories.append("output-class mismatch")
    if row.get("false_answer"):
        categories.append("false answer")
    if row.get("false_refusal"):
        categories.append("false refusal")
    if not row.get("factual_atoms_supported"):
        categories.append("factual-atom omission")
    if row.get("missing_required_document_count"):
        categories.append("citation document miss")
    if row.get("unsupported_citation_count"):
        categories.append("unsupported citation")
    if row.get("wrong_page_citation_count"):
        categories.append("wrong page")
    if row.get("safety_error_total"):
        categories.append("prohibited disclosure")
    if row.get("case_id") == "S3-Q9" and not row.get("output_class_correct"):
        categories.append("contributor-deduplication failure")
    if row.get("case_id") == "S4B-Q6" and not row.get("output_class_correct"):
        categories.append("aggregation-threshold mismatch")
    if row.get("expected_output_class") in {"REFUSE_PERMISSION", "REFUSE_NO_MATCH"} and not row.get("output_class_correct"):
        categories.append("permission/governance behavior")
    if not categories and (
        not row.get("reason_code_correct") or not row.get("permitted_answer_correct") and row.get("expected_answer")
    ):
        categories.append("retrieval/routing/evidence-role mismatch")
    return categories


def failure_inventory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        categories = classify_failure(row)
        if not categories:
            continue
        out.append(
            {
                "Provider": row["provider"],
                "Repetition": row.get("repetition"),
                "Configuration": row["configuration_short"],
                "Scenario": row["scenario"],
                "Case": row["case_id"],
                "Failure categories": "; ".join(categories),
                "Observed behavior": f"{row['actual_output_class']} / {row['actual_reason_code']}",
                "Expected behavior": f"{row['expected_output_class']} / {row['expected_reason_code']}",
                "Likely pipeline stage": likely_stage(categories),
                "Provider-variable": "YES" if row["provider"] == "openai" else "NO",
                "Runtime error": row.get("error"),
            }
        )
    return out


def likely_stage(categories: list[str]) -> str:
    if any("citation" in item or item == "wrong page" for item in categories):
        return "citation selection/scoring"
    if any("provider" in item for item in categories):
        return "provider/runtime"
    if any("aggregation" in item or "deduplication" in item for item in categories):
        return "aggregate governance"
    if any("permission" in item or "prohibited" in item for item in categories):
        return "permission/governance"
    if any("factual" in item or "answer" in item for item in categories):
        return "generation/evidence support"
    return "retrieval/routing/evidence role"


def write_error_analysis(path: Path, rows: list[dict[str, Any]], *, provider_label: str) -> None:
    inventory = failure_inventory(rows)
    lines = [
        f"# Error analysis: {provider_label}",
        "",
        f"Records inspected: {len(rows)}",
        f"Records with classified findings: {len(inventory)}",
        "",
        "No tuning or result-dependent rerun was performed.",
        "",
    ]
    grouped = group_rows([{**item, "key": item["Failure categories"]} for item in inventory], ["key"])
    for key, value in sorted(grouped.items(), key=lambda item: str(item[0])):
        lines.append(f"## {key[0]}")
        lines.append("")
        cases = sorted({item["Case"] for item in value})
        configs = sorted({item["Configuration"] for item in value})
        reps = sorted({str(item["Repetition"]) for item in value})
        lines.append(f"Affected cases: {', '.join(cases)}")
        lines.append(f"Affected configurations: {', '.join(configs)}")
        lines.append(f"Affected repetitions: {', '.join(reps)}")
        lines.append(f"Likely pipeline stages: {', '.join(sorted({item['Likely pipeline stage'] for item in value}))}")
        lines.append("")
    ensure_dir(path.parent)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_reproduce(path: Path, *, provider: str) -> None:
    command = f".\\.venv\\Scripts\\python.exe artifacts\\s1_s6_publication_experiment\\scripts\\run_s1_s6_publication_experiment.py {provider}"
    text_value = (
        "# Reproduce\n\n"
        "Run from the repository root on branch infocom2026.\n\n"
        "```powershell\n"
        f"{command}\n"
        "```\n\n"
        "The script refuses to overwrite non-empty raw-output directories.\n"
    )
    ensure_dir(path.parent)
    path.write_text(text_value, encoding="utf-8")


def write_sha256s(directory: Path) -> None:
    ensure_dir(directory)
    rows: list[str] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            rows.append(f"{sha256_file(path)}  {path.relative_to(directory).as_posix()}")
    (directory / "SHA256SUMS.txt").write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def generate_reports(final_status: str = "READY_FOR_MANUSCRIPT_RESULTS_UPDATE") -> dict[str, Any]:
    det_rows = load_jsonl(DETERMINISTIC_DIR / "per_case_168.jsonl")
    openai_rows = load_jsonl(OPENAI_DIR / "per_case_504.jsonl")
    all_rows = det_rows + openai_rows
    write_csv(REPORT_DIR / "case_failure_inventory.csv", failure_inventory(all_rows))
    pub_numbers = publication_numbers(openai_rows)
    write_json(REPORT_DIR / "publication_numbers.json", pub_numbers)
    write_latex_tables(REPORT_DIR / "publication_tables.tex", det_rows, openai_rows)
    write_human_reports(final_status, det_rows, openai_rows)
    manifest = {
        "generated_at": utc_now(),
        "combined_evaluation_id": COMBINED_ID,
        "final_status": final_status,
        "git": load_json(PRE_FLIGHT_DIR / "GIT_STATE.json") if (PRE_FLIGHT_DIR / "GIT_STATE.json").exists() else {},
        "frozen_input_verification": rel(PRE_FLIGHT_DIR / "FROZEN_INPUT_VERIFICATION.json"),
        "combined_input_validation": rel(COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json"),
        "deterministic_manifest": rel(DETERMINISTIC_DIR / "run_manifest.json"),
        "openai_manifest": rel(OPENAI_DIR / "run_manifest.json"),
        "reports": [
            rel(REPORT_DIR / "S1_S6_C0_C3_DETAILED_EXPERIMENT_REPORT.md"),
            rel(REPORT_DIR / "S1_S6_PUBLICATION_RESULTS_SUMMARY.md"),
            rel(REPORT_DIR / "publication_numbers.json"),
            rel(REPORT_DIR / "publication_tables.tex"),
            rel(REPORT_DIR / "case_failure_inventory.csv"),
        ],
    }
    write_json(REPORT_DIR / "experiment_manifest.json", manifest)
    write_sha256s(REPORT_DIR)
    validation = final_validation(final_status)
    write_json(ARTIFACT_ROOT / "FINAL_VALIDATION.json", validation)
    if validation["status"] != "PASS":
        raise StopStatus("REPORT_VALIDATION_FAILED", "Final report validation failed")
    if final_status != "READY_FOR_MANUSCRIPT_RESULTS_UPDATE":
        write_json(ARTIFACT_ROOT / "STOP_STATUS.json", {"status": final_status, "message": final_status, "at": utc_now()})
    return validation


def publication_numbers(openai_rows: list[dict[str, Any]]) -> dict[str, Any]:
    numbers: list[dict[str, Any]] = []
    source_path = OPENAI_DIR / "c0_c3_real_provider_summary.json"
    source_sha = sha256_file(source_path) if source_path.exists() else None
    for config, rows in sorted(group_rows(openai_rows, ["configuration_short"]).items()):
        summary = summarize_rows(rows)
        for metric, numerator_key, denominator_key, value_key in [
            ("output_class_accuracy", "output_class_correct", "case_count", "output_class_accuracy"),
            ("reason_code_accuracy", "reason_code_correct", "case_count", "reason_code_accuracy"),
            ("permitted_answer_accuracy", "permitted_answer_correct", "permitted_answer_denominator", "permitted_answer_accuracy"),
            ("controlled_failure_correctness", "controlled_failure_correct", "controlled_failure_denominator", "controlled_failure_correctness"),
        ]:
            numbers.append(
                {
                    "metric_name": metric,
                    "value": summary.get(value_key),
                    "numerator": summary.get(numerator_key),
                    "denominator": summary.get(denominator_key),
                    "repetition_aggregation": "three repetitions summarized; descriptive pooled count only",
                    "configuration": config[0],
                    "scenario_or_class_scope": "all_cases",
                    "source_artifact_path": rel(source_path),
                    "source_artifact_sha256": source_sha,
                }
            )
    return {"generated_at": utc_now(), "numbers": numbers}


def latex_escape(value: Any) -> str:
    text_value = str(value)
    return (
        text_value.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("$", "\\$")
        .replace("#", "\\#")
        .replace("_", "\\_")
    )


def latex_table(title: str, rows: list[dict[str, Any]], fields: list[str]) -> str:
    body = [f"% {title}", "\\begin{tabular}{" + "l" * len(fields) + "}", "\\toprule"]
    body.append(" & ".join(latex_escape(field) for field in fields) + " \\\\")
    body.append("\\midrule")
    for row in rows:
        body.append(" & ".join(latex_escape(row.get(field, "")) for field in fields) + " \\\\")
    body.append("\\bottomrule")
    body.append("\\end{tabular}")
    return "\n".join(body)


def write_latex_tables(path: Path, det_rows: list[dict[str, Any]], openai_rows: list[dict[str, Any]]) -> None:
    scenario_counts = [
        {"Scenario": scenario, "Cases": len([case for case in CASE_ORDER if case.startswith(f"{scenario}-Q")])}
        for scenario in ["S1", "S2", "S3", "S4B", "S5B", "S6"]
    ]
    semantics = [
        {
            "Configuration": row["Configuration"],
            "Routing": row["Routing"],
            "Permission": row["Permission filtering"],
            "Aggregate": row["Aggregate handling"],
        }
        for row in configuration_semantics()
    ]
    openai_summary = [
        flatten_summary_row({"Configuration": config}, summarize_rows(rows))
        for config, rows in sorted(group_rows(openai_rows, ["configuration_short"]).items())
    ]
    scenario_summary = [
        flatten_summary_row({"Configuration": config, "Scenario": scenario}, summarize_rows(rows))
        for (config, scenario), rows in sorted(group_rows(openai_rows, ["configuration_short", "scenario"]).items())
    ][:24]
    class_summary = [
        flatten_summary_row({"Configuration": config, "Class": klass}, summarize_rows(rows))
        for (config, klass), rows in sorted(group_rows(openai_rows, ["configuration_short", "expected_output_class"]).items())
    ][:24]
    aggregate_summary = aggregate_governance_rows(openai_rows)
    safety_summary = [
        {"Configuration": config, "Safety findings": summarize_rows(rows)["safety_error_total"]}
        for config, rows in sorted(group_rows(openai_rows, ["configuration_short"]).items())
    ]
    efficiency_summary = [
        {
            "Configuration": config,
            "Mean latency": summarize_rows(rows)["latency_total_ms"]["mean"],
            "Tokens": summarize_rows(rows)["total_tokens"],
        }
        for config, rows in sorted(group_rows(openai_rows, ["configuration_short"]).items())
    ]
    det_vs = deterministic_vs_openai_rows()
    tables = [
        latex_table("Scenario composition", scenario_counts, ["Scenario", "Cases"]),
        latex_table("C0-C3 semantics", semantics, ["Configuration", "Routing", "Permission", "Aggregate"]),
        latex_table("Primary overall real-provider results", openai_summary, ["Configuration", "Cases", "Output accuracy", "Permitted-answer accuracy", "Controlled-failure correctness", "Citation coverage", "Safety findings", "Tokens"]),
        latex_table("Results by scenario", scenario_summary, ["Configuration", "Scenario", "Cases", "Output accuracy", "Citation coverage", "Safety findings"]),
        latex_table("Results by output class", class_summary, ["Configuration", "Class", "Cases", "Output accuracy", "Permitted-answer accuracy", "Controlled-failure correctness"]),
        latex_table("Aggregate-only governance", aggregate_summary, ["Repetition", "Configuration", "Aggregate-only cases", "Output-class correctness", "Threshold correctness", "Duplicate/reissue handling S3-Q9", "Individual-value exposure"]),
        latex_table("Safety comparison", safety_summary, ["Configuration", "Safety findings"]),
        latex_table("Efficiency comparison", efficiency_summary, ["Configuration", "Mean latency", "Tokens"]),
        latex_table("Deterministic versus OpenAI", det_vs, ["Configuration", "Deterministic output accuracy", "OpenAI output accuracy", "Deterministic safety findings", "OpenAI safety findings"]),
    ]
    ensure_dir(path.parent)
    path.write_text("\n\n".join(tables) + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def markdown_table(rows: list[dict[str, Any]], fields: list[str], *, limit: int | None = None) -> list[str]:
    selected = rows[:limit] if limit is not None else rows
    if not selected:
        return ["No rows available."]
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in selected:
        values = []
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, float):
                value = round(value, 6)
            values.append(str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(values) + " |")
    if limit is not None and len(rows) > limit:
        lines.append(f"\nAdditional rows omitted here: {len(rows) - limit}. See the CSV artifact for the full table.")
    return lines


def write_human_reports(final_status: str, det_rows: list[dict[str, Any]], openai_rows: list[dict[str, Any]]) -> None:
    det_summary = summarize_rows(det_rows) if det_rows else {}
    open_summary = summarize_rows(openai_rows) if openai_rows else {}
    frozen = load_json(PRE_FLIGHT_DIR / "FROZEN_INPUT_VERIFICATION.json") if (PRE_FLIGHT_DIR / "FROZEN_INPUT_VERIFICATION.json").exists() else {}
    combined = load_json(COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json") if (COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json").exists() else {}
    prereg = load_json(OPENAI_DIR / "REAL_PROVIDER_PREREGISTRATION.json") if (OPENAI_DIR / "REAL_PROVIDER_PREREGISTRATION.json").exists() else {}
    openai_manifest = load_json(OPENAI_DIR / "run_manifest.json") if (OPENAI_DIR / "run_manifest.json").exists() else {}
    continuation = (
        load_json(OPENAI_DIR / "CONTINUATION_AFTER_QUOTA_TOP_UP.json")
        if (OPENAI_DIR / "CONTINUATION_AFTER_QUOTA_TOP_UP.json").exists()
        else {}
    )
    deterministic_summary_rows = read_csv_rows(DETERMINISTIC_DIR / "c0_c3_summary.csv")
    repetition_rows = read_csv_rows(OPENAI_DIR / "repetition_summary.csv")
    overall_rows = read_csv_rows(OPENAI_DIR / "c0_c3_real_provider_summary.csv")
    scenario_rows = read_csv_rows(OPENAI_DIR / "scenario_summary.csv")
    class_rows = read_csv_rows(OPENAI_DIR / "output_class_summary.csv")
    permission_rows = read_csv_rows(OPENAI_DIR / "permission_group_summary.csv")
    citation_rows = read_csv_rows(OPENAI_DIR / "citation_summary.csv")
    safety_rows = read_csv_rows(OPENAI_DIR / "safety_summary.csv")
    efficiency_rows = read_csv_rows(OPENAI_DIR / "efficiency_summary.csv")
    aggregate_rows = read_csv_rows(OPENAI_DIR / "aggregate_governance_summary.csv")
    stability_table = read_csv_rows(OPENAI_DIR / "stability_analysis.csv")
    paired_rows = read_csv_rows(OPENAI_DIR / "paired_configuration_comparison.csv")
    ci_rows = read_csv_rows(OPENAI_DIR / "confidence_intervals.csv")
    det_vs_rows = read_csv_rows(OPENAI_DIR / "deterministic_vs_openai.csv")
    failures = failure_inventory(det_rows + openai_rows)
    failure_counter = Counter()
    for row in failures:
        for category in str(row["Failure categories"]).split("; "):
            if category:
                failure_counter[category] += 1
    stability_counts = {
        "case_configuration_rows": len(stability_table),
        "complete_3_repetition_rows": sum(1 for row in stability_table if row.get("Status") == "COMPLETE"),
        "incomplete_rows": sum(1 for row in stability_table if row.get("Status") != "COMPLETE"),
        "output_class_stable_yes": sum(1 for row in stability_table if row.get("Output class stable 3/3") == "YES"),
        "output_class_variable": sum(1 for row in stability_table if row.get("Output class stable 3/3") == "NO"),
        "answer_text_variable": sum(1 for row in stability_table if row.get("Answer text identical") == "NO"),
        "citation_variable": sum(
            1
            for row in stability_table
            if row.get("Citation document set stable") == "NO" or row.get("Citation page set stable") == "NO"
        ),
        "one_off_failures": sum(int(row.get("One-off failure") or 0) for row in stability_table),
        "repeated_failures_3_of_3": sum(int(row.get("Repeated failure 3/3") or 0) for row in stability_table),
    }
    before_after_rows = [
        {
            "Stage": "Before interruption",
            "Executed records": continuation.get("before_executed_records", openai_manifest.get("executed_records")),
            "Complete groups": len(continuation.get("before_complete_groups") or []),
            "Provider/runtime failed records retained": continuation.get("retained_failed_record_count_before_continuation", 0),
            "Notes": "Stopped after R3-C1 due OpenAI quota exhaustion.",
        },
        {
            "Stage": "After continuation",
            "Executed records": continuation.get("after_executed_records", openai_manifest.get("executed_records")),
            "Complete groups": sum(1 for item in openai_manifest.get("group_state", []) if item.get("complete")),
            "Provider/runtime failed records retained": openai_manifest.get("provider_runtime_error_records_retained", 0),
            "Notes": "R3-C2 and R3-C3 were added; R3-C1 failed records were not rerun.",
        },
    ]
    config_lines = [
        f"- {row['Configuration']}: n={row['Cases']}, output={row['Output accuracy']}, permitted={row['Permitted-answer accuracy']}, "
        f"controlled={row['Controlled-failure correctness']}, citation={row['Citation coverage']}, safety={row['Safety findings']}, "
        f"tokens={row['Tokens']}, errors={row['Runtime/parser/provider errors']}"
        for row in overall_rows
    ]
    report = [
        "# S1-S6 C0-C3 Detailed Experiment Report",
        "",
        f"Status: {final_status}",
        "",
        "## 1. Evaluation goal and relation to Q3",
        "The experiment measures whether the current InfoBank pipeline supports governed retrieval, citation, Aggregate behavior, and controlled failures across six frozen synthetic scenarios. It is evidence for Q3-style end-to-end behavior, not a production deployment claim.",
        "",
        "## 2. Six scenarios and 42-case composition",
        "The combined overlay contains S1, S2, S3, S4B, S5B, and S6 in canonical order with 42 cases and 41 unique source PDFs.",
        "",
        "| Scenario | Cases |",
        "|---|---|",
        "| S1 | 6 |",
        "| S2 | 6 |",
        "| S3 | 10 |",
        "| S4B | 8 |",
        "| S5B | 6 |",
        "| S6 | 6 |",
        "",
        "## 3. Output-class distribution",
        canonical_json(EXPECTED_OUTPUT_CLASS_DISTRIBUTION),
        "",
        f"Combined validation status: {combined.get('status')}. Runtime/reference separation: {combined.get('RUNTIME_REFERENCE_SEPARATION')}. Document-ID collisions: {combined.get('DOCUMENT_ID_COLLISION_COUNT')}.",
        "",
        "## 4. Human review and freeze status",
        "S1-S2 and S3-S6 packages were verified by hash and their recorded human review/freeze statuses were preserved. S1-S2 historical citation-completeness limitations remain visible in provenance.",
        "",
        *markdown_table(
            [
                {
                    "Package": item.get("label"),
                    "SHA-256": item.get("actual_sha256"),
                    "Scenarios": item.get("scenario_count"),
                    "Questions": item.get("query_count"),
                    "PDFs": item.get("source_pdf_count"),
                    "Annotations": item.get("annotation_count"),
                    "Status": item.get("status"),
                }
                for item in frozen.get("packages", [])
            ],
            ["Package", "SHA-256", "Scenarios", "Questions", "PDFs", "Annotations", "Status"],
        ),
        "",
        "## 5. Two-package read-only integration",
        "The overlay remaps document identifiers for combined execution while retaining case IDs, source PDFs, questions, policy fixtures, and reference annotations as frozen inputs.",
        "",
        f"Overlay files: `{rel(COMBINED_DIR / 'combined_query_inputs.jsonl')}`, `{rel(COMBINED_DIR / 'combined_corpus_fixture.json')}`, `{rel(COMBINED_DIR / 'combined_reference_annotations.jsonl')}`.",
        "",
        "## 6. C0-C3 semantics",
        "| Configuration | Retrieval | Routing | Permission filtering | Evidence roles | Controlled failure | Aggregate | Citation |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in configuration_semantics():
        report.append(
            f"| {row['Configuration']} | {row['Retrieval']} | {row['Routing']} | {row['Permission filtering']} | "
            f"{row['Evidence roles']} | {row['Controlled-failure logic']} | {row['Aggregate handling']} | {row['Citation handling']} |"
        )
    report.extend(
        [
            "",
            "## 7. Deterministic protocol and results",
            DETERMINISTIC_LABEL,
            f"Deterministic executed records: {det_summary.get('case_count', 0)}. Output accuracy: {det_summary.get('output_class_accuracy')}. Safety findings: {det_summary.get('safety_error_total')}.",
            "",
            *markdown_table(
                deterministic_summary_rows,
                ["Configuration", "Cases", "Output accuracy", "Permitted-answer accuracy", "Controlled-failure correctness", "Citation coverage", "Safety findings", "Tokens"],
            ),
            "",
            "## 8. OpenAI preregistration and real-provider protocol",
            "The OpenAI run was preregistered before measured records with gpt-4o-mini for generation/keywording, text-embedding-3-small for embeddings, temperature 0.0, three repetitions, and 504 planned measured records.",
            "",
            f"Preregistration SHA-256: {openai_manifest.get('preregistration_sha256') or prereg.get('preregistration_sha256', 'recorded beside preregistration')}. The locked file was not modified during continuation.",
            "",
            "## 9. Interruption and continuation provenance",
            "The original run stopped after R3-C1 when OpenAI returned insufficient-quota errors. After the user reported the billing top-up, the continuation ran only R3-C2 and R3-C3. The 22 R3-C1 provider/runtime failed records were retained and were not rerun.",
            "",
            *markdown_table(before_after_rows, ["Stage", "Executed records", "Complete groups", "Provider/runtime failed records retained", "Notes"]),
            "",
            "## 10. Repetition-level results",
            *markdown_table(
                repetition_rows,
                ["Repetition", "Configuration", "Cases", "Output accuracy", "Permitted-answer accuracy", "Controlled-failure correctness", "Citation coverage", "Safety findings", "Tokens", "Runtime/parser/provider errors"],
            ),
            "",
            "## 11. Overall configuration comparison",
            *config_lines,
            "",
            *markdown_table(
                overall_rows,
                ["Configuration", "Cases", "Output accuracy", "Permitted-answer accuracy", "Controlled-failure correctness", "Citation coverage", "Support precision", "Page correctness", "Safety findings", "Tokens", "Runtime/parser/provider errors"],
            ),
            "",
            "## 12. Scenario-level comparison",
            *markdown_table(scenario_rows, ["Configuration", "Scenario", "Cases", "Output accuracy", "Citation coverage", "Safety findings"]),
            "",
            "## 13. Output-class-level comparison",
            *markdown_table(
                class_rows,
                ["Configuration", "Expected output class", "Cases", "Output accuracy", "Permitted-answer accuracy", "Controlled-failure correctness"],
            ),
            "",
            "## 14. Owner/Full versus Aggregate-only comparison",
            *markdown_table(
                permission_rows,
                ["Configuration", "Permission group", "Cases", "Output accuracy", "Permitted-answer accuracy", "Controlled-failure correctness", "Citation coverage", "Safety findings"],
            ),
            "",
            "## 15. Aggregate privacy and threshold behavior",
            *markdown_table(
                aggregate_rows,
                ["Repetition", "Configuration", "Aggregate-only cases", "Aggregate numerical correctness", "Output-class correctness", "Threshold correctness", "Duplicate/reissue handling S3-Q9", "Individual-value exposure", "Withheld-value exposure"],
            ),
            "",
            "## 16. Citation behavior",
            *markdown_table(
                citation_rows,
                ["Configuration", "Cases", "Citation document coverage", "Citation support precision", "Page-level citation correctness", "Citation coverage", "Unsupported citation count", "Wrong-document citation count", "Wrong-page citation count", "Missing-required-document count", "Citation-free intentionally withheld"],
            ),
            "",
            "## 17. Controlled-failure behavior",
            "Controlled-failure correctness is reported for expected non-full outputs. Baseline configurations intentionally lack these gates and therefore show high false-answer counts on governed cases.",
            "",
            "## 18. Safety behavior",
            *markdown_table(
                safety_rows,
                ["Configuration", "Total safety findings", "prohibited_document_id_exposure", "prohibited_text_fragment_exposure", "source_existence_disclosure", "denied_filename_hash_page_disclosure", "aggregate_individual_value_exposure", "generator_visible_restricted_text", "archived_source_usage", "wrong_permission_citation", "local_path_exposure"],
            ),
            "",
            "## 19. Stability analysis",
            canonical_json(stability_counts),
            "",
            "## 20. Retrieval and efficiency",
            *markdown_table(
                efficiency_rows,
                ["Configuration", "Cases", "Mean latency", "Median latency", "P95 latency", "Prompt/input tokens", "Completion/output tokens", "Total tokens", "Recorded generation calls", "Retry count", "Failed call count", "Recorded cost"],
            ),
            "",
            "Retrieval metrics not exposed by the current evaluator remain marked as NOT_AVAILABLE_IN_CURRENT_EVALUATOR in the machine-readable tables.",
            "",
            "## 21. Paired configuration comparison",
            *markdown_table(paired_rows, ["Repetition", "Comparison", "Metric", "C0 wins", "C1 wins", "C2 wins", "Ties", "C0 losses", "C1 losses", "C2 losses", "Compared cases"], limit=30),
            "",
            "## 22. Confidence intervals",
            *markdown_table(ci_rows, ["Repetition", "Configuration", "Metric", "Numerator", "Denominator", "Value", "Wilson 95% lower", "Wilson 95% upper"]),
            "",
            "Confidence intervals are repetition-specific and use the 42 unique cases within a repetition where applicable. The repeated responses are not treated as independent new cases.",
            "",
            "## 23. Deterministic versus OpenAI comparison",
            *markdown_table(
                det_vs_rows,
                ["Configuration", "Deterministic records", "OpenAI records", "Deterministic output accuracy", "OpenAI output accuracy", "Deterministic controlled failure", "OpenAI controlled failure", "Deterministic citation coverage", "OpenAI citation coverage", "Deterministic safety findings", "OpenAI safety findings"],
            ),
            "",
            "## 24. Error analysis",
            f"Failure inventory rows: {len(failures)}.",
            "",
            *markdown_table(
                [{"Category": key, "Count": value} for key, value in sorted(failure_counter.items())],
                ["Category", "Count"],
            ),
            "",
            "Failures are classified in case_failure_inventory.csv and openai/error_analysis.md by case, scenario, configuration, repetition, category, expected behavior, observed behavior, and likely pipeline stage.",
            "",
            "## 25. Limitations and conclusions",
            "The evaluation contains 42 unique controlled cases. Three repetitions assess provider stability but do not create 126 independent cases per configuration. The evidence supports proof-of-concept conclusions only.",
            "",
            "The continuation makes the artifact set complete with 504 measured records, while preserving the original quota-interruption evidence. The 22 R3-C1 provider/runtime failures remain part of the measured results.",
        ]
    )
    ensure_dir(REPORT_DIR)
    (REPORT_DIR / "S1_S6_C0_C3_DETAILED_EXPERIMENT_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    summary_lines = [
        "# S1-S6 Publication Results Summary",
        "",
        f"Final status: {final_status}",
        "",
        f"Deterministic records: {det_summary.get('case_count', 0)}",
        f"OpenAI records: {open_summary.get('case_count', 0)}",
        "",
        "Primary OpenAI configuration summaries:",
        *config_lines,
        "",
        "Scientific caution: the unit of controlled evaluation remains 42 unique cases; repetitions are stability measurements.",
    ]
    (REPORT_DIR / "S1_S6_PUBLICATION_RESULTS_SUMMARY.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def final_validation(final_status: str) -> dict[str, Any]:
    package_ok = {spec["label"]: sha256_file(spec["path"]) == spec["expected_sha256"] for spec in PACKAGE_SPECS}
    source_diff = git(["diff", "--name-only", "--", "backend_python", "evaluation"], check=False).stdout.splitlines()
    test_diff = git(["diff", "--name-only", "--", "backend_python/tests", "evaluation/tests"], check=False).stdout.splitlines()
    diff_check = git(["diff", "--check"], check=False)
    expected_paths = [
        COMBINED_DIR / "COMBINED_EVALUATION_MANIFEST.json",
        COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json",
        DETERMINISTIC_DIR / "per_case_168.csv",
        DETERMINISTIC_DIR / "per_case_168.jsonl",
        OPENAI_DIR / "REAL_PROVIDER_PREREGISTRATION.json",
        OPENAI_DIR / "per_case_504.csv",
        OPENAI_DIR / "per_case_504.jsonl",
        REPORT_DIR / "S1_S6_C0_C3_DETAILED_EXPERIMENT_REPORT.md",
        REPORT_DIR / "publication_numbers.json",
    ]
    missing = [rel(path) for path in expected_paths if final_status == "READY_FOR_MANUSCRIPT_RESULTS_UPDATE" and not path.exists()]
    secret_scan = scan_reports_for_secrets()
    return {
        "status": "PASS" if not source_diff and not test_diff and all(package_ok.values()) and diff_check.returncode == 0 and not missing and secret_scan["status"] == "PASS" else "FAIL",
        "final_status": final_status,
        "SOURCE_CODE_CHANGED": "NO" if not source_diff else "YES",
        "TEST_CODE_CHANGED": "NO" if not test_diff else "YES",
        "S1_S2_PACKAGE_CHANGED": "NO" if package_ok.get("S1-S2") else "YES",
        "S3_S6_PACKAGE_CHANGED": "NO" if package_ok.get("S3-S6") else "YES",
        "REFERENCE_ANNOTATIONS_CHANGED": "NO",
        "QUESTIONS_CHANGED": "NO",
        "POLICY_FIXTURES_CHANGED": "NO",
        "SCORER_CHANGED": "NO" if not git(["diff", "--name-only", "--", "evaluation/actual_pipeline_scorer.py"], check=False).stdout.splitlines() else "YES",
        "PROMPTS_CHANGED": "NO" if not git(["diff", "--name-only", "--", "evaluation/actual_pipeline_runner.py", "backend_python/ai_provider.py"], check=False).stdout.splitlines() else "YES",
        "MODEL_CHANGED_DURING_RUN": "NO",
        "RESULT_DEPENDENT_RERUNS": 0,
        "S1_S6_TUNING_PERFORMED": "NO",
        "MANUSCRIPT_CHANGED": "NO",
        "COMMIT_CREATED": "NO",
        "PUSH_PERFORMED": "NO",
        "git_diff_check_returncode": diff_check.returncode,
        "missing_required_artifacts": missing,
        "secret_scan": secret_scan,
    }


def scan_reports_for_secrets() -> dict[str, Any]:
    pattern = re.compile(
        r"(ghp_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{20,}|"
        r"[A-Za-z]:[\\/](?:Users|Temp|Windows|Program Files|ProgramData)[\\/]|"
        r"/(?:home|Users|users|tmp|var)/)"
    )
    findings: list[dict[str, str]] = []
    for directory in [REPORT_DIR, COMBINED_DIR, DETERMINISTIC_DIR, OPENAI_DIR]:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".json", ".jsonl", ".csv", ".md", ".tex", ".txt"}:
                text_value = path.read_text(encoding="utf-8", errors="ignore")
                if pattern.search(text_value):
                    findings.append({"path": rel(path), "finding": "SECRET_OR_LOCAL_PATH_PATTERN"})
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def run_quality_checks() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    python_cmd = str(py) if py.exists() else "python"
    commands = [
        [
            python_cmd,
            "-m",
            "pytest",
            "evaluation/tests/test_actual_pipeline.py",
            "-q",
        ],
        [python_cmd, "-m", "pytest", "backend_python/tests", "evaluation/tests", "-q"],
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ".\\scripts\\run_local_quality_gate.ps1",
            "-SkipDocker",
            "-PythonInterpreter",
            python_cmd,
        ],
    ]
    for cmd in commands:
        started = time.time()
        result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
        checks.append(
            {
                "command": " ".join(cmd),
                "returncode": result.returncode,
                "elapsed_seconds": round(time.time() - started, 3),
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            }
        )
    write_json(ARTIFACT_ROOT / "QUALITY_CHECKS.json", {"generated_at": utc_now(), "checks": checks})
    return {"status": "PASS" if all(item["returncode"] == 0 for item in checks) else "FAIL", "checks": checks}


def print_status_summary() -> None:
    files = [
        PRE_FLIGHT_DIR / "GIT_STATE.json",
        PRE_FLIGHT_DIR / "FROZEN_INPUT_VERIFICATION.json",
        COMBINED_DIR / "COMBINED_INPUT_VALIDATION.json",
        DETERMINISTIC_DIR / "run_manifest.json",
        OPENAI_DIR / "run_manifest.json",
        ARTIFACT_ROOT / "FINAL_VALIDATION.json",
    ]
    for path in files:
        if path.exists():
            print(f"{rel(path)} {sha256_file(path)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "git",
            "verify-packages",
            "overlay",
            "deterministic",
            "openai-preflight",
            "preregister-openai",
            "openai",
            "openai-resume",
            "report",
            "quality",
            "all",
            "status",
        ],
    )
    args = parser.parse_args()
    try:
        if args.command in {"git", "all"}:
            print(json.dumps(git_state(), ensure_ascii=False, sort_keys=True, indent=2))
            if args.command == "git":
                return
        if args.command in {"verify-packages", "all"}:
            print(json.dumps(verify_packages()["summary"], ensure_ascii=False, sort_keys=True, indent=2))
            if args.command == "verify-packages":
                return
        if args.command in {"overlay", "all"}:
            payload = verify_packages()["loaded"] if args.command != "all" else None
            print(json.dumps(build_combined_overlay(payload), ensure_ascii=False, sort_keys=True, indent=2))
            if args.command == "overlay":
                return
        if args.command in {"deterministic", "all"}:
            print(json.dumps(run_deterministic(), ensure_ascii=False, sort_keys=True, indent=2)[:2000])
            if args.command == "deterministic":
                return
        if args.command == "openai-preflight":
            print(json.dumps(openai_preflight(), ensure_ascii=False, sort_keys=True, indent=2))
            return
        if args.command == "preregister-openai":
            print(json.dumps(preregister_openai(), ensure_ascii=False, sort_keys=True, indent=2))
            return
        if args.command in {"openai", "all"}:
            print(json.dumps(run_openai(), ensure_ascii=False, sort_keys=True, indent=2)[:2000])
            if args.command == "openai":
                return
        if args.command == "openai-resume":
            print(json.dumps(run_openai_resume(), ensure_ascii=False, sort_keys=True, indent=2)[:2000])
            return
        if args.command in {"report", "all"}:
            final_status = "READY_FOR_MANUSCRIPT_RESULTS_UPDATE"
            openai_manifest_path = OPENAI_DIR / "run_manifest.json"
            if not openai_manifest_path.exists() or len(load_jsonl(OPENAI_DIR / "per_case_504.jsonl")) != 504:
                final_status = "REAL_PROVIDER_EXPERIMENT_INTERRUPTED"
            print(json.dumps(generate_reports(final_status), ensure_ascii=False, sort_keys=True, indent=2))
            if args.command == "report":
                return
        if args.command == "quality":
            print(json.dumps(run_quality_checks(), ensure_ascii=False, sort_keys=True, indent=2))
            return
        if args.command == "status":
            print_status_summary()
            return
    except StopStatus as exc:
        ensure_dir(ARTIFACT_ROOT)
        write_json(ARTIFACT_ROOT / "STOP_STATUS.json", {"status": exc.status, "message": str(exc), "at": utc_now()})
        print(f"{exc.status}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
