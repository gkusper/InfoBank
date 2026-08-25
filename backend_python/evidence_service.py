"""Evidence checking and action-list reconstruction for InfoBank.

This module implements the CITDS paper's requirement that retrieved sources are
not passed to generation as undifferentiated context. Evidence is checked for
role, status, conflict, permission, and support strength before an answer is
accepted.
"""

import calendar
import datetime
import hashlib
import json
import re
import uuid
from itertools import combinations
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

import citds_classifier
import action_closure
import models
import policy_engine
import relevance
from controlled_failure_config import load_controlled_failure_config


ACTION_ROLE_PRIMARY = "primary"
ACTION_ROLE_CONTEXTUAL = "contextual"
ACTION_ROLE_CONTRASTIVE = "contrastive"
ACTION_ROLE_EXCLUDED = "governance-excluded"

ACTION_VERBS = [
    "advise",
    "agree",
    "announce",
    "answer",
    "apply",
    "book",
    "calculate",
    "call",
    "check",
    "complete",
    "confirm",
    "contact",
    "digest",
    "disregard",
    "distribute",
    "draft",
    "email",
    "e-mail",
    "file",
    "forward",
    "give",
    "move",
    "prepare",
    "provide",
    "redo",
    "re-do",
    "reply",
    "return",
    "review",
    "run",
    "send",
    "sign",
    "stick",
    "submit",
    "update",
    "verify",
]
REQUEST_SIGNAL_RE = re.compile(
    r"\b(please|need to|needs to|must|required|assigned|could you|can you|"
    r"would you|should be|requested|reminder)\b",
    re.IGNORECASE,
)
COMPLETION_SIGNAL_RE = re.compile(
    r"\b(done|completed|finished|sent|provided|attached|resolved|submitted|"
    r"forwarded|reviewed|drafted|prepared|paid|filed|delivered|handed\s+off|"
    r"passed\s+on|have\s+done|have\s+finished|have\s+forwarded|have\s+asked|"
    r"agree\s+with|accepted|signed)\b",
    re.IGNORECASE,
)
CANCELLATION_SIGNAL_RE = re.compile(
    r"\b(cancelled|canceled|withdrawn|no longer needed|not needed|disregard\s+the\s+request)\b",
    re.IGNORECASE,
)
SUPERSESSION_SIGNAL_RE = re.compile(
    r"\b(replaced|superseded|new version|instead|revised|red-lined|updated language)\b",
    re.IGNORECASE,
)
NONCLOSING_SIGNAL_RE = re.compile(
    r"\b(working on|started|start(?:ed)? reviewing|will do|will be|going to|intend|"
    r"expect|plan|should be able|in progress)\b",
    re.IGNORECASE,
)
NON_ACTION_PATTERNS = [
    r"temporary\s+chatgpt\s+login\s+code",
    r"login\s+code",
    r"verification\s+code",
    r"multi-factor\s+authentication",
    r"two-factor\s+authentication",
    r"security\s+alert",
    r"third-party\s+github\s+application\s+has\s+been\s+added",
    r"application\s+has\s+been\s+added\s+to\s+your\s+account",
    r"if\s+you\s+did\s+not\s+make\s+this\s+request",
    r"unsubscribe",
    r"category_promotions",
    r"k[eé]szlet(?:riaszt[aá]s)?",
    r"legn[eé]pszer[uű]bb\s+iphone",
]


def parse_timestamp(value: Optional[str]) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def create_evidence_unit(db: Session, user_id: str, payload: Dict[str, Any]) -> models.EvidenceUnit:
    unit = models.EvidenceUnit(
        id=str(uuid.uuid4()),
        user_id=user_id,
        source_type=models.EvidenceSourceType(payload.get("source_type", "Other")),
        title=payload.get("title") or "Untitled evidence unit",
        content=payload.get("content") or "",
        source_timestamp=parse_timestamp(payload.get("source_timestamp")),
        thread_id=payload.get("thread_id"),
        relation_key=payload.get("relation_key"),
        metadata_json=json.dumps(payload.get("metadata") or {}, ensure_ascii=False),
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def import_evidence_units(db: Session, user_id: str, units: Iterable[Dict[str, Any]]) -> List[models.EvidenceUnit]:
    created: List[models.EvidenceUnit] = []
    for payload in units:
        created.append(create_evidence_unit(db, user_id, payload))
    return created


def _metadata(unit: models.EvidenceUnit) -> Dict[str, Any]:
    try:
        parsed = json.loads(unit.metadata_json or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _dedupe_key(unit: models.EvidenceUnit) -> str:
    meta = _metadata(unit)
    connector = meta.get("connector")
    message_id = meta.get("message_id")
    if connector in {"gmail", "gmail_oauth"} and message_id:
        return f"gmail-message:{message_id}"
    fingerprint = hashlib.sha1(
        f"{unit.user_id}|{unit.source_type}|{unit.title}|{unit.content}|{unit.relation_key}".encode("utf-8", errors="ignore")
    ).hexdigest()
    return f"evidence:{fingerprint}"


def dedupe_evidence_units(units: Iterable[models.EvidenceUnit]) -> List[models.EvidenceUnit]:
    """Keep one copy of each imported external evidence item.

    Re-running Gmail sync should not inflate the evidence set or the UI trace with
    duplicate message imports. The newest local row wins so manual re-syncs remain
    visible if metadata changes.
    """

    by_key: Dict[str, models.EvidenceUnit] = {}
    for unit in units:
        key = _dedupe_key(unit)
        current = by_key.get(key)
        if not current or (unit.created_at or datetime.datetime.min) >= (current.created_at or datetime.datetime.min):
            by_key[key] = unit
    return list(by_key.values())


def _citds_role_to_action_role(source_role: str, source_type: str, use_decision: str) -> str:
    if use_decision == relevance.USE_DENY or source_role == relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED:
        return ACTION_ROLE_EXCLUDED
    if use_decision == relevance.USE_METADATA:
        return ACTION_ROLE_CONTEXTUAL
    if source_role == relevance.SOURCE_ROLE_CONTRASTIVE:
        return ACTION_ROLE_CONTRASTIVE
    if source_type in {"BrowserHistory", "ActivityTrace"}:
        return ACTION_ROLE_CONTEXTUAL
    if source_role == relevance.SOURCE_ROLE_PRIMARY:
        return ACTION_ROLE_PRIMARY
    if source_role == relevance.SOURCE_ROLE_AGGREGATE_ONLY:
        return ACTION_ROLE_CONTEXTUAL
    return ACTION_ROLE_CONTEXTUAL


def is_non_action_notification(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in NON_ACTION_PATTERNS)


def is_unowned_outbound_request(text: str) -> bool:
    lowered = text.lower()
    if "direction: outbound" not in lowered:
        return False
    if any(marker in lowered for marker in ["i will", "i'll", "i commit", "committed", "accepted"]):
        return False
    # An outbound "please review" is usually a request to somebody else, not the
    # user's own open task. It may still be contextual support for a thread.
    return any(re.search(rf"\bplease\s+{verb}\b", lowered) for verb in ACTION_VERBS)


def _body_excerpt(text: str) -> str:
    match = re.search(r"Body excerpt:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _starts_with_action_verb(text: str) -> bool:
    body = _body_excerpt(text).lower().strip(" .:-")
    if re.match(r"^(agree\s+with|have\s+asked|have\s+forwarded|have\s+finished|have\s+done|had\s+)", body):
        return False
    return any(re.match(rf"^{re.escape(verb)}\b", body) for verb in ACTION_VERBS)


def has_obligation_signal(text: str) -> bool:
    lowered = text.lower()
    if is_non_action_notification(text):
        return False
    if "action:" in lowered or "official request" in lowered:
        return True
    if REQUEST_SIGNAL_RE.search(text):
        return True
    if _starts_with_action_verb(text):
        return True
    if any(re.search(rf"\b{verb}\b", lowered) for verb in ACTION_VERBS) and any(marker in lowered for marker in ["deadline", "due", " by 20"]):
        return True
    return False


def has_request_obligation_signal(text: str) -> bool:
    return has_obligation_signal(text) and (bool(REQUEST_SIGNAL_RE.search(text)) or _starts_with_action_verb(text))


def has_closure_signal(text: str) -> bool:
    return bool(COMPLETION_SIGNAL_RE.search(text) or CANCELLATION_SIGNAL_RE.search(text) or SUPERSESSION_SIGNAL_RE.search(text))


def has_nonclosing_signal(text: str) -> bool:
    return bool(NONCLOSING_SIGNAL_RE.search(text)) and not has_closure_signal(text)


def classify_evidence_unit(unit: models.EvidenceUnit, policy_resolution: Dict[str, Any] | None = None) -> Dict[str, Any]:
    text = f"{unit.title}\n{unit.content}"
    signal_text = unit.content or text
    source_type = unit.source_type.value if hasattr(unit.source_type, "value") else str(unit.source_type)
    policy_resolution = policy_resolution or {
        "use_decision": relevance.USE_FULL,
        "source_role": relevance.SOURCE_ROLE_PRIMARY,
        "reason": "owned_evidence_full",
        "policy_rule_id": None,
    }
    use_decision = policy_resolution.get("use_decision", relevance.USE_FULL)

    # Defence in depth: callers must never be able to turn a hard governance
    # decision into a content-bearing classification.  Aggregate evidence is
    # likewise unavailable to an individual action-list reconstruction; it may
    # be consumed only by a dedicated aggregate executor.
    if use_decision in {relevance.USE_DENY, relevance.USE_AGGREGATE}:
        denied = use_decision == relevance.USE_DENY
        role = ACTION_ROLE_EXCLUDED if denied else ACTION_ROLE_CONTEXTUAL
        source_role = (
            relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED
            if denied
            else relevance.SOURCE_ROLE_AGGREGATE_ONLY
        )
        label = "governance-excluded" if denied else "aggregate-only"
        return {
            "id": unit.id,
            "source_type": source_type,
            "title": f"[{label}: evidence identity and content withheld]",
            "content_summary": f"[{label}: evidence identity and content withheld]",
            "timestamp": None,
            "thread_id": None,
            "relation_key": unit.id,
            "role": role,
            "citds_source_role": source_role,
            "status": "governance_excluded" if denied else "aggregate_only",
            "due": None,
            "action": None,
            "object": None,
            "policy": {
                "use_decision": use_decision,
                "source_role": source_role,
                "reason": policy_resolution.get("reason"),
                "policy_rule_id": policy_resolution.get("policy_rule_id"),
            },
            "classifier": {
                "source_role": source_role,
                "warnings": [f"{label.replace('-', '_')}_content_withheld"],
            },
            "signals": {
                "primary": [],
                "contextual": [],
                "closure": [],
                "genre": [],
                "temporal_status": [],
            },
        }

    classifier_text = text if use_decision != relevance.USE_METADATA else unit.title
    classifier_result = citds_classifier.classify_source(
        text=classifier_text,
        task_intent="current_action_list",
        use_decision=use_decision,
        use_llm=False,
    )

    action_role = _citds_role_to_action_role(classifier_result.get("source_role"), source_type, use_decision)
    warnings = classifier_result.setdefault("warnings", [])
    if use_decision != relevance.USE_METADATA and action_role == ACTION_ROLE_PRIMARY:
        if is_non_action_notification(signal_text):
            action_role = ACTION_ROLE_CONTEXTUAL
            classifier_result["source_role"] = relevance.SOURCE_ROLE_CONTEXTUAL
            warnings.append("non_action_system_or_marketing_notification")
        elif is_unowned_outbound_request(signal_text):
            action_role = ACTION_ROLE_CONTEXTUAL
            classifier_result["source_role"] = relevance.SOURCE_ROLE_CONTEXTUAL
            warnings.append("outbound_request_contextual_not_user_obligation")
        elif source_type in {"BrowserHistory", "ActivityTrace"}:
            action_role = ACTION_ROLE_CONTEXTUAL
            classifier_result["source_role"] = relevance.SOURCE_ROLE_CONTEXTUAL
            warnings.append("activity_trace_contextual_not_obligation")
        elif has_closure_signal(signal_text) and not has_request_obligation_signal(signal_text):
            action_role = ACTION_ROLE_CONTRASTIVE
            classifier_result["source_role"] = relevance.SOURCE_ROLE_CONTRASTIVE
            warnings.append("completion_cancellation_or_supersession_signal")
        elif has_obligation_signal(signal_text):
            action_role = ACTION_ROLE_PRIMARY
            classifier_result["source_role"] = relevance.SOURCE_ROLE_PRIMARY
        elif not has_obligation_signal(signal_text):
            action_role = ACTION_ROLE_CONTEXTUAL
            classifier_result["source_role"] = relevance.SOURCE_ROLE_CONTEXTUAL
            warnings.append("no_explicit_user_obligation_signal")
    elif use_decision != relevance.USE_METADATA and action_role == ACTION_ROLE_CONTEXTUAL:
        if source_type not in {"BrowserHistory", "ActivityTrace"} and has_request_obligation_signal(signal_text):
            action_role = ACTION_ROLE_PRIMARY
            classifier_result["source_role"] = relevance.SOURCE_ROLE_PRIMARY
            warnings.append("generic_obligation_signal_promoted_to_primary")
        elif source_type not in {"BrowserHistory", "ActivityTrace"} and has_closure_signal(signal_text):
            action_role = ACTION_ROLE_CONTRASTIVE
            classifier_result["source_role"] = relevance.SOURCE_ROLE_CONTRASTIVE
            warnings.append("generic_closure_signal_promoted_to_contrastive")
    elif use_decision != relevance.USE_METADATA and action_role == ACTION_ROLE_CONTRASTIVE:
        if has_request_obligation_signal(signal_text):
            action_role = ACTION_ROLE_PRIMARY
            classifier_result["source_role"] = relevance.SOURCE_ROLE_PRIMARY
            warnings.append("obligation_signal_overrides_false_closure")
        elif has_nonclosing_signal(signal_text):
            action_role = ACTION_ROLE_CONTEXTUAL
            classifier_result["source_role"] = relevance.SOURCE_ROLE_CONTEXTUAL
            warnings.append("nonclosing_progress_or_future_commitment")

    status = "unknown"
    if action_role == ACTION_ROLE_EXCLUDED:
        status = "governance_excluded"
    elif use_decision == relevance.USE_METADATA:
        status = "metadata_only"
    elif action_role == ACTION_ROLE_CONTRASTIVE:
        status = "closed"
    elif action_role == ACTION_ROLE_CONTEXTUAL:
        status = "contextual"
    elif action_role == ACTION_ROLE_PRIMARY:
        status = "open"

    due = None if use_decision == relevance.USE_METADATA else extract_due_date(signal_text)
    action = "[metadata-only: evidence content withheld]" if use_decision == relevance.USE_METADATA else extract_action_text(signal_text)
    object_label = None if use_decision == relevance.USE_METADATA else extract_object_label(signal_text)
    content_summary = "[metadata-only: evidence content withheld]" if use_decision == relevance.USE_METADATA else summarize_text(unit.content)
    event_type = "metadata_only"
    if use_decision != relevance.USE_METADATA:
        metadata = _metadata(unit)
        event_type = action_closure.classify_event(action_closure.MessageEvidence(
            evidence_id=unit.id,
            source_type=source_type,
            timestamp=unit.source_timestamp.isoformat() if unit.source_timestamp else "",
            sender=str(metadata.get("sender") or "unknown"),
            recipients=tuple(str(value) for value in (metadata.get("recipients") or [])),
            subject=unit.title,
            body=unit.content,
            thread_id=unit.thread_id,
            reply_to=metadata.get("reply_to"),
            relation_key=unit.relation_key,
        ))

    return {
        "id": unit.id,
        "source_type": source_type,
        "title": unit.title,
        "content_summary": content_summary,
        "timestamp": unit.source_timestamp.isoformat() if unit.source_timestamp else None,
        "thread_id": unit.thread_id,
        "relation_key": unit.relation_key or object_label or unit.thread_id or unit.id,
        "role": action_role,
        "citds_source_role": classifier_result.get("source_role"),
        "status": status,
        "event_type": event_type,
        "due": due,
        "action": action,
        "object": object_label,
        "policy": policy_resolution,
        "classifier": classifier_result,
        "signals": {
            "primary": classifier_result.get("speech_acts", []),
            "contextual": ["activity_trace"] if source_type in {"BrowserHistory", "ActivityTrace"} else [],
            "closure": [s for s in classifier_result.get("speech_acts", []) if s in {"completion", "cancellation"}],
            "genre": classifier_result.get("genre", []),
            "temporal_status": classifier_result.get("temporal_status", []),
        },
    }


def extract_due_date(text: str) -> Optional[str]:
    match = re.search(r"20\d{2}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    due_match = re.search(r"(?:deadline|due|by)[:\s]+([^\.\n]+)", text, flags=re.IGNORECASE)
    if due_match:
        return due_match.group(1).strip()[:80]
    return None


def _clean_action(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .:-")
    value = re.sub(r"^please\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^action\s*[:\-]\s*", "", value, flags=re.IGNORECASE)
    return value[:160]


def extract_action_text(text: str) -> str:
    match = re.search(r"Action[:\s]+([^\n\.]+)", text, flags=re.IGNORECASE)
    if match:
        return _clean_action(match.group(1))

    body_match = re.search(r"Body excerpt:\s*([^\n]+)", text, flags=re.IGNORECASE)
    if body_match:
        return _clean_action(body_match.group(1))

    verb_group = "|".join(re.escape(verb) for verb in ACTION_VERBS)
    subject_match = re.search(rf"Subject:\s*(please\s+(?:{verb_group})[^\.\n]*)", text, flags=re.IGNORECASE)
    if subject_match:
        return _clean_action(subject_match.group(1))

    please_match = re.search(rf"\bplease\s+({verb_group})\b([^\.\n]*)", text, flags=re.IGNORECASE)
    if please_match:
        return _clean_action(" ".join(part for part in please_match.groups() if part))

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        low = line.lower()
        if any(word in low for word in ACTION_VERBS):
            return _clean_action(line[:160])
    return lines[0][:160] if lines else "Unspecified action"


def extract_object_label(text: str) -> Optional[str]:
    candidates = [
        r"candidate\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"course[:\s]+([^\n\.]+)",
        r"trip[:\s]+([^\n\.]+)",
        r"object[:\s]+([^\n\.]+)",
        r"task[:\s]+([^\n\.]+)",
    ]
    for pattern in candidates:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()[:120]
    return None


def summarize_text(text: str, max_len: int = 220) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:max_len] + ("..." if len(clean) > max_len else "")


def _normalise_action_key(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\b(please|gmail|message|direction|inbound|outbound|subject|body)\b", " ", value)
    return re.sub(r"\s+", " ", value).strip()[:120]


def _group_key(item: Dict[str, Any]) -> str:
    if item.get("relation_key"):
        return f"relation:{item['relation_key']}"
    if item.get("role") in {ACTION_ROLE_PRIMARY, ACTION_ROLE_CONTRASTIVE} and item.get("action"):
        action_key = _normalise_action_key(item.get("action") or "")
        if action_key and action_key != "unspecified action":
            return f"action:{action_key}|due:{item.get('due') or ''}"
    return item.get("relation_key") or item["id"]


def _timestamp_value(item: Dict[str, Any]) -> Optional[datetime.datetime]:
    return parse_timestamp(item.get("timestamp"))


def _valid_later_contrastive(primary: List[Dict[str, Any]], contrastive: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    primary_times = [_timestamp_value(item) for item in primary]
    primary_times = [value for value in primary_times if value is not None]
    if not primary_times:
        return contrastive
    earliest_primary = min(primary_times)
    valid = []
    for item in contrastive:
        timestamp = _timestamp_value(item)
        if timestamp and timestamp > earliest_primary:
            valid.append(item)
    return valid


def _runtime_action_id(relation_key: str, primary: List[Dict[str, Any]]) -> str:
    request_ids = "|".join(sorted(item["id"] for item in primary))
    return hashlib.sha256(f"{relation_key}|{request_ids}".encode("utf-8")).hexdigest()[:20]


def _action_item(
    group: Dict[str, Any],
    primary: List[Dict[str, Any]],
    contextual: List[Dict[str, Any]],
    contrastive: List[Dict[str, Any]],
    excluded: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
) -> Dict[str, Any]:
    strongest = sorted(primary, key=lambda item: item.get("timestamp") or "")[-1]
    ordered_evidence = sorted(
        primary + contextual + contrastive,
        key=lambda item: (item.get("timestamp") or "", item["id"]),
    )
    event_types = [item.get("event_type") or "informative" for item in ordered_evidence]
    closure_event_types = [item.get("event_type") or "informative" for item in contrastive]
    status = action_closure.resolve_action_status(closure_event_types)
    evidence = {
        "primary": primary,
        "contextual": contextual,
        "contrastive": contrastive,
        "excluded": excluded,
        "metadata_only": metadata,
    }
    return {
        "action_id": _runtime_action_id(group["relation_key"], primary),
        "actor": "user",
        "action": strongest.get("action") or "Unspecified action",
        "object": strongest.get("object"),
        "due": strongest.get("due"),
        "status": status,
        "E": [item["id"] for item in ordered_evidence],
        "linked_evidence_ids": [item["id"] for item in ordered_evidence],
        "event_types": event_types,
        "closure_event_types": closure_event_types,
        "R": {
            "primary": len(primary),
            "contextual": len(contextual),
            "contrastive": len(contrastive),
            "excluded": len(excluded),
            "metadata_only": len(metadata),
        },
        "evidence": evidence,
    }


def reconstruct_action_list(db: Session, user_id: str, as_of: datetime.datetime | None = None) -> Dict[str, Any]:
    query = db.query(models.EvidenceUnit).filter(models.EvidenceUnit.user_id == user_id)
    if as_of is not None:
        query = query.filter((models.EvidenceUnit.source_timestamp == None) | (models.EvidenceUnit.source_timestamp <= as_of))
    # Resolve policy from identifiers first.  Denied and aggregate-only rows
    # must not be loaded into the individual action reconstruction at all.
    unit_ids = sorted(row[0] for row in query.with_entities(models.EvidenceUnit.id).all())
    policy_context = policy_engine.resolve_evidence_unit_access_bulk(
        db=db,
        user_id=user_id,
        unit_ids=unit_ids,
        purpose="action_reconstruction",
    ) if unit_ids else {
        "use_decisions": {},
        "source_roles": {},
        "policy_reasons": {},
        "policy_rule_ids": {},
        "usable_unit_ids": [],
        "content_unit_ids": [],
        "metadata_only_unit_ids": [],
        "denied_unit_ids": [],
    }
    individually_usable_ids = [
        unit_id
        for unit_id in unit_ids
        if policy_context["use_decisions"].get(unit_id) in {relevance.USE_FULL, relevance.USE_METADATA}
    ]
    raw_units = query.filter(models.EvidenceUnit.id.in_(individually_usable_ids)).all() if individually_usable_ids else []
    units = dedupe_evidence_units(raw_units)
    classified = [
        classify_evidence_unit(
            unit,
            {
                "use_decision": policy_context["use_decisions"].get(unit.id, relevance.USE_DENY),
                "source_role": policy_context["source_roles"].get(unit.id, relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED),
                "reason": policy_context["policy_reasons"].get(unit.id),
                "policy_rule_id": policy_context["policy_rule_ids"].get(unit.id),
            },
        )
        for unit in units
    ]

    grouped: Dict[str, Dict[str, Any]] = {}
    for item in classified:
        key = _group_key(item)
        if key not in grouped:
            grouped[key] = {
                "relation_key": key,
                "primary_evidence": [],
                "contextual_support": [],
                "contrastive_evidence": [],
                "excluded_evidence": [],
                "metadata_only_evidence": [],
            }
        if item["status"] == "metadata_only":
            grouped[key]["metadata_only_evidence"].append(item)
        elif item["role"] == ACTION_ROLE_PRIMARY:
            grouped[key]["primary_evidence"].append(item)
        elif item["role"] == ACTION_ROLE_CONTRASTIVE:
            grouped[key]["contrastive_evidence"].append(item)
        elif item["role"] == ACTION_ROLE_EXCLUDED:
            grouped[key]["excluded_evidence"].append(item)
        else:
            grouped[key]["contextual_support"].append(item)

    open_items: List[Dict[str, Any]] = []
    closed_items: List[Dict[str, Any]] = []
    contextual_only: List[Dict[str, Any]] = []
    excluded_only: List[Dict[str, Any]] = []
    metadata_only: List[Dict[str, Any]] = []

    for group in grouped.values():
        primary = group["primary_evidence"]
        contextual = group["contextual_support"]
        contrastive = _valid_later_contrastive(primary, group["contrastive_evidence"])
        invalid_contrastive = [item for item in group["contrastive_evidence"] if item not in contrastive]
        contextual = contextual + invalid_contrastive
        excluded = group["excluded_evidence"]
        metadata = group["metadata_only_evidence"]
        if primary:
            action_item = _action_item(group, primary, contextual, contrastive, excluded, metadata)
            if action_item["status"] == action_closure.OPEN:
                open_items.append(action_item)
            else:
                closed_items.append(action_item)
        elif contextual:
            contextual_only.append({
                "relation_key": group["relation_key"],
                "status": "contextual_only_not_action",
                "reason": "Contextual/activity evidence cannot create an obligation without primary evidence.",
                "evidence": contextual,
            })
        elif metadata:
            metadata_only.append({
                "relation_key": group["relation_key"],
                "status": "metadata_only_not_action",
                "reason": "Metadata-only evidence cannot create or describe an action obligation without content access.",
                "evidence": metadata,
            })
        elif excluded:
            excluded_only.append({
                "relation_key": group["relation_key"],
                "status": "governance_excluded",
                "reason": "Evidence exists but is excluded by governance.",
                "evidence": excluded,
            })

    return {
        "status": "success",
        "engine_version": action_closure.ACTION_ENGINE_VERSION,
        "closure_states": [
            action_closure.OPEN,
            action_closure.CLOSED_COMPLETED,
            action_closure.CLOSED_CANCELLED,
            action_closure.SUPERSEDED,
        ],
        "policy": {
            "policy_enforced": True,
            "usable_unit_ids": sorted(unit.id for unit in units),
            "content_unit_ids": sorted(
                unit.id
                for unit in units
                if policy_context["use_decisions"].get(unit.id) == relevance.USE_FULL
            ),
            "metadata_only_unit_ids": sorted(
                unit.id
                for unit in units
                if policy_context["use_decisions"].get(unit.id) == relevance.USE_METADATA
            ),
        },
        "open_items": open_items,
        "closed_items": closed_items,
        "actions": sorted(open_items + closed_items, key=lambda item: item["action_id"]),
        "contextual_only": contextual_only,
        "metadata_only": metadata_only,
        "excluded_only": excluded_only,
        "counts": {
            "open": len(open_items),
            "closed": len(closed_items),
            "contextual_only": len(contextual_only),
            "metadata_only": len(metadata_only),
            "excluded_only": len(excluded_only),
            "evidence_units": len(classified),
            "raw_evidence_units": len(raw_units),
        },
        "classified_units": classified,
    }


def check_rag_evidence(sources: Iterable[Dict[str, Any]], query_profile: Dict[str, Any], governance: Dict[str, Any]) -> Dict[str, Any]:
    sources = list(sources)
    role_summary = relevance.summarize_source_roles(sources)
    level_summary = relevance.summarize_relevance_levels(sources)
    has_primary = role_summary.get(relevance.SOURCE_ROLE_PRIMARY, 0) > 0
    has_aggregate = role_summary.get(relevance.SOURCE_ROLE_AGGREGATE_ONLY, 0) > 0
    has_contrastive = role_summary.get(relevance.SOURCE_ROLE_CONTRASTIVE, 0) > 0
    has_metadata_only = bool(governance.get("metadata_only_doc_ids"))
    has_denied = bool(governance.get("denied_doc_ids"))

    required = query_profile.get("required_evidence_strength")
    warnings: List[str] = []
    decision = "answer_allowed"

    if has_denied:
        warnings.append("Some candidate sources were denied before generation.")
    if has_metadata_only:
        warnings.append("Some candidate sources are metadata-only; content claims must not rely on them.")
    if required == "primary_required_for_direct_claim" and not has_primary:
        decision = "controlled_failure_or_cautious_answer"
        warnings.append("Primary evidence is required for this task, but no primary source was retrieved.")
    if has_aggregate and not has_primary:
        warnings.append("Only aggregate evidence is available; do not quote individual source text.")
    if has_contrastive:
        warnings.append("Contrastive evidence was retrieved; check whether it closes, cancels, or weakens a candidate claim.")

    for source in sources:
        profile = source.get("usable_relevance", {})
        for warning in profile.get("evidence_warnings", []):
            if warning not in warnings:
                warnings.append(warning)

    return {
        "decision": decision,
        "role_summary": role_summary,
        "relevance_level_summary": level_summary,
        "has_primary": has_primary,
        "has_aggregate": has_aggregate,
        "has_contrastive": has_contrastive,
        "has_metadata_only": has_metadata_only,
        "warnings": warnings,
    }


_SUPPORT_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "does", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "the", "this", "to", "what",
    "when", "where", "which", "who", "why", "with", "you", "your", "much",
    "az", "egy", "és", "hogy", "hogyan", "hol", "is", "mely", "melyik", "mi", "milyen",
    "mit", "van", "vagy", "volt",
}
_SUPPORT_TOKEN_CANONICAL_FORMS = {
    "bought": "purchase",
    "buy": "purchase",
    "purchased": "purchase",
    "purchases": "purchase",
    "purchasing": "purchase",
    "paid": "payment",
    "pay": "payment",
    "payments": "payment",
    "paying": "payment",
}
_OBJECT_IDENTIFIER = re.compile(
    r"\b(?=[A-Z0-9-]{4,}\b)(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)+\b"
)
_AMBIGUOUS_RELATION_PATTERNS = [
    # "What damage is described for cracked panels" does not state whether
    # the caller means an exclusion, a symptom, or a causal relationship.
    r"\bwhat\s+[a-z0-9_-]+\s+(?:is|are)\s+described\s+(?:for|on)\b",
    r"\bmilyen\s+[\w-]+\s+(?:van|lett)\s+le[ií]rva\s+(?:ehhez|erre|enn[eé]l)\b",
]


def _support_threshold() -> float:
    value = load_controlled_failure_config().get("thresholds", {}).get("minimum_support_score", 0.5)
    return float(value)


def _full_source_rows(sources: Iterable[Dict[str, Any]]) -> List[tuple[Dict[str, Any], str]]:
    source_rows = list(sources)
    return [
        (
            row,
            " ".join(
            str(value or "")
            for value in (
                row.get("file_name"),
                row.get("text"),
                " ".join(row.get("usable_relevance", {}).get("genre", [])),
            )
            ),
        )
        for row in source_rows
        if row.get("use_decision") == relevance.USE_FULL
    ]


def _identifier_scoped_source_text(
    sources: Iterable[Dict[str, Any]], identifiers: Iterable[str]
) -> tuple[List[Dict[str, Any]], str, List[str]]:
    rows = _full_source_rows(sources)
    requested = list(identifiers)
    if not requested:
        return [row for row, _ in rows], " ".join(text for _, text in rows), []
    matched = [
        identifier
        for identifier in requested
        if any(identifier.casefold() in text.casefold() for _, text in rows)
    ]
    scoped = [
        (row, text)
        for row, text in rows
        if any(identifier.casefold() in text.casefold() for identifier in requested)
    ]
    return [row for row, _ in scoped], " ".join(text for _, text in scoped), matched


def _support_tokens(text: str) -> set[str]:
    return {
        _SUPPORT_TOKEN_CANONICAL_FORMS.get(token, token)
        for token in re.findall(r"[^\W_][\w-]{2,}", (text or "").casefold(), flags=re.UNICODE)
        if token not in _SUPPORT_STOP_WORDS
    }


def _factual_numbers(text: str) -> set[str]:
    """Extract numeric facts while ignoring Markdown-style list ordinals."""

    without_list_ordinals = re.sub(r"(?m)^\s*\d{1,2}[.)]\s+", "", text or "")
    return set(re.findall(r"\b\d+(?:[.,]\d+)?\b", without_list_ordinals))


def _ambiguous_claim_relation(question: str, question_relations: Iterable[str]) -> bool:
    if list(question_relations):
        return False
    return any(re.search(pattern, question or "", flags=re.IGNORECASE) for pattern in _AMBIGUOUS_RELATION_PATTERNS)


def question_source_support(question: str, sources: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a deterministic, policy-preserving pre-generation support signal."""

    requested_ids = sorted(set(_OBJECT_IDENTIFIER.findall(question or "")))
    source_rows, searchable, matched_ids = _identifier_scoped_source_text(sources, requested_ids)
    object_match = not requested_ids or len(matched_ids) == len(requested_ids)
    question_tokens = _support_tokens(question) - {identifier.lower() for identifier in requested_ids}
    source_tokens = _support_tokens(searchable)
    matched_tokens = sorted(question_tokens & source_tokens)
    coverage = len(matched_tokens) / len(question_tokens) if question_tokens else (1.0 if object_match else 0.0)
    threshold = _support_threshold()
    question_relations = relevance.claim_relation_signals(question)
    source_relations = relevance.claim_relation_signals(searchable)
    missing_relations = sorted(set(question_relations) - set(source_relations))
    ambiguous_relation = _ambiguous_claim_relation(question, question_relations)

    if not object_match:
        decision = "wrong_object"
        reason = "wrong_object_identifier"
    elif ambiguous_relation:
        decision = "clarification_required"
        reason = "ambiguous_claim_relation"
    elif missing_relations:
        decision = "insufficient_evidence"
        reason = "unsupported_claim_relation"
    elif not searchable.strip() or coverage < threshold:
        decision = "insufficient_evidence"
        reason = "insufficient_lexical_support"
    else:
        decision = "supported"
        reason = "supported"
    sufficient = decision == "supported"
    return {
        "sufficient": sufficient,
        "decision": decision,
        "reason": reason,
        "requested_object_identifiers": requested_ids,
        "matched_object_identifiers": matched_ids,
        "question_term_count": len(question_tokens),
        "matched_question_terms": matched_tokens,
        "support_coverage": round(coverage, 6),
        "threshold": threshold,
        "question_claim_relations": question_relations,
        "source_claim_relations": source_relations,
        "missing_claim_relations": missing_relations,
        "identifier_scoped_source_count": len(source_rows),
    }


SOURCE_SELECTION_VERSION = "infobank-minimal-evidence-set-v1"


def select_minimal_evidence_sources(
    question: str,
    sources: Iterable[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Select the smallest supported document set without using evaluation gold.

    Selection is intentionally conservative. It operates only on ordinary
    primary/full sources, preserves every question term and object identifier
    matched by the complete retrieved set, and keeps the complete set whenever
    support is insufficient or a security/evidence role requires special
    handling. Shared object identifiers provide a deterministic tie-break for
    same-object multi-document evidence.
    """

    source_list = list(sources)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    document_order: List[str] = []
    for index, source in enumerate(source_list):
        document_key = str(source.get("document_id") or f"__source_{index}")
        if document_key not in grouped:
            grouped[document_key] = []
            document_order.append(document_key)
        grouped[document_key].append(source)

    def trace(*, applied: bool, reason: str, selected: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "version": SOURCE_SELECTION_VERSION,
            "applied": applied,
            "reason": reason,
            "retrieved_document_count": len(grouped),
            "selected_document_count": len({str(item.get("document_id") or "") for item in selected}),
            "retrieved_chunk_count": len(source_list),
            "selected_chunk_count": len(selected),
        }

    if len(grouped) < 2:
        return source_list, trace(applied=False, reason="single_document_set", selected=source_list)
    if any(source.get("security", {}).get("prompt_injection_detected") for source in source_list):
        return source_list, trace(applied=False, reason="security_source_present", selected=source_list)
    if any(
        source.get("use_decision") != relevance.USE_FULL
        or source.get("role") != relevance.SOURCE_ROLE_PRIMARY
        for source in source_list
    ):
        return source_list, trace(applied=False, reason="special_evidence_role_present", selected=source_list)

    full_support = question_source_support(question, source_list)
    if not full_support["sufficient"]:
        return source_list, trace(applied=False, reason="full_set_not_supported", selected=source_list)

    target_terms = set(full_support["matched_question_terms"])
    target_relations = set(full_support["question_claim_relations"])
    target_identifiers = set(full_support["matched_object_identifiers"])
    if not (target_terms or target_relations or target_identifiers):
        return source_list, trace(
            applied=False,
            reason="no_discriminating_question_evidence",
            selected=source_list,
        )

    identifiers_by_document = {
        document_key: set(_OBJECT_IDENTIFIER.findall(" ".join(str(row.get("text") or "") for row in rows)))
        for document_key, rows in grouped.items()
    }
    viable: List[tuple[int, int, tuple[int, ...], tuple[str, ...], List[Dict[str, Any]]]] = []
    for subset_size in range(1, len(document_order)):
        for indexes in combinations(range(len(document_order)), subset_size):
            document_keys = tuple(document_order[index] for index in indexes)
            subset_sources = [source for key in document_keys for source in grouped[key]]
            subset_support = question_source_support(question, subset_sources)
            if not subset_support["sufficient"]:
                continue
            if not target_terms.issubset(subset_support["matched_question_terms"]):
                continue
            if not target_identifiers.issubset(subset_support["matched_object_identifiers"]):
                continue
            identifier_counts: Dict[str, int] = {}
            for key in document_keys:
                for identifier in identifiers_by_document[key]:
                    identifier_counts[identifier] = identifier_counts.get(identifier, 0) + 1
            shared_identifier_count = sum(count >= 2 for count in identifier_counts.values())
            viable.append((
                subset_size,
                -shared_identifier_count,
                indexes,
                document_keys,
                subset_sources,
            ))
        if viable:
            break

    if not viable:
        return source_list, trace(applied=False, reason="minimal_set_is_full_set", selected=source_list)

    selected = min(viable, key=lambda item: (item[0], item[1], item[2]))[4]
    selection_trace = trace(applied=True, reason="minimal_sufficient_evidence_set", selected=selected)
    selection_trace["preserved_question_term_count"] = len(target_terms)
    selection_trace["preserved_claim_relation_count"] = len(target_relations)
    selection_trace["preserved_object_identifier_count"] = len(target_identifiers)
    return selected, selection_trace


_ENGLISH_MONTH_NUMBERS = {
    month.casefold(): index
    for index, month in enumerate(calendar.month_name)
    if month
}
_TEXT_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(calendar.month_name[1:]) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)
_PURCHASE_DATE_RE = re.compile(
    r"\bpurchase\s+date\b[^\d]{0,40}"
    r"(\d{1,2}\s+(?:" + "|".join(calendar.month_name[1:]) + r")\s+\d{4})",
    re.IGNORECASE,
)
_WARRANTY_MONTHS_PATTERNS = (
    re.compile(r"\bwarranty\s+period\s+(?:is|of|lasts?)\s+(\d{1,3})\s*[- ]?\s*months?\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,3})\s*[- ]?\s*month\s+(?:manufacturer\s+)?warranty\b", re.IGNORECASE),
)
_POSITIVE_TEMPORAL_COVERAGE_RE = re.compile(
    r"\b(?:still|currently)\s+covered\b|"
    r"\bremains?\s+covered\b|"
    r"\bis\s+covered\b|"
    r"\bwithin\s+(?:the\s+)?(?:manufacturer\s+)?warranty\b|"
    r"\bwarranty\s+(?:is\s+)?(?:valid|active|in\s+effect)\b|"
    r"\b(?:has\s+)?not\s+expired\b",
    re.IGNORECASE,
)
_NEGATIVE_TEMPORAL_COVERAGE_RE = re.compile(
    r"\b(?:not|no\s+longer)\s+covered\b|"
    r"\boutside\s+(?:the\s+)?(?:manufacturer\s+)?warranty\b|"
    r"\bwarranty\s+(?:has\s+)?expired\b",
    re.IGNORECASE,
)
_NON_TEMPORAL_EXCLUSION_RE = re.compile(r"\bexclud(?:e|es|ed|ing|sion|sions)\b", re.IGNORECASE)


def _parse_english_text_date(value: str) -> Optional[datetime.date]:
    match = _TEXT_DATE_RE.search(value or "")
    if not match:
        return None
    day, month_name, year = match.groups()
    try:
        return datetime.date(int(year), _ENGLISH_MONTH_NUMBERS[month_name.casefold()], int(day))
    except ValueError:
        return None


def _add_calendar_months(value: datetime.date, months: int) -> datetime.date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def _temporal_coverage_resolution(question: str, searchable: str) -> Optional[Dict[str, Any]]:
    if "coverage" not in relevance.claim_relation_signals(question):
        return None

    question_date = _parse_english_text_date(question)
    purchase_match = _PURCHASE_DATE_RE.search(searchable or "")
    purchase_date = _parse_english_text_date(purchase_match.group(1)) if purchase_match else None
    warranty_months = next(
        (
            int(match.group(1))
            for pattern in _WARRANTY_MONTHS_PATTERNS
            if (match := pattern.search(searchable or ""))
        ),
        None,
    )
    if question_date is None or purchase_date is None or warranty_months is None:
        return None

    coverage_end_date = _add_calendar_months(purchase_date, warranty_months)
    return {
        "question_date": question_date,
        "purchase_date": purchase_date,
        "warranty_months": warranty_months,
        "coverage_end_date": coverage_end_date,
        "covered": question_date <= coverage_end_date,
    }


def _temporal_coverage_conclusion_supported(question: str, answer: str, searchable: str) -> bool:
    """Validate a generated covered/not-covered conclusion from source dates.

    This is deliberately narrow: it requires an explicit English question
    date, a labelled purchase date, a manufacturer-warranty duration, and an
    unambiguous answer polarity. Product exclusions are never treated as this
    temporal inference.
    """

    if _NON_TEMPORAL_EXCLUSION_RE.search(answer or ""):
        return False

    resolution = _temporal_coverage_resolution(question, searchable)
    if resolution is None:
        return False

    positive = bool(_POSITIVE_TEMPORAL_COVERAGE_RE.search(answer or ""))
    negative = bool(_NEGATIVE_TEMPORAL_COVERAGE_RE.search(answer or ""))
    if positive == negative:
        return False
    return positive if resolution["covered"] else negative


def answer_source_support(
    answer: str,
    sources: Iterable[Dict[str, Any]],
    question: str = "",
) -> Dict[str, Any]:
    """Validate generated claim relations against permitted full-source text.

    This is intentionally deterministic and conservative.  It does not claim
    full natural-language entailment; it blocks relation and numeric facts that
    the source text never states, which closes the observed exclusion-to-cause
    failure without weakening authorization.
    """

    answer_ids = sorted(set(_OBJECT_IDENTIFIER.findall(answer or "")))
    source_rows, searchable, matched_ids = _identifier_scoped_source_text(sources, answer_ids)
    answer_relations = relevance.claim_relation_signals(answer)
    source_relations = relevance.claim_relation_signals(searchable)
    missing_relation_set = set(answer_relations) - set(source_relations)
    temporal_coverage_inference_supported = False
    if "exclusion" in missing_relation_set:
        temporal_coverage_inference_supported = _temporal_coverage_conclusion_supported(
            question,
            answer,
            searchable,
        )
        if temporal_coverage_inference_supported:
            missing_relation_set.remove("exclusion")
    missing_relations = sorted(missing_relation_set)
    unmatched_ids = [identifier for identifier in answer_ids if identifier not in matched_ids]
    answer_numbers = sorted(_factual_numbers(answer or ""))
    source_numbers = _factual_numbers(searchable)
    question_numbers = _factual_numbers(question or "")
    accepted_question_numbers = [
        value for value in answer_numbers
        if value not in source_numbers and value in question_numbers
    ]
    unsupported_numbers = [
        value for value in answer_numbers
        if value not in source_numbers and value not in question_numbers
    ]
    supported = bool(searchable.strip()) and not missing_relations and not unmatched_ids and not unsupported_numbers
    return {
        "sufficient": supported,
        "reason": "supported" if supported else "unsupported_generated_claim",
        "answer_claim_relations": answer_relations,
        "source_claim_relations": source_relations,
        "missing_claim_relations": missing_relations,
        "temporal_coverage_inference_supported": temporal_coverage_inference_supported,
        "unmatched_object_identifiers": unmatched_ids,
        "accepted_question_number_count": len(accepted_question_numbers),
        "unsupported_numbers": unsupported_numbers,
        "identifier_scoped_source_count": len(source_rows),
    }


TEMPORAL_COVERAGE_CORRECTION_VERSION = "infobank-temporal-coverage-correction-v1"


def _format_english_date(value: datetime.date) -> str:
    return f"{value.day} {calendar.month_name[value.month]} {value.year}"


def correct_temporal_coverage_answer(
    question: str,
    answer: str,
    sources: Iterable[Dict[str, Any]],
    answer_support: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Correct only a source-resolvable temporal coverage polarity failure.

    The correction is deliberately unavailable for concrete exclusion claims,
    unsupported numbers, unmatched object identifiers, incomplete date facts,
    or any grounding failure beyond the observed coverage polarity relation.
    """

    if answer_support.get("missing_claim_relations") != ["exclusion"]:
        return None
    if answer_support.get("unsupported_numbers") or answer_support.get("unmatched_object_identifiers"):
        return None
    if _NON_TEMPORAL_EXCLUSION_RE.search(answer or ""):
        return None

    source_list = list(sources)
    _, searchable, _ = _identifier_scoped_source_text(source_list, [])
    resolution = _temporal_coverage_resolution(question, searchable)
    if resolution is None:
        return None

    positive = bool(_POSITIVE_TEMPORAL_COVERAGE_RE.search(answer or ""))
    negative = bool(_NEGATIVE_TEMPORAL_COVERAGE_RE.search(answer or ""))
    expected_matches = positive if resolution["covered"] else negative
    if positive != negative and expected_matches:
        return None

    question_date = _format_english_date(resolution["question_date"])
    purchase_date = _format_english_date(resolution["purchase_date"])
    coverage_end_date = _format_english_date(resolution["coverage_end_date"])
    if resolution["covered"]:
        conclusion = "Yes"
        comparison = "on or before"
        coverage_state = "covered"
    else:
        conclusion = "No"
        comparison = "after"
        coverage_state = "not covered"

    corrected_answer = (
        f"{conclusion}. The purchase date is {purchase_date}. "
        f"The manufacturer warranty period is {resolution['warranty_months']} months from that date, "
        f"ending on {coverage_end_date}. Because {question_date} is {comparison} the warranty end date, "
        f"the product is {coverage_state} on that date."
    )
    corrected_support = answer_source_support(corrected_answer, source_list, question)
    if not corrected_support["sufficient"]:
        return None

    reason = (
        "contradictory_generated_temporal_coverage"
        if positive and negative
        else "mismatched_generated_temporal_coverage"
    )
    return {
        "answer": corrected_answer,
        "answer_source_support": corrected_support,
        "trace": {
            "version": TEMPORAL_COVERAGE_CORRECTION_VERSION,
            "applied": True,
            "reason": reason,
            "source_fact_count": 3,
            "covered": resolution["covered"],
        },
    }
