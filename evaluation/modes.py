from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .backend import ensure_backend_path
from .prompts import (
    build_governance_prompt,
    build_role_aware_prompt,
    build_standard_prompt,
    format_raw_candidate_blocks,
)
from .schemas import (
    EvaluationResult,
    GenerationConfig,
    GenerationOutput,
    MODE_GOVERNANCE,
    MODE_ROLE_AWARE,
    MODE_STANDARD,
    RetrievedCandidate,
    SharedRetrievalResult,
    base_result_fields,
)
from .usage_logging import empty_usage, usage_from_openai_response


USE_FULL = "full"
USE_AGGREGATE = "aggregate"
USE_METADATA = "metadata"
USE_DENY = "deny"

ROLE_PRIMARY = "primary"
ROLE_CONTEXTUAL = "contextual"
ROLE_AGGREGATE_ONLY = "aggregate-only"
ROLE_GOVERNANCE_EXCLUDED = "governance-excluded"


class Generator(Protocol):
    def generate(self, system_prompt: str, user_prompt: str, config: GenerationConfig) -> GenerationOutput:
        ...


class OpenAIGenerator:
    def generate(self, system_prompt: str, user_prompt: str, config: GenerationConfig) -> GenerationOutput:
        ensure_backend_path()
        import ai_service

        params: dict[str, Any] = {
            "model": config.generator_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": config.temperature,
        }
        if config.top_p is not None:
            params["top_p"] = config.top_p
        if config.seed is not None:
            params["seed"] = config.seed
        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens
        response = ai_service.openai_client.chat.completions.create(**params)
        return GenerationOutput(
            answer=response.choices[0].message.content or "",
            api_usage=usage_from_openai_response(response, generation_calls=1),
        )


@dataclass
class BackendServices:
    resolve_document_access_bulk: Callable[..., dict[str, Any]]
    classify_chunk_profile: Callable[..., dict[str, Any]]
    detect_prompt_injection: Callable[[str], dict[str, Any]]
    make_generator_safe_chunk: Callable[[str, str, dict[str, Any]], str]
    make_context_block: Callable[[dict[str, Any], str, str], str]
    public_source_text: Callable[[str, str], str]
    summarize_source_roles: Callable[[list[dict[str, Any]]], dict[str, Any]]
    summarize_relevance_levels: Callable[[list[dict[str, Any]]], dict[str, Any]]
    check_rag_evidence: Callable[[list[dict[str, Any]], dict[str, Any], dict[str, Any]], dict[str, Any]]
    select_pre_generation_output_mode: Callable[[str, dict[str, Any]], dict[str, Any]]
    select_rag_output_mode: Callable[..., dict[str, Any]]
    is_aggregate_statistics_question: Callable[[str], bool]
    is_browser_history_action_rule_question: Callable[[str], bool]
    make_controlled_failure: Callable[..., dict[str, Any]]
    evidence_state: Callable[..., dict[str, Any]]
    safe_policy_state: Callable[[dict[str, Any]], dict[str, Any]]
    from_not_found_answer: Callable[..., dict[str, Any]]


def load_backend_services() -> BackendServices:
    ensure_backend_path()
    import controlled_failure
    import evidence_service
    import policy_engine
    import relevance
    from routers import chat as chat_router

    return BackendServices(
        resolve_document_access_bulk=policy_engine.resolve_document_access_bulk,
        classify_chunk_profile=relevance.classify_chunk_profile,
        detect_prompt_injection=controlled_failure.detect_prompt_injection,
        make_generator_safe_chunk=chat_router.make_generator_safe_chunk,
        make_context_block=relevance.make_context_block,
        public_source_text=relevance.public_source_text,
        summarize_source_roles=relevance.summarize_source_roles,
        summarize_relevance_levels=relevance.summarize_relevance_levels,
        check_rag_evidence=evidence_service.check_rag_evidence,
        select_pre_generation_output_mode=controlled_failure.select_pre_generation_output_mode,
        select_rag_output_mode=controlled_failure.select_rag_output_mode,
        is_aggregate_statistics_question=chat_router.is_aggregate_statistics_question,
        is_browser_history_action_rule_question=chat_router.is_browser_history_action_rule_question,
        make_controlled_failure=controlled_failure.make_controlled_failure,
        evidence_state=controlled_failure.evidence_state,
        safe_policy_state=controlled_failure.safe_policy_state,
        from_not_found_answer=controlled_failure.from_not_found_answer,
    )


def run_standard_rag(
    *,
    run_id: str,
    case_id: str,
    repetition: int,
    git_commit: str | None,
    retrieval: SharedRetrievalResult,
    generation_config: GenerationConfig,
    generator: Generator,
) -> EvaluationResult:
    context_blocks = format_raw_candidate_blocks(retrieval.retrieved_candidates)
    system_prompt, user_prompt = build_standard_prompt(retrieval.question, context_blocks)
    generation, error = _safe_generate(generator, system_prompt, user_prompt, generation_config)
    fields = base_result_fields(
        run_id=run_id,
        case_id=case_id,
        mode=MODE_STANDARD,
        repetition=repetition,
        git_commit=git_commit,
        retrieval=retrieval,
        generation_config=generation_config,
    )
    return EvaluationResult(
        **fields,
        generator_context_blocks=context_blocks,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        answer=generation.answer if generation else None,
        output_mode="full_answer" if generation and not error else None,
        use_decisions=None,
        source_roles=None,
        source_role_summary=None,
        relevance_level_summary=None,
        evidence_decision=None,
        evidence_check=None,
        controlled_failure_status=None,
        controlled_failure_reason=None,
        controlled_failure=None,
        withheld_document_ids=[],
        redacted_chunk_ids=[],
        protected_content_disclosed=None,
        api_usage=generation.api_usage if generation else _error_usage(error),
        error=error,
    )


def run_governance_only_rag(
    *,
    run_id: str,
    case_id: str,
    repetition: int,
    git_commit: str | None,
    retrieval: SharedRetrievalResult,
    generation_config: GenerationConfig,
    generator: Generator,
    user_id: str,
    db: Any | None = None,
    policy_context: dict[str, Any] | None = None,
    services: BackendServices | None = None,
) -> EvaluationResult:
    governance_context = _resolve_governance_context(
        db=db,
        user_id=user_id,
        retrieval=retrieval,
        policy_context=policy_context,
        services=services,
    )
    context_blocks, withheld_doc_ids, redacted_chunk_ids = _build_governance_context_blocks(
        retrieval.retrieved_candidates,
        governance_context,
    )
    system_prompt = user_prompt = None
    generation: GenerationOutput | None = None
    error: dict[str, Any] | None = None
    output_mode = "full_answer"
    if context_blocks:
        system_prompt, user_prompt = build_governance_prompt(retrieval.question, context_blocks, governance_context)
        generation, error = _safe_generate(generator, system_prompt, user_prompt, generation_config)
        if error:
            output_mode = None
    else:
        output_mode = "governance_no_content"
        generation = GenerationOutput(
            answer="No generator-visible document content remains after governance filtering.",
            api_usage=empty_usage(),
        )

    fields = base_result_fields(
        run_id=run_id,
        case_id=case_id,
        mode=MODE_GOVERNANCE,
        repetition=repetition,
        git_commit=git_commit,
        retrieval=retrieval,
        generation_config=generation_config,
    )
    return EvaluationResult(
        **fields,
        generator_context_blocks=context_blocks,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        answer=generation.answer if generation else None,
        output_mode=output_mode,
        use_decisions=governance_context.get("use_decisions"),
        source_roles=None,
        source_role_summary=None,
        relevance_level_summary=None,
        evidence_decision=None,
        evidence_check=None,
        controlled_failure_status=None,
        controlled_failure_reason=None,
        controlled_failure=None,
        withheld_document_ids=withheld_doc_ids,
        redacted_chunk_ids=redacted_chunk_ids,
        protected_content_disclosed=None,
        api_usage=generation.api_usage if generation else _error_usage(error),
        error=error,
    )


def run_role_aware_rag(
    *,
    run_id: str,
    case_id: str,
    repetition: int,
    git_commit: str | None,
    retrieval: SharedRetrievalResult,
    generation_config: GenerationConfig,
    generator: Generator,
    user_id: str,
    db: Any | None = None,
    policy_context: dict[str, Any] | None = None,
    services: BackendServices | None = None,
) -> EvaluationResult:
    services = services or load_backend_services()
    pre_gate = services.select_pre_generation_output_mode(retrieval.question, retrieval.query_profile)
    governance_context = _resolve_governance_context(
        db=db,
        user_id=user_id,
        retrieval=retrieval,
        policy_context=policy_context,
        services=services,
    )
    fields = base_result_fields(
        run_id=run_id,
        case_id=case_id,
        mode=MODE_ROLE_AWARE,
        repetition=repetition,
        git_commit=git_commit,
        retrieval=retrieval,
        generation_config=generation_config,
    )
    if pre_gate.get("decision") == "controlled_failure":
        cf = pre_gate["controlled_failure"]
        return _role_aware_result(
            fields=fields,
            retrieval=retrieval,
            generation_config=generation_config,
            context_blocks=[],
            governance_context=governance_context,
            sources=[],
            role_summary={},
            relevance_level_summary={},
            evidence_check={"decision": "controlled_failure", "controlled_failure": cf},
            output_gate=pre_gate,
            answer=cf.get("safeOutput"),
            system_prompt=None,
            user_prompt=None,
            api_usage=empty_usage(),
            error=None,
        )

    sources, context_blocks, redacted_chunk_ids = _build_role_aware_sources(
        retrieval=retrieval,
        governance_context=governance_context,
        services=services,
    )
    role_summary = services.summarize_source_roles(sources)
    relevance_level_summary = services.summarize_relevance_levels(sources)
    evidence_check = services.check_rag_evidence(sources, retrieval.query_profile, governance_context)
    output_gate = services.select_rag_output_mode(
        question=retrieval.question,
        sources=sources,
        query_profile=retrieval.query_profile,
        governance=governance_context,
        context_blocks_available=bool(context_blocks),
        aggregate_request=services.is_aggregate_statistics_question(retrieval.question),
    )
    evidence_check["output_mode"] = output_gate.get("output_mode")
    evidence_check["output_gate"] = output_gate.get("trace", {})
    if output_gate.get("controlled_failure"):
        evidence_check["controlled_failure"] = output_gate["controlled_failure"]
        evidence_check["decision"] = output_gate.get("decision")

    if output_gate.get("decision") == "controlled_failure":
        cf = output_gate["controlled_failure"]
        return _role_aware_result(
            fields=fields,
            retrieval=retrieval,
            generation_config=generation_config,
            context_blocks=context_blocks,
            governance_context=governance_context,
            sources=sources,
            role_summary=role_summary,
            relevance_level_summary=relevance_level_summary,
            evidence_check=evidence_check,
            output_gate=output_gate,
            answer=cf.get("safeOutput") or "The answer cannot be found in the document.",
            system_prompt=None,
            user_prompt=None,
            api_usage=empty_usage(),
            error=None,
            redacted_chunk_ids=redacted_chunk_ids,
        )

    system_prompt, user_prompt = build_role_aware_prompt(
        question=retrieval.question,
        query_profile=retrieval.query_profile,
        governance_context=governance_context,
        role_summary=role_summary,
        relevance_level_summary=relevance_level_summary,
        evidence_check=evidence_check,
        output_gate=output_gate,
        context_blocks=context_blocks,
    )
    generation, error = _safe_generate(generator, system_prompt, user_prompt, generation_config)
    answer = generation.answer if generation else None
    controlled_failure_obj = output_gate.get("controlled_failure")
    output_mode = output_gate.get("output_mode", "full_answer")
    if answer and services.is_browser_history_action_rule_question(retrieval.question):
        answer = (
            "No. Browser history or activity traces can provide contextual support, refine details, or help prioritize an existing task, "
            "but they cannot create an action item by themselves without primary evidence such as an official request, assignment, calendar obligation, or user commitment."
        )
        controlled_failure_obj = services.make_controlled_failure(
            "restricted_answer",
            "evidential",
            services.evidence_state(sources, retrieval.query_profile, bool(context_blocks)),
            services.safe_policy_state(governance_context),
            answer,
            ["Use browser history only as contextual support and connect a primary source before creating an obligation."],
            {"gate": "output_mode_selection", "rule": "browser_history_contextual_only"},
        )
        output_mode = controlled_failure_obj["status"]
        evidence_check.setdefault("warnings", []).append("browser_history_contextual_only_rule_applied")
        evidence_check["decision"] = "restricted_answer"
        evidence_check["controlled_failure"] = controlled_failure_obj
        evidence_check["output_mode"] = output_mode
    if answer and "The answer cannot be found in the document." in answer:
        controlled_failure_obj = services.from_not_found_answer(
            retrieval.question,
            sources,
            retrieval.query_profile,
            governance_context,
        )
        output_mode = controlled_failure_obj["status"]
        evidence_check["decision"] = "controlled_failure"
        evidence_check["controlled_failure"] = controlled_failure_obj
        evidence_check["output_mode"] = output_mode

    return _role_aware_result(
        fields=fields,
        retrieval=retrieval,
        generation_config=generation_config,
        context_blocks=context_blocks,
        governance_context=governance_context,
        sources=sources,
        role_summary=role_summary,
        relevance_level_summary=relevance_level_summary,
        evidence_check=evidence_check,
        output_gate={**output_gate, "output_mode": output_mode, "controlled_failure": controlled_failure_obj},
        answer=answer,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_usage=generation.api_usage if generation else _error_usage(error),
        error=error,
        redacted_chunk_ids=redacted_chunk_ids,
    )


def _safe_generate(
    generator: Generator,
    system_prompt: str,
    user_prompt: str,
    generation_config: GenerationConfig,
) -> tuple[GenerationOutput | None, dict[str, Any] | None]:
    try:
        return generator.generate(system_prompt, user_prompt, generation_config), None
    except Exception as exc:
        return None, {"type": exc.__class__.__name__, "message": str(exc)}


def _error_usage(error: dict[str, Any] | None) -> dict[str, Any]:
    usage = empty_usage()
    if error:
        usage["errors"].append(error)
    return usage


def _resolve_governance_context(
    *,
    db: Any | None,
    user_id: str,
    retrieval: SharedRetrievalResult,
    policy_context: dict[str, Any] | None,
    services: BackendServices | None,
) -> dict[str, Any]:
    if policy_context is not None:
        return policy_context
    if db is None:
        raise ValueError("db or policy_context is required for governance-aware modes")
    services = services or load_backend_services()
    doc_ids = list(dict.fromkeys(candidate.document_id for candidate in retrieval.retrieved_candidates))
    return services.resolve_document_access_bulk(
        db=db,
        user_id=user_id,
        doc_ids=doc_ids,
        purpose=retrieval.query_profile.get("purpose", "grounded_question_answering"),
    )


def _build_governance_context_blocks(
    candidates: list[RetrievedCandidate],
    governance_context: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    decisions = governance_context.get("use_decisions", {})
    blocks: list[str] = []
    withheld_doc_ids: list[str] = []
    redacted_chunk_ids: list[str] = []
    for candidate in candidates:
        decision = decisions.get(candidate.document_id, USE_DENY)
        if decision == USE_FULL:
            blocks.append(_governance_block(candidate, candidate.raw_text, "full"))
        elif decision == USE_AGGREGATE:
            blocks.append(_governance_block(candidate, _aggregate_safe_text(candidate.raw_text), "aggregate-only"))
            redacted_chunk_ids.append(candidate.chunk_id)
        elif decision in {USE_METADATA, USE_DENY}:
            withheld_doc_ids.append(candidate.document_id)
            redacted_chunk_ids.append(candidate.chunk_id)
    return blocks, list(dict.fromkeys(withheld_doc_ids)), redacted_chunk_ids


def _governance_block(candidate: RetrievedCandidate, text: str, decision: str) -> str:
    return "\n".join(
        [
            f"[Permitted passage {candidate.rank}]",
            f"Document: {candidate.file_name}",
            f"Document ID: {candidate.document_id}",
            f"Chunk ID: {candidate.chunk_id}",
            f"Access decision: {decision}",
            text,
        ]
    )


def _aggregate_safe_text(text: str, max_facts: int = 3) -> str:
    aggregate_markers = [
        "average",
        "mean",
        "median",
        "count",
        "total",
        "statistics",
        "statistic",
        "aggregate",
        "approval time",
        "rate",
        "percentage",
        "percent",
    ]
    clean = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    facts: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(marker in lowered for marker in aggregate_markers) and re.search(r"\b\d+(?:\.\d+)?\b", sentence):
            safe = re.sub(r"[\w\.-]+@[\w\.-]+", "[redacted-email]", sentence)
            safe = re.sub(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", "[redacted-person]", safe)
            facts.append(safe[:220])
        if len(facts) >= max_facts:
            break
    fact_text = " | ".join(facts) if facts else "No aggregate-safe numeric/statistical fact extracted from this passage."
    return (
        "[Aggregate-only non-quotable passage. Individual source text is withheld. "
        f"Aggregate-safe facts: {fact_text}]"
    )


def _build_role_aware_sources(
    *,
    retrieval: SharedRetrievalResult,
    governance_context: dict[str, Any],
    services: BackendServices,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    decisions = governance_context.get("use_decisions", {})
    base_roles = governance_context.get("source_roles", {})
    sources: list[dict[str, Any]] = []
    context_blocks: list[str] = []
    redacted_chunk_ids: list[str] = []
    for candidate in retrieval.retrieved_candidates:
        decision = decisions.get(candidate.document_id, USE_DENY)
        base_role = base_roles.get(candidate.document_id, ROLE_CONTEXTUAL)
        if decision == USE_METADATA:
            redacted_chunk_ids.append(candidate.chunk_id)
            sources.append(_withheld_source(candidate, ROLE_CONTEXTUAL, USE_METADATA, "metadata_only_content_withheld"))
            continue
        if decision == USE_DENY:
            redacted_chunk_ids.append(candidate.chunk_id)
            sources.append(_withheld_source(candidate, ROLE_GOVERNANCE_EXCLUDED, USE_DENY, "governance_denied_do_not_use"))
            continue
        source_profile = services.classify_chunk_profile(
            question=retrieval.question,
            chunk_text=candidate.raw_text,
            file_name=candidate.file_name,
            query_profile=retrieval.query_profile,
            base_role=base_role,
            use_decision=decision,
        )
        if services.detect_prompt_injection(candidate.raw_text).get("detected"):
            source_profile.setdefault("evidence_warnings", []).append("source_prompt_injection_detected_do_not_send_to_generator")
            redacted_chunk_ids.append(candidate.chunk_id)
            sources.append(
                {
                    "document_id": candidate.document_id,
                    "file_name": candidate.file_name,
                    "role": ROLE_CONTEXTUAL,
                    "use_decision": decision,
                    "usable_relevance": source_profile,
                    "text": "[Source withheld: instruction-like content was detected and was not sent to the generator.]",
                    "security": {"prompt_injection_detected": True},
                }
            )
            continue
        role = source_profile["role"]
        safe_text = services.make_generator_safe_chunk(role, candidate.raw_text, source_profile)
        if safe_text != candidate.raw_text:
            redacted_chunk_ids.append(candidate.chunk_id)
        context_blocks.append(services.make_context_block(source_profile, candidate.file_name, safe_text))
        sources.append(
            {
                "document_id": candidate.document_id,
                "file_name": candidate.file_name,
                "role": role,
                "use_decision": decision,
                "usable_relevance": source_profile,
                "text": services.public_source_text(role, candidate.raw_text),
            }
        )
    return sources, context_blocks, redacted_chunk_ids


def _withheld_source(candidate: RetrievedCandidate, role: str, decision: str, warning: str) -> dict[str, Any]:
    return {
        "document_id": candidate.document_id,
        "file_name": candidate.file_name,
        "role": role,
        "use_decision": decision,
        "usable_relevance": {
            "levels": {},
            "role": role,
            "base_role": role,
            "use_decision": decision,
            "evidence_warnings": [warning],
        },
        "text": "[content withheld]",
    }


def _role_aware_result(
    *,
    fields: dict[str, Any],
    retrieval: SharedRetrievalResult,
    generation_config: GenerationConfig,
    context_blocks: list[str],
    governance_context: dict[str, Any],
    sources: list[dict[str, Any]],
    role_summary: dict[str, Any],
    relevance_level_summary: dict[str, Any],
    evidence_check: dict[str, Any],
    output_gate: dict[str, Any],
    answer: str | None,
    system_prompt: str | None,
    user_prompt: str | None,
    api_usage: dict[str, Any],
    error: dict[str, Any] | None,
    redacted_chunk_ids: list[str] | None = None,
) -> EvaluationResult:
    cf = output_gate.get("controlled_failure")
    source_roles = {
        "sources": [
            {"document_id": src.get("document_id"), "file_name": src.get("file_name"), "role": src.get("role")}
            for src in sources
        ]
    }
    withheld = [
        candidate.document_id
        for candidate in retrieval.retrieved_candidates
        if governance_context.get("use_decisions", {}).get(candidate.document_id) in {USE_METADATA, USE_DENY}
    ]
    return EvaluationResult(
        **fields,
        generator_context_blocks=context_blocks,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        answer=answer,
        output_mode=output_gate.get("output_mode"),
        use_decisions=governance_context.get("use_decisions"),
        source_roles=source_roles,
        source_role_summary=role_summary,
        relevance_level_summary=relevance_level_summary,
        evidence_decision=evidence_check.get("decision"),
        evidence_check=evidence_check,
        controlled_failure_status=cf.get("status") if cf else None,
        controlled_failure_reason=cf.get("reason") if cf else None,
        controlled_failure=cf,
        withheld_document_ids=list(dict.fromkeys(withheld)),
        redacted_chunk_ids=redacted_chunk_ids or [],
        protected_content_disclosed=None,
        api_usage=api_usage,
        error=error,
    )
