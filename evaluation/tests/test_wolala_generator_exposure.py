from __future__ import annotations

import json
import unittest

from evaluation.wolala2026.labels import json_safe
from evaluation.wolala2026.pipeline import run_pipeline
from evaluation.wolala2026.run_smoke import load_smoke_cases


class WolalaGeneratorExposureTests(unittest.TestCase):
    def case_state(self, case_id: str):
        case = next(case for case in load_smoke_cases() if case["case_id"] == case_id)
        return case, run_pipeline(case)

    def test_denied_content_never_enters_generator_context(self) -> None:
        _, state = self.case_state("S5_DENIED_SOURCE")
        context = json.dumps(json_safe(state.generator_context), sort_keys=True)
        self.assertNotIn("DENIED_SECRET_S5", context)

    def test_metadata_content_never_enters_generator_context(self) -> None:
        _, state = self.case_state("S4B_CONTENT_WITH_METADATA_ACCESS")
        context = json.dumps(json_safe(state.generator_context), sort_keys=True)
        self.assertNotIn("S4_PRIVATE_CONTENT", context)
        self.assertIn("created_at", context)

    def test_aggregate_individual_content_never_enters_generator_context(self) -> None:
        _, state = self.case_state("S3A_AGGREGATE_REQUEST_ALLOWED")
        context = json.dumps(json_safe(state.generator_context), sort_keys=True)
        self.assertNotIn("S3_INDIVIDUAL_CANARY", context)
        self.assertIn("Twelve approval requests", context)

    def test_forbidden_generated_marker_uses_fallback(self) -> None:
        _, state = self.case_state("S10_VALIDATOR_FORBIDDEN_MARKER")
        context = json.dumps(json_safe(state.generator_context), sort_keys=True)
        self.assertNotIn("FORBIDDEN_S10_CANARY", context)
        self.assertEqual(state.validation.status.value, "FAIL")
        self.assertTrue(state.validation.fallback_used)
        self.assertNotIn("FORBIDDEN_S10_CANARY", state.final_response or "")


if __name__ == "__main__":
    unittest.main()
