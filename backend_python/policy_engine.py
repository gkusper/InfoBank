"""Purpose-aware governance policy engine for CITDS retrieval.

The engine resolves each candidate source into one of four use decisions:
Full, Aggregate, Metadata, or Deny. It combines explicit policy rules,
document visibility, direct user permissions, and owned evidence-unit policy.
Retrieval and generation must consume only the resulting decision, never raw
caller-provided user_id.
"""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, Iterable

from sqlalchemy.orm import Session

import models
import relevance


TARGET_DOCUMENT = "Document"
TARGET_EVIDENCE_UNIT = "EvidenceUnit"
DEFAULT_DOCUMENT_PURPOSE = "grounded_question_answering"
AUDIT_VIEW_PURPOSE = "audit_view"
QUERY_LIMIT_EXHAUSTED = "QUERY_LIMIT_EXHAUSTED"
EXPLAINABILITY_REQUIRED_UNSATISFIED = "EXPLAINABILITY_REQUIRED_UNSATISFIED"
GRANTABLE_PERMISSION_TYPES = {
    models.PermissionType.Reader,
    models.PermissionType.Aggregate,
    models.PermissionType.Metadata,
    models.PermissionType.Audit,
}


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _mode_value(mode: Any) -> str:
    if hasattr(mode, "value"):
        return mode.value
    return str(mode)


def _is_rule_active(rule: models.PolicyRule, purpose: str) -> bool:
    current = _now()
    if rule.purpose not in {"any", purpose}:
        return False
    if rule.valid_from and rule.valid_from > current:
        return False
    if rule.valid_until and rule.valid_until < current:
        return False
    return True


def _mode_to_use_decision(mode: str) -> str:
    normalized = mode.lower()
    if normalized == "full":
        return relevance.USE_FULL
    if normalized == "aggregate":
        return relevance.USE_AGGREGATE
    if normalized == "metadata":
        return relevance.USE_METADATA
    return relevance.USE_DENY


def _decision_to_role(decision: str) -> str:
    if decision == relevance.USE_FULL:
        return relevance.SOURCE_ROLE_PRIMARY
    if decision == relevance.USE_AGGREGATE:
        return relevance.SOURCE_ROLE_AGGREGATE_ONLY
    if decision == relevance.USE_METADATA:
        return relevance.SOURCE_ROLE_CONTEXTUAL
    return relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED


def _constraint_summary(permission: models.UserDocumentPermission) -> Dict[str, Any]:
    max_queries = getattr(permission, "max_queries", None)
    queries_used = int(getattr(permission, "queries_used", 0) or 0)
    return {
        "max_queries": max_queries,
        "queries_used": queries_used,
        "queries_remaining": None if max_queries is None else max(max_queries - queries_used, 0),
        "requires_explainability": bool(getattr(permission, "requires_explainability", False)),
    }


def _permission_constraint_state(
    permission: models.UserDocumentPermission,
    *,
    require_quota_available: bool = True,
) -> Dict[str, Any]:
    """Return whether query-limited persistent grant capacity remains available."""

    summary = _constraint_summary(permission)
    permission_type = _mode_value(permission.permission_type)
    if permission_type == models.PermissionType.Owner.value:
        return {"active": True, "reason": "owner_relation", "constraints": summary}

    max_queries = getattr(permission, "max_queries", None)
    if require_quota_available and max_queries is not None:
        queries_used = int(getattr(permission, "queries_used", 0) or 0)
        if queries_used >= max_queries:
            return {"active": False, "reason": "persistent_permission_quota_exhausted", "constraints": summary}

    return {"active": True, "reason": "persistent_permission_active", "constraints": summary}


def _permission_to_document_decision(permission_type: str) -> tuple[str, str]:
    if permission_type in {models.PermissionType.Owner.value, models.PermissionType.Reader.value}:
        return relevance.USE_FULL, "direct_permission_full"
    if permission_type == models.PermissionType.Aggregate.value:
        return relevance.USE_AGGREGATE, "direct_permission_aggregate"
    if permission_type == models.PermissionType.Metadata.value:
        return relevance.USE_METADATA, "direct_permission_metadata"
    if permission_type == models.PermissionType.Audit.value:
        return relevance.USE_DENY, "audit_only_no_content_access"
    return relevance.USE_DENY, "direct_permission_unknown"


def _document_visibility_decision(doc: models.Document) -> tuple[str, str]:
    if doc.visibility == "Aggregate":
        return relevance.USE_AGGREGATE, "document_visibility_aggregate"
    if doc.visibility == "Metadata":
        return relevance.USE_METADATA, "document_visibility_metadata"
    return relevance.USE_DENY, "private_no_permission"


def _strongest_active_rule(db: Session, target_type: str, target_id: str, purpose: str) -> models.PolicyRule | None:
    policy_rules = db.query(models.PolicyRule).filter(
        models.PolicyRule.target_type == target_type,
        models.PolicyRule.target_id == target_id,
    ).all()
    active_rules = [rule for rule in policy_rules if _is_rule_active(rule, purpose)]
    if not active_rules:
        return None
    deny_rules = [r for r in active_rules if _mode_value(r.access_mode) == models.PolicyAccessMode.Deny.value]
    if deny_rules:
        return deny_rules[0]
    rank = {"Full": 3, "Aggregate": 2, "Metadata": 1}
    return sorted(active_rules, key=lambda r: rank.get(_mode_value(r.access_mode), 0), reverse=True)[0]


def resolve_document_access(db: Session, user_id: str, doc_id: str, purpose: str = DEFAULT_DOCUMENT_PURPOSE) -> Dict[str, Any]:
    """Resolve one document into a CITDS use decision."""

    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        return {
            "target_id": doc_id,
            "target_type": TARGET_DOCUMENT,
            "use_decision": relevance.USE_DENY,
            "source_role": relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED,
            "reason": "document_not_found",
            "policy_rule_id": None,
            "authorization_path": None,
        }

    if getattr(doc, "source_status", "ACTIVE") == "ARCHIVED":
        return {
            "target_id": doc_id,
            "target_type": TARGET_DOCUMENT,
            "use_decision": relevance.USE_DENY,
            "source_role": relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED,
            "reason": "document_archived",
            "policy_rule_id": None,
            "authorization_path": None,
        }

    rule = _strongest_active_rule(db, TARGET_DOCUMENT, doc_id, purpose)
    if rule:
        decision = _mode_to_use_decision(_mode_value(rule.access_mode))
        return {
            "target_id": doc_id,
            "target_type": TARGET_DOCUMENT,
            "use_decision": decision,
            "source_role": _decision_to_role(decision),
            "reason": f"explicit_policy_{_mode_value(rule.access_mode).lower()}",
            "policy_rule_id": rule.id,
            "authorization_path": "policy_rule",
        }

    permission = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.user_id == user_id,
        models.UserDocumentPermission.document_id == doc_id,
    ).first()
    inactive_permission_state: dict[str, Any] | None = None
    if permission:
        permission_type = _mode_value(permission.permission_type)
        constraint_state = _permission_constraint_state(permission)
        if constraint_state["active"]:
            decision, reason = _permission_to_document_decision(permission_type)
            if decision != relevance.USE_DENY:
                constraints = constraint_state["constraints"]
                return {
                    "target_id": doc_id,
                    "target_type": TARGET_DOCUMENT,
                    "use_decision": decision,
                    "source_role": _decision_to_role(decision),
                    "reason": reason,
                    "policy_rule_id": None,
                    "authorization_path": "persistent_permission",
                    "permission_id": permission.id,
                    "permission_type": permission_type,
                    "permission_constraints": constraints,
                    "quota_limited": constraints["max_queries"] is not None,
                    "requires_explainability": constraints["requires_explainability"],
                }
            inactive_permission_state = constraint_state | {"reason": reason, "permission_type": permission_type}
        else:
            inactive_permission_state = constraint_state | {"permission_type": permission_type}

    decision, reason = _document_visibility_decision(doc)
    result = {
        "target_id": doc_id,
        "target_type": TARGET_DOCUMENT,
        "use_decision": decision,
        "source_role": _decision_to_role(decision),
        "reason": reason,
        "policy_rule_id": None,
        "authorization_path": "document_visibility" if decision != relevance.USE_DENY else None,
    }
    if inactive_permission_state:
        result["inactive_permission_reason"] = inactive_permission_state["reason"]
        result["inactive_permission_type"] = inactive_permission_state.get("permission_type")
        result["inactive_permission_constraints"] = inactive_permission_state.get("constraints")
        if decision == relevance.USE_DENY:
            result["reason"] = inactive_permission_state["reason"]

    return result


def resolve_evidence_unit_access(db: Session, user_id: str, evidence_unit_id: str, purpose: str = "action_reconstruction") -> Dict[str, Any]:
    """Resolve one owned EvidenceUnit into a CITDS use decision."""

    # Policy resolution must not materialize private evidence content before the
    # access decision is known.  Fetch only the ownership fields needed here;
    # callers may load content after this function returns a permitted mode.
    unit = db.query(models.EvidenceUnit.id, models.EvidenceUnit.user_id).filter(
        models.EvidenceUnit.id == evidence_unit_id
    ).first()
    if not unit:
        return {
            "target_id": evidence_unit_id,
            "target_type": TARGET_EVIDENCE_UNIT,
            "use_decision": relevance.USE_DENY,
            "source_role": relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED,
            "reason": "evidence_unit_not_found",
            "policy_rule_id": None,
        }

    rule = _strongest_active_rule(db, TARGET_EVIDENCE_UNIT, evidence_unit_id, purpose)
    if rule:
        decision = _mode_to_use_decision(_mode_value(rule.access_mode))
        return {
            "target_id": evidence_unit_id,
            "target_type": TARGET_EVIDENCE_UNIT,
            "use_decision": decision,
            "source_role": _decision_to_role(decision),
            "reason": f"explicit_policy_{_mode_value(rule.access_mode).lower()}",
            "policy_rule_id": rule.id,
        }

    if unit.user_id == user_id:
        decision = relevance.USE_FULL
        reason = "owned_evidence_full"
    else:
        decision = relevance.USE_DENY
        reason = "evidence_not_owned"

    return {
        "target_id": evidence_unit_id,
        "target_type": TARGET_EVIDENCE_UNIT,
        "use_decision": decision,
        "source_role": _decision_to_role(decision),
        "reason": reason,
        "policy_rule_id": None,
    }


def resolve_document_access_bulk(db: Session, user_id: str, doc_ids: Iterable[str], purpose: str) -> Dict[str, Any]:
    decisions: Dict[str, str] = {}
    roles: Dict[str, str] = {}
    reasons: Dict[str, str] = {}
    policy_rule_ids: Dict[str, str | None] = {}
    authorization_paths: Dict[str, str | None] = {}
    permission_ids: Dict[str, str] = {}
    permission_types: Dict[str, str] = {}
    permission_constraints: Dict[str, Dict[str, Any]] = {}
    inactive_permission_reasons: Dict[str, str] = {}

    for doc_id in sorted(set(doc_ids)):
        resolved = resolve_document_access(db, user_id, doc_id, purpose)
        decisions[doc_id] = resolved["use_decision"]
        roles[doc_id] = resolved["source_role"]
        reasons[doc_id] = resolved["reason"]
        policy_rule_ids[doc_id] = resolved.get("policy_rule_id")
        authorization_paths[doc_id] = resolved.get("authorization_path")
        if resolved.get("permission_id"):
            permission_ids[doc_id] = resolved["permission_id"]
        if resolved.get("permission_type"):
            permission_types[doc_id] = resolved["permission_type"]
        if resolved.get("permission_constraints"):
            permission_constraints[doc_id] = resolved["permission_constraints"]
        if resolved.get("inactive_permission_reason"):
            inactive_permission_reasons[doc_id] = resolved["inactive_permission_reason"]

    usable_doc_ids = [doc_id for doc_id, d in decisions.items() if d in {relevance.USE_FULL, relevance.USE_AGGREGATE, relevance.USE_METADATA}]
    content_doc_ids = [doc_id for doc_id, d in decisions.items() if d in {relevance.USE_FULL, relevance.USE_AGGREGATE}]
    metadata_only_doc_ids = [doc_id for doc_id, d in decisions.items() if d == relevance.USE_METADATA]
    denied_doc_ids = [doc_id for doc_id, d in decisions.items() if d == relevance.USE_DENY]
    quota_limited_doc_ids = [
        doc_id for doc_id in usable_doc_ids
        if permission_constraints.get(doc_id, {}).get("max_queries") is not None
        and authorization_paths.get(doc_id) == "persistent_permission"
    ]
    explainability_required_doc_ids = [
        doc_id for doc_id in usable_doc_ids
        if permission_constraints.get(doc_id, {}).get("requires_explainability") is True
        and authorization_paths.get(doc_id) == "persistent_permission"
    ]

    return {
        "use_decisions": decisions,
        "source_roles": roles,
        "policy_reasons": reasons,
        "policy_rule_ids": policy_rule_ids,
        "authorization_paths": authorization_paths,
        "permission_ids": permission_ids,
        "permission_types": permission_types,
        "permission_constraints": permission_constraints,
        "inactive_permission_reasons": inactive_permission_reasons,
        "quota_limited_doc_ids": quota_limited_doc_ids,
        "explainability_required_doc_ids": explainability_required_doc_ids,
        "usable_doc_ids": usable_doc_ids,
        "content_doc_ids": content_doc_ids,
        "metadata_only_doc_ids": metadata_only_doc_ids,
        "denied_doc_ids": denied_doc_ids,
        "has_primary_evidence": any(roles.get(doc_id) == relevance.SOURCE_ROLE_PRIMARY for doc_id in content_doc_ids),
        "has_aggregate_evidence": any(roles.get(doc_id) == relevance.SOURCE_ROLE_AGGREGATE_ONLY for doc_id in content_doc_ids),
        "has_metadata_only": bool(metadata_only_doc_ids),
    }


def resolve_evidence_unit_access_bulk(db: Session, user_id: str, unit_ids: Iterable[str], purpose: str) -> Dict[str, Any]:
    decisions: Dict[str, str] = {}
    roles: Dict[str, str] = {}
    reasons: Dict[str, str] = {}
    policy_rule_ids: Dict[str, str | None] = {}

    for unit_id in sorted(set(unit_ids)):
        resolved = resolve_evidence_unit_access(db, user_id, unit_id, purpose)
        decisions[unit_id] = resolved["use_decision"]
        roles[unit_id] = resolved["source_role"]
        reasons[unit_id] = resolved["reason"]
        policy_rule_ids[unit_id] = resolved.get("policy_rule_id")

    usable_unit_ids = [uid for uid, d in decisions.items() if d in {relevance.USE_FULL, relevance.USE_AGGREGATE, relevance.USE_METADATA}]
    content_unit_ids = [uid for uid, d in decisions.items() if d in {relevance.USE_FULL, relevance.USE_AGGREGATE}]
    metadata_only_unit_ids = [uid for uid, d in decisions.items() if d == relevance.USE_METADATA]
    denied_unit_ids = [uid for uid, d in decisions.items() if d == relevance.USE_DENY]

    return {
        "use_decisions": decisions,
        "source_roles": roles,
        "policy_reasons": reasons,
        "policy_rule_ids": policy_rule_ids,
        "usable_unit_ids": usable_unit_ids,
        "content_unit_ids": content_unit_ids,
        "metadata_only_unit_ids": metadata_only_unit_ids,
        "denied_unit_ids": denied_unit_ids,
    }


def consume_query_quotas_for_governance(db: Session, governance: dict, request_id: str) -> Dict[str, Any]:
    """Atomically consume one query from each quota-limited grant used by one /api/ask."""

    permission_ids = governance.get("permission_ids") or {}
    permission_types = governance.get("permission_types") or {}
    quota_doc_ids = sorted(set(governance.get("quota_limited_doc_ids") or []))
    consumed: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    seen_permissions: set[str] = set()

    for doc_id in quota_doc_ids:
        permission_id = permission_ids.get(doc_id)
        if not permission_id or permission_id in seen_permissions:
            continue
        seen_permissions.add(permission_id)
        if permission_types.get(doc_id) in {models.PermissionType.Owner.value, models.PermissionType.Audit.value}:
            continue
        rows = db.query(models.UserDocumentPermission).filter(
            models.UserDocumentPermission.id == permission_id,
            models.UserDocumentPermission.max_queries.isnot(None),
            models.UserDocumentPermission.queries_used < models.UserDocumentPermission.max_queries,
        ).update(
            {models.UserDocumentPermission.queries_used: models.UserDocumentPermission.queries_used + 1},
            synchronize_session=False,
        )
        if rows == 1:
            consumed.append({"document_id": doc_id, "permission_id": permission_id})
        else:
            failures.append({"document_id": doc_id, "permission_id": permission_id, "reason": "quota_unavailable"})

    if consumed:
        db.flush()
        db.expire_all()
    return {
        "ok": not failures,
        "request_id": request_id,
        "consumed_count": len(consumed),
        "consumed_permission_ids": [item["permission_id"] for item in consumed],
        "failed_count": len(failures),
        "failures": failures,
        "reason_code": QUERY_LIMIT_EXHAUSTED if failures else None,
    }


def record_document_audit_links(
    db: Session,
    audit_log_id: str,
    document_relations: dict[str, Iterable[str]],
) -> None:
    """Index structured audit-to-document relations for document-scoped audit views."""

    for relation_type, document_ids in sorted((document_relations or {}).items()):
        for document_id in sorted(set(document_ids or [])):
            if not document_id:
                continue
            link_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"infobank:audit-link:{audit_log_id}:{document_id}:{relation_type}",
            ))
            if db.query(models.DocumentAuditLink.id).filter(models.DocumentAuditLink.id == link_id).first():
                continue
            db.add(models.DocumentAuditLink(
                id=link_id,
                audit_log_id=audit_log_id,
                document_id=document_id,
                relation_type=relation_type,
            ))


def document_audit_relations_from_governance(governance: dict, sources: Iterable[dict] | None = None) -> dict[str, list[str]]:
    if (governance or {}).get("source_type") == "evidence_units":
        return {}
    relations = {
        "content": list(governance.get("content_doc_ids") or []),
        "metadata": list(governance.get("metadata_only_doc_ids") or []),
        "denied": list(governance.get("denied_doc_ids") or []),
    }
    source_ids = [
        source.get("document_id")
        for source in (sources or [])
        if source.get("document_id")
    ]
    if source_ids:
        relations["source"] = source_ids
    return relations


def resolve_document_audit_access(
    db: Session,
    user_id: str,
    doc_id: str,
) -> Dict[str, Any]:
    """Resolve access to document-scoped audit records without granting content access."""

    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        return {"allowed": False, "reason": "document_not_found", "document_id": doc_id}

    owner = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.user_id == user_id,
        models.UserDocumentPermission.document_id == doc_id,
        models.UserDocumentPermission.permission_type == models.PermissionType.Owner,
    ).first()
    if owner:
        return {
            "allowed": True,
            "reason": "owner_audit_access",
            "document_id": doc_id,
            "authorization_path": "owner_permission",
            "permission_id": owner.id,
        }

    audit_permission = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.user_id == user_id,
        models.UserDocumentPermission.document_id == doc_id,
        models.UserDocumentPermission.permission_type == models.PermissionType.Audit,
    ).first()
    if not audit_permission:
        return {"allowed": False, "reason": "audit_permission_required", "document_id": doc_id}

    constraint_state = _permission_constraint_state(
        audit_permission,
        require_quota_available=False,
    )
    if not constraint_state["active"]:
        return {
            "allowed": False,
            "reason": constraint_state["reason"],
            "document_id": doc_id,
            "permission_id": audit_permission.id,
            "permission_constraints": constraint_state["constraints"],
        }

    return {
        "allowed": True,
        "reason": "direct_permission_audit",
        "document_id": doc_id,
        "authorization_path": "persistent_permission",
        "permission_id": audit_permission.id,
        "permission_constraints": constraint_state["constraints"],
    }


def evaluate_explainability_requirements(
    governance: dict,
    sources: Iterable[dict],
    *,
    aggregate_execution: dict | None = None,
) -> Dict[str, Any]:
    """Check whether explainability-required grants have adequate trace for used sources."""

    required_doc_ids = set(governance.get("explainability_required_doc_ids") or [])
    sources = list(sources or [])
    relevant_sources = [
        source for source in sources
        if source.get("document_id") in required_doc_ids
    ]
    satisfied: list[dict[str, str]] = []
    unsatisfied: list[dict[str, str]] = []

    for source in relevant_sources:
        doc_id = source.get("document_id")
        decision = source.get("use_decision")
        if decision == relevance.USE_FULL:
            citation = source.get("citation") or {}
            if citation.get("available") is True:
                satisfied.append({"document_id": doc_id, "reason": "full_source_citation_available"})
            else:
                unsatisfied.append({
                    "document_id": doc_id,
                    "reason": citation.get("reason") or "full_source_trace_unavailable",
                })
        elif decision == relevance.USE_METADATA:
            satisfied.append({"document_id": doc_id, "reason": "metadata_trace_available"})
        elif decision == relevance.USE_AGGREGATE and aggregate_execution and aggregate_execution.get("output_class") == "AGGREGATE_RESULT":
            satisfied.append({"document_id": doc_id, "reason": "aggregate_execution_trace_available"})
        else:
            unsatisfied.append({"document_id": doc_id, "reason": "source_trace_unavailable"})

    return {
        "required": bool(required_doc_ids),
        "required_doc_count": len(required_doc_ids),
        "used_source_count": len(relevant_sources),
        "satisfied_source_count": len(satisfied),
        "unsatisfied_source_count": len(unsatisfied),
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "ok": not unsatisfied,
        "reason_code": EXPLAINABILITY_REQUIRED_UNSATISFIED if unsatisfied else None,
    }


def public_explainability_state(result: dict) -> dict:
    return {
        "required": bool(result.get("required")),
        "used_source_count": int(result.get("used_source_count") or 0),
        "satisfied_source_count": int(result.get("satisfied_source_count") or 0),
        "unsatisfied_source_count": int(result.get("unsatisfied_source_count") or 0),
        "ok": bool(result.get("ok")),
        "reason_code": result.get("reason_code"),
    }


def public_metadata_summary(db: Session, doc_id: str) -> Dict[str, Any]:
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc:
        return {"document_id": doc_id, "status": "missing"}
    kw_records = db.query(models.Keyword.word).join(models.DocumentKeyword, models.Keyword.id == models.DocumentKeyword.keyword_id).filter(models.DocumentKeyword.document_id == doc_id).all()
    return {
        "document_id": doc.id,
        "file_name": doc.file_path,
        "visibility": doc.visibility,
        "keywords": [row[0] for row in kw_records],
        "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
        "content": "[metadata-only: document content withheld]",
    }


def public_evidence_metadata_summary(db: Session, unit_id: str) -> Dict[str, Any]:
    unit = db.query(models.EvidenceUnit).filter(models.EvidenceUnit.id == unit_id).first()
    if not unit:
        return {"evidence_unit_id": unit_id, "status": "missing"}
    return {
        "evidence_unit_id": unit.id,
        "source_type": unit.source_type.value if hasattr(unit.source_type, "value") else str(unit.source_type),
        "title": unit.title,
        "source_timestamp": unit.source_timestamp.isoformat() if unit.source_timestamp else None,
        "thread_id": unit.thread_id,
        "relation_key": unit.relation_key,
        "metadata": json.loads(unit.metadata_json or "{}"),
        "content": "[metadata-only: evidence content withheld]",
    }


def create_policy_rule(
    db: Session,
    owner_user_id: str,
    target_type: str,
    target_id: str,
    purpose: str,
    access_mode: str,
    valid_from: datetime.datetime | None = None,
    valid_until: datetime.datetime | None = None,
) -> models.PolicyRule:
    import uuid

    mode = models.PolicyAccessMode(access_mode)
    rule = models.PolicyRule(
        id=str(uuid.uuid4()),
        owner_user_id=owner_user_id,
        target_type=target_type,
        target_id=target_id,
        purpose=purpose or "any",
        access_mode=mode,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule




def grant_document_permission(
    db: Session,
    *,
    owner_user_id: str,
    document_id: str,
    target_user_id: str,
    permission_type: models.PermissionType | str,
    max_queries: int | None = None,
    requires_explainability: bool = False,
) -> models.UserDocumentPermission:
    """Create or replace a non-owner persistent document relation."""

    if max_queries is not None and max_queries <= 0:
        raise ValueError("max_queries must be a positive integer")

    owner = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.document_id == document_id,
        models.UserDocumentPermission.user_id == owner_user_id,
        models.UserDocumentPermission.permission_type == models.PermissionType.Owner,
    ).first()
    if not owner:
        raise PermissionError("Only the document Owner may grant persistent access")
    if owner_user_id == target_user_id:
        raise ValueError("The Owner relation cannot be replaced by a grant")
    target = db.query(models.User).filter(models.User.id == target_user_id).first()
    if not target:
        raise LookupError("Target user was not found")
    normalized = permission_type if isinstance(permission_type, models.PermissionType) else models.PermissionType(str(permission_type))
    if normalized not in GRANTABLE_PERMISSION_TYPES:
        raise ValueError("Grant type must be Reader, Aggregate, Metadata, or Audit")
    existing = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.document_id == document_id,
        models.UserDocumentPermission.user_id == target_user_id,
    ).first()
    if existing:
        if existing.permission_type == models.PermissionType.Owner:
            raise ValueError("An Owner relation cannot be overwritten")
        existing.permission_type = normalized
        existing.max_queries = max_queries
        existing.queries_used = 0
        existing.requires_explainability = bool(requires_explainability)
        db.flush()
        return existing
    relation = models.UserDocumentPermission(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:permission:{document_id}:{target_user_id}")),
        document_id=document_id,
        user_id=target_user_id,
        permission_type=normalized,
        max_queries=max_queries,
        queries_used=0,
        requires_explainability=bool(requires_explainability),
    )
    db.add(relation)
    db.flush()
    return relation


def revoke_document_permission(
    db: Session,
    *,
    owner_user_id: str,
    document_id: str,
    target_user_id: str,
) -> bool:
    """Remove a non-owner persistent relation without touching the document."""

    owner = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.document_id == document_id,
        models.UserDocumentPermission.user_id == owner_user_id,
        models.UserDocumentPermission.permission_type == models.PermissionType.Owner,
    ).first()
    if not owner:
        raise PermissionError("Only the document Owner may revoke persistent access")
    relation = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.document_id == document_id,
        models.UserDocumentPermission.user_id == target_user_id,
    ).first()
    if not relation:
        return False
    if relation.permission_type == models.PermissionType.Owner:
        raise ValueError("Ownership must be transferred, not revoked")
    db.delete(relation)
    db.flush()
    return True


def transfer_document_ownership(
    db: Session,
    *,
    owner_user_id: str,
    document_id: str,
    target_user_id: str,
) -> models.UserDocumentPermission:
    """Move the sole Owner relation while preserving document identity."""

    if owner_user_id == target_user_id:
        raise ValueError("Ownership cannot be transferred to the same user")
    current = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.document_id == document_id,
        models.UserDocumentPermission.user_id == owner_user_id,
        models.UserDocumentPermission.permission_type == models.PermissionType.Owner,
    ).first()
    if not current:
        raise PermissionError("Only the current Owner may transfer ownership")
    if not db.query(models.User).filter(models.User.id == target_user_id).first():
        raise LookupError("Target user was not found")
    existing = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.document_id == document_id,
        models.UserDocumentPermission.user_id == target_user_id,
    ).first()
    if existing and existing is not current:
        db.delete(existing)
        db.flush()
    current.user_id = target_user_id
    current.permission_type = models.PermissionType.Owner
    db.flush()
    return current
