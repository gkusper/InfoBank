from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from evaluation.load_evidence_fixtures import SCORER_ONLY_FIELDS, load_benchmark


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = REPO_ROOT / "data" / "benchmarks" / "evidence_unit_v2_holdout"


@unittest.skipUnless((BENCHMARK_ROOT / "cases.jsonl").exists(), "evidence_unit_v2_holdout has not been generated")
class EvidenceUnitV2HoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = load_benchmark(BENCHMARK_ROOT)
        cls.gold = cls.benchmark.gold
        cls.cases = cls.benchmark.cases
        cls.source_manifest = json.loads((BENCHMARK_ROOT / "source_manifest.json").read_text(encoding="utf-8"))
        cls.stats = json.loads((BENCHMARK_ROOT / "benchmark_statistics.json").read_text(encoding="utf-8"))

    def test_required_counts_and_closure_distribution(self) -> None:
        self.assertEqual(len(self.cases), 340)
        self.assertEqual(Counter(case["scenario"] for case in self.cases), {"D6": 100, "D7": 100, "D8": 100, "D8_NONCLOSING": 40})
        self.assertEqual(self.stats["closure_type_counts"], {"completed": 40, "cancelled": 30, "superseded": 30})

    def test_runtime_cases_do_not_contain_scorer_only_fields(self) -> None:
        for case in self.cases:
            self.assertFalse(SCORER_ONLY_FIELDS & set(case), case["case_id"])
            for unit in case.get("evidence_units") or []:
                leaked = SCORER_ONLY_FIELDS & set(unit)
                self.assertFalse(leaked, f"{case['case_id']} leaked {sorted(leaked)}")
                provenance = unit.get("provenance") or {}
                self.assertNotIn("closure_type", provenance)
                self.assertNotIn("gold_role", provenance)

    def test_source_threads_are_disjoint_from_v1(self) -> None:
        excluded = set(self.source_manifest["source_exclusion_manifest"]["excluded_threads"])
        used = {
            unit.get("provenance", {}).get("source_thread_id")
            for case in self.cases
            for unit in case.get("evidence_units") or []
            if unit.get("provenance", {}).get("source_thread_id")
        }
        self.assertFalse(excluded & used)

    def test_triplets_exist_for_all_main_seeds(self) -> None:
        triplets = [
            json.loads(line)
            for line in (BENCHMARK_ROOT / "triplets.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(triplets), 100)
        case_ids = {case["case_id"] for case in self.cases}
        for row in triplets:
            self.assertIn(row["d6_case_id"], case_ids)
            self.assertIn(row["d7_case_id"], case_ids)
            self.assertIn(row["d8_case_id"], case_ids)

    def test_natural_and_synthetic_strata_are_recorded(self) -> None:
        strata = Counter(row.get("natural_or_synthetic") for row in self.gold)
        self.assertGreater(strata["natural"], 0)
        self.assertGreater(strata["synthetic"], 0)


if __name__ == "__main__":
    unittest.main()
