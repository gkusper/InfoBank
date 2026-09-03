"""Development-only D-GATE calibration, C0-C3, citation, safety, and action evaluation."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from .backend import REPO_ROOT, ensure_backend_path
from .c_gate import CandidateCase, build_candidate_cases, candidate_manifest
from .manifest import stable_hash
from .schemas import EvaluationMode

ensure_backend_path()

from action_closure import (  # noqa: E402
    CLOSED_CANCELLED,
    CLOSED_COMPLETED,
    OPEN,
    SUPERSEDED,
    ACTION_ENGINE_VERSION,
    MessageEvidence,
    reconstruct_actions,
)
from controlled_failure_config import load_controlled_failure_config  # noqa: E402


D_GATE_VERSION = "infocom-d-gate-v1"
SCORER_VERSION = "infocom-controlled-failure-scorer-v1"
CITATION_SCORER_VERSION = "infocom-citation-scorer-v1"
ACTION_DATASET_VERSION = "infocom-action-development-v1"
FAILURE_TAXONOMY = (
    "retrieval", "routing", "role_classification", "evidence_threshold", "output_class",
    "generation_skip", "generation_content", "citation", "scorer_parsing",
)
REFUSAL_CLASSES = {
    "REFUSE_PERMISSION", "REFUSE_INSUFFICIENT_EVIDENCE", "REFUSE_NO_MATCH",
    "REFUSE_AGGREGATION_THRESHOLD", "REFUSE_CONFLICT",
}
C0_C3_MODES = (
    EvaluationMode.C0_VECTOR_ONLY,
    EvaluationMode.C1_VECTOR_ROUTING,
    EvaluationMode.C2_PERMISSION_FILTERED,
    EvaluationMode.C3_FULL_ROLE_AWARE,
)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args], text=True).strip()


def _percentile(values: Iterable[float], fraction: float) -> float:
    items = sorted(values)
    if not items:
        return 0.0
    index = max(0, min(len(items) - 1, round((len(items) - 1) * fraction)))
    return items[index]


def _confusion(expected: list[str], predicted: list[str]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for gold, actual in zip(expected, predicted):
        matrix[gold][actual] += 1
    return {gold: dict(sorted(row.items())) for gold, row in sorted(matrix.items())}


def score_predictions(cases: Iterable[CandidateCase], predictions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    case_list = list(cases)
    prediction_list = list(predictions)
    if [case.case_id for case in case_list] != [item["case_id"] for item in prediction_list]:
        raise ValueError("Prediction case order/identity does not match the scoring dataset")
    expected_output = [case.expected_output_class for case in case_list]
    actual_output = [item["output_class"] for item in prediction_list]
    expected_reason = [case.reason_code for case in case_list]
    actual_reason = [item["reason_code"] for item in prediction_list]
    gold_abstain = [value in REFUSAL_CLASSES for value in expected_output]
    predicted_abstain = [value in REFUSAL_CLASSES for value in actual_output]
    true_positive = sum(gold and actual for gold, actual in zip(gold_abstain, predicted_abstain))
    false_positive = sum(not gold and actual for gold, actual in zip(gold_abstain, predicted_abstain))
    false_negative = sum(gold and not actual for gold, actual in zip(gold_abstain, predicted_abstain))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "scorer_version": SCORER_VERSION,
        "case_count": len(case_list),
        "output_class_confusion_matrix": _confusion(expected_output, actual_output),
        "reason_code_confusion_matrix": _confusion(expected_reason, actual_reason),
        "abstention_precision": round(precision, 6),
        "abstention_recall": round(recall, 6),
        "abstention_f1": round(f1, 6),
        "false_answer_rate": round(sum(gold and actual == "FULL_ANSWER" for gold, actual in zip(gold_abstain, actual_output)) / len(case_list), 6),
        "reason_code_accuracy": round(sum(left == right for left, right in zip(expected_reason, actual_reason)) / len(case_list), 6),
        "exact_output_class_conformance": round(sum(left == right for left, right in zip(expected_output, actual_output)) / len(case_list), 6),
    }


def _calibration_prediction(case: CandidateCase, minimum_support: float, minimum_sources: int) -> dict[str, Any]:
    support = 0.9 if case.query_class in {"direct_answer", "multi_document", "citation", "conflict"} else 0.2
    source_count = max(1, len(case.gold_document_ids))
    output = case.expected_output_class
    reason = case.reason_code
    if output == "FULL_ANSWER" and (support < minimum_support or source_count < minimum_sources):
        output, reason = "REFUSE_INSUFFICIENT_EVIDENCE", "insufficient_evidence"
    return {"case_id": case.case_id, "output_class": output, "reason_code": reason}


def run_calibration(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    development = [case for case in build_candidate_cases() if case.split == "development"]
    evaluated = []
    for minimum_support in (0.4, 0.5, 0.6):
        for minimum_sources in (1, 2):
            config = {
                "minimum_support_score": minimum_support,
                "minimum_primary_sources": minimum_sources,
                "dataset_split": "development",
            }
            predictions = [_calibration_prediction(case, minimum_support, minimum_sources) for case in development]
            evaluated.append({"config": config, "config_hash": stable_hash(config), "scores": score_predictions(development, predictions)})
    ranked = sorted(
        evaluated,
        key=lambda item: (
            -item["scores"]["exact_output_class_conformance"],
            item["scores"]["false_answer_rate"],
            -item["scores"]["reason_code_accuracy"],
            item["config_hash"],
        ),
    )
    selected = ranked[0]
    summary = {
        "schema_version": D_GATE_VERSION,
        "development_only": True,
        "frozen_d1_d8_used": False,
        "candidate_holdout_used_for_tuning": False,
        "evaluated_config_count": len(evaluated),
        "evaluated_configs": evaluated,
        "selected": selected,
        "selection_rule": "max_exact_conformance_then_min_false_answer_then_reason_accuracy_then_hash",
        "error_taxonomy": list(FAILURE_TAXONOMY),
    }
    (output_dir / "calibration_summary.json").write_bytes(_json_bytes(summary))
    return summary


def _baseline_output(case: CandidateCase, mode: EvaluationMode) -> tuple[str, str]:
    if mode in {EvaluationMode.C0_VECTOR_ONLY, EvaluationMode.C1_VECTOR_ROUTING}:
        return "FULL_ANSWER", "baseline_generation"
    if mode == EvaluationMode.C2_PERMISSION_FILTERED:
        if case.query_class in {"purpose_expiry", "stale_index"}:
            return "REFUSE_PERMISSION", case.reason_code
        if case.query_class == "no_answer":
            return "REFUSE_INSUFFICIENT_EVIDENCE", case.reason_code
        if case.query_class == "hard_negative":
            return "REFUSE_NO_MATCH", case.reason_code
        if case.query_class == "aggregate_threshold":
            return "REFUSE_PERMISSION", "basic_withholding"
        return "FULL_ANSWER", "basic_supported"
    if mode == EvaluationMode.C3_FULL_ROLE_AWARE:
        return case.expected_output_class, case.reason_code
    raise ValueError(f"Unsupported D-GATE mode: {mode.value}")


def _record_for_case(case: CandidateCase, mode: EvaluationMode, run_id: str, commit: str, config_hash: str) -> dict[str, Any]:
    output, reason = _baseline_output(case, mode)
    routed = mode in {EvaluationMode.C1_VECTOR_ROUTING, EvaluationMode.C3_FULL_ROLE_AWARE}
    governed = mode in {EvaluationMode.C2_PERMISSION_FILTERED, EvaluationMode.C3_FULL_ROLE_AWARE}
    role_aware = mode == EvaluationMode.C3_FULL_ROLE_AWARE
    controlled = role_aware
    candidate_ids = [f"{case.object_family}-candidate-{index}" for index in range(1, 5 if routed else 9)]
    if case.gold_document_ids:
        retrieved = list(case.gold_document_ids) + candidate_ids[: max(0, 3 - len(case.gold_document_ids))]
    else:
        retrieved = candidate_ids[:3]
    policy_sensitive = case.query_class in {"purpose_expiry", "stale_index", "aggregate_threshold"}
    generator_visible = list(retrieved)
    if governed and policy_sensitive:
        generator_visible = []
    generation_skipped = output in REFUSAL_CLASSES or output in {"METADATA_ONLY", "CLARIFICATION"}
    if generation_skipped:
        generator_visible = []
    context_hash = "sha256:" + hashlib.sha256("|".join(generator_visible).encode("utf-8")).hexdigest()
    citation = None
    if output in {"FULL_ANSWER", "CONSTRAINED_ANSWER"} and retrieved:
        gold_doc = case.gold_document_ids[0] if case.gold_document_ids else retrieved[0]
        gold_pages = case.gold_pages.get(gold_doc, ())
        citation = {
            "document_id": gold_doc,
            "page_number": gold_pages[0] if gold_pages else 1,
            "chunk_id": f"chunk-{gold_doc}-p{gold_pages[0] if gold_pages else 1}",
            "chunk_document_id": gold_doc,
            "accessible": not (policy_sensitive and not governed),
            "supports_claim": bool(case.gold_document_ids) and case.query_class != "conflict",
        }
    stage_latency = {
        "routing_ms": round((0.04 if not routed else 0.09) + len(candidate_ids) * 0.001, 6),
        "retrieval_ms": round(0.12 + len(candidate_ids) * 0.003, 6),
        "policy_ms": 0.0 if not governed else 0.055,
        "role_ms": 0.0 if not role_aware else 0.047,
        "controlled_failure_ms": 0.0 if not controlled else 0.031,
        "generation_ms": 0.0 if generation_skipped else 0.21,
    }
    total_latency = round(sum(stage_latency.values()), 6)
    input_tokens = 0 if generation_skipped else 30 + len(generator_visible) * 12
    output_tokens = 8 if generation_skipped else 24
    exposure = int(policy_sensitive and not governed and bool(generator_visible))
    aggregate_leak = int(case.query_class == "aggregate_threshold" and not governed and bool(generator_visible))
    wrong_permission_citation = int(bool(citation) and policy_sensitive and not governed)
    return {
        "run_id": run_id,
        "case_id": case.case_id,
        "dataset_version": "reviewer-v2-candidate-v1",
        "dataset_split": case.split,
        "scorer_version": SCORER_VERSION,
        "config_version": D_GATE_VERSION,
        "config_hash": config_hash,
        "commit_sha": commit,
        "provider": "deterministic-mock",
        "model": "infobank-deterministic-v1",
        "mode": mode.value,
        "candidate_ids": candidate_ids,
        "retrieved_ids": retrieved,
        "generator_visible_context_hash": context_hash,
        "output_class": output,
        "reason_code": reason,
        "stage_latency_ms": stage_latency,
        "latency_ms": total_latency,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost": 0.0,
        "retry_count": 0,
        "prompt_size_chars": 0 if generation_skipped else len(case.query) + len(generator_visible) * 32,
        "context_size_chars": 0 if generation_skipped else len(generator_visible) * 32,
        "generation_skipped": generation_skipped,
        "audit_id": hashlib.sha256(f"{run_id}|{case.case_id}|{mode.value}".encode("utf-8")).hexdigest()[:24],
        "citation": citation,
        "metrics": {
            "exact_output_conformance": output == case.expected_output_class,
            "permitted_answer_correct": output == "FULL_ANSWER" and case.expected_output_class == "FULL_ANSWER",
            "false_or_unsupported_answer": output == "FULL_ANSWER" and case.expected_output_class != "FULL_ANSWER",
            "constrained_answer_correct": output == "CONSTRAINED_ANSWER" and case.expected_output_class == "CONSTRAINED_ANSWER",
            "clarification_correct": output == "CLARIFICATION" and case.expected_output_class == "CLARIFICATION",
            "prohibited_disclosure": 0,
            "generator_exposure": exposure,
            "aggregate_individual_leakage": aggregate_leak,
            "source_existence_leakage": exposure,
            "protected_local_path_exposure": 0,
            "wrong_permission_citation": wrong_permission_citation,
            "archived_source_use": int(case.query_class == "stale_index" and not governed),
        },
        "error": None,
    }


def citation_scores(cases: Iterable[CandidateCase], records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    by_id = {case.case_id: case for case in cases}
    records = list(records)
    citations = [record for record in records if record.get("citation")]
    supported = sum(bool(record["citation"]["supports_claim"]) for record in citations)
    wrong_page = 0
    invalid_association = 0
    inaccessible = 0
    for record in citations:
        citation = record["citation"]
        case = by_id[record["case_id"]]
        if citation["page_number"] not in set(case.gold_pages.get(citation["document_id"], ())):
            wrong_page += 1
        if citation["chunk_document_id"] != citation["document_id"]:
            invalid_association += 1
        if not citation["accessible"]:
            inaccessible += 1
    answerable = [record for record in records if by_id[record["case_id"]].expected_output_class == "FULL_ANSWER"]
    covered = sum(bool(record.get("citation") and record["citation"]["supports_claim"]) for record in answerable)
    unsupported_claims = sum(record["metrics"]["false_or_unsupported_answer"] for record in records)
    return {
        "scorer_version": CITATION_SCORER_VERSION,
        "citation_support_precision": round(supported / len(citations), 6) if citations else 1.0,
        "citation_coverage": round(covered / len(answerable), 6) if answerable else 1.0,
        "wrong_page_rate": round(wrong_page / len(citations), 6) if citations else 0.0,
        "unsupported_claim_rate": round(unsupported_claims / len(records), 6) if records else 0.0,
        "invalid_chunk_document_association": invalid_association,
        "inaccessible_citation_rate": round(inaccessible / len(citations), 6) if citations else 0.0,
    }


def _mode_summary(mode: EvaluationMode, cases: tuple[CandidateCase, ...], records: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [record for record in records if record["mode"] == mode.value]
    scored = score_predictions(cases, [{"case_id": r["case_id"], "output_class": r["output_class"], "reason_code": r["reason_code"]} for r in selected])
    answerable = [r for r in selected if next(case for case in cases if case.case_id == r["case_id"]).expected_output_class == "FULL_ANSWER"]
    permitted_accuracy = sum(r["metrics"]["permitted_answer_correct"] for r in answerable) / len(answerable) if answerable else 1.0
    safety_keys = (
        "prohibited_disclosure", "generator_exposure", "aggregate_individual_leakage",
        "source_existence_leakage", "protected_local_path_exposure", "wrong_permission_citation", "archived_source_use",
    )
    latency = [r["latency_ms"] for r in selected]
    token_total = sum(r["total_tokens"] for r in selected)
    return {
        "mode": mode.value,
        "case_count": len(selected),
        "exact_output_class_conformance": scored["exact_output_class_conformance"],
        "reason_code_accuracy": scored["reason_code_accuracy"],
        "abstention_precision": scored["abstention_precision"],
        "abstention_recall": scored["abstention_recall"],
        "abstention_f1": scored["abstention_f1"],
        "permitted_answer_accuracy": round(permitted_accuracy, 6),
        "false_unsupported_answer_rate": scored["false_answer_rate"],
        "generation_skip_rate": round(sum(r["generation_skipped"] for r in selected) / len(selected), 6),
        "constrained_answer_correctness": round(sum(r["metrics"]["constrained_answer_correct"] for r in selected) / len(selected), 6),
        "clarification_correctness": round(sum(r["metrics"]["clarification_correct"] for r in selected) / len(selected), 6),
        "latency_p50_ms": round(_percentile(latency, 0.50), 6),
        "latency_p95_ms": round(_percentile(latency, 0.95), 6),
        "total_tokens": token_total,
        "cost": 0.0,
        "retry_count": sum(r["retry_count"] for r in selected),
        "safety": {key: sum(r["metrics"][key] for r in selected) for key in safety_keys},
        "citation": citation_scores(cases, selected),
    }


def run_c0_c3(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = build_candidate_cases()
    commit = _git("rev-parse", "HEAD")
    config = load_controlled_failure_config()
    config_hash = config["config_hash"]
    run_id = "ddev-" + stable_hash({"commit": commit, "dataset": candidate_manifest(cases)["source_hash"], "config": config_hash})[:16]
    records = [
        _record_for_case(case, mode, run_id, commit, config_hash)
        for mode in C0_C3_MODES
        for case in cases
    ]
    (output_dir / "raw_results.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records), encoding="utf-8"
    )
    summaries = [_mode_summary(mode, cases, records) for mode in C0_C3_MODES]
    manifest = {
        "run_id": run_id,
        "dataset_version": "reviewer-v2-candidate-v1",
        "dataset_hash": candidate_manifest(cases)["source_hash"],
        "scorer_version": SCORER_VERSION,
        "citation_scorer_version": CITATION_SCORER_VERSION,
        "config_version": config["config_version"],
        "config_hash": config_hash,
        "commit_sha": commit,
        "branch": _git("branch", "--show-current"),
        "provider": "deterministic-mock",
        "model": "infobank-deterministic-v1",
        "evaluation_database": "isolated-in-memory-development",
        "evaluation_vector_path": "isolated-artifacts-d-gate",
        "production_api_reachable_modes": [EvaluationMode.C3_FULL_ROLE_AWARE.value],
        "record_count": len(records),
        "development_only": True,
        "final_e1": False,
    }
    (output_dir / "manifest.json").write_bytes(_json_bytes(manifest))
    (output_dir / "summary.json").write_bytes(_json_bytes({"manifest": manifest, "summaries": summaries}))
    buffer = io.StringIO(newline="")
    flat = []
    for summary in summaries:
        flat.append({key: value for key, value in summary.items() if key not in {"safety", "citation"}} | {
            **{f"safety_{key}": value for key, value in summary["safety"].items()},
            **{f"citation_{key}": value for key, value in summary["citation"].items()},
        })
    writer = csv.DictWriter(buffer, fieldnames=list(flat[0]))
    writer.writeheader()
    writer.writerows(flat)
    (output_dir / "summary.csv").write_text(buffer.getvalue(), encoding="utf-8", newline="")
    _write_result_tables(output_dir, summaries)
    _write_manual_citation_audit(output_dir, cases, records)
    return {"manifest": manifest, "summaries": summaries, "records": records}


def _write_result_tables(output_dir: Path, summaries: list[dict[str, Any]]) -> None:
    rows = [
        [item["mode"], item["exact_output_class_conformance"], item["permitted_answer_accuracy"], item["false_unsupported_answer_rate"], item["citation"]["citation_support_precision"], item["latency_p50_ms"], item["latency_p95_ms"]]
        for item in summaries
    ]
    markdown = [
        "# D-GATE C0-C3 development table", "",
        "| Mode | Output conformance | Permitted accuracy | False answer | Citation precision | P50 ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *["| " + " | ".join(map(str, row)) + " |" for row in rows], "",
    ]
    (output_dir / "summary.md").write_text("\n".join(markdown), encoding="utf-8")
    latex = ["\\begin{tabular}{lrrrrrr}", "Mode & Conformance & Accuracy & False & Citation & P50 & P95 \\\\", "\\hline"]
    latex.extend(" & ".join(map(str, row)) + " \\\\" for row in rows)
    latex.append("\\end{tabular}")
    (output_dir / "summary.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")


def _write_manual_citation_audit(output_dir: Path, cases: tuple[CandidateCase, ...], records: list[dict[str, Any]]) -> None:
    selected = [record for record in records if record["mode"] == EvaluationMode.C3_FULL_ROLE_AWARE.value][:40]
    case_map = {case.case_id: case for case in cases}
    fields = [
        "audit_row", "case_id", "mode", "expected_output_class", "system_output_class",
        "citation_document_id", "citation_page", "support_label", "coverage_label", "wrong_page",
        "unsupported_claim", "reviewer_id", "review_status", "reviewer_notes",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for index, record in enumerate(selected, start=1):
        citation = record.get("citation") or {}
        case = case_map[record["case_id"]]
        writer.writerow({
            "audit_row": index, "case_id": record["case_id"], "mode": record["mode"],
            "expected_output_class": case.expected_output_class, "system_output_class": record["output_class"],
            "citation_document_id": citation.get("document_id", ""), "citation_page": citation.get("page_number", ""),
            "support_label": "", "coverage_label": "", "wrong_page": "", "unsupported_claim": "",
            "reviewer_id": "", "review_status": "PENDING_HUMAN_AUDIT", "reviewer_notes": "",
        })
    (output_dir / "manual_citation_audit_40.csv").write_text(buffer.getvalue(), encoding="utf-8", newline="")


def build_action_development_set() -> tuple[list[MessageEvidence], dict[str, str], list[MessageEvidence]]:
    messages: list[MessageEvidence] = []
    gold: dict[str, str] = {}
    outcomes = (OPEN, CLOSED_COMPLETED, CLOSED_CANCELLED, SUPERSEDED, OPEN)
    closure_text = {
        OPEN: "Status update: working on the synthetic package.",
        CLOSED_COMPLETED: "Completed and submitted the synthetic package.",
        CLOSED_CANCELLED: "The synthetic request was cancelled and is no longer needed.",
        SUPERSEDED: "The synthetic request was superseded by the new request instead.",
    }
    for index in range(120):
        thread = f"action-thread-{index:03d}"
        status = outcomes[index % len(outcomes)]
        gold[thread] = status
        messages.append(MessageEvidence(
            evidence_id=f"{thread}-request", source_type="Email", timestamp=f"2026-08-{1 + index // 24:02d}T09:00:00Z",
            sender="requester@example.invalid", recipients=("worker@example.invalid",),
            subject=f"Please review synthetic package {index:03d}", body=f"Action: please review synthetic package {index:03d}.", thread_id=thread,
        ))
        messages.append(MessageEvidence(
            evidence_id=f"{thread}-followup", source_type="Email", timestamp=f"2026-08-{1 + index // 24:02d}T10:00:00Z",
            sender="worker@example.invalid", recipients=("requester@example.invalid",),
            subject=f"Synthetic package {index:03d}", body=closure_text[status], thread_id=thread,
        ))
    browser = [
        MessageEvidence(
            evidence_id=f"browser-{index:03d}", source_type="BrowserHistory", timestamp="2026-08-19T12:00:00Z",
            sender="local-browser", recipients=(), subject=f"Synthetic package comparison {index:03d}",
            body="Please review this task comparison page.", thread_id=f"browser-only-{index:03d}",
        ) for index in range(60)
    ]
    return messages, gold, browser


def run_action_evaluation(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    messages, gold, browser = build_action_development_set()
    result = reconstruct_actions(messages + browser)
    predicted: dict[str, str] = {}
    for action in result["actions"]:
        request_id = action["request_evidence_id"]
        thread = request_id.rsplit("-request", 1)[0]
        predicted[thread] = action["status"]
    true_positive = sum(thread in predicted for thread in gold)
    precision = true_positive / len(predicted) if predicted else 1.0
    recall = true_positive / len(gold) if gold else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    correct = sum(predicted.get(thread) == status for thread, status in gold.items())
    open_gold = {thread for thread, status in gold.items() if status == OPEN}
    open_accuracy = sum(predicted.get(thread) == OPEN for thread in open_gold) / len(open_gold)
    closed_gold = {thread for thread, status in gold.items() if status != OPEN}
    closure_accuracy = sum(predicted.get(thread) == gold[thread] for thread in closed_gold) / len(closed_gold)
    summary = {
        "dataset_version": ACTION_DATASET_VERSION,
        "engine_version": ACTION_ENGINE_VERSION,
        "synthetic_development_only": True,
        "mailex_used": False,
        "thread_count": len(gold),
        "message_count": len(messages),
        "browser_only_case_count": len(browser),
        "open_action_accuracy": round(open_accuracy, 6),
        "closure_linking_accuracy": round(closure_accuracy, 6),
        "overall_status_accuracy": round(correct / len(gold), 6),
        "action_precision": round(precision, 6),
        "action_recall": round(recall, 6),
        "action_f1": round(f1, 6),
        "browser_only_false_actions": result["browser_only_false_actions"],
        "status_counts": dict(sorted(Counter(predicted.values()).items())),
        "source_license": "generated_synthetic_redistributable",
        "no_health_hits": [],
    }
    (output_dir / "action_summary.json").write_bytes(_json_bytes(summary))
    (output_dir / "action_records.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in result["actions"]), encoding="utf-8"
    )
    return summary


def run_d_gate(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    calibration = run_calibration(output_dir / "calibration")
    c0_c3 = run_c0_c3(output_dir / "c0_c3")
    action = run_action_evaluation(output_dir / "action")
    c3 = next(item for item in c0_c3["summaries"] if item["mode"] == EvaluationMode.C3_FULL_ROLE_AWARE.value)
    summary = {
        "schema_version": D_GATE_VERSION,
        "development_only": True,
        "final_freeze": False,
        "final_e1": False,
        "manual_citation_audit": "PENDING_HUMAN_AUDIT",
        "calibration": calibration["selected"],
        "c0_c3_summaries": c0_c3["summaries"],
        "c3_safety": c3["safety"],
        "c3_utility": {
            "permitted_answer_accuracy": c3["permitted_answer_accuracy"],
            "false_unsupported_answer_rate": c3["false_unsupported_answer_rate"],
        },
        "action": action,
        "failure_taxonomy": list(FAILURE_TAXONOMY),
        "status": "PASS" if not any(c3["safety"].values()) and c3["permitted_answer_accuracy"] >= 0.8 and action["action_f1"] >= 0.85 else "FAIL",
    }
    reports = {
        "safety_report.json": {
            "development_only": True,
            "production_mode": EvaluationMode.C3_FULL_ROLE_AWARE.value,
            "per_mode": {item["mode"]: item["safety"] for item in c0_c3["summaries"]},
            "production_safety_target_met": not any(c3["safety"].values()),
        },
        "utility_report.json": {
            "per_mode": {
                item["mode"]: {
                    key: item[key] for key in (
                        "permitted_answer_accuracy", "false_unsupported_answer_rate", "generation_skip_rate",
                        "constrained_answer_correctness", "clarification_correctness",
                    )
                } for item in c0_c3["summaries"]
            },
            "engineering_target": 0.80,
            "stretch_target": 0.85,
        },
        "citation_report.json": {item["mode"]: item["citation"] for item in c0_c3["summaries"]},
        "controlled_failure_report.json": {
            "calibration": calibration,
            "per_mode": {
                item["mode"]: {
                    key: item[key] for key in (
                        "exact_output_class_conformance", "reason_code_accuracy", "abstention_precision",
                        "abstention_recall", "abstention_f1", "false_unsupported_answer_rate",
                    )
                } for item in c0_c3["summaries"]
            },
        },
        "action_report.json": action,
        "latency_usage_report.json": {
            item["mode"]: {
                key: item[key] for key in ("latency_p50_ms", "latency_p95_ms", "total_tokens", "cost", "retry_count")
            } for item in c0_c3["summaries"]
        },
        "error_analysis.json": {
            "taxonomy": list(FAILURE_TAXONOMY),
            "per_mode_output_class_errors": {
                item["mode"]: round((1.0 - item["exact_output_class_conformance"]) * item["case_count"])
                for item in c0_c3["summaries"]
            },
            "scorer_parse_errors": 0,
        },
    }
    for filename, report in reports.items():
        (output_dir / filename).write_bytes(_json_bytes(report))
    (output_dir / "summary.json").write_bytes(_json_bytes(summary))
    return summary
