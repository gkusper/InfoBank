from __future__ import annotations

import datetime
import re
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

CONTROLLED_FAILURE_VERSION = "controlled-failure-v2"

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|system|developer)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above|system|developer)\s+instructions",
    r"reveal\s+(the\s+)?(system|developer|hidden)\s+(prompt|message|instructions)",
    r"print\s+(the\s+)?(system|developer|hidden)\s+(prompt|message|instructions)",
    r"you\s+are\s+now\s+(in\s+)?(developer|admin|root|sudo)\s+mode",
    r"jailbreak",
    r"do\s+not\s+follow\s+(the\s+)?(system|developer)\s+message",
    r"exfiltrat(e|ion)",
    r"tool\s+(token|secret|credential|key)",
]

SAFETY_PATTERNS = [
    r"\b(make|build|assemble|construct)\b.{0,80}\b(bomb|explosive|grenade|molotov)\b",
    r"\b(write|create|generate|give)\b.{0,80}\b(malware|ransomware|keylogger|stealer|phishing kit)\b",
    r"\b(steal|dump|exfiltrate|bypass)\b.{0,80}\b(password|credential|token|cookie|2fa|mfa)\b",
    r"\b(hack into|break into|unauthorized access)\b",
    r"\b(dox|doxx|doxxing)\b",
]

MUTATING_ACTION_PATTERNS = [
    r"\b(delete|trash|remove)\b.{0,80}\b(document|file|account|permission|policy|source)\b",
    r"\b(send|forward|email)\b.{0,80}\b(on my behalf|now|to)\b",
    r"\b(grant|revoke|transfer|change)\b.{0,80}\b(access|permission|ownership|policy|owner)\b",
    r"\b(publish|share|export)\b.{0,80}\b(private|metadata|document|data|source)\b",
]

CLARIFICATION_PATTERNS = [
    r"^\s*(this|that|it|ez|az|ezt|azt|erről|arról)\s*\??\s*$",
    r"^\s*(what about|mi van|és ezzel|and this)\s+.{0,20}\??\s*$",
]

CURRENT_STATUS_TERMS = [
    "current", "latest", "today", "now", "active", "open", "status", "aktuális", "jelenlegi", "ma", "most", "nyitott", "státusz",
]

CURRENT_TEMPORAL_SIGNALS = {"explicit_deadline", "open", "closed", "recent"}
SOURCE_ATTACK_WARNING = "source_prompt_injection_detected_do_not_send_to_generator"
LEAKAGE_WARNING = "source_content_withheld_to_avoid_instruction_or_policy_leakage"


def _now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _source_ids(governance: Dict[str, Any], key: str) -> List[str]:
    value = governance.get(key) or []
    return list(value) if isinstance(value, list) else []


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    lowered = text or ""
    return any(re.search(pattern, lowered, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def detect_prompt_injection(text: str) -> Dict[str, Any]:
    matched = [pattern for pattern in PROMPT_INJECTION_PATTERNS if re.search(pattern, text or "", flags=re.IGNORECASE | re.DOTALL)]
    return {"detected": bool(matched), "matched_patterns": matched[:5]}


def detect_request_risk(question: str) -> Dict[str, Any]:
    q = question or ""
    stripped = q.strip()
    if not stripped or _matches_any(stripped, CLARIFICATION_PATTERNS):
        return {
            "detected": True,
            "status": STATUS_ASK_CLARIFICATION,
            "reason": REASON_EPISTEMIC,
            "label": "underspecified_question",
            "safe_output": "Please clarify what source, object, time period, or claim I should evaluate.",
            "next_steps": ["Ask a more specific question and include the relevant object, source, or time window."],
            "gate": "query_profiling",
        }
    injection = detect_prompt_injection(stripped)
    if injection["detected"]:
        return {
            "detected": True,
            "status": STATUS_REFUSE,
            "reason": REASON_OPERATIONAL_SECURITY,
            "label": "prompt_injection_request",
            "safe_output": "I cannot follow instructions that try to override system rules, reveal hidden instructions, or exfiltrate protected information.",
            "next_steps": ["Ask the substantive question without instruction-override or exfiltration wording."],
            "gate": "policy_and_safety_filtering",
            "matched_patterns": injection["matched_patterns"],
        }
    if _matches_any(stripped, SAFETY_PATTERNS):
        return {
            "detected": True,
            "status": STATUS_REFUSE,
            "reason": REASON_SAFETY,
            "label": "unsafe_or_harmful_request",
            "safe_output": "I cannot provide operational instructions that would enable harm, abuse, credential theft, or unauthorized access.",
            "next_steps": ["I can help with a defensive, high-level, or policy-compliant version of the question."],
            "gate": "policy_and_safety_filtering",
        }
    if _matches_any(stripped, MUTATING_ACTION_PATTERNS):
        return {
            "detected": True,
            "status": STATUS_ESCALATE,
            "reason": REASON_OPERATIONAL_SECURITY,
            "label": "unsafe_action_boundary",
            "safe_output": "This chat route cannot perform or authorize state-changing actions. The request must go through an explicit action workflow with confirmation and audit.",
            "next_steps": ["Use the dedicated permission, export, delete, or connector workflow and confirm the exact target."],
            "gate": "operational_security_boundary",
        }
    return {"detected": False}


def select_pre_generation_output_mode(question: str, query_profile: Dict[str, Any]) -> Dict[str, Any]:
    risk = detect_request_risk(question)
    if not risk.get("detected"):
        return allowed_output(STATUS_FULL_ANSWER, {"gate": "query_profiling"})
    cf = make_controlled_failure(
        risk["status"],
        risk["reason"],
        evidence_state([], query_profile, False),
        safe_policy_state({}),
        risk["safe_output"],
        risk.get("next_steps", []),
        {
            "gate": risk.get("gate"),
            "risk_label": risk.get("label"),
            "matched_patterns": risk.get("matched_patterns", []),
            "question_fingerprint": len(question or ""),
        },
    )
    return blocked_output(cf)


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
    temporal_signals: List[str] = []
    for source in sources:
        profile = source.get("usable_relevance") or {}
        for warning in profile.get("evidence_warnings") or []:
            if warning not in warnings:
                warnings.append(warning)
        for signal in profile.get("temporal_status") or []:
            if signal not in temporal_signals:
                temporal_signals.append(signal)
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
        "has_analogical": role_summary.get(relevance.SOURCE_ROLE_ANALOGICAL, 0) > 0,
        "has_governance_excluded": role_summary.get(relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED, 0) > 0,
        "has_source_prompt_attack": SOURCE_ATTACK_WARNING in warnings,
        "temporal_signals": temporal_signals,
        "has_current_temporal_signal": bool(set(temporal_signals).intersection(CURRENT_TEMPORAL_SIGNALS)),
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


def allowed_output(mode: str = STATUS_FULL_ANSWER, trace: Dict[str, Any] | None = None, controlled_failure_obj: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "decision": "restricted_generation_allowed" if controlled_failure_obj else "answer_allowed",
        "output_mode": mode,
        "controlled_failure": controlled_failure_obj,
        "trace": trace or {},
    }


def blocked_output(cf: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "decision": "controlled_failure",
        "output_mode": cf["status"],
        "controlled_failure": cf,
        "trace": cf.get("trace", {}),
    }


def _question_mentions_current_status(question: str, query_profile: Dict[str, Any]) -> bool:
    q = (question or "").lower()
    if any(term in q for term in CURRENT_STATUS_TERMS):
        return True
    return query_profile.get("task_intent") in {"current_action_list", "deadline_or_status"}


def _restricted_output(status: str, reason: str, state: Dict[str, Any], policy: Dict[str, Any], safe_output: str, next_steps: List[str], trace: Dict[str, Any]) -> Dict[str, Any]:
    cf = make_controlled_failure(status, reason, state, policy, safe_output, next_steps, trace)
    return allowed_output(status, trace=cf.get("trace", {}), controlled_failure_obj=cf)


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
    has_analogical = state["has_analogical"]

    trace = {
        "question_fingerprint": len(question or ""),
        "task_intent": query_profile.get("task_intent"),
        "retrieval_strategy": query_profile.get("retrieval_strategy"),
    }

    if state["has_source_prompt_attack"]:
        cf = make_controlled_failure(
            STATUS_REFUSE,
            REASON_OPERATIONAL_SECURITY,
            state,
            policy,
            "A retrieved source contained instruction-like content that was treated as an untrusted prompt-injection risk, so it was not sent to the generator.",
            ["Review the source manually or remove the instruction-like text before using it as evidence."],
            {**trace, "gate": "prompt_injection_shield"},
        )
        return blocked_output(cf)

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

    if has_aggregate and not has_primary and aggregate_request:
        return _restricted_output(
            STATUS_AGGREGATE_ANSWER,
            REASON_GOVERNANCE,
            state,
            policy,
            "Answer only at aggregate/statistical level. Do not reveal individual source text, identifiers, names, codenames, or document-specific content.",
            ["Keep the answer numeric, statistical, or cohort-level only."],
            {**trace, "gate": "output_mode_selection"},
        )

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
        if has_analogical:
            reason = REASON_EVIDENTIAL
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

    if has_analogical and not has_primary and query_profile.get("task_intent") != "comparison":
        cf = make_controlled_failure(
            STATUS_ABSTAIN,
            REASON_EVIDENTIAL,
            state,
            policy,
            "The answer cannot be found in the document.",
            ["Use analogical evidence only for comparison, or provide primary evidence for a direct claim."],
            {**trace, "gate": "source_role_labelling"},
        )
        return blocked_output(cf)

    if has_primary and _question_mentions_current_status(question, query_profile) and not state["has_current_temporal_signal"]:
        cf = make_controlled_failure(
            STATUS_ASK_CLARIFICATION,
            REASON_TEMPORAL_STATUS,
            state,
            policy,
            "I found permitted evidence, but it does not contain a clear current/open/closed/recent status signal for this time-sensitive question.",
            ["Provide a time window or connect a current source such as a recent email, calendar event, or status record."],
            {**trace, "gate": "temporal_status_check"},
        )
        return blocked_output(cf)

    if has_primary and has_contrastive:
        return _restricted_output(
            STATUS_RESTRICTED_ANSWER,
            REASON_CONFLICT_DEFEAT,
            state,
            policy,
            "Answer with qualification: contrastive evidence may close, cancel, or weaken the candidate claim.",
            ["Mention the conflict or closure status instead of presenting the primary source as an unquestioned open claim."],
            {**trace, "gate": "conflict_defeat_check"},
        )

    return allowed_output(STATUS_FULL_ANSWER, {**trace, "gate": "output_mode_selection"})


def from_not_found_answer(question: str, sources: Iterable[Dict[str, Any]], query_profile: Dict[str, Any], governance: Dict[str, Any]) -> Dict[str, Any]:
    state = evidence_state(sources, query_profile, True)
    policy = safe_policy_state(governance)
    reason = REASON_TEMPORAL_STATUS if _question_mentions_current_status(question, query_profile) and not state.get("has_current_temporal_signal") else REASON_EPISTEMIC
    return make_controlled_failure(
        STATUS_ABSTAIN,
        reason,
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
