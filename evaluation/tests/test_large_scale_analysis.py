from __future__ import annotations

import unittest

from evaluation.large_scale_analysis import (
    clustered_bootstrap,
    document_case_aggregates,
    document_statistical_tests,
    evidence_case_aggregates,
    evidence_determinism,
    exact_mcnemar_pvalue,
    holm_adjust,
    triplet_results,
    wilson_interval,
)
from evaluation.run_d1_d8_large_scale import failed_document_attempts, is_retryable_generation_error, successful_document_records


def document_score(case_id: str, mode: str, repetition: int, value: bool) -> dict:
    return {
        "case_id": case_id,
        "mode": mode,
        "repetition": repetition,
        "scenario_family": "D1_full",
        "case_subtype": "full",
        "pair_id": case_id,
        "metadata": {"scenario": "D1"},
        "retrieval_target_recalled_at_4": True,
        "permitted_answer_correct": value,
        "prohibited_disclosure": None,
        "safe_withholding": None,
        "generator_exposure": None,
        "exact_output_class_conformance": value,
        "behavioral_conformance": value,
        "expected_source_role_conformance": True,
        "controlled_failure_conformance": True,
        "generation_skipped": False,
        "generation_calls": 1,
    }


class LargeScaleAnalysisTests(unittest.TestCase):
    def test_wilson_and_exact_mcnemar(self) -> None:
        interval = wilson_interval(5, 10)
        self.assertLess(interval["low"], 0.5)
        self.assertGreater(interval["high"], 0.5)
        self.assertEqual(exact_mcnemar_pvalue(0, 5), 0.0625)

    def test_holm_adjustment_is_monotone(self) -> None:
        rows = holm_adjust([{"p_value": 0.01}, {"p_value": 0.03}, {"p_value": 0.02}])
        adjusted = sorted(row["holm_p_value"] for row in rows)
        self.assertEqual(adjusted, sorted(adjusted))
        self.assertTrue(all(value >= 0.01 for value in adjusted))

    def test_document_majority_and_bootstrap_are_reproducible(self) -> None:
        scores = []
        for repetition in range(1, 6):
            scores.append(document_score("CASE_A", "role_aware_rag", repetition, repetition != 1))
            scores.append(document_score("CASE_A", "standard_rag", repetition, False))
            scores.append(document_score("CASE_B", "role_aware_rag", repetition, True))
            scores.append(document_score("CASE_B", "standard_rag", repetition, repetition == 1))
        aggregates = document_case_aggregates(scores)
        role_case_a = next(row for row in aggregates if row["case_id"] == "CASE_A" and row["mode"] == "role_aware_rag")
        self.assertTrue(role_case_a["behavioral_conformance_majority"])
        self.assertFalse(role_case_a["all_five_behavioral_consistency"])
        self.assertEqual(clustered_bootstrap(scores, samples=20), clustered_bootstrap(scores, samples=20))
        tests = document_statistical_tests(scores, bootstrap_samples=20)
        self.assertTrue(tests["case_level_mcnemar_holm"])

    def test_evidence_determinism_and_triplets(self) -> None:
        scores = [
            {"case_id": "D6_A", "seed_id": "S1", "scenario": "D6", "expected_status": "OPEN", "observed_status": "OPEN", "case_pass": True, "role_pass": True, "linking_pass": True},
            {"case_id": "D7_A", "seed_id": "S1", "scenario": "D7", "expected_status": "ABSENT", "observed_status": "ABSENT", "case_pass": True, "role_pass": True, "linking_pass": True},
            {"case_id": "D8_A", "seed_id": "S1", "scenario": "D8", "expected_status": "CLOSED", "observed_status": "CLOSED", "case_pass": True, "role_pass": True, "linking_pass": True},
            {"case_id": "D6_A", "seed_id": "S1", "scenario": "D6", "expected_status": "OPEN", "observed_status": "OPEN", "case_pass": True, "role_pass": True, "linking_pass": True},
            {"case_id": "D7_A", "seed_id": "S1", "scenario": "D7", "expected_status": "ABSENT", "observed_status": "ABSENT", "case_pass": True, "role_pass": True, "linking_pass": True},
            {"case_id": "D8_A", "seed_id": "S1", "scenario": "D8", "expected_status": "CLOSED", "observed_status": "CLOSED", "case_pass": True, "role_pass": True, "linking_pass": True},
        ]
        aggregates = evidence_case_aggregates(scores)
        self.assertEqual(evidence_determinism(aggregates)["rate"], 1.0)
        self.assertEqual(triplet_results(aggregates)[0]["triplet_pass"], True)

    def test_failed_document_attempt_is_not_measured_record(self) -> None:
        records = [
            {"case_id": "CASE_A", "mode": "role_aware_rag", "repetition": 1, "answer": None, "error": {"type": "APIConnectionError"}},
            {"case_id": "CASE_A", "mode": "role_aware_rag", "repetition": 1, "answer": "ok", "error": None},
            {"case_id": "CASE_A", "mode": "standard_rag", "repetition": 1, "answer": "ok", "error": None},
        ]
        self.assertEqual(len(successful_document_records(records)), 2)
        self.assertEqual(len(failed_document_attempts(records)), 1)

    def test_retryable_generation_error_classifier(self) -> None:
        self.assertTrue(is_retryable_generation_error({"error": {"type": "APIConnectionError"}}))
        self.assertTrue(is_retryable_generation_error({"error": {"type": "RateLimitError"}}))
        self.assertFalse(is_retryable_generation_error({"error": {"type": "BadRequestError"}}))


if __name__ == "__main__":
    unittest.main()
