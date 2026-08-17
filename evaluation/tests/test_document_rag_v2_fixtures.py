from __future__ import annotations

import re
import unittest
from pathlib import Path

from evaluation.fixture_schema import load_fixture
from evaluation.validate_fixtures import validate_fixture


REPO_ROOT = Path(__file__).resolve().parents[2]
V1_PATH = REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v1.yaml"
V2_PATH = REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v2.yaml"

PROHIBITED_D5_ROLE_HINTS = [
    r"\bprimary evidence\b",
    r"\bcontextual evidence\b",
    r"\bauthoritative evidence\b",
    r"\bcannot prove\b",
    r"\bnot proof\b",
    r"\bnot sufficient\b",
    r"\bonly background\b",
    r"\bcontextual support only\b",
    r"\bthis source is not sufficient\b",
]


class DocumentRagV2FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v1 = load_fixture(V1_PATH)
        cls.v2 = load_fixture(V2_PATH)

    def test_a_v2_validates_structurally(self) -> None:
        self.assertEqual(self.v2.fixture_id, "document_rag_v2")
        self.assertEqual(len(self.v2.cases), 40)
        validate_fixture(self.v2)

    def test_b_d1_to_d4_cases_preserved(self) -> None:
        v1_docs = self.v1.document_by_alias()
        v2_docs = self.v2.document_by_alias()
        v1_cases = {case.case_id: case for case in self.v1.cases}
        v2_cases = {case.case_id: case for case in self.v2.cases}
        preserved_prefixes = ("FULL_", "METADATA_", "DENY_", "AGG_")
        for case_id, v1_case in v1_cases.items():
            if not case_id.startswith(preserved_prefixes):
                continue
            self.assertEqual(v2_cases[case_id].dict(), v1_case.dict())
            for alias in v1_case.scope:
                self.assertEqual(v2_docs[alias].content, v1_docs[alias].content)

    def test_c_d5_has_matched_mixed_and_contextual_cases(self) -> None:
        mixed = [case for case in self.v2.cases if case.case_subtype == "mixed_primary"]
        context_only = [case for case in self.v2.cases if case.case_subtype == "contextual_only"]
        self.assertEqual(len(mixed), 4)
        self.assertEqual(len(context_only), 4)
        self.assertEqual([case.pair_id for case in mixed], [f"MIXED_{index:02d}" for index in range(1, 5)])
        self.assertEqual([case.pair_id for case in context_only], [f"CONTEXT_{index:02d}" for index in range(1, 5)])
        for case in mixed:
            self.assertEqual(case.expected_role_aware_source_roles, ["primary", "contextual"])
            self.assertEqual(len(case.expected_supporting_document_aliases), 1)
            self.assertEqual(len(case.expected_contextual_document_aliases), 1)
        for case in context_only:
            self.assertEqual(case.expected_role_aware_source_roles, ["contextual"])
            self.assertFalse(case.answerable_with_primary_evidence)

    def test_d_d5_generator_visible_source_prose_has_no_role_hint_leakage(self) -> None:
        docs = self.v2.document_by_alias()
        d5_aliases = {
            alias
            for case in self.v2.cases
            if case.scenario_family == "mixed_or_insufficient_primary_evidence"
            for alias in case.scope
        }
        for alias in sorted(d5_aliases):
            text = docs[alias].content.lower()
            for pattern in PROHIBITED_D5_ROLE_HINTS:
                self.assertIsNone(re.search(pattern, text), f"{alias} leaked role hint pattern {pattern!r}")


if __name__ == "__main__":
    unittest.main()
