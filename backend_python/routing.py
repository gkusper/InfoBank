"""Governance-preserving document routing for A-GATE Phase A2.

Routing is deliberately a post-policy operation: callers must pass only document
identifiers already deemed usable by the policy engine.  Neither evaluation
mode can add an identifier that is absent from that governed input set.
"""

from __future__ import annotations

import enum
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping


class RoutingMode(str, enum.Enum):
    ROUTING_OFF = "ROUTING_OFF"
    KEYWORD_ROUTING = "KEYWORD_ROUTING"


ROUTING_CONFIG_VERSION = "infocom-a2-routing-v1"
RUNTIME_ROUTING_MODE_ENV = "INFOBANK_ROUTING_MODE"


def normalize_keyword(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", str(value).strip().lower())


def routing_config_hash() -> str:
    payload = {
        "config_version": ROUTING_CONFIG_VERSION,
        "fallback": "all_governance_permitted_documents",
        "matching": "normalized_exact_keyword",
        "modes": [mode.value for mode in RoutingMode],
        "policy_order": "governance_before_routing",
        "runtime_feature_flag": RUNTIME_ROUTING_MODE_ENV,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def runtime_routing_mode() -> RoutingMode:
    """Resolve the server-controlled production routing feature flag."""

    raw = os.getenv(RUNTIME_ROUTING_MODE_ENV, RoutingMode.KEYWORD_ROUTING.value).strip().upper()
    try:
        return RoutingMode(raw)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in RoutingMode)
        raise RuntimeError(f"{RUNTIME_ROUTING_MODE_ENV} must be one of: {allowed}") from exc


@dataclass(frozen=True)
class RoutingDecision:
    mode: str
    candidate_document_ids: tuple[str, ...]
    excluded_document_ids: tuple[str, ...]
    selected_keywords: tuple[str, ...]
    matched_keywords: tuple[str, ...]
    fallback_used: bool
    fallback_reason: str | None
    governed_input_count: int
    candidate_set_size: int
    config_version: str = ROUTING_CONFIG_VERSION
    config_hash: str = ""

    def to_trace(self) -> dict:
        return asdict(self)


def route_documents(
    permitted_document_ids: Iterable[str],
    document_keywords: Mapping[str, Iterable[str]],
    selected_keywords: Iterable[str],
    mode: RoutingMode | str,
) -> RoutingDecision:
    """Return a stable candidate set that is always a subset of governed input."""

    resolved_mode = RoutingMode(mode)
    permitted = tuple(sorted({str(doc_id) for doc_id in permitted_document_ids}))
    permitted_set = set(permitted)
    selected = tuple(sorted({kw for value in selected_keywords if (kw := normalize_keyword(value))}))

    normalized_by_document = {
        str(doc_id): {kw for value in values if (kw := normalize_keyword(value))}
        for doc_id, values in document_keywords.items()
        if str(doc_id) in permitted_set
    }

    fallback_used = False
    fallback_reason: str | None = None
    matched_keywords: set[str] = set()

    if resolved_mode == RoutingMode.ROUTING_OFF:
        candidates = permitted
    elif not selected:
        candidates = permitted
        fallback_used = True
        fallback_reason = "no_selected_keyword"
    else:
        selected_set = set(selected)
        matches: list[str] = []
        for doc_id in permitted:
            hits = normalized_by_document.get(doc_id, set()) & selected_set
            if hits:
                matches.append(doc_id)
                matched_keywords.update(hits)
        if matches:
            candidates = tuple(matches)
        else:
            candidates = permitted
            fallback_used = True
            fallback_reason = "no_governed_keyword_match"

    candidate_set = set(candidates)
    excluded = tuple(doc_id for doc_id in permitted if doc_id not in candidate_set)
    return RoutingDecision(
        mode=resolved_mode.value,
        candidate_document_ids=tuple(candidates),
        excluded_document_ids=excluded,
        selected_keywords=selected,
        matched_keywords=tuple(sorted(matched_keywords)),
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        governed_input_count=len(permitted),
        candidate_set_size=len(candidates),
        config_hash=routing_config_hash(),
    )
