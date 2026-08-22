from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluation.wolala2026.adapters import ALL_MODES
from evaluation.wolala2026.common import read_json, read_jsonl, sha256_file
from evaluation.wolala2026.execution_spec import load_execution_spec, validate_execution_spec
from evaluation.wolala2026.generate_heldout_v3 import GOLD_HINT_TERMS, validate_runtime_cases
from evaluation.wolala2026.pilot_data import HELDOUT_DATASET_V1, HELDOUT_DATASET_V2, HELDOUT_DATASET_V3, RETIRED_HELDOUT_DATASETS
from evaluation.wolala2026.run_pilot import run_pilot


ROOT = Path(__file__).resolve().parents[1] / "wolala2026"
DATASET_DIR = ROOT / "data" / HELDOUT_DATASET_V3
SPEC_V4_PATH = ROOT / "HELDOUT_EXECUTION_SPEC_v4.json"
PREHELDOUT_DIR = ROOT / "preheldout_v3_attempt1"
GOLD_ONLY_FIELDS = {
    "expected_top_level_mode",
    "expected_fulfilment_status",
    "expected_cfaf_realization",
    "expected_public_reason_class",
    "expected_internal_reason_class",
    "expected_next_step_codes",
    "expected_permitted_output",
    "expected_public_response_norm",
    "canonical_answer_markers",
    "gold_answer",
}


class WolalaFinalExperimentV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = read_jsonl(DATASET_DIR / "cases.jsonl")
        cls.gold = read_jsonl(DATASET_DIR / "gold.jsonl")
        cls.manifest = read_json(DATASET_DIR / "manifest.json")
        cls.generation_manifest = read_json(DATASET_DIR / "generation_manifest.json")
        cls.overlap = read_json(DATASET_DIR / "OVERLAP_AUDIT.json")
        cls.spec = load_execution_spec(SPEC_V4_PATH)

    def test_dataset_shape_prefixes_and_seed(self) -> None:
        validation = validate_runtime_cases(self.cases, self.gold)
        self.assertTrue(validation["valid"])
        self.assertEqual(self.manifest["case_count"], 40)
        self.assertEqual(self.manifest["pair_count"], 20)
        self.assertEqual(self.manifest["families"], {"P1": 8, "P2": 8, "P3": 8, "P4": 8, "P5": 8})
        self.assertEqual(self.manifest["fixed_seed"], 20261017)
        self.assertTrue(all(case["case_id"].startswith("HELD3_") for case in self.cases))
        self.assertTrue(all(case["pair_id"].startswith("H3PAIR_") for case in self.cases))

    def test_runtime_cases_are_separate_from_scorer_gold(self) -> None:
        leaked_fields = sorted({field for case in self.cases for field in GOLD_ONLY_FIELDS if field in case})
        self.assertEqual(leaked_fields, [])
        self.assertTrue(all("protected_markers" in case for case in self.cases))
        self.assertTrue(all("forbidden_disclosures" in case for case in self.cases))
        self.assertEqual(sorted(case["case_id"] for case in self.cases), sorted(record["case_id"] for record in self.gold))
        self.assertTrue(all(record["scorer_only"] is True for record in self.gold))
        self.assertTrue(self.manifest["runtime_gold_separation"]["cases_jsonl_runtime_visible_only"])
        self.assertTrue(self.manifest["runtime_gold_separation"]["gold_jsonl_scorer_only"])

    def test_generator_visible_gold_hint_scan_is_zero(self) -> None:
        scan = self.generation_manifest["generator_visible_gold_hint_scan"]
        self.assertEqual(scan["terms"], GOLD_HINT_TERMS)
        self.assertEqual(scan["generator_visible_gold_hint_count"], 0)
        self.assertEqual(scan["generator_visible_gold_hint_hits"], [])
        self.assertEqual(self.manifest["generator_visible_gold_hint_count"], 0)

    def test_overlap_audit_required_sets_are_empty(self) -> None:
        for key in [
            "case_id_overlap",
            "pair_id_overlap",
            "evidence_id_overlap",
            "source_id_overlap",
            "thread_id_overlap",
            "protected_marker_overlap",
            "exact_query_overlap",
            "exact_source_text_overlap",
            "normalized_text_hash_overlap",
        ]:
            self.assertEqual(self.overlap[key], [])
        self.assertTrue(self.overlap["all_required_overlap_sets_empty"])

    def test_pair_design_and_p5_source_existence_pattern(self) -> None:
        pairs = read_json(DATASET_DIR / "pair_design_manifest.json")["pairs"]
        self.assertEqual(len(pairs), 20)
        p5_cases = [case for case in self.cases if case["family"] == "P5"]
        for pair_id in sorted({case["pair_id"] for case in p5_cases}):
            pair = {case["variant"]: case for case in p5_cases if case["pair_id"] == pair_id}
            self.assertEqual(pair["A"]["sources"], [])
            self.assertEqual(len(pair["B"]["sources"]), 1)
            self.assertEqual(pair["B"]["sources"][0]["access_mode"], "DENY")
            self.assertEqual(pair["B"]["sources"][0]["existence_visibility"], "INTERNAL_ONLY")

    def test_execution_spec_v4_exact_counts(self) -> None:
        validation = validate_execution_spec(
            self.spec,
            cases=self.cases,
            modes=ALL_MODES,
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

    def test_plan_only_outputs_no_raw_results_or_api_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = run_pilot(
                dataset=HELDOUT_DATASET_V3,
                modes=ALL_MODES,
                repetitions=3,
                output_dir=tmp,
                max_mode_executions=360,
                max_embedding_calls=60,
                max_generation_calls=380,
                max_total_external_calls=420,
                plan_only=True,
                execution_spec=SPEC_V4_PATH,
            )
            plan = read_json(Path(tmp) / "execution_plan.json")
            self.assertEqual(manifest["completion_status"], "PLANNED")
            self.assertEqual(plan["schema_version"], "wolala-heldout-plan-only-v4")
            self.assertEqual(plan["dataset"], HELDOUT_DATASET_V3)
            self.assertEqual(plan["external_api_calls_in_plan_only"], 0)
            self.assertEqual(plan["heldout_model_execution_count"], 0)
            self.assertTrue(plan["no_retrieval_embedding_adapter_generation_or_scoring_performed"])
            self.assertFalse((Path(tmp) / "raw_results.jsonl").exists())
            self.assertFalse((Path(tmp) / "case_scores.jsonl").exists())

    def test_preheldout_attempt1_plan_artifacts_are_plan_only(self) -> None:
        plan = read_json(PREHELDOUT_DIR / "execution_plan.json")
        self.assertEqual(plan["dataset"], HELDOUT_DATASET_V3)
        self.assertEqual(plan["heldout_model_execution_count"], 0)
        self.assertEqual(plan["heldout_embedding_calls"], 0)
        self.assertEqual(plan["heldout_generation_calls"], 0)
        self.assertEqual(plan["external_api_calls_in_plan_only"], 0)
        self.assertFalse((PREHELDOUT_DIR / "HELDOUT_RUN_AUTHORIZATION.json").exists())
        self.assertFalse((PREHELDOUT_DIR / "raw_results.jsonl").exists())

    def test_execution_requires_authorization_before_api_key_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = dict(self.spec)
            spec["authorization_path"] = str(Path(tmp) / "missing_authorization.json")
            with self.assertRaisesRegex(RuntimeError, "authorization artifact"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V3,
                    modes=ALL_MODES,
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    allow_heldout=True,
                    allow_real_api=True,
                    execution_spec=spec,
                )

    def test_nonempty_output_directory_fails_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "already-there.txt").write_text("not empty\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "nonempty output directory"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V3,
                    modes=ALL_MODES,
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    allow_heldout=True,
                    allow_real_api=True,
                    execution_spec=self.spec,
                )

    def test_retired_registry_and_code_block_v1_v2(self) -> None:
        registry = read_json(ROOT / "RETIRED_HELDOUT_DATASET_REGISTRY_v1.json")
        retired = {row["dataset"]: row for row in registry["datasets"]}
        self.assertEqual(registry["active_heldout_dataset"], HELDOUT_DATASET_V3)
        self.assertEqual(RETIRED_HELDOUT_DATASETS[HELDOUT_DATASET_V1], "RETIRED_AFTER_PRE_EXECUTION_IMPLEMENTATION_GUARD_FAILURE")
        self.assertEqual(RETIRED_HELDOUT_DATASETS[HELDOUT_DATASET_V2], "RETIRED_AFTER_SCIENTIFIC_INTEGRITY_FAILURE")
        self.assertFalse(retired[HELDOUT_DATASET_V1]["execution_permitted"])
        self.assertFalse(retired[HELDOUT_DATASET_V2]["execution_permitted"])
        self.assertFalse(retired[HELDOUT_DATASET_V2]["valid_for_manuscript"])

    def test_preaudit_and_freeze_manifest_are_closed(self) -> None:
        preaudit = read_json(ROOT / "FINAL_HELDOUT_V3_PREAUDIT.json")
        freeze_manifest = read_json(ROOT / "PRE_HELDOUT_V3_FREEZE_MANIFEST.json")
        self.assertTrue(preaudit["all_booleans_true"])
        self.assertTrue(preaudit["audit_passed"])
        self.assertTrue(all(preaudit["checks"].values()))
        self.assertTrue(freeze_manifest["preaudit_passed"])
        self.assertFalse(freeze_manifest["authorization_created_in_freeze_phase"])
        self.assertEqual(freeze_manifest["heldout_mode_executions_in_freeze_phase"], 0)

    def test_spec_checksums_match_frozen_files(self) -> None:
        checksums = self.spec["checksums"]
        self.assertEqual(checksums["heldout_dataset"], self.manifest["dataset_checksum"])
        self.assertEqual(checksums["protocol_v4"], sha256_file(ROOT / "WOLALA2026_PILOT_PROTOCOL_v4.md"))
        self.assertEqual(checksums["runner"], sha256_file(ROOT / "run_pilot.py"))
        self.assertEqual(checksums["retrieval"], sha256_file(ROOT / "retrieval.py"))
        self.assertEqual(checksums["adapters"], sha256_file(ROOT / "adapters.py"))
        self.assertEqual(checksums["parser"], sha256_file(ROOT / "adapters.py"))
        self.assertEqual(checksums["scorer"], sha256_file(ROOT / "score_pilot.py"))
        self.assertEqual(checksums["heldout_v3_cases"], sha256_file(DATASET_DIR / "cases.jsonl"))
        self.assertEqual(checksums["heldout_v3_gold"], sha256_file(DATASET_DIR / "gold.jsonl"))


if __name__ == "__main__":
    unittest.main()
