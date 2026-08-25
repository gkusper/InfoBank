"""Dry-run-first cross-store consistency scanning and fixture-scoped repair."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from typing import Any


SCANNER_VERSION = "infobank-orphan-scanner-v1"
TASK_OWNED_SCOPE = "TASK_OWNED_FIXTURE"


@dataclass
class ConsistencySnapshot:
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    chunks: dict[str, dict[str, Any]] = field(default_factory=dict)
    vectors: dict[str, dict[str, Any]] = field(default_factory=dict)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    staged_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)


def _issue(kind: str, object_id: str, *, repair: str, scope: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "issue_type": kind,
        "object_id": object_id,
        "scope": scope,
        "recommended_repair": repair,
        "details": details or {},
    }


def scan_snapshot(snapshot: ConsistencySnapshot) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for doc_id, doc in sorted(snapshot.documents.items()):
        scope = doc.get("scope", "EXTERNAL_OR_UNKNOWN")
        source = snapshot.sources.get(doc_id)
        if not source:
            issues.append(_issue("DB_DOCUMENT_MISSING_SOURCE", doc_id, repair="RESTORE_SOURCE_FROM_BACKUP", scope=scope))
        elif source.get("sha256") != doc.get("source_sha256"):
            issues.append(_issue("SOURCE_SHA_MISMATCH", doc_id, repair="QUARANTINE_AND_RESTORE_VERIFIED_SOURCE", scope=scope))
        active_vectors = [vector_id for vector_id, vector in snapshot.vectors.items() if vector.get("document_id") == doc_id and vector.get("active", True)]
        if doc.get("source_status") == "ARCHIVED" and active_vectors:
            issues.append(_issue("ARCHIVED_DOCUMENT_ACTIVE_VECTORS", doc_id, repair="DEACTIVATE_DOCUMENT_VECTORS", scope=scope, details={"vector_ids": sorted(active_vectors)}))

    for doc_id, source in sorted(snapshot.sources.items()):
        if doc_id not in snapshot.documents and not source.get("quarantined"):
            issues.append(_issue("SOURCE_DIRECTORY_WITHOUT_DB_DOCUMENT", doc_id, repair="QUARANTINE_SOURCE_DIRECTORY", scope=source.get("scope", "EXTERNAL_OR_UNKNOWN")))

    for chunk_id, chunk in sorted(snapshot.chunks.items()):
        if chunk.get("quarantined"):
            continue
        scope = chunk.get("scope", "EXTERNAL_OR_UNKNOWN")
        if chunk.get("document_id") not in snapshot.documents:
            issues.append(_issue("CHUNK_MISSING_DOCUMENT", chunk_id, repair="QUARANTINE_CHUNK", scope=scope))
        vector_id = chunk.get("vector_id")
        if vector_id not in snapshot.vectors:
            issues.append(_issue("DB_CHUNK_MISSING_VECTOR", chunk_id, repair="RECREATE_VECTOR_FROM_CHUNK", scope=scope, details={"vector_id": vector_id}))

    for vector_id, vector in sorted(snapshot.vectors.items()):
        if vector.get("quarantined") or not vector.get("active", True):
            continue
        scope = vector.get("scope", "EXTERNAL_OR_UNKNOWN")
        if vector.get("document_id") not in snapshot.documents or vector.get("chunk_id") not in snapshot.chunks:
            issues.append(_issue("VECTOR_MISSING_DOCUMENT_OR_CHUNK", vector_id, repair="DEACTIVATE_ORPHAN_VECTOR", scope=scope))

    for staged_id, staged in sorted(snapshot.staged_sources.items()):
        if staged.get("document_deleted") and staged.get("pending_purge"):
            issues.append(_issue("DELETED_DOCUMENT_STAGED_SOURCE_PENDING_PURGE", staged_id, repair="RETAIN_FOR_EXPLICIT_PURGE_OR_RESTORE", scope=staged.get("scope", "EXTERNAL_OR_UNKNOWN")))

    for index, citation in enumerate(snapshot.citations):
        if citation.get("valid") is False:
            continue
        chunk = snapshot.chunks.get(citation.get("chunk_id"))
        citation_id = citation.get("citation_id") or f"citation-{index:04d}"
        scope = citation.get("scope", "EXTERNAL_OR_UNKNOWN")
        if not chunk or chunk.get("document_id") != citation.get("document_id"):
            issues.append(_issue("CROSS_DOCUMENT_CITATION_CHUNK_MISMATCH", citation_id, repair="INVALIDATE_CITATION_LINK", scope=scope))

    return {
        "scanner_version": SCANNER_VERSION,
        "mode": "DRY_RUN",
        "issue_count": len(issues),
        "issues": issues,
        "issue_type_counts": {kind: sum(1 for issue in issues if issue["issue_type"] == kind) for kind in sorted({item["issue_type"] for item in issues})},
    }


def repair_snapshot(snapshot: ConsistencySnapshot, *, apply: bool = False) -> tuple[ConsistencySnapshot, dict[str, Any]]:
    result = copy.deepcopy(snapshot)
    scan = scan_snapshot(result)
    actions: list[dict[str, Any]] = []
    for issue in scan["issues"]:
        allowed = issue["scope"] == TASK_OWNED_SCOPE
        action = {**issue, "applied": False, "reason": "DRY_RUN" if not apply else "NOT_TASK_OWNED"}
        if not apply or not allowed:
            actions.append(action)
            continue
        kind, object_id = issue["issue_type"], issue["object_id"]
        if kind == "ARCHIVED_DOCUMENT_ACTIVE_VECTORS":
            for vector in result.vectors.values():
                if vector.get("document_id") == object_id:
                    vector["active"] = False
        elif kind == "DB_CHUNK_MISSING_VECTOR":
            chunk = result.chunks[object_id]
            vector_id = chunk["vector_id"]
            document = result.documents.get(chunk["document_id"], {})
            result.vectors[vector_id] = {"document_id": chunk["document_id"], "chunk_id": object_id, "active": document.get("source_status") != "ARCHIVED", "scope": TASK_OWNED_SCOPE, "recreated": True}
        elif kind == "VECTOR_MISSING_DOCUMENT_OR_CHUNK":
            result.vectors[object_id]["active"] = False
            result.vectors[object_id]["quarantined"] = True
        elif kind == "SOURCE_DIRECTORY_WITHOUT_DB_DOCUMENT":
            result.sources[object_id]["quarantined"] = True
        elif kind == "CHUNK_MISSING_DOCUMENT":
            result.chunks[object_id]["quarantined"] = True
        elif kind == "CROSS_DOCUMENT_CITATION_CHUNK_MISMATCH":
            for citation in result.citations:
                if citation.get("citation_id") == object_id:
                    citation["valid"] = False
        else:
            action["reason"] = "MANUAL_RESTORE_OR_EXPLICIT_PURGE_REQUIRED"
            actions.append(action)
            continue
        action["applied"] = True
        action["reason"] = "TASK_OWNED_FIXTURE_APPLY"
        actions.append(action)
    return result, {
        "scanner_version": SCANNER_VERSION,
        "mode": "APPLY" if apply else "DRY_RUN",
        "actions": actions,
        "applied_count": sum(1 for item in actions if item["applied"]),
    }


def source_record(payload: bytes, *, scope: str = TASK_OWNED_SCOPE) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(payload).hexdigest(), "byte_size": len(payload), "scope": scope}
