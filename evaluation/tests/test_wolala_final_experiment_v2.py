from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluation.wolala2026.common import read_json, read_jsonl, sha256_file
from evaluation.wolala2026.execution_spec import load_execution_spec, validate_execution_spec, validate_heldout_authorization
from evaluation.wolala2026.pilot_data import DEV_DATASET, HELDOUT_DATASET_V1, HELDOUT_DATASET_V2, validate_dataset
from evaluation.wolala2026.run_pilot import run_pilot


ROOT = Path(__file__).resolve().parents[1] / "wolala2026"
SPEC_V3_PATH = ROOT / "HELDOUT_EXECUTION_SPEC_v3.json"


class WolalaFinalExperimentV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dev_cases = read_jsonl(ROOT / "data" / DEV_DATASET / "cases.jsonl")
        cls.v1_cases = read_jsonl(ROOT / "data" / HELDOUT_DATASET_V1 / "cases.jsonl")
        cls.v2_cases = read_jsonl(ROOT / "data" / HELDOUT_DATASET_V2 / "cases.jsonl")
        cls.v2_manifest = read_json(ROOT / "data" / HELDOUT_DATASET_V2 / "manifest.json")
        cls.v2_generation_manifest = read_json(ROOT / "data" / HELDOUT_DATASET_V2 / "generation_manifest.json")
        cls.spec = load_execution_spec(SPEC_V3_PATH)

    def test_heldout_v2_dataset_shape_and_prefix(self) -> None:
        validation = validate_dataset(self.v2_cases, expected_count=40)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["pair_count"], 20)
        self.assertEqual(validation["families"], {"P1": 8, "P2": 8, "P3": 8, "P4": 8, "P5": 8})
        self.assertTrue(all(case["case_id"].startswith("HELD2_") for case in self.v2_cases))
        self.assertTrue(all(case["pair_id"].startswith("HELD2_") for case in self.v2_cases))
        self.assertEqual(self.v2_manifest["fixed_seed"], 20261013)
        self.assertEqual(self.v2_generation_manifest["fixed_seed"], 20261013)
        self.assertTrue(self.v2_generation_manifest["personal_data_check"]["privacy_safe"])

    def test_no_development_v1_or_marker_overlap(self) -> None:
        dev_ids = {case["case_id"] for case in self.dev_cases}
        v1_ids = {case["case_id"] for case in self.v1_cases}
        v2_ids = {case["case_id"] for case in self.v2_cases}
        self.assertFalse(v2_ids & dev_ids)
        self.assertFalse(v2_ids & v1_ids)
        for key in [
            "no_case_id_overlap",
            "no_pair_id_overlap",
            "no_protected_marker_overlap",
            "no_source_text_overlap",
            "no_query_text_overlap",
            "no_evidence_unit_id_overlap",
        ]:
            self.assertTrue(self.v2_generation_manifest["overlap_checks"][key])

    def test_execution_spec_v3_validation_and_exact_counts(self) -> None:
        validation = validate_execution_spec(
            self.spec,
            cases=self.v2_cases,
            modes=self.spec["modes"],
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
        self.assertEqual(validation["external_warmup_calls"], 0)

    def test_development_path_rejects_heldout_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "allow-heldout"):
                run_pilot(
                    dataset=DEV_DATASET,
                    modes=self.spec["modes"],
                    repetitions=1,
                    output_dir=tmp,
                    max_mode_executions=30,
                    max_embedding_calls=10,
                    max_generation_calls=30,
                    max_total_external_calls=40,
                    allow_heldout=True,
                    plan_only=True,
                )

    def test_heldout_v1_is_retired_and_cannot_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "retired"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V1,
                    modes=self.spec["modes"],
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    allow_heldout=True,
                    allow_real_api=True,
                    execution_spec=ROOT / "HELDOUT_EXECUTION_SPEC_v2.json",
                )

    def test_v3_rejects_v1_or_wrong_case_prefix(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "HELD2_"):
            validate_execution_spec(self.spec, cases=[{"case_id": f"HELD_{index:02d}"} for index in range(40)], modes=self.spec["modes"], repetitions=3, plan_only=True)
        with self.assertRaisesRegex(RuntimeError, "HELD2_"):
            validate_execution_spec(self.spec, cases=[{"case_id": f"BAD_{index:02d}"} for index in range(40)], modes=self.spec["modes"], repetitions=3, plan_only=True)

    def test_heldout_v2_execution_fails_without_required_flags_or_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "allow-heldout"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V2,
                    modes=self.spec["modes"],
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    execution_spec=SPEC_V3_PATH,
                )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "execution requires --execution-spec"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V2,
                    modes=self.spec["modes"],
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    allow_heldout=True,
                )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "allow-real-api"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V2,
                    modes=self.spec["modes"],
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    allow_heldout=True,
                    execution_spec=SPEC_V3_PATH,
                )

    def test_checksum_caps_and_nonempty_output_dir_fail_closed(self) -> None:
        bad = dict(self.spec)
        bad["checksums"] = dict(self.spec["checksums"], heldout_dataset="bad")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "dataset checksum"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V2,
                    modes=self.spec["modes"],
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    allow_heldout=True,
                    allow_real_api=True,
                    execution_spec=bad,
                )

        with self.assertRaises(RuntimeError):
            validate_execution_spec(dict(self.spec, max_total_external_calls=399), plan_only=True)

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "already-there.txt").write_text("not empty\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "nonempty output directory"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V2,
                    modes=self.spec["modes"],
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    allow_heldout=True,
                    allow_real_api=True,
                    execution_spec=SPEC_V3_PATH,
                )

    def test_plan_only_makes_no_api_call_or_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = run_pilot(
                dataset=HELDOUT_DATASET_V2,
                modes=self.spec["modes"],
                repetitions=3,
                output_dir=tmp,
                max_mode_executions=360,
                max_embedding_calls=60,
                max_generation_calls=380,
                max_total_external_calls=420,
                plan_only=True,
                execution_spec=SPEC_V3_PATH,
            )
            plan = read_json(Path(tmp) / "execution_plan.json")
            self.assertEqual(manifest["completion_status"], "PLANNED")
            self.assertEqual(plan["dataset"], HELDOUT_DATASET_V2)
            self.assertEqual(plan["planned_mode_executions"], 360)
            self.assertEqual(plan["planned_unique_embedding_requests"], 40)
            self.assertEqual(plan["planned_generation_requests_maximum"], 360)
            self.assertEqual(plan["planned_external_requests_without_retries_maximum"], 400)
            self.assertEqual(plan["external_api_calls_in_plan_only"], 0)
            self.assertTrue(plan["no_retrieval_embedding_adapter_generation_or_scoring_performed"])
            self.assertFalse((Path(tmp) / "raw_results.jsonl").exists())
            self.assertFalse((Path(tmp) / "case_scores.jsonl").exists())

    def test_authorization_attempt_matching(self) -> None:
        auth = {
            "authorization_status": "AUTHORIZED_NOT_STARTED",
            "dataset": HELDOUT_DATASET_V2,
            "run_attempt": 1,
            "allow_real_api": True,
            "allow_heldout": True,
            "checksums": dict(self.spec["checksums"]),
            "max_mode_executions": 360,
            "max_embedding_calls": 60,
            "max_generation_calls": 380,
            "max_total_external_calls": 420,
            "max_total_retry_attempts": 20,
            "max_retries_per_logical_request": 1,
            "external_warmup_calls": 0,
        }
        self.assertTrue(validate_heldout_authorization(auth, self.spec)["valid"])
        with self.assertRaises(RuntimeError):
            validate_heldout_authorization(dict(auth, run_attempt=2), self.spec)

    def test_scorer_parser_statistics_and_latency_checksums_are_frozen(self) -> None:
        checksums = self.spec["checksums"]
        self.assertEqual(checksums["parser"], sha256_file(ROOT / "adapters.py"))
        self.assertEqual(checksums["scorer"], sha256_file(ROOT / "score_pilot.py"))
        self.assertEqual(checksums["statistical_analysis_module"], sha256_file(ROOT / "analyze_heldout.py"))
        self.assertEqual(checksums["latency_analysis_module"], sha256_file(ROOT / "latency_analysis.py"))
        self.assertEqual(checksums["prompt_only_prompt"], sha256_file(ROOT / "prompts" / "prompt_only_v1.txt"))
        self.assertEqual(checksums["cfaf_generator_prompt"], sha256_file(ROOT / "prompts" / "cfaf_generator_v1.txt"))


if __name__ == "__main__":
    unittest.main()
