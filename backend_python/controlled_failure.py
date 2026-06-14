from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, List

import relevance


STATUS_FULL_ANSWER = "full_answer"
STATUS_ABSTAIN = "abstain"
STATUS_REFUSE = "refuse"
STATUS_RESTRICTED_ANSWER = "restricted_answer"
STATUS_AGGREGATE_ANSWER = "aggregate_answer"
STATUS_METADATA_ONLY_ANSWER = "metadata_only_answer"
STATUS_ASK_CLARIFICATION = "ask_clarification"
STATUS_ESCALATE = "escalate_to_human"

REASON_EPISTEMIC = "epistemic"
REASON_EVIDENTIAL = "evidential"
REASON_GOVERNANCE = "governance"
REASON_SAFETY = "safety"
REASON_CONFLICT_DEFEAT = "conflict_defeat"
REASON_TEMPORAL_STATUS = "temporal_status"
REASON_OPERATIONAL_SECURITY = "operational_security"

CONTROLLED_FAILURE_VERSION = "controlled-failure-v1"


def _now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _source_ids(governance: Dict[str, Any], key: str) -> List[str]:
    value = governance.get(key) or []
    return list(value) if isinstance(value, list) else []


def safe_policy_state(governance: Dict[str, Any]) -> Dict[str, Any]:
    content_ids = _source_ids(governance, "content_doc_ids")
    metadata_ids = _source_ids(governance, "metadata_only_doc_ids")
    denied_ids = _source_ids(governance, "denied_doc_ids")
    usable_ids = _source_ids(governance, "usable_doc_ids")
    return {
        "content_source_count": len(content_ids),
        "metadata_only_source_count": len(metadata_ids),
        "denied_source_count": len(denied_ids),
        "usable_source_count": len(usable_ids),
        "has_primary_evidence": bool(governance.get("has_primary_evidence")),
        "has_aggregate_evidence": bool(governance.get("has_aggregate_evidence")),
        "has_metadata_only": bool(governance.get("has_metadata_only") or metadata_ids),
        "fallback_used": bool(governance.get("fallback_used")),
    }


def evidence_state(sources: Iterable[Dict[str, Any]], query_profile: Dict[str, Any], context_blocks_available: bool) -> Dict[str, Any]:
    sources = list(sources or [])
    role_summary = relevance.summarize_source_roles(sources)
    level_summary = relevance.summarize_relevance_levels(sources)
    warnings: List[str] = []
    for source in sources:
        profile = source.get("usable_relevance") or {}
        for warning in profile.get("evidence_warnings") or []:
            if warning not in warnings:
                warnings.append(warning)
    return {
        "source_count": len(sources),
        "context_blocks_available": context_blocks_available,
        "required_evidence_strength": query_profile.get("required_evidence_strength"),
        "task_intent": query_profile.get("task_intent"),
        "role_summary": role_summary,
        "relevance_level_summary": level_summary,
        "has_primary": role_summary.get(relevance.SOURCE_ROLE_PRIMARY, 0) > 0,
        "has_aggregate": role_summary.get(relevance.SOURCE_ROLE_AGGREGATE_ONLY, 0) > 0,
        "has_contrastive": role_summary.get(relevance.SOURCE_ROLE_CONTRASTIVE, 0) > 0,
        "has_contextual": role_summary.get(relevance.SOURCE_ROLE_CONTEXTUAL, 0) > 0,
        "warnings": warnings,
    }


def make_controlled_failure(
    status: str,
    reason: str,
    evidence_state_value: Dict[str, Any],
    policy_state_value: Dict[str, Any],
    safe_output: str,
    next_steps: Iterable[str] | None = None,
    trace: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "version": CONTROLLED_FAILURE_VERSION,
        "status": status,
        "reason": reason,
        "evidenceState": evidence_state_value,
        "policyState": policy_state_value,
        "safeOutput": safe_output,
        "nextSteps": list(next_steps or []),
        "trace": {
            "created_at": _now_iso(),
            **(trace or {}),
        },
    }


def allowed_output(mode: str = STATUS_FULL_ANSWER, trace: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "decision": "answer_allowed",
        "output_mode": mode,
        "controlled_failure": None,
        "trace": trace or {},
    }


def blocked_output(cf: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "decision": "controlled_failure",
        "output_mode": cf["status"],
        "controlled_failure": cf,
        "trace": cf.get("trace", {}),
    }


def select_rag_output_mode(
    question: str,
    sources: Iterable[Dict[str, Any]],
    query_profile: Dict[str, Any],
    governance: Dict[str, Any],
    context_blocks_available: bool,
    aggregate_request: bool = False,
) -> Dict[str, Any]:
    state = evidence_state(sources, query_profile, context_blocks_available)
    policy = safe_policy_state(governance)
    required = query_profile.get("required_evidence_strength")
    has_primary = state["has_primary"]
    has_aggregate = state["has_aggregate"]
    has_contrastive = state["has_contrastive"]
    has_contextual = state["has_contextual"]

    trace = {
        "question_fingerprint": len(question or ""),
        "task_intent": query_profile.get("task_intent"),
        "retrieval_strategy": query_profile.get("retrieval_strategy"),
    }

    if policy["metadata_only_source_count"] and not policy["content_source_count"]:
        cf = make_controlled_failure(
            STATUS_METADATA_ONLY_ANSWER,
            REASON_GOVERNANCE,
            state,
            policy,
            "Only metadata-level sources are available for this question; document content is withheld by policy, so the answer cannot be found in the document content.",
            ["Request full access to the source or connect a permitted primary source."],
            {**trace, "gate": "policy_and_safety_filtering"},
        )
        return blocked_output(cf)

    if not policy["content_source_count"]:
        reason = REASON_GOVERNANCE if policy["denied_source_count"] else REASON_EPISTEMIC
        cf = make_controlled_failure(
            STATUS_REFUSE if reason == REASON_GOVERNANCE else STATUS_ABSTAIN,
            reason,
            state,
            policy,
            "There is no permitted source that can be used for this question in the InfoBank.",
            ["Upload, connect, or grant a permitted source for this purpose."],
            {**trace, "gate": "policy_and_safety_filtering"},
        )
        return blocked_output(cf)

    if not context_blocks_available:
        cf = make_controlled_failure(
            STATUS_ABSTAIN,
            REASON_EVIDENTIAL,
            state,
            policy,
            "The answer cannot be found in the document.",
            ["Add a more directly relevant document or choose a narrower question."],
            {**trace, "gate": "evidence_sufficiency_checking"},
        )
        return blocked_output(cf)

    if has_aggregate and not has_primary and not aggregate_request:
        cf = make_controlled_failure(
            STATUS_RESTRICTED_ANSWER,
            REASON_GOVERNANCE,
            state,
            policy,
            "The answer cannot be found in the document.",
            ["Ask for aggregate/statistical information, or grant access to a primary source for the specific content claim."],
            {**trace, "gate": "source_role_labelling"},
        )
        return blocked_output(cf)

    if required == "primary_required_for_direct_claim" and not has_primary:
        reason = REASON_CONFLICT_DEFEAT if has_contrastive else REASON_EVIDENTIAL
        cf = make_controlled_failure(
            STATUS_ABSTAIN,
            reason,
            state,
            policy,
            "The answer cannot be found in the document.",
            ["Connect or grant primary evidence, such as an official request, assignment, calendar obligation, or user commitment."],
            {**trace, "gate": "evidence_sufficiency_checking"},
        )
        return blocked_output(cf)

    if has_contextual and not has_primary and not has_aggregate:
        cf = make_controlled_failure(
            STATUS_RESTRICTED_ANSWER,
            REASON_EVIDENTIAL,
            state,
            policy,
            "The answer cannot be found in the document.",
            ["Use the contextual evidence only as background, or add a primary source before making a direct claim."],
            {**trace, "gate": "source_role_labelling"},
        )
        return blocked_output(cf)

    mode = STATUS_AGGREGATE_ANSWER if has_aggregate and aggregate_request and not has_primary else STATUS_FULL_ANSWER
    return allowed_output(mode, {**trace, "gate": "output_mode_selection"})


def from_not_found_answer(question: str, sources: Iterable[Dict[str, Any]], query_profile: Dict[str, Any], governance: Dict[str, Any]) -> Dict[str, Any]:
    state = evidence_state(sources, query_profile, True)
    policy = safe_policy_state(governance)
    return make_controlled_failure(
        STATUS_ABSTAIN,
        REASON_EPISTEMIC,
        state,
        policy,
        "The answer cannot be found in the document.",
        ["Provide a source that explicitly supports the requested claim or ask a narrower question."],
        {
            "question_fingerprint": len(question or ""),
            "gate": "generation_result_validation",
            "task_intent": query_profile.get("task_intent"),
        },
    )
