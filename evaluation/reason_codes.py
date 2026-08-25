"""Canonical reason-code taxonomy for evaluation comparisons."""

from __future__ import annotations


ANSWER_REASON_CODES = {
    "baseline_generation": "supported",
    "supported": "supported",
}

OUTPUT_CLASS_DEFAULT_REASON_CODES = {
    "CLARIFICATION": "clarification",
    "REFUSE_PERMISSION": "permission_refusal",
    "REFUSE_INSUFFICIENT_EVIDENCE": "insufficient_evidence",
    "REFUSE_NO_MATCH": "no_match",
    "REFUSE_AGGREGATION_THRESHOLD": "aggregation_threshold_not_met",
    "REFUSE_CONFLICT": "conflict",
}

REASON_ALIASES = {
    "aggregation_threshold_not_met": "aggregation_threshold_not_met",
    "clarification": "clarification",
    "conflict": "conflict",
    "conflict_defeat": "conflict",
    "conflicting_evidence": "conflict",
    "evidential": "insufficient_evidence",
    "governance": "permission_refusal",
    "inactive_policy": "permission_refusal",
    "insufficient_evidence": "insufficient_evidence",
    "no_match": "no_match",
    "permission_lifecycle_expected": "permission_refusal",
    "permission_refusal": "permission_refusal",
    "stale_index_denied": "permission_refusal",
    "underspecified_question": "clarification",
    "wrong_object": "no_match",
}


def canonical_reason_code(output_class: str, reason_code: str) -> str:
    """Return the machine-stable reason code used by scorers and reports."""

    output = str(output_class or "").strip()
    raw = str(reason_code or "").strip()
    if raw in ANSWER_REASON_CODES:
        return ANSWER_REASON_CODES[raw]
    if raw in REASON_ALIASES:
        canonical = REASON_ALIASES[raw]
        if output == "CLARIFICATION" and canonical == "insufficient_evidence":
            return OUTPUT_CLASS_DEFAULT_REASON_CODES[output]
        if output == "REFUSE_NO_MATCH" and canonical == "insufficient_evidence":
            return OUTPUT_CLASS_DEFAULT_REASON_CODES[output]
        if output == "REFUSE_PERMISSION" and canonical == "insufficient_evidence":
            return OUTPUT_CLASS_DEFAULT_REASON_CODES[output]
        return canonical
    return OUTPUT_CLASS_DEFAULT_REASON_CODES.get(output, raw)
