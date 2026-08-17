from __future__ import annotations

import json
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.fixture_schema import load_fixture
from evaluation.validate_fixtures import validate_fixture


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v3.yaml"
STATS_PATH = REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v3_statistics.json"


@unittest.skipUnless(FIXTURE_PATH.exists() and STATS_PATH.exists(), "document_rag_v3 fixture has not been generated")
class DocumentRagV3FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_fixture(FIXTURE_PATH)
        cls.stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))

    def test_fixture_validates_and_has_required_counts(self) -> None:
        validate_fixture(self.fixture)
        self.assertEqual(self.fixture.fixture_id, "document_rag_v3")
        self.assertEqual(len(self.fixture.cases), 400)
        counts = Counter(case.metadata.get("scenario") for case in self.fixture.cases)
        self.assertEqual(counts, {"D1": 80, "D2": 80, "D3": 80, "D4": 80, "D5": 80})

    def test_matched_families_are_structurally_complete(self) -> None:
        by_pair: dict[str, list] = defaultdict(list)
        for case in self.fixture.cases:
            by_pair[case.pair_id].append(case)
        d124 = [rows for pair_id, rows in by_pair.items() if pair_id and pair_id.startswith("D124_")]
        d3 = [rows for pair_id, rows in by_pair.items() if pair_id and pair_id.startswith("D3_")]
        d5 = [rows for pair_id, rows in by_pair.items() if pair_id and pair_id.startswith("D5_")]
        self.assertEqual(len(d124), 80)
        self.assertTrue(all(Counter(row.metadata.get("scenario") for row in rows) == {"D1": 1, "D2": 1, "D4": 1} for rows in d124))
        self.assertEqual(len(d3), 40)
        self.assertTrue(all(Counter(row.case_subtype for row in rows) == {"aggregate_safe": 1, "individual_restricted": 1} for rows in d3))
        self.assertEqual(len(d5), 40)
        self.assertTrue(all(Counter(row.case_subtype for row in rows) == {"mixed_primary": 1, "contextual_only": 1} for rows in d5))

    def test_no_unexpected_duplicate_questions_or_documents(self) -> None:
        self.assertEqual(self.stats["unexpected_exact_duplicate_questions"], 0)
        self.assertEqual(self.stats["unexpected_exact_duplicate_document_content"], 0)
        self.assertEqual(self.stats["exact_duplicate_questions"], 0)
        self.assertEqual(self.stats["exact_duplicate_document_content"], 0)

    def test_d5_source_text_has_no_role_hint_phrases(self) -> None:
        prohibited = [
            "primary evidence",
            "contextual evidence",
            "authoritative source",
            "not authoritative",
            "cannot prove",
            "insufficient evidence",
            "background only",
            "does not include a signed confirmation",
            "final assignment notice",
            "this source must not be used",
        ]
        for document in self.fixture.documents:
            if document.metadata.get("scenario") != "D5":
                continue
            lowered = document.content.lower()
            for phrase in prohibited:
                self.assertNotIn(phrase, lowered, f"{document.alias} leaked phrase {phrase!r}")


if __name__ == "__main__":
    unittest.main()
