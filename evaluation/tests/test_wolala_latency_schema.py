from __future__ import annotations

import unittest

from evaluation.wolala2026.labels import StageName
from evaluation.wolala2026.pipeline import latency_summary, run_pipeline
from evaluation.wolala2026.run_smoke import load_smoke_cases


class WolalaLatencySchemaTests(unittest.TestCase):
    def test_every_stage_has_nonnegative_timing_and_summary_percentiles(self) -> None:
        states = [run_pipeline(case) for case in load_smoke_cases()[:3]]
        for state in states:
            for stage in StageName:
                key = f"{stage.value.lower()}_ms"
                self.assertIn(key, state.stage_timings)
                self.assertGreaterEqual(state.stage_timings[key], 0.0)
            self.assertIn("end_to_end_ms", state.stage_timings)
            self.assertGreaterEqual(state.stage_timings["end_to_end_ms"], 0.0)
            self.assertIn("embedding_api_ms", state.api_timings)
            self.assertIn("generation_api_ms", state.api_timings)
            self.assertIn("external_api_ms", state.api_timings)
        summary = latency_summary(states)
        self.assertIn("end_to_end_ms", summary)
        self.assertIn("p50_ms", summary["end_to_end_ms"])
        self.assertIn("p95_ms", summary["end_to_end_ms"])


if __name__ == "__main__":
    unittest.main()
