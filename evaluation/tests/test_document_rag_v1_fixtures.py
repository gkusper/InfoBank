from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from evaluation.clean_state import CleanStateError
from evaluation.fixture_schema import EvaluationFixture, load_fixture
from evaluation.generate_fixture_documents import generate_documents
from evaluation.load_fixtures import (
    MockEmbeddingProvider,
    build_id_mappings,
    case_to_harness_inputs,
    load_fixture_data,
)
from evaluation.retrieval import run_shared_retrieval
from evaluation.run_case import run_case
from evaluation.schemas import GenerationConfig, GenerationOutput
from evaluation.validate_fixtures import EXPECTED_FAMILY_COUNTS, validate_fixture


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v1.yaml"


class RecordingGenerator:
    def generate(self, system_prompt: str, user_prompt: str, config: GenerationConfig) -> GenerationOutput:
        return GenerationOutput(
            answer="MOCK",
            api_usage={
                "embedding_calls": 0,
                "generation_calls": 1,
                "keyword_routing_calls": 0,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "errors": [],
                "retries": 0,
            },
        )


class FakeEmbeddingClient:
    class Embeddings:
        def create(self, input: str, model: str) -> Any:
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])], usage=None)

    def __init__(self):
        self.embeddings = self.Embeddings()


class FakeCollection:
    def __init__(self):
        self.added: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []
        self.rows = [
            {"id": "chunk-doc-a", "document": "Allowed scoped text", "metadata": {"document_id": "doc-a", "file_name": "a.pdf"}, "distance": 0.1},
            {"id": "chunk-doc-b", "document": "Forbidden variant text", "metadata": {"document_id": "doc-b", "file_name": "b.pdf"}, "distance": 0.2},
        ]

    def add(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict[str, Any]], documents: list[str]) -> None:
        self.added.append({"ids": ids, "embeddings": embeddings, "metadatas": metadatas, "documents": documents})

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.query_calls.append(kwargs)
        rows = self.rows
        where = kwargs.get("where")
        if where:
            if "$in" in where.get("document_id", {}):
                allowed = set(where["document_id"]["$in"])
            else:
                allowed = {where["document_id"]}
            rows = [row for row in rows if row["metadata"]["document_id"] in allowed]
        rows = rows[: kwargs.get("n_results", len(rows))]
        return {
            "ids": [[row["id"] for row in rows]],
            "documents": [[row["document"] for row in rows]],
            "metadatas": [[row["metadata"] for row in rows]],
            "distances": [[row["distance"] for row in rows]],
        }


class DocumentRagFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_fixture(FIXTURE_PATH)

    def test_a_fixture_count_and_family_counts(self) -> None:
        fixture = self.fixture
        self.assertEqual(fixture.fixture_id, "document_rag_v1")
        self.assertEqual(len(fixture.cases), 40)
        counts = {}
        for case in fixture.cases:
            counts[case.scenario_family] = counts.get(case.scenario_family, 0) + 1
        self.assertEqual(counts, EXPECTED_FAMILY_COUNTS)
        validate_fixture(fixture)

    def test_b_counterfactual_triplets(self) -> None:
        docs = self.fixture.document_by_alias()
        cases = {case.case_id: case for case in self.fixture.cases}
        for index in range(1, 9):
            suffix = f"{index:02d}"
            full = cases[f"FULL_{suffix}"]
            metadata = cases[f"METADATA_{suffix}"]
            deny = cases[f"DENY_{suffix}"]
            invariant = self._triplet_invariant(full, docs)
            self.assertEqual(self._triplet_invariant(metadata, docs), invariant)
            self.assertEqual(self._triplet_invariant(deny, docs), invariant)
            self.assertEqual([full.expected_policy_decision, metadata.expected_policy_decision, deny.expected_policy_decision], ["full", "metadata", "deny"])

    def test_c_marker_isolation(self) -> None:
        docs = self.fixture.document_by_alias()
        for case in self.fixture.cases:
            scoped = set(case.scope)
            scoped_text = "\n".join(docs[alias].content for alias in scoped)
            unrelated_text = "\n".join(doc.content for alias, doc in docs.items() if alias not in scoped)
            metadata_surface = " ".join([case.question] + [docs[alias].file_name for alias in scoped])
            for marker in case.protected:
                self.assertIn(marker, scoped_text)
                self.assertNotIn(marker, unrelated_text)
                self.assertNotIn(marker, metadata_surface)

    def test_d_case_scoped_retrieval_filter(self) -> None:
        collection = FakeCollection()
        result = run_shared_retrieval(
            question="question",
            top_k=4,
            collection=collection,
            embedding_client=FakeEmbeddingClient(),
            embedding_model="text-embedding-3-small",
            query_profile={"purpose": "grounded_question_answering"},
            document_ids=["doc-a"],
        )
        self.assertEqual(result.retrieved_chunk_ids, ["chunk-doc-a"])
        self.assertEqual(collection.query_calls[0]["where"], {"document_id": "doc-a"})
        self.assertNotIn("Forbidden variant text", [candidate.raw_text for candidate in result.retrieved_candidates])

    def test_e_aggregate_pairing(self) -> None:
        aggregate_cases = [case for case in self.fixture.cases if case.scenario_family == "aggregate_only"]
        pairs: dict[str, list[str]] = {}
        for case in aggregate_cases:
            pairs.setdefault(case.aggregate_pair_id or "", []).append(case.case_subtype or "")
        self.assertEqual(len(pairs), 4)
        for subtypes in pairs.values():
            self.assertEqual(sorted(subtypes), ["aggregate_safe", "individual_disclosure"])

    def test_f_contextual_only_validation(self) -> None:
        context_cases = [case for case in self.fixture.cases if case.case_subtype == "contextual_only"]
        self.assertEqual(len(context_cases), 4)
        for case in context_cases:
            self.assertEqual(case.expected_role_aware_source_roles, ["contextual"])
            self.assertEqual(case.expected_supporting_document_aliases, [])
            self.assertFalse(case.answerable_with_primary_evidence)

    def test_g_deterministic_ids(self) -> None:
        self.assertEqual(build_id_mappings(self.fixture), build_id_mappings(load_fixture(FIXTURE_PATH)))

    def test_h_deterministic_document_generation(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            left_manifest = generate_documents(self.fixture, left)
            right_manifest = generate_documents(self.fixture, right)
        left_hashes = [(doc["document_alias"], doc["sha256"], doc["source_text_sha256"]) for doc in left_manifest["documents"]]
        right_hashes = [(doc["document_alias"], doc["sha256"], doc["source_text_sha256"]) for doc in right_manifest["documents"]]
        self.assertEqual(left_hashes, right_hashes)

    def test_i_fixture_schema_serialization(self) -> None:
        parsed = EvaluationFixture.parse_obj(self.fixture.dict())
        self.assertEqual(parsed.fixture_id, self.fixture.fixture_id)
        self.assertEqual(len(parsed.cases), len(self.fixture.cases))
        self.assertEqual(parsed.dict(), self.fixture.dict())

    def test_j_clean_state_refusal(self) -> None:
        with self.assertRaises(CleanStateError):
            load_fixture_data(
                fixture=self.fixture,
                db=SimpleNamespace(),
                collection=FakeCollection(),
                embedding_provider=MockEmbeddingProvider(),
                clean_checker=lambda: (_ for _ in ()).throw(CleanStateError("contaminated")),
                case_ids=["FULL_01"],
            )

    def test_k_mocked_loader(self) -> None:
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        from evaluation.backend import ensure_backend_path

        ensure_backend_path()
        import models

        engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        collection = FakeCollection()
        manifest = load_fixture_data(
            fixture=self.fixture,
            db=db,
            collection=collection,
            embedding_provider=MockEmbeddingProvider(),
            clean_checker=lambda: None,
            case_ids=["FULL_01"],
        )
        try:
            self.assertEqual(manifest.document_count, 1)
            self.assertEqual(db.query(models.Document).count(), 1)
            self.assertEqual(db.query(models.DocumentChunk).count(), 1)
            self.assertEqual(len(collection.added), 1)
        finally:
            db.close()

    def test_l_harness_compatibility(self) -> None:
        representatives = ["FULL_01", "METADATA_01", "DENY_01", "AGG_SAFE_01", "CONTEXT_ONLY_01"]
        config = GenerationConfig("gpt-4o-mini", "text-embedding-3-small", temperature=0.0)
        for case_id in representatives:
            retrieval, policy_context = case_to_harness_inputs(self.fixture, case_id)
            results = run_case(
                run_id="compat",
                case_id=case_id,
                user_id="eval_reader",
                retrieval=retrieval,
                generation_config=config,
                generator=RecordingGenerator(),
                modes="standard",
                policy_context=policy_context,
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].case_id, case_id)

    def _triplet_invariant(self, case: Any, docs: dict[str, Any]) -> tuple[Any, ...]:
        return (
            case.pair_id,
            tuple(case.scope),
            "\n".join(docs[alias].content for alias in case.scope),
            case.question,
            case.canonical_answer,
            tuple(case.acceptable_answer_markers),
            tuple(case.protected),
            tuple(case.forbidden_answer_markers),
        )


if __name__ == "__main__":
    unittest.main()
