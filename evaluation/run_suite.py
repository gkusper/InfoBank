from __future__ import annotations

import argparse
import re
import uuid
from pathlib import Path
from typing import Any

from .clean_state import CleanStateError, check_clean_state
from .fixture_schema import load_fixture
from .manifest import build_manifest, git_info, write_manifest
from .modes import BackendServices, OpenAIGenerator
from .run_case import normalize_modes, run_case
from .schemas import GenerationConfig, GenerationOutput, RetrievedCandidate, SharedRetrievalResult


class MockGenerator:
    def generate(self, system_prompt: str, user_prompt: str, config: GenerationConfig) -> GenerationOutput:
        return GenerationOutput(
            answer="MOCK_GENERATION: available passages were processed.",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="InfoBank document-RAG evaluation harness")
    parser.add_argument("--check-clean-only", action="store_true", help="Only verify isolated DB/Chroma state.")
    parser.add_argument("--fixture", help="Future YAML/JSON fixture path.")
    parser.add_argument("--results-dir", default="evaluation/results", help="Directory for local JSONL results and manifests.")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--modes", default="standard,governance,role-aware")
    parser.add_argument("--mock-generation", action="store_true", help="Use a mocked generator; no OpenAI generation call.")
    args = parser.parse_args(argv)

    generation_config = default_generation_config()
    run_id = f"run-{uuid.uuid4()}"
    clean_report = None
    if args.check_clean_only:
        try:
            clean_report = check_clean_state()
        except CleanStateError as exc:
            print(f"CLEAN CHECK: FAIL - {exc}")
            return 2
        print(
            "CLEAN CHECK: PASS "
            f"database={clean_report.database_name} "
            f"chroma={clean_report.chroma_persist_dir} "
            f"vectors={clean_report.vector_count}"
        )
        return 0

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    fixture = load_fixture(args.fixture) if args.fixture else None
    fixture_id = fixture.fixture_id if fixture else None
    generator = MockGenerator() if args.mock_generation else OpenAIGenerator()
    if fixture is None and args.mock_generation:
        results = run_mock_dry_run(
            run_id=run_id,
            results_dir=results_dir,
            generation_config=generation_config,
            top_k=args.top_k,
            repetitions=args.repetitions,
            modes=normalize_modes(args.modes),
            generator=generator,
        )
    elif fixture is None:
        raise SystemExit("A fixture is required unless --mock-generation is used for a no-fixture dry run.")
    else:
        raise SystemExit("Fixture parsing is implemented; fixture DB loading will be added with the benchmark dataset task.")

    manifest = build_manifest(
        run_id=run_id,
        retrieval_top_k=args.top_k,
        repetitions=args.repetitions,
        generation_config=generation_config,
        clean_state_report=clean_report,
        fixture_path=args.fixture,
        fixture_identifier=fixture_id,
    )
    write_manifest(results_dir / run_id / "run_manifest.json", manifest)
    print(f"RUN: PASS run_id={run_id} records={len(results)} results_dir={results_dir / run_id}")
    return 0


def default_generation_config() -> GenerationConfig:
    try:
        from .backend import BACKEND_DIR

        source = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        generator_model = re.search(r'MODEL_NAME\s*=\s*"([^"]+)"', source).group(1)
        embedding_model = re.search(r'EMBEDDING_MODEL\s*=\s*"([^"]+)"', source).group(1)
        return GenerationConfig(
            generator_model=generator_model,
            embedding_model=embedding_model,
            temperature=0.0,
        )
    except Exception:
        return GenerationConfig(
            generator_model="gpt-4o-mini",
            embedding_model="text-embedding-3-small",
            temperature=0.0,
        )


def run_mock_dry_run(
    *,
    run_id: str,
    results_dir: Path,
    generation_config: GenerationConfig,
    top_k: int,
    repetitions: int,
    modes: list[str],
    generator: Any,
) -> list[Any]:
    retrieval = SharedRetrievalResult(
        question="What does the retrieved document say?",
        query_profile={"purpose": "grounded_question_answering", "required_evidence_strength": "primary_or_aggregate_with_role_label"},
        query_embedding_identifier="mock:query",
        retrieval_top_k=top_k,
        embedding_model=generation_config.embedding_model,
        api_usage={"embedding_calls": 1, "keyword_routing_calls": 0},
        retrieved_candidates=[
            RetrievedCandidate(1, "chunk-1", "doc-1", "mock.pdf", "The mock document says the pilot approval count is 4.", {"document_id": "doc-1"}, 0.1, 0.9),
            RetrievedCandidate(2, "chunk-2", "doc-2", "denied.pdf", "Denied fixture text should not reach governed modes.", {"document_id": "doc-2"}, 0.2, 0.8),
        ],
    )
    policy_context = {
        "use_decisions": {"doc-1": "full", "doc-2": "deny"},
        "source_roles": {"doc-1": "primary", "doc-2": "governance-excluded"},
        "content_doc_ids": ["doc-1"],
        "metadata_only_doc_ids": [],
        "denied_doc_ids": ["doc-2"],
        "usable_doc_ids": ["doc-1"],
        "has_primary_evidence": True,
        "has_aggregate_evidence": False,
        "has_metadata_only": False,
    }
    services = mock_role_aware_services(policy_context)
    info = git_info()
    return run_case(
        run_id=run_id,
        case_id="mock_case",
        user_id="mock_user",
        retrieval=retrieval,
        generation_config=generation_config,
        generator=generator,
        repetitions=repetitions,
        modes=modes,
        git_commit=info.get("git_commit"),
        policy_context=policy_context,
        services=services,
        results_jsonl=results_dir / run_id / "results.jsonl",
    )


def mock_role_aware_services(policy_context: dict[str, Any]) -> BackendServices:
    def classify_chunk_profile(**kwargs: Any) -> dict[str, Any]:
        return {
            "role": policy_context["source_roles"].get(kwargs["file_name"], "primary"),
            "use_decision": kwargs["use_decision"],
            "levels": {"evidential": 1.0},
            "evidence_warnings": [],
        }

    return BackendServices(
        resolve_document_access_bulk=lambda **kwargs: policy_context,
        classify_chunk_profile=classify_chunk_profile,
        detect_prompt_injection=lambda text: {"detected": False},
        make_generator_safe_chunk=lambda role, text, profile: text,
        make_context_block=lambda profile, file_name, text: f"[Source role: {profile.get('role')}]\n{text}",
        public_source_text=lambda role, text: text,
        summarize_source_roles=lambda sources: {"primary": len([s for s in sources if s.get("role") == "primary"])},
        summarize_relevance_levels=lambda sources: {"evidential": 1.0 if sources else 0.0},
        check_rag_evidence=lambda sources, query_profile, governance: {"decision": "answer_allowed", "warnings": []},
        select_pre_generation_output_mode=lambda question, query_profile: {"decision": "answer_allowed", "output_mode": "full_answer", "trace": {}},
        select_rag_output_mode=lambda **kwargs: {"decision": "answer_allowed", "output_mode": "full_answer", "trace": {}},
        is_aggregate_statistics_question=lambda question: False,
        is_browser_history_action_rule_question=lambda question: False,
        make_controlled_failure=lambda *args, **kwargs: {"status": args[0] if args else "restricted_answer", "reason": args[1] if len(args) > 1 else "evidential"},
        evidence_state=lambda *args, **kwargs: {},
        safe_policy_state=lambda governance: {},
        from_not_found_answer=lambda *args, **kwargs: {"status": "abstain", "reason": "epistemic"},
    )


if __name__ == "__main__":
    raise SystemExit(main())
