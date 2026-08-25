"""Deterministic development action/closure reconstruction engine."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Iterable


ACTION_ENGINE_VERSION = "infocom-action-closure-v1"
OPEN = "OPEN"
CLOSED_COMPLETED = "CLOSED_COMPLETED"
CLOSED_CANCELLED = "CLOSED_CANCELLED"
SUPERSEDED = "SUPERSEDED"

_CLOSURE_EVENT_STATES = {
    "completion": CLOSED_COMPLETED,
    "cancellation": CLOSED_CANCELLED,
    "rejection": CLOSED_CANCELLED,
    "supersession": SUPERSEDED,
}


@dataclass(frozen=True)
class MessageEvidence:
    evidence_id: str
    source_type: str
    timestamp: str
    sender: str
    recipients: tuple[str, ...]
    subject: str
    body: str
    thread_id: str | None = None
    reply_to: str | None = None
    relation_key: str | None = None


@dataclass
class ActionCandidate:
    action_id: str
    normalized_action_key: str
    request_evidence_id: str
    request_timestamp: str
    request_participants: tuple[str, ...]
    status: str = OPEN
    linked_evidence_ids: list[str] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    link_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def normalized_action_key(text: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", " ", text.lower())
    lowered = re.sub(
        r"\b(please|could|would|you|the|this|that|request|completed|cancelled|canceled|done|accepted|reminder)\b",
        " ",
        lowered,
    )
    return re.sub(r"\s+", " ", lowered).strip()[:160]


def classify_event(item: MessageEvidence) -> str:
    if item.source_type.lower() in {"browserhistory", "browser_history", "activitytrace", "activity_trace"}:
        return "contextual_browser"
    text = f"{item.subject} {item.body}".lower()
    patterns = (
        ("supersession", r"\b(superseded|replaced by|new request instead)\b"),
        ("cancellation", r"\b(cancelled|canceled|withdrawn|no longer needed)\b"),
        ("rejection", r"\b(rejected|declined|will not proceed)\b"),
        ("completion", r"\b(completed|finished|done|delivered|submitted)\b"),
        ("postponement", r"\b(postponed|deferred|moved to|later date)\b"),
        ("acceptance", r"\b(accepted|i will|we will|agreed to)\b"),
        ("reminder", r"\b(reminder|follow up|overdue)\b"),
        ("acknowledgement", r"\b(acknowledged|received|noted)\b"),
        ("status_update", r"\b(in progress|working on|status update)\b"),
        ("request", r"\b(please|could you|must|required|action:)\b"),
    )
    for label, pattern in patterns:
        if re.search(pattern, text):
            return label
    return "informative"


def resolve_action_status(event_types: Iterable[str]) -> str:
    """Resolve the final action state from chronologically ordered events.

    Non-closing events deliberately leave the current state unchanged.  A later
    explicit closure event replaces an earlier closure state, matching the
    ordered reconstruction performed by :func:`reconstruct_actions`.
    """

    status = OPEN
    for event_type in event_types:
        status = _CLOSURE_EVENT_STATES.get(event_type, status)
    return status


def _direct_group(item: MessageEvidence) -> str | None:
    if item.relation_key:
        return f"relation:{item.relation_key}"
    if item.thread_id:
        return f"thread:{item.thread_id}"
    if item.reply_to:
        return f"reply:{item.reply_to}"
    return None


def _semantic_overlap(left: str, right: str) -> float:
    left_tokens = set(normalized_action_key(left).split())
    right_tokens = set(normalized_action_key(right).split())
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) if left_tokens | right_tokens else 0.0


def reconstruct_actions(items: Iterable[MessageEvidence]) -> dict:
    ordered = sorted(items, key=lambda item: (item.timestamp, item.evidence_id))
    candidates: list[ActionCandidate] = []
    by_group: dict[str, ActionCandidate] = {}
    by_evidence: dict[str, ActionCandidate] = {}
    contextual_only: list[str] = []

    for item in ordered:
        event = classify_event(item)
        group = _direct_group(item)
        candidate = by_group.get(group) if group else None
        link_signal = "relation_or_thread"
        if not candidate and item.reply_to:
            candidate = by_evidence.get(item.reply_to)
            link_signal = "reply"
        if not candidate and event not in {"request", "contextual_browser", "informative"}:
            participants = {item.sender, *item.recipients}
            ranked = []
            for existing_candidate in candidates:
                semantic = _semantic_overlap(item.subject + " " + item.body, existing_candidate.normalized_action_key)
                participant = bool(participants & set(existing_candidate.request_participants))
                temporal = item.timestamp >= existing_candidate.request_timestamp
                score = semantic + (0.2 if participant else 0.0) + (0.1 if temporal else -1.0)
                ranked.append((score, semantic, participant, temporal, existing_candidate))
            ranked.sort(key=lambda value: (-value[0], value[4].action_id))
            if ranked and ranked[0][3] and (ranked[0][1] >= 0.5 or (ranked[0][2] and ranked[0][1] >= 0.25)):
                _, _, participant, _, candidate = ranked[0]
                link_signal = "participant_temporal_semantic" if participant else "temporal_semantic_secondary"

        if event == "request" and item.source_type.lower() not in {"browserhistory", "browser_history", "activitytrace", "activity_trace"}:
            key = normalized_action_key(item.subject or item.body)
            action_id = hashlib.sha256(f"{key}|{item.evidence_id}".encode("utf-8")).hexdigest()[:20]
            candidate = ActionCandidate(
                action_id=action_id,
                normalized_action_key=key,
                request_evidence_id=item.evidence_id,
                request_timestamp=item.timestamp,
                request_participants=tuple(sorted({item.sender, *item.recipients})),
                linked_evidence_ids=[item.evidence_id],
                event_types=[event],
                link_signals=["request_origin"],
            )
            candidates.append(candidate)
            if group:
                by_group[group] = candidate
            by_evidence[item.evidence_id] = candidate
            continue

        if event == "contextual_browser":
            contextual_only.append(item.evidence_id)
            if candidate:
                candidate.linked_evidence_ids.append(item.evidence_id)
                candidate.event_types.append(event)
                candidate.link_signals.append("contextual_only")
            continue

        if not candidate:
            continue
        candidate.linked_evidence_ids.append(item.evidence_id)
        candidate.event_types.append(event)
        candidate.link_signals.append(link_signal)
        by_evidence[item.evidence_id] = candidate
        candidate.status = resolve_action_status(candidate.event_types)

    result = [candidate.to_dict() for candidate in sorted(candidates, key=lambda item: item.action_id)]
    return {
        "engine_version": ACTION_ENGINE_VERSION,
        "actions": result,
        "open_actions": [item for item in result if item["status"] == OPEN],
        "closed_actions": [item for item in result if item["status"] != OPEN],
        "contextual_only_evidence_ids": sorted(contextual_only),
        "browser_only_false_actions": 0,
    }
