from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "mailex"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_evidence_benchmark import validate


BENCHMARK_ROOT = REPO_ROOT / "data" / "benchmarks" / "evidence_unit_v1"
SOURCE_ROOT = REPO_ROOT / "data" / "external" / "mailex" / "extracted" / "data"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class EvidenceUnitV1BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = read_jsonl(BENCHMARK_ROOT / "cases.jsonl")
        cls.gold = read_jsonl(BENCHMARK_ROOT / "gold.jsonl")
        cls.manifest = json.loads((BENCHMARK_ROOT / "source_manifest.json").read_text(encoding="utf-8"))

    def test_a_validator_passes(self) -> None:
        self.assertEqual(validate(BENCHMARK_ROOT), [])

    def test_b_case_and_gold_counts(self) -> None:
        by_scenario = {}
        for row in self.gold:
            by_scenario[row["scenario"]] = by_scenario.get(row["scenario"], 0) + 1
        self.assertEqual(by_scenario, {"D6": 10, "D7": 10, "D8": 10, "D8_NONCLOSING": 2})
        self.assertEqual(len(self.cases), 32)
        self.assertEqual(len(self.gold), 32)

    def test_c_runtime_cases_do_not_contain_scorer_only_fields(self) -> None:
        forbidden = {
            "gold_role",
            "gold_status",
            "expected_status",
            "expected_presence",
            "primary_evidence_ids",
            "contextual_evidence_ids",
            "contrastive_evidence_ids",
            "closure_type",
        }
        for case in self.cases:
            self.assertFalse(forbidden & set(case), case["case_id"])
            for unit in case["evidence_units"]:
                self.assertFalse(forbidden & set(unit), f"{case['case_id']}::{unit['evidence_id']}")

    def test_d_d6_d7_d8_triplets_have_expected_states(self) -> None:
        by_seed: dict[str, dict[str, dict]] = {}
        for row in self.gold:
            if row["scenario"] in {"D6", "D7", "D8"}:
                by_seed.setdefault(row["seed_id"], {})[row["scenario"]] = row
        self.assertEqual(len(by_seed), 10)
        for seed_id, group in by_seed.items():
            self.assertEqual(set(group), {"D6", "D7", "D8"})
            self.assertEqual(group["D6"]["expected_status"], "OPEN")
            self.assertTrue(group["D6"]["expected_presence"])
            self.assertEqual(group["D7"]["expected_status"], "ABSENT")
            self.assertFalse(group["D7"]["expected_presence"])
            self.assertEqual(group["D8"]["expected_status"], "CLOSED")
            self.assertFalse(group["D8"]["expected_presence"])

    def test_e_d7_is_browser_history_only_and_deterministic(self) -> None:
        for case in self.cases:
            if case["scenario"] != "D7":
                continue
            self.assertTrue(case["evidence_units"])
            for unit in case["evidence_units"]:
                self.assertEqual(unit["source_type"], "BrowserHistory")
                self.assertTrue(unit["provenance"]["synthetic"])
                self.assertEqual(unit["provenance"]["transformation_rule"], "deterministic_topic_trace_v1")

    def test_f_license_and_provenance_are_recorded(self) -> None:
        for filename in ["README.md", "LICENSE_DATA.md", "ATTRIBUTION.md", "SOURCE_PROVENANCE.md", "source_manifest.json"]:
            self.assertTrue((BENCHMARK_ROOT / filename).exists(), filename)
        self.assertEqual(self.manifest["source_dataset"], "MailEx")
        self.assertTrue(self.manifest["downloaded_archive_sha256"])
        self.assertTrue(self.manifest["source_repository_commit"])
        self.assertIn("data/external/", (REPO_ROOT / ".gitignore").read_text(encoding="utf-8"))

    def test_g_selected_person_name_tokens_are_masked(self) -> None:
        text = (BENCHMARK_ROOT / "cases.jsonl").read_text(encoding="utf-8")
        for token in ["Andy", "Carol", "Gossett", "Jay", "Jeff", "Mary", "Rabon", "Tom", "Vernon"]:
            self.assertNotRegex(text, rf"\b{token}\b")

    @unittest.skipUnless(SOURCE_ROOT.exists(), "raw MailEx data is intentionally not committed")
    def test_h_downloaded_source_json_parse_when_present(self) -> None:
        counts = {}
        for split in ["train", "dev", "test"]:
            files = sorted((SOURCE_ROOT / split).glob("*.json"))
            counts[split] = len(files)
            for path in files:
                json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(counts, {"train": 1200, "dev": 150, "test": 150})


if __name__ == "__main__":
    unittest.main()
