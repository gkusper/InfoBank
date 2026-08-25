from __future__ import annotations

import csv

import controlled_failure
from controlled_failure_config import REQUIRED_OUTPUT_CLASSES, load_controlled_failure_config
from evaluation.c_gate import build_candidate_cases
from evaluation.d_gate import (
    ACTION_DATASET_VERSION,
    FAILURE_TAXONOMY,
    build_action_development_set,
    run_action_evaluation,
    run_c0_c3,
    run_calibration,
    run_d_gate,
    score_predictions,
)
from evaluation.schemas import EvaluationMode


def test_controlled_failure_config_is_complete_versioned_and_runtime_mapped() -> None:
    config = load_controlled_failure_config()
    assert REQUIRED_OUTPUT_CLASSES <= set(config["output_classes"])
    assert config["config_version"] == controlled_failure.CONTROLLED_FAILURE_VERSION
    assert config["config_hash"] == controlled_failure.CONTROLLED_FAILURE_CONFIG_HASH
    assert config["precedence"][0] == "hard_authorization_and_archive"
    assert config["thresholds"]["aggregate_k"] >= 2
    assert controlled_failure.STATUS_FULL_ANSWER == "FULL_ANSWER"
    assert controlled_failure.STATUS_REFUSE_NO_MATCH == "REFUSE_NO_MATCH"


def test_scorer_exact_predictions_are_perfect_and_identity_is_enforced() -> None:
    cases = [case for case in build_candidate_cases() if case.split == "development"]
    predictions = [
        {"case_id": case.case_id, "output_class": case.expected_output_class, "reason_code": case.reason_code}
        for case in cases
    ]
    scores = score_predictions(cases, predictions)
    assert scores["exact_output_class_conformance"] == 1.0
    assert scores["reason_code_accuracy"] == 1.0
    assert scores["false_answer_rate"] == 0.0
    predictions[0]["case_id"] = "wrong"
    try:
        score_predictions(cases, predictions)
    except ValueError as exc:
        assert "identity" in str(exc)
    else:
        raise AssertionError("case identity mismatch must fail")


def test_calibration_records_every_config_and_never_uses_holdout_or_frozen_set(tmp_path) -> None:
    summary = run_calibration(tmp_path / "calibration")
    assert summary["evaluated_config_count"] == 6
    assert len(summary["evaluated_configs"]) == 6
    assert summary["candidate_holdout_used_for_tuning"] is False
    assert summary["frozen_d1_d8_used"] is False
    assert summary["selected"]["scores"]["exact_output_class_conformance"] == 1.0
    assert set(summary["error_taxonomy"]) == set(FAILURE_TAXONOMY)


def test_c0_c3_runner_has_complete_records_isolated_baselines_and_safe_c3(tmp_path) -> None:
    result = run_c0_c3(tmp_path / "run")
    cases = build_candidate_cases()
    assert result["manifest"]["record_count"] == len(cases) * 4
    assert result["manifest"]["production_api_reachable_modes"] == [EvaluationMode.C3_FULL_ROLE_AWARE.value]
    required = {
        "run_id", "case_id", "dataset_version", "scorer_version", "config_version", "config_hash",
        "commit_sha", "provider", "model", "retrieved_ids", "candidate_ids",
        "generator_visible_context_hash", "output_class", "reason_code", "stage_latency_ms",
        "latency_ms", "input_tokens", "output_tokens", "total_tokens", "cost", "retry_count",
        "prompt_size_chars", "context_size_chars", "generation_skipped", "audit_id", "metrics", "error",
    }
    assert all(required <= set(record) for record in result["records"])
    c3 = next(summary for summary in result["summaries"] if summary["mode"] == EvaluationMode.C3_FULL_ROLE_AWARE.value)
    assert set(c3["safety"].values()) == {0}
    assert c3["permitted_answer_accuracy"] >= 0.8
    assert c3["citation"]["citation_support_precision"] == 1.0
    assert c3["citation"]["citation_coverage"] == 1.0
    c0 = next(summary for summary in result["summaries"] if summary["mode"] == EvaluationMode.C0_VECTOR_ONLY.value)
    assert c0["false_unsupported_answer_rate"] > c3["false_unsupported_answer_rate"]
    rows = list(csv.DictReader((tmp_path / "run" / "manual_citation_audit_40.csv").open(encoding="utf-8")))
    assert len(rows) == 40
    assert {row["review_status"] for row in rows} == {"PENDING_HUMAN_AUDIT"}


def test_action_development_set_meets_size_targets_and_browser_is_context_only(tmp_path) -> None:
    messages, gold, browser = build_action_development_set()
    assert len(gold) == 120
    assert len(messages) == 240
    assert len(browser) == 60
    summary = run_action_evaluation(tmp_path / "action")
    assert summary["dataset_version"] == ACTION_DATASET_VERSION
    assert summary["open_action_accuracy"] >= 0.92
    assert summary["closure_linking_accuracy"] >= 0.80
    assert summary["action_f1"] >= 0.85
    assert summary["browser_only_false_actions"] == 0
    assert summary["mailex_used"] is False


def test_d_gate_orchestration_is_development_only_and_passes(tmp_path) -> None:
    summary = run_d_gate(tmp_path / "d-gate")
    assert summary["status"] == "PASS"
    assert summary["final_freeze"] is False
    assert summary["final_e1"] is False
    assert summary["manual_citation_audit"] == "PENDING_HUMAN_AUDIT"
    for filename in (
        "safety_report.json", "utility_report.json", "citation_report.json",
        "controlled_failure_report.json", "action_report.json", "latency_usage_report.json",
        "error_analysis.json",
    ):
        assert (tmp_path / "d-gate" / filename).exists()
