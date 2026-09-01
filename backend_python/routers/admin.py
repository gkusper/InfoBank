import hashlib
import datetime as dt
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import policy_engine
import security
from database import get_db

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def serialize_log(log: models.AuditLog):
    parsed_details = None
    if log.details:
        try:
            parsed_details = json.loads(log.details)
        except Exception:
            parsed_details = {"raw": log.details}
    return {
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "target_id": log.target_id,
        "details": parsed_details,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
    }


def _actor_fingerprint(user_id: str | None) -> str | None:
    if not user_id:
        return None
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def _parse_details(log: models.AuditLog) -> dict:
    if not log.details:
        return {}
    try:
        parsed = json.loads(log.details)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _doc_policy_summary(details: dict, doc_id: str) -> dict:
    governance = details.get("governance") or {}
    return {
        "use_decision": (governance.get("use_decisions") or {}).get(doc_id),
        "source_role": (governance.get("source_roles") or {}).get(doc_id),
        "reason": (governance.get("policy_reasons") or {}).get(doc_id),
        "authorization_path": (governance.get("authorization_paths") or {}).get(doc_id),
        "quota_limited": doc_id in set(governance.get("quota_limited_doc_ids") or []),
        "explainability_required": doc_id in set(governance.get("explainability_required_doc_ids") or []),
    }


def serialize_document_audit_log(log: models.AuditLog, doc_id: str, relation_types: list[str]) -> dict:
    details = _parse_details(log)
    summary: dict[str, object] = {
        "status": details.get("status"),
        "output_mode": details.get("output_mode"),
    }
    if log.action == "CHAT_ASK":
        controlled = details.get("controlled_failure") or {}
        summary.update({
            "query_purpose": (details.get("query_profile") or {}).get("purpose"),
            "controlled_failure_status": controlled.get("status"),
            "controlled_failure_reason": controlled.get("reason"),
            "document_policy": _doc_policy_summary(details, doc_id),
            "question_recorded": "question" in details,
            "answer_recorded": "answer" in details,
            "raw_text_redacted": True,
        })
    elif log.action in {"DOCUMENT_PERMISSION_GRANTED", "DOCUMENT_PERMISSION_REVOKED"}:
        target_user_id = details.get("target_user_id")
        summary.update({
            "target_user_fingerprint": _actor_fingerprint(target_user_id),
            "permission_type": details.get("permission_type"),
            "max_queries": details.get("max_queries"),
            "requires_explainability": details.get("requires_explainability"),
            "revoked": details.get("revoked"),
        })
    else:
        summary.update({
            "detail_keys": sorted(details.keys()),
            "raw_details_redacted": True,
        })
    return {
        "id": log.id,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "action": log.action,
        "document_id": doc_id,
        "actor_user_fingerprint": _actor_fingerprint(log.user_id),
        "relation_types": relation_types,
        "summary": {key: value for key, value in summary.items() if value is not None},
    }


@router.get("/documents/{doc_id}/audit")
def get_document_audit_records(
    doc_id: str,
    limit: int = 50,
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    access = policy_engine.resolve_document_audit_access(db, user_id, doc_id)
    if not access.get("allowed"):
        raise HTTPException(status_code=404, detail="Document audit records not found.")

    link_rows = db.query(models.DocumentAuditLink).filter(
        models.DocumentAuditLink.document_id == doc_id,
    ).all()
    relation_types_by_log: dict[str, set[str]] = {}
    for link in link_rows:
        relation_types_by_log.setdefault(link.audit_log_id, set()).add(link.relation_type)

    logs_by_id: dict[str, models.AuditLog] = {}
    if relation_types_by_log:
        for log in db.query(models.AuditLog).filter(models.AuditLog.id.in_(list(relation_types_by_log))).all():
            logs_by_id[log.id] = log
    for log in db.query(models.AuditLog).filter(models.AuditLog.target_id == doc_id).all():
        logs_by_id[log.id] = log
        relation_types_by_log.setdefault(log.id, set()).add("target")

    logs = sorted(
        logs_by_id.values(),
        key=lambda item: item.timestamp or dt.datetime.min,
        reverse=True,
    )[: min(limit, 200)]
    return {
        "status": "success",
        "document_id": doc_id,
        "authorization": {
            "reason": access.get("reason"),
            "authorization_path": access.get("authorization_path"),
        },
        "count": len(logs),
        "logs": [
            serialize_document_audit_log(log, doc_id, sorted(relation_types_by_log.get(log.id, [])))
            for log in logs
        ],
    }


@router.get("/logs")
def get_my_audit_logs(
    action: str | None = None,
    limit: int = 50,
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return the authenticated user's audit logs.

    Earlier prototype code accepted an arbitrary user_id query parameter. CITDS
    governance requires traceability without cross-user log disclosure, so this
    endpoint now scopes logs to the bearer-token user.
    """

    query = db.query(models.AuditLog).filter(models.AuditLog.user_id == user_id)
    if action:
        query = query.filter(models.AuditLog.action == action)
    logs = query.order_by(models.AuditLog.timestamp.desc()).limit(min(limit, 200)).all()
    return {"status": "success", "logs": [serialize_log(log) for log in logs]}


@router.get("/citds-traces")
def get_my_citds_traces(
    limit: int = 25,
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    logs = db.query(models.AuditLog).filter(
        models.AuditLog.user_id == user_id,
        models.AuditLog.action == "CHAT_ASK",
    ).order_by(models.AuditLog.timestamp.desc()).limit(min(limit, 100)).all()

    traces = []
    for log in logs:
        item = serialize_log(log)
        details = item.get("details") or {}
        traces.append({
            "id": item["id"],
            "timestamp": item["timestamp"],
            "question": details.get("question"),
            "answer": details.get("answer"),
            "status": details.get("status"),
            "output_mode": details.get("output_mode"),
            "controlled_failure": details.get("controlled_failure"),
            "query_profile": details.get("query_profile", {}),
            "source_roles": details.get("source_roles", {}),
            "relevance_levels": details.get("relevance_levels", {}),
            "governance": details.get("governance", {}),
            "evidence_check": details.get("evidence_check", {}),
        })
    return {"status": "success", "traces": traces}


@router.get("/citds-coverage")
def get_my_citds_coverage(
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    logs = db.query(models.AuditLog).filter(
        models.AuditLog.user_id == user_id,
        models.AuditLog.action == "CHAT_ASK",
    ).all()

    coverage = {
        "lexical": False,
        "semantic": False,
        "ontological": False,
        "pragmatic": False,
        "genre": False,
        "perlocutionary": False,
        "temporal_status": False,
        "governance": False,
        "evidential": False,
        "primary": False,
        "aggregate_only": False,
        "metadata_only": False,
        "contrastive": False,
        "controlled_failure": False,
        "controlled_failure_object": False,
        "output_mode_selection": False,
    }

    for log in logs:
        try:
            details = json.loads(log.details or "{}")
        except Exception:
            continue
        levels = details.get("relevance_levels", {}) or {}
        for key in ["lexical", "semantic", "ontological", "pragmatic", "genre", "perlocutionary", "temporal_status", "governance", "evidential"]:
            if float(levels.get(key, 0) or 0) > 0:
                coverage[key] = True
        roles = details.get("source_roles", {}) or {}
        if roles.get("primary", 0) > 0:
            coverage["primary"] = True
        if roles.get("aggregate-only", 0) > 0:
            coverage["aggregate_only"] = True
        if roles.get("contrastive", 0) > 0:
            coverage["contrastive"] = True
        governance = details.get("governance", {}) or {}
        if governance.get("metadata_only_doc_ids"):
            coverage["metadata_only"] = True
        if details.get("status") in {"not_found", "rejected", "metadata_only"}:
            coverage["controlled_failure"] = True
        if details.get("controlled_failure"):
            coverage["controlled_failure_object"] = True
        if details.get("output_mode"):
            coverage["output_mode_selection"] = True

    passed = sum(1 for v in coverage.values() if v)
    return {
        "status": "success",
        "coverage": coverage,
        "summary": {
            "passed": passed,
            "total": len(coverage),
            "score": round(passed / max(1, len(coverage)), 3),
        },
    }
