from __future__ import annotations

import json
import unittest

from evaluation.wolala2026.labels import PipelineState
from evaluation.wolala2026.pipeline import (
    AccessAndSafetyResolutionStage,
    CandidateRetrievalStage,
    EvidenceLabellingStage,
    QueryProfilingStage,
    RunContext,
    SufficiencyAndPermittedOutputStage,
    TopLevelModeSelectionStage,
)
from evaluation.wolala2026.run_smoke import load_smoke_cases


class WolalaLabelPropagationTests(unittest.TestCase):
    def test_state_is_serializable_after_each_stage_and_labels_are_append_only(self) -> None:
        case = next(case for case in load_smoke_cases() if case["case_id"] == "S4B_CONTENT_WITH_METADATA_ACCESS")
        context = RunContext(case=case)
        state = PipelineState(case_id=case["case_id"], query_id=f"query-{case['case_id']}", query=case["query"])
        previous_count = 0
        for stage in [
            QueryProfilingStage(),
            CandidateRetrievalStage(),
            AccessAndSafetyResolutionStage(),
            EvidenceLabellingStage(),
            SufficiencyAndPermittedOutputStage(),
            TopLevelModeSelectionStage(),
        ]:
            state = stage.run(state, context)
            json.loads(state.to_json())
            self.assertGreaterEqual(len(state.labels), previous_count)
            previous_count = len(state.labels)

    def test_access_role_state_disposition_and_mode_are_separate_dimensions(self) -> None:
        case = next(case for case in load_smoke_cases() if case["case_id"] == "S4B_CONTENT_WITH_METADATA_ACCESS")
        state = PipelineState(case_id=case["case_id"], query_id=f"query-{case['case_id']}", query=case["query"])
        context = RunContext(case=case)
        for stage in [
            QueryProfilingStage(),
            CandidateRetrievalStage(),
            AccessAndSafetyResolutionStage(),
            EvidenceLabellingStage(),
            SufficiencyAndPermittedOutputStage(),
            TopLevelModeSelectionStage(),
        ]:
            state = stage.run(state, context)
        dimensions = {label.dimension for label in state.labels}
        self.assertIn("access.access_mode", dimensions)
        self.assertIn("evidence.evidential_role", dimensions)
        self.assertIn("evidence.evidence_state", dimensions)
        self.assertIn("disposition", dimensions)
        self.assertIn("top_level_mode", dimensions)


if __name__ == "__main__":
    unittest.main()
