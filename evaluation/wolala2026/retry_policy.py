from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


RETRYABLE_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRYABLE_NETWORK_MARKERS = (
    "connection reset",
    "connection aborted",
    "connection refused",
    "network error",
    "timed out",
    "timeout",
    "temporarily unavailable",
)

VALID_EMPIRICAL_RESULT_EVENTS = {
    "WRONG_ANSWER",
    "FALSE_CFAF",
    "INCORRECT_CFAF_REALIZATION",
    "REFUSAL",
    "OVER_REFUSAL",
    "PROTECTED_CONTENT_LEAKAGE",
    "GENERATOR_EXPOSURE",
    "SOURCE_EXISTENCE_LEAKAGE",
    "SAFE_NEXT_STEP_FAILURE",
    "POOR_LATENCY",
    "UNFAVORABLE_STATISTICAL_RESULT",
}
INFRASTRUCTURE_FAILURE_EVENTS = {
    "PROVIDER_OUTAGE",
    "UNRECOVERABLE_NETWORK_FAILURE",
    "PERSISTENT_RETRYABLE_PROVIDER_FAILURE",
    "HOST_PROCESS_TERMINATION",
    "RETRYABLE_CAP_EXHAUSTION",
}
SCIENTIFIC_INTEGRITY_FAILURE_EVENTS = {
    "CHECKSUM_DRIFT",
    "WRONG_MODEL_OR_PROVIDER",
    "WRONG_PROMPT",
    "WRONG_DATASET",
    "GOLD_LABEL_CONTAMINATION",
    "BASELINE_RECEIVES_CFAF_LABELS",
    "SHARED_RETRIEVAL_MISMATCH",
    "PRIMARY_SCORER_OR_PARSER_DEFECT",
    "RUN_MANIFEST_AUDIT_DEFECT",
    "INCORRECT_COVERAGE",
    "HELDOUT_DATA_CORRUPTION",
    "CAP_ENFORCEMENT_DEFECT",
    "NON_FROZEN_CODE_USED",
}


@dataclass(frozen=True)
class RetryClassification:
    retryable: bool
    reason: str
    http_status: int | None = None


def is_retryable_status(status_code: int | str | None) -> bool:
    if status_code is None:
        return False
    try:
        normalized = int(status_code)
    except (TypeError, ValueError):
        return False
    return normalized in RETRYABLE_HTTP_STATUS_CODES


def classify_retryable_condition(error: BaseException | str | None = None, *, http_status: int | None = None) -> RetryClassification:
    if is_retryable_status(http_status):
        return RetryClassification(True, f"HTTP_{int(http_status)}", int(http_status))
    message = str(error or "")
    parsed_status = _extract_http_status(message)
    if is_retryable_status(parsed_status):
        return RetryClassification(True, f"HTTP_{parsed_status}", parsed_status)
    lowered = message.lower()
    if any(marker in lowered for marker in RETRYABLE_NETWORK_MARKERS):
        return RetryClassification(True, "NETWORK_OR_TIMEOUT", parsed_status)
    return RetryClassification(False, "NON_RETRYABLE_PROVIDER_OR_CONTENT_ERROR", parsed_status)


def retry_wait_seconds(retry_after: str | int | float | None, *, default_seconds: float = 2.0, maximum_seconds: float = 60.0) -> float:
    if retry_after is None:
        return default_seconds
    try:
        value = float(retry_after)
    except (TypeError, ValueError):
        return default_seconds
    if value < 0 or value > maximum_seconds:
        return default_seconds
    return value


def classify_invalidation(event_code: str) -> str:
    if event_code in VALID_EMPIRICAL_RESULT_EVENTS:
        return "VALID_EMPIRICAL_RESULT"
    if event_code in INFRASTRUCTURE_FAILURE_EVENTS:
        return "INVALIDATED_INFRASTRUCTURE_FAILURE"
    if event_code in SCIENTIFIC_INTEGRITY_FAILURE_EVENTS:
        return "INVALIDATED_SCIENTIFIC_INTEGRITY_FAILURE"
    return "UNKNOWN_REQUIRES_AUDIT"


def rerun_authorized(
    *,
    invalidation_class: str,
    independent_audit_passed: bool,
    artifacts_retained: bool,
    unchanged_freeze_state: bool,
    separate_task_authorized: bool,
    new_empty_output_directory: bool,
    attempt_number: int,
) -> bool:
    return all(
        [
            invalidation_class == "INVALIDATED_INFRASTRUCTURE_FAILURE",
            independent_audit_passed,
            artifacts_retained,
            unchanged_freeze_state,
            separate_task_authorized,
            new_empty_output_directory,
            attempt_number == 2,
        ]
    )


def _extract_http_status(message: str) -> int | None:
    match = re.search(r"\bHTTP\s+(\d{3})\b", message)
    if not match:
        return None
    return int(match.group(1))


def retry_policy_summary(spec: dict[str, Any]) -> dict[str, Any]:
    planned_without_retries = int(spec["planned_external_requests_without_retries_maximum"])
    hard_total_cap = int(spec["max_total_external_calls"])
    return {
        "max_total_retry_attempts": int(spec["max_total_retry_attempts"]),
        "max_retries_per_logical_request": int(spec["max_retries_per_logical_request"]),
        "total_cap_retry_slack": hard_total_cap - planned_without_retries,
        "retryable_http_status_codes": sorted(RETRYABLE_HTTP_STATUS_CODES),
        "external_warmup_calls": int(spec["external_warmup_calls"]),
    }
