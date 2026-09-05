from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.wolala2026.analyze_heldout import (
    aggregate_case_metric,
    aggregate_p5_pair_leakage,
    case_clustered_bootstrap_risk_difference,
    denominator_cases,
    denominator_pairs,
    exact_mcnemar_pvalue,
    holm_adjust,
    is_descriptive_only,
    primary_test_family,
    wilson_interval,
)
from evaluation.wolala2026.common import read_json, sha256_file
from evaluation.wolala2026.execution_spec import load_execution_spec, validate_execution_spec
from evaluation.wolala2026.latency_analysis import aggregate_case_mode_medians, derive_latency_record, percentile_summary, summarize_case_mode_latency
from evaluation.wolala2026.pilot_data import HELDOUT_DATASET
from evaluation.wolala2026.retry_policy import classify_invalidation, is_retryable_status, rerun_authorized, retry_policy_summary
from evaluation.wolala2026.run_pilot import run_pilot


ROOT = Path(__file__).resolve().parents[1] / "wolala2026"
SPEC_PATH = ROOT / "HELDOUT_EXECUTION_SPEC_v2.json"
PROTOCOL_V2 = ROOT / "WOLALA2026_PILOT_PROTOCOL_v2.md"


class WolalaProtocolV2FreezeTests(unittest.TestCase):
    def test_protocol_v1_checksum_unchanged(self) -> None:
        self.assertEqual(sha256_file(ROOT / "WOLALA2026_PILOT_PROTOCOL_v1.md"), "91c6e3279821abdd0c5b92006a4ce572293fc5ed29a77e7edbf5d1b47147f93e")

    def test_protocol_v2_required_sections_and_checksums(self) -> None:
        text = PROTOCOL_V2.read_text(encoding="utf-8")
        for phrase in [
            "Frozen Provider And Model Configuration",
            "Frozen Execution Counts",
            "Frozen Hard Caps",
            "Warm-Up Policy",
            "Retry Policy",
            "Invalid-Run Policy",
            "Rerun Policy",
            "Statistical Analysis Plan",
            "Latency Definition",
            "Held-Out Authorization And Execution Lock",
        ]:
            self.assertIn(phrase, text)
        spec = load_execution_spec(SPEC_PATH)
        self.assertEqual(spec["checksums"]["protocol_v2"], sha256_file(PROTOCOL_V2))
        self.assertEqual(spec["checksums"]["statistical_plan"], sha256_file(ROOT / "WOLALA2026_STATISTICAL_ANALYSIS_PLAN_v1.md"))
        self.assertEqual(spec["checksums"]["latency_definition"], sha256_file(ROOT / "WOLALA2026_LATENCY_DEFINITION_v1.md"))

    def test_execution_spec_validation_and_exact_counts(self) -> None:
        spec = load_execution_spec(SPEC_PATH)
        validation = validate_execution_spec(
            spec,
            cases=[{"case_id": f"HELD_{index:02d}"} for index in range(40)],
            modes=spec["modes"],
            repetitions=3,
            max_mode_executions=360,
            max_embedding_calls=60,
            max_generation_calls=380,
            max_total_external_calls=420,
            plan_only=True,
        )
        self.assertEqual(validation["planned_mode_executions"], 360)
        self.assertEqual(validation["planned_unique_embedding_requests"], 40)
        self.assertEqual(validation["planned_generation_requests_maximum"], 360)
        self.assertEqual(validation["planned_external_requests_without_retries_maximum"], 400)
        self.assertEqual(validation["hard_total_external_cap"], 420)
        self.assertEqual(validation["retry_budget"], 20)
        self.assertEqual(validation["external_warmup_calls"], 0)

    def test_hard_cap_and_retry_budget_enforcement(self) -> None:
        spec = load_execution_spec(SPEC_PATH)
        broken_total = dict(spec, max_total_external_calls=399)
        with self.assertRaises(RuntimeError):
            validate_execution_spec(broken_total, plan_only=True)
        broken_retry = dict(spec, max_retries_per_logical_request=2)
        with self.assertRaises(RuntimeError):
            validate_execution_spec(broken_retry, plan_only=True)
        summary = retry_policy_summary(spec)
        self.assertEqual(summary["total_cap_retry_slack"], 20)
        self.assertEqual(summary["max_total_retry_attempts"], 20)
        self.assertEqual(summary["external_warmup_calls"], 0)

    def test_retryable_and_non_retryable_status_classification(self) -> None:
        for status in [408, 429, 500, 502, 503, 504]:
            self.assertTrue(is_retryable_status(status))
        for status in [400, 401, 403, 404, 422]:
            self.assertFalse(is_retryable_status(status))

    def test_invalidation_and_rerun_policy(self) -> None:
        self.assertEqual(classify_invalidation("PROVIDER_OUTAGE"), "INVALIDATED_INFRASTRUCTURE_FAILURE")
        self.assertEqual(classify_invalidation("PRIMARY_SCORER_OR_PARSER_DEFECT"), "INVALIDATED_SCIENTIFIC_INTEGRITY_FAILURE")
        self.assertEqual(classify_invalidation("FALSE_CFAF"), "VALID_EMPIRICAL_RESULT")
        self.assertFalse(
            rerun_authorized(
                invalidation_class="VALID_EMPIRICAL_RESULT",
                independent_audit_passed=True,
                artifacts_retained=True,
                unchanged_freeze_state=True,
                separate_task_authorized=True,
                new_empty_output_directory=True,
                attempt_number=2,
            )
        )
        self.assertTrue(
            rerun_authorized(
                invalidation_class="INVALIDATED_INFRASTRUCTURE_FAILURE",
                independent_audit_passed=True,
                artifacts_retained=True,
                unchanged_freeze_state=True,
                separate_task_authorized=True,
                new_empty_output_directory=True,
                attempt_number=2,
            )
        )

    def test_heldout_plan_only_validates_without_execution_or_authorization_flags(self) -> None:
        spec = load_execution_spec(SPEC_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = run_pilot(
                dataset=HELDOUT_DATASET,
                modes=spec["modes"],
                repetitions=3,
                output_dir=tmp,
                max_mode_executions=360,
                max_embedding_calls=60,
                max_generation_calls=380,
                max_total_external_calls=420,
                plan_only=True,
                execution_spec=SPEC_PATH,
            )
            self.assertEqual(manifest["completion_status"], "PLANNED")
            self.assertEqual(manifest["heldout_model_execution_count"], 0)
            self.assertEqual(manifest["planned_mode_executions"], 360)
            self.assertEqual(manifest["planned_unique_embedding_requests"], 40)
            self.assertEqual(manifest["planned_generation_requests_maximum"], 360)
            self.assertFalse((Path(tmp) / "raw_results.jsonl").exists())
            self.assertFalse((Path(tmp) / "case_scores.jsonl").exists())
            plan = read_json(Path(tmp) / "execution_plan.json")
            self.assertTrue(plan["no_retrieval_embedding_adapter_generation_or_scoring_performed"])
            self.assertEqual(plan["external_api_calls_in_plan_only"], 0)

    def test_majority_any_event_and_p5_aggregation(self) -> None:
        records = _synthetic_records()
        majority = aggregate_case_metric(records, "top_level_mode_correct")
        self.assertTrue(next(row for row in majority if row["case_id"] == "C1" and row["mode_name"] == "cfaf_pipeline")["value"])
        self.assertFalse(next(row for row in majority if row["case_id"] == "C2" and row["mode_name"] == "standard_rag")["value"])
        leakage = aggregate_case_metric(records, "protected_content_leakage", violation_metric=True)
        self.assertTrue(next(row for row in leakage if row["case_id"] == "C2" and row["mode_name"] == "standard_rag")["value"])
        p5 = aggregate_p5_pair_leakage(records)
        self.assertTrue(next(row for row in p5 if row["pair_id"] == "P5_01" and row["mode_name"] == "standard_rag")["source_existence_leakage"])

    def test_wilson_mcnemar_holm_and_bootstrap(self) -> None:
        low, high = wilson_interval(0, 10)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0)
        self.assertAlmostEqual(exact_mcnemar_pvalue(0, 5), 0.0625)
        self.assertEqual(exact_mcnemar_pvalue(0, 0), 1.0)
        adjusted = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.20})
        self.assertAlmostEqual(adjusted["a"], 0.03)
        self.assertAlmostEqual(adjusted["b"], 0.08)
        cases = _synthetic_cases()
        boot_a = case_clustered_bootstrap_risk_difference(_synthetic_records(include_modes=("cfaf_pipeline", "standard_rag")), cases=cases, metric="top_level_mode_correct", mode_a="cfaf_pipeline", mode_b="standard_rag", samples=50)
        boot_b = case_clustered_bootstrap_risk_difference(_synthetic_records(include_modes=("cfaf_pipeline", "standard_rag")), cases=cases, metric="top_level_mode_correct", mode_a="cfaf_pipeline", mode_b="standard_rag", samples=50)
        self.assertEqual(boot_a, boot_b)
        self.assertEqual(boot_a["sample_unit"], "unique_heldout_case")

    def test_denominators_primary_family_and_descriptive_labels(self) -> None:
        cases = _synthetic_cases()
        self.assertEqual(len(denominator_cases(cases, "top_level_mode_correct")), 2)
        self.assertEqual(denominator_cases(cases, "request_fulfilment_correct"), ["C1"])
        self.assertEqual(denominator_cases(cases, "cfaf_realization_correct"), ["C2"])
        self.assertEqual(denominator_cases(cases, "safe_next_step_correct"), ["C2"])
        self.assertEqual(denominator_cases(cases, "public_reason_class_correct"), ["C2"])
        self.assertEqual(denominator_pairs(cases, "source_existence_leakage"), ["P5_01"])
        tests = primary_test_family(_synthetic_records())
        self.assertEqual(len(tests), 4)
        self.assertTrue(all(row["result_label"] == "primary_confirmatory" for row in tests.values()))
        self.assertTrue(is_descriptive_only("latency"))
        self.assertTrue(is_descriptive_only("source_existence_leakage"))

    def test_latency_derivation_shared_retrieval_median_and_sample_units(self) -> None:
        first = derive_latency_record(_latency_result("C1", "cfaf_pipeline", 1, 40.0))
        self.assertEqual(first["shared_retrieval_ms"], 15.0)
        self.assertEqual(first["mode_processing_ms"], 25.0)
        self.assertEqual(first["user_visible_end_to_end_ms"], 40.0)
        self.assertEqual(first["user_visible_external_api_ms"], 30.0)
        rows = [
            derive_latency_record(_latency_result("C1", "cfaf_pipeline", 1, 40.0)),
            derive_latency_record(_latency_result("C1", "cfaf_pipeline", 2, 50.0)),
            derive_latency_record(_latency_result("C1", "cfaf_pipeline", 3, 60.0)),
        ]
        case_modes = aggregate_case_mode_medians(rows)
        self.assertEqual(case_modes[0]["case_mode_latency_ms"], 50.0)
        self.assertEqual(case_modes[0]["sample_unit"], "case_mode_after_repetition_median")
        summary = summarize_case_mode_latency(case_modes)
        self.assertEqual(summary["cfaf_pipeline"]["sample_unit"], "case_mode_after_repetition_median")
        self.assertEqual(percentile_summary([1.0, 2.0, 3.0], sample_unit="x")["p50_ms"], 2.0)

    def test_scorer_sanity_audit_completeness(self) -> None:
        audit_path = ROOT / "PRE_HELDOUT_SCORER_SANITY_AUDIT_v1.md"
        text = audit_path.read_text(encoding="utf-8")
        self.assertIn("Total observations: `30`", text)
        self.assertIn("Disagreements affecting a primary metric: `0`", text)
        self.assertEqual(sum(1 for line in text.splitlines() if line.startswith("| DEV_")), 30)


def _synthetic_cases() -> list[dict[str, object]]:
    return [
        {
            "case_id": "C1",
            "pair_id": "P5_01",
            "family": "P5",
            "expected_top_level_mode": "FULL",
            "forbidden_disclosures": ["SECRET"],
            "protected_markers": ["SECRET"],
            "expected_next_step_codes": [],
            "expected_public_reason_class": None,
        },
        {
            "case_id": "C2",
            "pair_id": "P5_01",
            "family": "P5",
            "expected_top_level_mode": "CFAF",
            "expected_cfaf_realization": "ABSTAIN",
            "forbidden_disclosures": ["SECRET"],
            "protected_markers": ["SECRET"],
            "expected_next_step_codes": ["provide_primary_evidence"],
            "expected_public_reason_class": "EVIDENTIAL",
        },
    ]


def _synthetic_records(include_modes: tuple[str, ...] = ("cfaf_pipeline", "standard_rag", "prompt_only_control")) -> list[dict[str, object]]:
    values = {
        ("C1", "cfaf_pipeline"): [True, True, False],
        ("C1", "standard_rag"): [True, False, True],
        ("C1", "prompt_only_control"): [False, True, False],
        ("C2", "cfaf_pipeline"): [True, True, True],
        ("C2", "standard_rag"): [True, False, False],
        ("C2", "prompt_only_control"): [False, False, True],
    }
    records = []
    for case in _synthetic_cases():
        for mode in include_modes:
            for repetition, value in enumerate(values[(case["case_id"], mode)], start=1):
                records.append(
                    {
                        "case_id": case["case_id"],
                        "pair_id": case["pair_id"],
                        "family": case["family"],
                        "mode_name": mode,
                        "repetition": repetition,
                        "top_level_mode_correct": value,
                        "request_fulfilment_correct": value,
                        "protected_content_leakage": case["case_id"] == "C2" and mode == "standard_rag" and repetition == 2,
                        "source_existence_leakage": case["case_id"] == "C2" and mode == "standard_rag" and repetition == 3,
                    }
                )
    return records


def _latency_result(case_id: str, mode: str, repetition: int, end_to_end: float) -> dict[str, object]:
    return {
        "case_id": case_id,
        "pair_id": "P1",
        "family": "P1",
        "mode_name": mode,
        "repetition": repetition,
        "generation_skipped": False,
        "end_to_end_ms": end_to_end,
        "stage_timings": {
            "embedding_api_ms": 10.0,
            "candidate_retrieval_ms": 5.0,
            "generation_api_ms": 20.0,
            "end_to_end_ms": end_to_end,
        },
    }


if __name__ == "__main__":
    unittest.main()
