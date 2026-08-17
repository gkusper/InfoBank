from __future__ import annotations

import unittest

from evaluation.wolala2026.pipeline import assert_pipeline_invariants, run_pipeline
from evaluation.wolala2026.run_smoke import load_smoke_cases, run_smoke


class WolalaPipelineSmokeTests(unittest.TestCase):
    def test_all_declared_smoke_cases_pass_expected_modes(self) -> None:
        cases = load_smoke_cases()
        self.assertEqual(len(cases), 13)
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                state = run_pipeline(case)
                assert_pipeline_invariants(state)
                self.assertEqual(state.mode_decision.mode.value, case["expected_top_level_mode"])
                self.assertEqual(state.validation.status.value, case.get("expected_validation_status", "PASS"))

    def test_smoke_runner_reports_no_full_benchmark_or_paid_api(self) -> None:
        payload = run_smoke()
        self.assertTrue(payload["passed"])
        self.assertFalse(payload["full_benchmark_executed"])
        self.assertFalse(payload["paid_api_calls_executed"])


if __name__ == "__main__":
    unittest.main()
