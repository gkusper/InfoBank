from __future__ import annotations

import json
import unittest

from evaluation.wolala2026.labels import json_safe
from evaluation.wolala2026.pipeline import run_pipeline
from evaluation.wolala2026.run_smoke import load_smoke_cases


class WolalaPublicTraceTests(unittest.TestCase):
    def state(self, case_id: str):
        case = next(case for case in load_smoke_cases() if case["case_id"] == case_id)
        return run_pipeline(case)

    def test_internal_only_source_is_normalized_to_no_source_public_reason(self) -> None:
        no_source = self.state("S9A_NO_RELEVANT_SOURCE")
        internal_only = self.state("S9B_INTERNAL_INACCESSIBLE_SOURCE")
        self.assertEqual(no_source.response_contract.public_reason_class, internal_only.response_contract.public_reason_class)
        self.assertEqual(no_source.response_contract.public_reason_text, internal_only.response_contract.public_reason_text)
        self.assertNotEqual(json.dumps(json_safe(no_source.internal_trace), sort_keys=True), json.dumps(json_safe(internal_only.internal_trace), sort_keys=True))

    def test_public_trace_hides_internal_only_source_identity(self) -> None:
        state = self.state("S9B_INTERNAL_INACCESSIBLE_SOURCE")
        public_text = json.dumps(json_safe(state.public_trace), sort_keys=True) + (state.final_response or "")
        self.assertNotIn("s9b-internal", public_text)
        self.assertNotIn("Internal-only hidden source", public_text)
        self.assertIn("s9b-internal", json.dumps(json_safe(state.internal_trace), sort_keys=True))


if __name__ == "__main__":
    unittest.main()
