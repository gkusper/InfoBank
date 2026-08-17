from __future__ import annotations

import unittest

from evaluation.wolala2026.pipeline import run_pipeline
from evaluation.wolala2026.run_smoke import load_smoke_cases


class WolalaRequestRelativeModeTests(unittest.TestCase):
    def state(self, case_id: str):
        case = next(case for case in load_smoke_cases() if case["case_id"] == case_id)
        return run_pipeline(case)

    def test_same_aggregate_permission_is_full_for_aggregate_and_cfaf_for_individual(self) -> None:
        aggregate_state = self.state("S3A_AGGREGATE_REQUEST_ALLOWED")
        individual_state = self.state("S3B_INDIVIDUAL_REQUEST_WITH_AGGREGATE_ACCESS")
        self.assertEqual(aggregate_state.mode_decision.mode.value, "FULL")
        self.assertEqual(individual_state.mode_decision.mode.value, "CFAF")
        self.assertEqual(individual_state.mode_decision.cfaf_realization.value, "RESTRICT_GRANULARITY")

    def test_same_metadata_permission_is_full_for_metadata_and_cfaf_for_content(self) -> None:
        metadata_state = self.state("S4A_METADATA_LOOKUP_ALLOWED")
        content_state = self.state("S4B_CONTENT_WITH_METADATA_ACCESS")
        self.assertEqual(metadata_state.mode_decision.mode.value, "FULL")
        self.assertEqual(content_state.mode_decision.mode.value, "CFAF")
        self.assertEqual(content_state.mode_decision.cfaf_realization.value, "RESTRICT_CONTENT")

    def test_later_cancellation_can_return_full_closed_answer(self) -> None:
        state = self.state("S8_UNAMBIGUOUS_LATER_CANCELLATION")
        self.assertEqual(state.mode_decision.mode.value, "FULL")
        self.assertEqual(state.claim_assessments[0].support_status, "CLOSED")
        self.assertIn("closed or cancelled", state.final_response or "")

    def test_browser_only_activity_cannot_create_obligation(self) -> None:
        state = self.state("S7_BROWSER_ONLY_ACTION_CANDIDATE")
        self.assertEqual(state.mode_decision.mode.value, "CFAF")
        self.assertEqual(state.mode_decision.reason_class.value, "EVIDENTIAL")


if __name__ == "__main__":
    unittest.main()
