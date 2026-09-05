from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from typing import Any

from evaluation.clean_state import CleanStateError, assert_clean_counts
from evaluation.modes import BackendServices, run_governance_only_rag, run_role_aware_rag, run_standard_rag
from evaluation.run_case import run_case
from evaluation.schemas import (
    GenerationConfig,
    GenerationOutput,
    MODE_GOVERNANCE,
    MODE_ROLE_AWARE,
    MODE_STANDARD,
    RetrievedCandidate,
    SharedRetrievalResult,
    read_jsonl_records,
    write_jsonl_record,
)


class RecordingGenerator:
    def __init__(self, answer: str = "mock answer"):
        self.answer = answer
        self.calls: list[tuple[str, str, GenerationConfig]] = []

    def generate(self, system_prompt: str, user_prompt: str, config: GenerationConfig) -> GenerationOutput:
        self.calls.append((system_prompt, user_prompt, config))
        return GenerationOutput(
            answer=self.answer,
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


class Counter:
    def __init__(self):
        self.calls: dict[str, int] = {}

    def inc(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1


def generation_config() -> GenerationConfig:
    return GenerationConfig(
        generator_model="gpt-4o-mini",
        embedding_model="text-embedding-3-small",
        temperature=0.0,
    )


def retrieval() -> SharedRetrievalResult:
    return SharedRetrievalResult(
        question="What is the project codename?",
        query_profile={"purpose": "grounded_question_answering", "required_evidence_strength": "primary_or_aggregate_with_role_label"},
        query_embedding_identifier="mock:embedding",
        retrieval_top_k=4,
        embedding_model="text-embedding-3-small",
        api_usage={"embedding_calls": 1, "keyword_routing_calls": 0},
        retrieved_candidates=[
            RetrievedCandidate(
                rank=1,
                chunk_id="chunk-a",
                document_id="doc-a",
                file_name="allowed.pdf",
                raw_text="The project codename is ALPHA.",
                metadata={"document_id": "doc-a"},
                distance=0.1,
                score=0.9,
            ),
            RetrievedCandidate(
                rank=2,
                chunk_id="chunk-b",
                document_id="doc-b",
                file_name="denied.pdf",
                raw_text="DENIED SECRET: the protected codename is OMEGA.",
                metadata={"document_id": "doc-b"},
                distance=0.2,
                score=0.8,
            ),
        ],
    )


def policy_context() -> dict[str, Any]:
    return {
        "use_decisions": {"doc-a": "full", "doc-b": "deny"},
        "source_roles": {"doc-a": "primary", "doc-b": "governance-excluded"},
        "content_doc_ids": ["doc-a"],
        "metadata_only_doc_ids": [],
        "denied_doc_ids": ["doc-b"],
        "usable_doc_ids": ["doc-a"],
        "has_primary_evidence": True,
        "has_aggregate_evidence": False,
        "has_metadata_only": False,
    }


def fake_services(counter: Counter | None = None) -> BackendServices:
    counter = counter or Counter()

    def classify_chunk_profile(**kwargs: Any) -> dict[str, Any]:
        counter.inc("classify_chunk_profile")
        return {
            "role": "primary",
            "use_decision": kwargs["use_decision"],
            "levels": {"evidential": 1.0},
            "evidence_warnings": [],
        }

    def check_rag_evidence(sources: list[dict[str, Any]], query_profile: dict[str, Any], governance: dict[str, Any]) -> dict[str, Any]:
        counter.inc("check_rag_evidence")
        return {"decision": "answer_allowed", "warnings": []}

    def select_rag_output_mode(**kwargs: Any) -> dict[str, Any]:
        counter.inc("select_rag_output_mode")
        return {"decision": "answer_allowed", "output_mode": "full_answer", "trace": {}}

    return BackendServices(
        resolve_document_access_bulk=lambda **kwargs: policy_context(),
        classify_chunk_profile=classify_chunk_profile,
        detect_prompt_injection=lambda text: {"detected": False},
        make_generator_safe_chunk=lambda role, text, profile: text,
        make_context_block=lambda profile, file_name, text: f"[Source role: {profile['role']}]\n{text}",
        public_source_text=lambda role, text: text,
        summarize_source_roles=lambda sources: {"primary": len([s for s in sources if s.get("role") == "primary"])},
        summarize_relevance_levels=lambda sources: {"evidential": 1.0 if sources else 0.0},
        check_rag_evidence=check_rag_evidence,
        select_pre_generation_output_mode=lambda question, query_profile: {"decision": "answer_allowed", "output_mode": "full_answer", "trace": {}},
        select_rag_output_mode=select_rag_output_mode,
        is_aggregate_statistics_question=lambda question: False,
        is_browser_history_action_rule_question=lambda question: False,
        make_controlled_failure=lambda *args, **kwargs: {"status": args[0], "reason": args[1], "safeOutput": args[4] if len(args) > 4 else ""},
        evidence_state=lambda *args, **kwargs: {},
        safe_policy_state=lambda governance: {},
        from_not_found_answer=lambda *args, **kwargs: {"status": "abstain", "reason": "epistemic"},
    )


class HarnessTests(unittest.TestCase):
    def test_shared_retrieval_identity_across_modes(self) -> None:
        results = run_case(
            run_id="run",
            case_id="case",
            user_id="user",
            retrieval=retrieval(),
            generation_config=generation_config(),
            generator=RecordingGenerator(),
            modes=[MODE_STANDARD, MODE_GOVERNANCE, MODE_ROLE_AWARE],
            policy_context=policy_context(),
            services=fake_services(),
        )
        ids = [result.retrieved_chunk_ids for result in results]
        texts = [[chunk["raw_text"] for chunk in result.raw_retrieved_chunks] for result in results]
        distances = [result.retrieval_distances for result in results]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[1], ids[2])
        self.assertEqual(texts[0], texts[1])
        self.assertEqual(texts[1], texts[2])
        self.assertEqual(distances[0], distances[1])
        self.assertEqual(distances[1], distances[2])

    def test_standard_rag_bypasses_governance(self) -> None:
        generator = RecordingGenerator()
        result = run_standard_rag(
            run_id="run",
            case_id="case",
            repetition=1,
            git_commit="commit",
            retrieval=retrieval(),
            generation_config=generation_config(),
            generator=generator,
        )
        self.assertIn("DENIED SECRET", result.user_prompt or "")
        self.assertIsNone(result.use_decisions)
        self.assertIsNone(result.source_roles)

    def test_governance_only_removes_denied_content(self) -> None:
        generator = RecordingGenerator()
        result = run_governance_only_rag(
            run_id="run",
            case_id="case",
            repetition=1,
            git_commit="commit",
            retrieval=retrieval(),
            generation_config=generation_config(),
            generator=generator,
            user_id="user",
            policy_context=policy_context(),
        )
        self.assertNotIn("DENIED SECRET", result.user_prompt or "")
        self.assertIn("doc-b", result.withheld_document_ids)
        self.assertIn("chunk-b", result.redacted_chunk_ids)

    def test_governance_only_does_not_use_role_evidence_reasoning(self) -> None:
        counter = Counter()
        result = run_governance_only_rag(
            run_id="run",
            case_id="case",
            repetition=1,
            git_commit="commit",
            retrieval=retrieval(),
            generation_config=generation_config(),
            generator=RecordingGenerator(),
            user_id="user",
            policy_context=policy_context(),
            services=fake_services(counter),
        )
        self.assertEqual(counter.calls, {})
        self.assertIsNone(result.evidence_check)
        self.assertIsNone(result.source_roles)

    def test_role_aware_uses_role_and_evidence_logic(self) -> None:
        counter = Counter()
        result = run_role_aware_rag(
            run_id="run",
            case_id="case",
            repetition=1,
            git_commit="commit",
            retrieval=retrieval(),
            generation_config=generation_config(),
            generator=RecordingGenerator(),
            user_id="user",
            policy_context=policy_context(),
            services=fake_services(counter),
        )
        self.assertGreater(counter.calls.get("classify_chunk_profile", 0), 0)
        self.assertEqual(counter.calls.get("check_rag_evidence"), 1)
        self.assertEqual(counter.calls.get("select_rag_output_mode"), 1)
        self.assertIsNotNone(result.evidence_check)
        self.assertIsNotNone(result.source_roles)

    def test_standard_prompt_contains_no_role_labels(self) -> None:
        result = run_standard_rag(
            run_id="run",
            case_id="case",
            repetition=1,
            git_commit="commit",
            retrieval=retrieval(),
            generation_config=generation_config(),
            generator=RecordingGenerator(),
        )
        prompt_text = f"{result.system_prompt}\n{result.user_prompt}".lower()
        self.assertNotIn("primary", prompt_text)
        self.assertNotIn("contextual", prompt_text)
        self.assertNotIn("contrastive", prompt_text)
        self.assertNotIn("aggregate", prompt_text)
        self.assertNotIn("governance score", prompt_text)

    def test_result_schema_serializes_jsonl(self) -> None:
        result = run_standard_rag(
            run_id="run",
            case_id="case",
            repetition=1,
            git_commit="commit",
            retrieval=retrieval(),
            generation_config=generation_config(),
            generator=RecordingGenerator(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            write_jsonl_record(path, result)
            records = read_jsonl_records(path)
        self.assertEqual(records[0]["case_id"], "case")
        self.assertEqual(records[0]["mode"], MODE_STANDARD)

    def test_clean_state_guard_refuses_contamination(self) -> None:
        with self.assertRaises(CleanStateError):
            assert_clean_counts({"documents": 1, "document_chunks": 0}, 0)
        with self.assertRaises(CleanStateError):
            assert_clean_counts({"documents": 0}, 1)

    def test_production_ask_route_has_no_mode_parameter(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        chat_path = repo_root / "backend_python" / "routers" / "chat.py"
        tree = ast.parse(chat_path.read_text(encoding="utf-8"))
        ask_fn = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "ask_infobank")
        arg_names = [arg.arg for arg in ask_fn.args.args]
        self.assertNotIn("mode", arg_names)


if __name__ == "__main__":
    unittest.main()
