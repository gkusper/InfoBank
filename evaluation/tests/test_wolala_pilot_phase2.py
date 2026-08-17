from __future__ import annotations

import unittest
from pathlib import Path

from evaluation.wolala2026.adapters import MODE_CFAF_PIPELINE, MODE_PROMPT_ONLY_CONTROL, MODE_STANDARD_RAG
from evaluation.wolala2026.common import read_json, read_jsonl, sha256_file, stable_hash
from evaluation.wolala2026.pilot_data import DEV_DATASET, HELDOUT_DATASET, REQUIRED_CASE_FIELDS, validate_dataset
from evaluation.wolala2026.run_pilot import run_pilot
from evaluation.wolala2026.score_pilot import score_results


ROOT = Path(__file__).resolve().parents[1] / "wolala2026"
DEV_DIR = ROOT / "data" / DEV_DATASET
HELDOUT_DIR = ROOT / "data" / HELDOUT_DATASET
RUN_DIR = ROOT / "development_run"


class WolalaPilotPhase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dev_cases = read_jsonl(DEV_DIR / "cases.jsonl")
        cls.heldout_cases = read_jsonl(HELDOUT_DIR / "cases.jsonl")
        cls.raw_results = read_jsonl(RUN_DIR / "raw_results.jsonl")
        cls.summary = read_json(RUN_DIR / "summary.json")
        cls.manifest = read_json(RUN_DIR / "run_manifest.json")
        cls.baseline = read_json(ROOT / "readiness_baseline_manifest.json")

    def test_dataset_counts_schema_and_family_composition(self) -> None:
        self.assertEqual(len(self.dev_cases), 10)
        self.assertEqual(len(self.heldout_cases), 40)
        self.assertTrue(validate_dataset(self.dev_cases, expected_count=10)["valid"])
        self.assertTrue(validate_dataset(self.heldout_cases, expected_count=40)["valid"])
        for case in self.dev_cases + self.heldout_cases:
            self.assertFalse([field for field in REQUIRED_CASE_FIELDS if field not in case])
        self.assertEqual({case["family"] for case in self.dev_cases}, {"P1", "P2", "P3", "P4", "P5"})
        self.assertEqual({case["family"] for case in self.heldout_cases}, {"P1", "P2", "P3", "P4", "P5"})

    def test_development_and_heldout_are_disjoint(self) -> None:
        dev_ids = {case["case_id"] for case in self.dev_cases}
        held_ids = {case["case_id"] for case in self.heldout_cases}
        dev_pairs = {case["pair_id"] for case in self.dev_cases}
        held_pairs = {case["pair_id"] for case in self.heldout_cases}
        dev_markers = {marker for case in self.dev_cases for marker in case.get("protected_markers", [])}
        held_markers = {marker for case in self.heldout_cases for marker in case.get("protected_markers", [])}
        self.assertFalse(dev_ids & held_ids)
        self.assertFalse(dev_pairs & held_pairs)
        self.assertFalse(dev_markers & held_markers)

    def test_heldout_cases_were_not_model_executed(self) -> None:
        result_case_ids = {result["case_id"] for result in self.raw_results}
        heldout_ids = {case["case_id"] for case in self.heldout_cases}
        self.assertFalse(result_case_ids & heldout_ids)
        self.assertEqual(self.baseline["heldout_mode_execution_count"], 0)
        self.assertEqual(self.manifest["heldout_mode_execution_count"], 0)

    def test_protocol_and_dataset_checksums_are_stable(self) -> None:
        self.assertEqual(self.baseline["protocol_checksum"], sha256_file(ROOT / "WOLALA2026_PILOT_PROTOCOL_v1.md"))
        self.assertEqual(self.baseline["development_dataset_checksum"], read_json(DEV_DIR / "manifest.json")["dataset_checksum"])
        self.assertEqual(self.baseline["heldout_dataset_checksum"], read_json(HELDOUT_DIR / "manifest.json")["dataset_checksum"])
        self.assertEqual(self.baseline["run_manifest_schema_checksum"], sha256_file(ROOT / "run_manifest_schema.json"))

    def test_shared_retrieval_snapshot_across_modes(self) -> None:
        by_case: dict[str, set[str]] = {}
        for result in self.raw_results:
            by_case.setdefault(result["case_id"], set()).add(result["retrieval_snapshot_hash"])
        self.assertEqual(len(by_case), 10)
        self.assertTrue(all(len(hashes) == 1 for hashes in by_case.values()))

    def test_baseline_modes_receive_no_external_cfaf_decision_labels(self) -> None:
        for result in self.raw_results:
            if result["mode_name"] in {MODE_STANDARD_RAG, MODE_PROMPT_ONLY_CONTROL}:
                self.assertFalse(result["generator_context_contains_cfaf_decision"])

    def test_cfaf_mode_has_filtered_generator_context(self) -> None:
        cfaf_results = [result for result in self.raw_results if result["mode_name"] == MODE_CFAF_PIPELINE]
        self.assertEqual(len(cfaf_results), 10)
        self.assertTrue(all(not result["generator_context_protected_markers"] for result in cfaf_results))

    def test_call_caps_and_heldout_guard(self) -> None:
        with self.assertRaises(RuntimeError):
            run_pilot(
                dataset=DEV_DATASET,
                modes=[MODE_STANDARD_RAG, MODE_PROMPT_ONLY_CONTROL, MODE_CFAF_PIPELINE],
                repetitions=1,
                output_dir=RUN_DIR / "_cap_test",
                max_mode_executions=29,
                max_embedding_calls=10,
                max_generation_calls=30,
                max_total_external_calls=40,
            )
        with self.assertRaises(RuntimeError):
            run_pilot(
                dataset=HELDOUT_DATASET,
                modes=[MODE_STANDARD_RAG],
                repetitions=1,
                output_dir=RUN_DIR / "_heldout_test",
                max_mode_executions=40,
                max_embedding_calls=0,
                max_generation_calls=0,
                max_total_external_calls=0,
            )

    def test_run_manifest_completeness_and_counts(self) -> None:
        schema = read_json(ROOT / "run_manifest_schema.json")
        for field in schema["required"]:
            self.assertIn(field, self.manifest)
        self.assertEqual(self.manifest["mode_execution_count"], 30)
        self.assertEqual(self.manifest["actual_embedding_calls"], 0)
        self.assertEqual(self.manifest["actual_generation_calls"], 0)
        self.assertEqual(self.manifest["actual_total_external_calls"], 0)
        self.assertEqual(self.manifest["completion_status"], "COMPLETED")

    def test_scorer_metrics_and_p5_source_existence_checks(self) -> None:
        scores = score_results(self.dev_cases, self.raw_results)
        cfaf_summary = next(row for row in scores["mode_summaries"] if row["mode_name"] == MODE_CFAF_PIPELINE)
        self.assertEqual(cfaf_summary["top_level_mode_accuracy"], 1.0)
        self.assertEqual(cfaf_summary["protected_content_leakage_rate"], 0.0)
        self.assertEqual(cfaf_summary["generator_exposure_rate"], 0.0)
        p5_pairs = [row for row in scores["pair_scores"] if row["family"] == "P5" and row["mode_name"] == MODE_CFAF_PIPELINE]
        self.assertTrue(p5_pairs)
        self.assertTrue(all(row["p5_public_response_equal"] for row in p5_pairs))
        self.assertTrue(all(row["source_existence_leakage"] is False for row in p5_pairs))

    def test_false_cfaf_and_request_fulfilment_are_measured(self) -> None:
        mode_summaries = {row["mode_name"]: row for row in self.summary["mode_summaries"]}
        for mode in [MODE_STANDARD_RAG, MODE_PROMPT_ONLY_CONTROL, MODE_CFAF_PIPELINE]:
            self.assertIn("false_cfaf_rate", mode_summaries[mode])
            self.assertIn("request_fulfilment_accuracy", mode_summaries[mode])

    def test_latency_fields_are_complete_and_nonnegative(self) -> None:
        required = [
            "query_profiling_ms",
            "candidate_retrieval_ms",
            "access_and_safety_resolution_ms",
            "evidence_labelling_ms",
            "sufficiency_and_permitted_output_ms",
            "top_level_mode_selection_ms",
            "response_realization_ms",
            "validation_trace_and_feedback_ms",
            "embedding_api_ms",
            "generation_api_ms",
            "external_api_ms",
            "end_to_end_ms",
        ]
        for result in self.raw_results:
            for field in required:
                self.assertIn(field, result["stage_timings"])
                self.assertGreaterEqual(result["stage_timings"][field], 0.0)
            self.assertGreaterEqual(result["end_to_end_ms"], 0.0)

    def test_baseline_manifest_checksum_is_self_consistent(self) -> None:
        without_self = {key: value for key, value in self.baseline.items() if key != "baseline_checksum"}
        self.assertEqual(self.baseline["baseline_checksum"], stable_hash(without_self))


if __name__ == "__main__":
    unittest.main()
