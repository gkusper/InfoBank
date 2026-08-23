import uuid
import json
import os
import re
from fastapi import APIRouter, Depends, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import models
import ai_service
import relevance
import evidence_service
import owned_object_context
import security
import policy_engine
import controlled_failure
import citation_service
from document_processing import sha256_text
from ai_provider import keyword_provider_error_fallback
from aggregate_executor import (
    AggregateConfig,
    AggregateContribution,
    execute_aggregate,
    extract_unambiguous_numeric_value,
)
from routing import RoutingDecision, RoutingMode, route_documents, runtime_routing_mode
from database import get_db

router = APIRouter(prefix="/api", tags=["Chat"])


def log_chat_event(db: Session, user_id: str, question: str, answer: str, keywords: list, sources: list, status: str, query_profile: dict = None, governance: dict = None, evidence_check: dict = None, controlled_failure_obj: dict = None, output_mode: str = None, audit_id: str | None = None):
    details = json.dumps({
        "question": question,
        "answer": answer,
        "extracted_keywords": keywords,
        "query_profile": query_profile or {},
        "source_roles": relevance.summarize_source_roles(sources) if sources else {},
        "relevance_levels": relevance.summarize_relevance_levels(sources) if sources else {},
        "sources_used": [s.get("file_name") for s in sources] if sources else [],
        "governance": governance or {},
        "evidence_check": evidence_check or {},
        "controlled_failure": controlled_failure_obj,
        "output_mode": output_mode,
        "status": status
    }, ensure_ascii=False)
    log_entry = models.AuditLog(id=audit_id or str(uuid.uuid4()), user_id=user_id, action="CHAT_ASK", details=details)
    db.add(log_entry)
    db.commit()


def get_permitted_fallback_doc_ids(db: Session, user_id: str) -> list[str]:
    direct_records = db.query(models.UserDocumentPermission.document_id).join(
        models.Document, models.Document.id == models.UserDocumentPermission.document_id
    ).filter(
        models.UserDocumentPermission.user_id == user_id,
        models.Document.source_status == "ACTIVE",
    ).all()
    direct_doc_ids = [r[0] for r in direct_records]
    public_records = db.query(models.Document.id).filter(
        models.Document.visibility.in_(["Aggregate", "Metadata"]),
        models.Document.source_status == "ACTIVE",
    ).all()
    public_doc_ids = [r[0] for r in public_records]
    return sorted(set(direct_doc_ids + public_doc_ids))


def get_governance_scope_doc_ids(db: Session) -> list[str]:
    """Return identifiers for internal policy resolution, never public routing.

    Policy must run before routing so revoked, archived, expired, purpose-bound,
    and explicit-Deny sources remain distinguishable from a genuine no-match.
    The resulting denied identifiers are kept in the privileged audit trace and
    are removed from the public response by ``_public_governance_context``.
    """

    return sorted(row[0] for row in db.query(models.Document.id).all())


def _full_permitted_document_contents(
    db: Session,
    governance: dict,
) -> list[owned_object_context.PermittedDocumentContent]:
    """Load only content the policy engine marked FULL for this request."""

    full_doc_ids = sorted(
        doc_id
        for doc_id, use_decision in (governance.get("use_decisions") or {}).items()
        if use_decision == relevance.USE_FULL
    )
    if not full_doc_ids:
        return []
    rows = db.query(
        models.DocumentChunk.document_id,
        models.DocumentChunk.text_content,
    ).filter(
        models.DocumentChunk.document_id.in_(full_doc_ids),
    ).order_by(
        models.DocumentChunk.document_id,
        models.DocumentChunk.chunk_index,
        models.DocumentChunk.id,
    ).all()
    text_by_document = {doc_id: [] for doc_id in full_doc_ids}
    for doc_id, text_content in rows:
        text_by_document.setdefault(doc_id, []).append(text_content or "")
    return [
        owned_object_context.PermittedDocumentContent(doc_id, "\n".join(text_by_document[doc_id]))
        for doc_id in full_doc_ids
        if text_by_document.get(doc_id)
    ]


def _routing_decision_in_governed_scope(
    scoped_decision: RoutingDecision,
    governed_document_ids: list[str],
) -> RoutingDecision:
    """Preserve full governed counts after a content-derived scope reduction."""

    governed = tuple(sorted(set(governed_document_ids)))
    candidate_set = set(scoped_decision.candidate_document_ids)
    return RoutingDecision(
        mode=scoped_decision.mode,
        candidate_document_ids=scoped_decision.candidate_document_ids,
        excluded_document_ids=tuple(doc_id for doc_id in governed if doc_id not in candidate_set),
        selected_keywords=scoped_decision.selected_keywords,
        matched_keywords=scoped_decision.matched_keywords,
        fallback_used=scoped_decision.fallback_used,
        fallback_reason=scoped_decision.fallback_reason,
        governed_input_count=len(governed),
        candidate_set_size=len(scoped_decision.candidate_document_ids),
        config_version=scoped_decision.config_version,
        config_hash=scoped_decision.config_hash,
    )


def _public_routing_trace(trace: dict | None) -> dict:
    trace = trace or {}
    return {
        key: trace[key]
        for key in (
            "mode",
            "candidate_set_size",
            "governed_input_count",
            "fallback_used",
            "fallback_reason",
            "selected_keywords",
            "matched_keywords",
            "config_version",
            "config_hash",
        )
        if key in trace
    }


def _public_keyword_selection_trace(trace: dict | None) -> dict:
    trace = trace or {}
    return {
        key: trace[key]
        for key in (
            "provider",
            "adapter",
            "prompt_version",
            "available_keyword_count",
            "parsed_item_count",
            "selected_keyword_count",
            "rejected_item_count",
            "selection_strategy_version",
            "provider_outcome",
            "provider_selected_keyword_count",
            "deterministic_match_count",
            "outcome",
        )
        if key in trace
    }


def _public_query_profile(query_profile: dict | None) -> dict:
    public = dict(query_profile or {})
    if "routing_trace" in public:
        public["routing_trace"] = _public_routing_trace(public.get("routing_trace"))
    if "keyword_selection_trace" in public:
        public["keyword_selection_trace"] = _public_keyword_selection_trace(
            public.get("keyword_selection_trace")
        )
    return public


def _public_governance_context(governance: dict | None) -> dict:
    governance = governance or {}
    policy_state = controlled_failure.safe_policy_state(governance)
    policy_state.pop("denied_source_count", None)
    public = {
        "policy_enforced": True,
        **policy_state,
    }
    if governance.get("routing_trace"):
        public["routing_trace"] = _public_routing_trace(governance.get("routing_trace"))
    return public


def _public_controlled_failure(cf: dict | None) -> dict | None:
    """Remove privileged denied-source counts from a public failure object."""

    if not cf:
        return cf
    public = dict(cf)
    policy_state = dict(public.get("policyState") or {})
    policy_state.pop("denied_source_count", None)
    public["policyState"] = policy_state
    return public


def _public_evidence_check(evidence_check: dict | None) -> dict:
    public = dict(evidence_check or {})
    if public.get("controlled_failure"):
        public["controlled_failure"] = _public_controlled_failure(public["controlled_failure"])
    return public


def make_generator_safe_chunk(role: str, chunk_text: str, source_profile: dict) -> str:
    if role == relevance.SOURCE_ROLE_AGGREGATE_ONLY:
        return "[Aggregate-only source withheld. Use only the thresholded aggregate executor result.]"
    if role == relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED:
        return "[Governance-excluded source. Content withheld and must not be used.]"
    return chunk_text


def metadata_only_source(db: Session, doc_id: str) -> dict:
    meta = policy_engine.public_metadata_summary(db, doc_id)
    return {
        "document_id": doc_id,
        "file_name": meta.get("file_name", "Unknown document"),
        "role": relevance.SOURCE_ROLE_CONTEXTUAL,
        "use_decision": relevance.USE_METADATA,
        "usable_relevance": {
            "levels": {level: 0.0 for level in relevance.RELEVANCE_LEVELS} | {"governance": 1.0, "evidential": 0.2},
            "role": relevance.SOURCE_ROLE_CONTEXTUAL,
            "base_role": relevance.SOURCE_ROLE_CONTEXTUAL,
            "use_decision": relevance.USE_METADATA,
            "genre": ["metadata"],
            "speech_acts": ["not_applicable"],
            "temporal_status": ["unspecified"],
            "evidence_warnings": ["metadata_only_content_withheld"],
        },
        "text": meta.get("content", "[metadata-only: document content withheld]"),
        "metadata": meta,
        "citation": {"available": False, "reason": "metadata_only_content_withheld"},
    }


def is_browser_history_action_rule_question(question: str) -> bool:
    q = question.lower()
    has_activity_source = "browser history" in q or "activity trace" in q or "browsing" in q
    has_action_target = "action item" in q or "task" in q or "obligation" in q or "todo" in q
    asks_rule = "alone" in q or "by itself" in q or "create" in q or "make" in q
    return has_activity_source and has_action_target and asks_rule


def is_aggregate_statistics_question(question: str) -> bool:
    q = question.lower()
    markers = [
        "average", "mean", "median", "count", "total", "statistics", "statistic",
        "aggregate", "pilot statistics", "approval time", "percentage", "percent", "rate",
    ]
    return any(marker in q for marker in markers)


def prompt_injection_source(doc_id: str, file_name: str, source_profile: dict, citation: dict | None = None) -> dict:
    warnings = source_profile.setdefault("evidence_warnings", [])
    for warning in [controlled_failure.SOURCE_ATTACK_WARNING, controlled_failure.LEAKAGE_WARNING]:
        if warning not in warnings:
            warnings.append(warning)
    source_profile["role"] = relevance.SOURCE_ROLE_CONTEXTUAL
    source_profile["use_decision"] = relevance.USE_FULL
    return {
        "document_id": doc_id,
        "file_name": file_name,
        "role": relevance.SOURCE_ROLE_CONTEXTUAL,
        "use_decision": relevance.USE_FULL,
        "usable_relevance": source_profile,
        "text": "[Source withheld: instruction-like content was detected and was not sent to the generator.]",
        "security": {"prompt_injection_detected": True},
        "citation": citation or {"available": False, "reason": "source_withheld"},
    }


def citation_from_chunk(document: models.Document | None, chunk: models.DocumentChunk | None, use_decision: str) -> dict:
    return citation_service.citation_from_chunk(document, chunk, use_decision)


def _retrieved_chunk_integrity_error(
    *,
    document: models.Document,
    chunk: models.DocumentChunk | None,
    vector_id: str,
    chunk_text: str,
    metadata: dict,
) -> str | None:
    """Return a deterministic reason when SQL and vector state diverge."""

    if chunk is None:
        return "missing_sql_chunk"
    if chunk.vector_id != vector_id:
        return "vector_id_mismatch"
    if not chunk.content_sha256:
        return "missing_sql_content_hash"
    if chunk.text_content != chunk_text or sha256_text(chunk_text) != chunk.content_sha256:
        return "content_hash_mismatch"
    if metadata.get("content_hash") and metadata["content_hash"] != chunk.content_sha256:
        return "vector_metadata_content_hash_mismatch"
    if metadata.get("config_hash") and metadata["config_hash"] != chunk.chunk_config_hash:
        return "vector_metadata_config_hash_mismatch"
    if chunk.source_sha256 and document.source_sha256 and chunk.source_sha256 != document.source_sha256:
        return "sql_source_hash_mismatch"
    if metadata.get("source_sha256") and document.source_sha256 and metadata["source_sha256"] != document.source_sha256:
        return "vector_metadata_source_hash_mismatch"
    return None


def _record_stale_index_rejection(governance_context: dict, doc_id: str, chunk_id: str, reason: str) -> None:
    records = governance_context.setdefault("stale_index_rejections", [])
    record = {"document_id": doc_id, "chunk_id": chunk_id, "reason": reason}
    if record not in records:
        records.append(record)
    governance_context["integrity_reason_code"] = "stale_index_denied"


def query_retrieved_sources(db: Session, question: str, question_vector: list[float], query_profile: dict, governance_context: dict, doc_ids: list[str], n_results: int = 4) -> tuple[list[dict], list[str], list[AggregateContribution]]:
    if not doc_ids:
        return [], [], []
    where_clause = {"document_id": doc_ids[0]} if len(doc_ids) == 1 else {"document_id": {"$in": doc_ids}}
    results = ai_service.collection.query(query_embeddings=[question_vector], n_results=n_results, where=where_clause)
    sources: list[dict] = []
    blocks: list[str] = []
    block_rows: list[tuple[dict, str]] = []
    aggregate_contributions: list[AggregateContribution] = []
    if not results.get('documents') or not results['documents'][0]:
        return sources, blocks, aggregate_contributions

    seen = set()
    result_ids = results.get("ids", [[]])[0]
    for vector_id, chunk_text, meta in zip(result_ids, results['documents'][0], results['metadatas'][0]):
        meta = meta or {}
        doc_id = meta.get("document_id")
        chunk_id = meta.get("chunk_id") or vector_id
        dedupe_key = (doc_id, chunk_id)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        doc_record = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if not doc_record or doc_record.source_status != "ACTIVE":
            continue
        use_decision = governance_context["use_decisions"].get(doc_id, relevance.USE_DENY)
        if use_decision not in {relevance.USE_FULL, relevance.USE_AGGREGATE}:
            continue
        chunk_record = db.query(models.DocumentChunk).filter(
            models.DocumentChunk.id == chunk_id,
            models.DocumentChunk.document_id == doc_id,
        ).first()
        integrity_error = _retrieved_chunk_integrity_error(
            document=doc_record,
            chunk=chunk_record,
            vector_id=vector_id,
            chunk_text=chunk_text,
            metadata=meta,
        )
        if integrity_error:
            _record_stale_index_rejection(governance_context, doc_id, chunk_id, integrity_error)
            continue
        # Use the SQL-backed canonical text after the cross-store integrity gate.
        chunk_text = chunk_record.text_content
        file_name = (doc_record.original_filename or doc_record.file_path) if doc_record else "Unknown document"
        base_role = governance_context["source_roles"].get(doc_id, relevance.SOURCE_ROLE_CONTEXTUAL)
        source_profile = relevance.classify_chunk_profile(
            question=question,
            chunk_text=chunk_text,
            file_name=file_name,
            query_profile=query_profile,
            base_role=base_role,
            use_decision=use_decision,
        )
        citation = citation_from_chunk(doc_record, chunk_record, use_decision)
        if citation.get("available"):
            citation["evidence_role"] = source_profile["role"]
        if controlled_failure.detect_prompt_injection(chunk_text).get("detected"):
            sources.append(prompt_injection_source(doc_id, file_name, source_profile, citation))
            continue
        role = source_profile["role"]
        safe_chunk_text = make_generator_safe_chunk(role, chunk_text, source_profile)
        if role == relevance.SOURCE_ROLE_AGGREGATE_ONLY:
            numeric_value = extract_unambiguous_numeric_value(chunk_text)
            if numeric_value is not None:
                aggregate_contributions.append(
                    AggregateContribution(source_id=doc_id, contributor_id=doc_id, value=numeric_value)
                )
        else:
            block = relevance.make_context_block(source_profile, file_name, safe_chunk_text)
        source = {
            "document_id": doc_id,
            "file_name": file_name,
            "role": role,
            "use_decision": use_decision,
            "usable_relevance": source_profile,
            "text": relevance.public_source_text(role, chunk_text),
            "citation": citation,
        }
        sources.append(source)
        if role != relevance.SOURCE_ROLE_AGGREGATE_ONLY:
            block_rows.append((source, block))

    selected_sources, source_selection_trace = evidence_service.select_minimal_evidence_sources(
        question,
        sources,
    )
    query_profile["source_selection_trace"] = source_selection_trace
    selected_source_objects = {id(source) for source in selected_sources}
    blocks = [block for source, block in block_rows if id(source) in selected_source_objects]
    sources = selected_sources
    return sources, blocks, aggregate_contributions


def aggregate_config_from_environment() -> AggregateConfig:
    raw = os.getenv("AGGREGATE_K_THRESHOLD", "3")
    try:
        threshold = int(raw)
    except ValueError as exc:
        raise RuntimeError("AGGREGATE_K_THRESHOLD must be an integer of at least 2") from exc
    return AggregateConfig(k_threshold=threshold)


def chat_success_payload(question, question_keywords, query_profile, governance_context, role_summary, relevance_level_summary, evidence_check, answer, sources_list, controlled_failure_obj=None, output_mode="full_answer", audit_id=None):
    return {
        "status": "success",
        "question": question,
        "extracted_keywords": question_keywords,
        "query_profile": _public_query_profile(query_profile),
        "governance": _public_governance_context(governance_context),
        "source_role_summary": role_summary,
        "relevance_level_summary": relevance_level_summary,
        "evidence_check": _public_evidence_check(evidence_check),
        "controlled_failure": _public_controlled_failure(controlled_failure_obj),
        "output_mode": output_mode,
        "audit_id": audit_id,
        "searched_documents_count": len(governance_context.get("usable_doc_ids", [])),
        "answer": answer,
        "sources": sources_list,
    }


def controlled_failure_payload(message: str, query_profile: dict, governance_context: dict, evidence_check: dict, cf: dict, sources_list: list | None = None, audit_id: str | None = None) -> dict:
    public_cf = _public_controlled_failure(cf) or {}
    return {
        "status": "controlled_failure",
        "message": message,
        "answer": message,
        "query_profile": _public_query_profile(query_profile),
        "governance": _public_governance_context(governance_context),
        "evidence_check": _public_evidence_check(evidence_check),
        "controlled_failure": public_cf,
        "output_mode": public_cf.get("status"),
        "audit_id": audit_id,
        "sources": sources_list or [],
    }


def _action_source_profile(unit: dict) -> dict:
    role = unit.get("role", relevance.SOURCE_ROLE_CONTEXTUAL)
    evidential = {
        relevance.SOURCE_ROLE_PRIMARY: 1.0,
        relevance.SOURCE_ROLE_CONTRASTIVE: 0.85,
        relevance.SOURCE_ROLE_CONTEXTUAL: 0.45,
    }.get(role, 0.0)
    return {
        "levels": {
            level: (
                1.0 if level in {"semantic", "ontological", "pragmatic", "genre", "governance"}
                else evidential if level == "evidential"
                else 0.8 if level == "lexical" and role == relevance.SOURCE_ROLE_PRIMARY
                else 0.5 if level == "perlocutionary" and role != relevance.SOURCE_ROLE_CONTEXTUAL
                else 0.2 if level == "temporal_status" and not unit.get("due")
                else 1.0 if level == "temporal_status"
                else 0.3
            )
            for level in relevance.RELEVANCE_LEVELS
        },
        "role": role,
        "base_role": unit.get("citds_source_role", role),
        "use_decision": unit.get("policy", {}).get("use_decision", relevance.USE_FULL),
        "genre": unit.get("classifier", {}).get("genre") or unit.get("signals", {}).get("genre") or ["evidence_unit"],
        "speech_acts": unit.get("classifier", {}).get("speech_acts") or unit.get("signals", {}).get("primary") or ["informative"],
        "temporal_status": unit.get("classifier", {}).get("temporal_status") or unit.get("signals", {}).get("temporal_status") or ["unspecified"],
        "evidence_warnings": unit.get("classifier", {}).get("warnings", []),
    }


def _action_sources(units: list[dict]) -> list[dict]:
    return [
        {
            "document_id": unit["id"],
            "file_name": f"{unit.get('source_type') or 'Evidence'} · {unit.get('title') or 'Untitled'}",
            "role": unit.get("role", relevance.SOURCE_ROLE_CONTEXTUAL),
            "use_decision": unit.get("policy", {}).get("use_decision", relevance.USE_FULL),
            "usable_relevance": _action_source_profile(unit),
            "text": unit.get("content_summary") or "[evidence content unavailable]",
            "citation": {"available": False, "reason": "evidence_unit_not_document_page"},
        }
        for unit in units
    ]


def _is_hungarian_question(question: str) -> bool:
    lowered = question.casefold()
    return bool(re.search(r"[áéíóöőúüű]", lowered)) or any(
        marker in lowered.split()
        for marker in {"mi", "milyen", "melyik", "mennyi", "teendő", "feladat", "tennivaló"}
    )


def _safe_document_display_name(document: models.Document) -> str:
    original = (document.original_filename or "").strip()
    if original:
        return original
    normalized_path = (document.file_path or "").replace("\\", "/")
    return normalized_path.rsplit("/", 1)[-1] or "Untitled document"


def _permission_value(permission: models.UserDocumentPermission) -> str:
    value = permission.permission_type
    return value.value if hasattr(value, "value") else str(value)


def _document_inventory_rows(db: Session, user_id: str) -> list[dict]:
    """Return only documents explicitly related to the current account.

    The inventory is metadata administration, not content retrieval.  It uses
    the same direct account relations as ``GET /api/documents/me`` and never
    enumerates unrelated public, denied, or other-user documents.
    """

    rows = db.query(models.Document, models.UserDocumentPermission).join(
        models.UserDocumentPermission,
        models.UserDocumentPermission.document_id == models.Document.id,
    ).filter(
        models.UserDocumentPermission.user_id == user_id,
    ).all()
    permission_rank = {"Owner": 4, "Reader": 3, "Aggregate": 2, "Metadata": 1}
    by_document: dict[str, dict] = {}
    for document, permission in rows:
        permission_value = _permission_value(permission)
        candidate = {
            "document_id": document.id,
            "file_name": _safe_document_display_name(document),
            "permission": permission_value,
            "is_owner": permission_value == models.PermissionType.Owner.value,
            "upload_date": document.upload_date.isoformat() if document.upload_date else None,
            "source_status": document.source_status or "UNKNOWN",
            "processing_status": document.processing_status or "UNKNOWN",
            "page_count": document.page_count,
        }
        previous = by_document.get(document.id)
        if previous is None or permission_rank.get(permission_value, 0) > permission_rank.get(previous["permission"], 0):
            by_document[document.id] = candidate
    return sorted(by_document.values(), key=lambda row: (row["file_name"].casefold(), row["document_id"]))


def _document_inventory_sources(rows: list[dict]) -> list[dict]:
    sources = []
    for row in rows:
        source_profile = {
            "levels": {level: 0.0 for level in relevance.RELEVANCE_LEVELS}
            | {"lexical": 1.0, "semantic": 1.0, "governance": 1.0, "evidential": 1.0},
            "role": relevance.SOURCE_ROLE_CONTEXTUAL,
            "base_role": relevance.SOURCE_ROLE_CONTEXTUAL,
            "use_decision": relevance.USE_METADATA,
            "genre": ["metadata"],
            "speech_acts": ["not_applicable"],
            "temporal_status": ["current" if row["source_status"] == "ACTIVE" else "inactive"],
            "evidence_warnings": ["document_content_not_queried"],
        }
        sources.append({
            "document_id": row["document_id"],
            "file_name": row["file_name"],
            "role": relevance.SOURCE_ROLE_CONTEXTUAL,
            "use_decision": relevance.USE_METADATA,
            "usable_relevance": source_profile,
            "text": "[Authorized document metadata; document content was not queried.]",
            "metadata": {
                "permission": row["permission"],
                "is_owner": row["is_owner"],
                "upload_date": row["upload_date"],
                "source_status": row["source_status"],
                "processing_status": row["processing_status"],
                "page_count": row["page_count"],
            },
            "citation": {"available": False, "reason": "document_inventory_metadata"},
        })
    return sources


def _format_document_inventory_answer(question: str, rows: list[dict]) -> str:
    hungarian = _is_hungarian_question(question)
    if not rows:
        return (
            "Jelenleg nincs a fiókodhoz rendelt feltöltött dokumentum."
            if hungarian
            else "There are currently no uploaded documents assigned to your account."
        )
    rendered = []
    for index, row in enumerate(rows, start=1):
        status = f"{row['source_status']} / {row['processing_status']}"
        rendered.append(f"{index}. {row['file_name']} — {row['permission']}; {status}")
    lead = (
        f"A fiókodhoz {len(rows)} feltöltött dokumentum van rendelve:"
        if hungarian
        else f"Your account has {len(rows)} uploaded document(s) assigned to it:"
    )
    return lead + "\n" + "\n".join(rendered)


def document_inventory_chat_result(
    db: Session,
    user_id: str,
    question: str,
    query_profile: dict,
    audit_id: str,
) -> tuple[dict, dict, list[dict], str]:
    rows = _document_inventory_rows(db, user_id)
    sources = _document_inventory_sources(rows)
    document_ids = [row["document_id"] for row in rows]
    query_profile["retrieval_strategy"] = "authorized_document_metadata_inventory"
    query_profile["provider_called"] = False
    query_profile["inventory_scope"] = "direct_account_permissions"
    governance = {
        "use_decisions": {document_id: relevance.USE_METADATA for document_id in document_ids},
        "source_roles": {document_id: relevance.SOURCE_ROLE_CONTEXTUAL for document_id in document_ids},
        "usable_doc_ids": document_ids,
        "content_doc_ids": [],
        "metadata_only_doc_ids": document_ids,
        "denied_doc_ids": [],
        "has_metadata_only": bool(document_ids),
    }
    answer = _format_document_inventory_answer(question, rows)
    evidence_check = {
        "decision": "metadata_answer_allowed",
        "output_mode": controlled_failure.STATUS_METADATA_ONLY_ANSWER,
        "generator_called": False,
        "counts": {
            "documents": len(rows),
            "owned": sum(1 for row in rows if row["is_owner"]),
            "shared": sum(1 for row in rows if not row["is_owner"]),
        },
    }
    return (
        chat_success_payload(
            question,
            query_profile.get("lexical_terms", []),
            query_profile,
            governance,
            relevance.summarize_source_roles(sources),
            relevance.summarize_relevance_levels(sources),
            evidence_check,
            answer,
            sources,
            None,
            controlled_failure.STATUS_METADATA_ONLY_ANSWER,
            audit_id,
        ),
        governance,
        sources,
        answer,
    )


def _format_action_answer(question: str, reconstruction: dict) -> str:
    open_items = reconstruction.get("open_items", [])
    closed_items = reconstruction.get("closed_items", [])
    contextual_only = reconstruction.get("contextual_only", [])
    hungarian = _is_hungarian_question(question)
    if not open_items:
        if hungarian:
            answer = "Nem találtam elsődleges bizonyítékkal alátámasztott nyitott teendőt."
            if contextual_only:
                answer += " Van kontextuális vagy böngészési előzmény, de ez önmagában nem hozhat létre teendőt."
            if closed_items:
                answer += " Néhány jelölt teendő már lezárt vagy visszavont állapotú."
            return answer
        answer = "I found no open action items supported by primary evidence."
        if contextual_only:
            answer += " Contextual or browser-history evidence exists, but it cannot create an action item by itself."
        if closed_items:
            answer += " Some candidate items are already closed or cancelled."
        return answer

    rendered = []
    for index, item in enumerate(open_items, start=1):
        text = f"({index}) {item.get('action') or ('Nincs megadott teendő' if hungarian else 'Unspecified action')}"
        if item.get("object") and item["object"] not in text:
            text += f" ({item['object']})"
        if item.get("due"):
            text += f" — határidő: {item['due']}" if hungarian else f" by {item['due']}"
        rendered.append(text)
    if hungarian:
        return f"A jelenlegi teendőlistád {len(open_items)} nyitott elemet tartalmaz: " + "; ".join(rendered) + "."
    return f"Your current action list contains {len(open_items)} open item(s): " + "; ".join(rendered) + "."


def action_list_chat_result(db: Session, user_id: str, question: str, query_profile: dict, audit_id: str) -> tuple[dict, dict, list[dict], str, dict | None]:
    reconstruction = evidence_service.reconstruct_action_list(db, user_id)
    units = reconstruction.get("classified_units", [])
    sources = _action_sources(units)
    policy = reconstruction.get("policy", {})
    governance = {
        "source_type": "evidence_units",
        "usable_doc_ids": policy.get("usable_unit_ids", []),
        "content_doc_ids": policy.get("content_unit_ids", []),
        "metadata_only_doc_ids": policy.get("metadata_only_unit_ids", []),
        "denied_doc_ids": [],
        "has_primary_evidence": any(source.get("role") == relevance.SOURCE_ROLE_PRIMARY for source in sources),
    }
    query_profile["retrieval_strategy"] = "evidence_reconstruction"
    answer = _format_action_answer(question, reconstruction)
    role_summary = relevance.summarize_source_roles(sources)
    level_summary = relevance.summarize_relevance_levels(sources)
    open_count = len(reconstruction.get("open_items", []))
    if open_count:
        output_mode = controlled_failure.STATUS_FULL_ANSWER
        cf = None
        decision = "answer_allowed"
    else:
        has_non_action_evidence = bool(
            reconstruction.get("closed_items")
            or reconstruction.get("contextual_only")
            or reconstruction.get("metadata_only")
        )
        output_mode = controlled_failure.STATUS_RESTRICTED_ANSWER if has_non_action_evidence else controlled_failure.STATUS_ABSTAIN
        cf = controlled_failure.make_controlled_failure(
            output_mode,
            controlled_failure.REASON_EVIDENTIAL,
            controlled_failure.evidence_state(sources, query_profile, bool(sources)),
            controlled_failure.safe_policy_state(governance),
            answer,
            ["Add or connect primary request, assignment, calendar-obligation, or user-commitment evidence."],
            {"gate": "action_evidence_reconstruction", "open_item_count": 0},
        )
        decision = "controlled_failure"
    evidence_check = {
        "decision": decision,
        "counts": reconstruction.get("counts", {}),
        "output_mode": output_mode,
        "controlled_failure": cf,
    }
    payload = (
        chat_success_payload(
            question, query_profile.get("lexical_terms", []), query_profile, governance,
            role_summary, level_summary, evidence_check, answer, sources, cf, output_mode, audit_id,
        )
        if sources or open_count
        else controlled_failure_payload(answer, query_profile, {}, evidence_check, cf or {}, [], audit_id)
    )
    return payload, governance, sources, answer, cf


@router.post("/controlled-failure/feedback")
async def controlled_failure_feedback(
    controlled_failure_status: str = Form(...),
    feedback: str = Form(...),
    question: str = Form(""),
    expected_output_mode: str = Form(""),
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    details = json.dumps({
        "question": question,
        "controlled_failure_status": controlled_failure_status,
        "expected_output_mode": expected_output_mode,
        "feedback": feedback[:2000],
    }, ensure_ascii=False)
    log_entry = models.AuditLog(id=str(uuid.uuid4()), user_id=user_id, action="CONTROLLED_FAILURE_FEEDBACK", details=details)
    db.add(log_entry)
    db.commit()
    return {"status": "success", "message": "Feedback recorded for controlled-failure review."}


@router.post("/ask")
async def ask_infobank(
    background_tasks: BackgroundTasks,
    question: str = Form(...),
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    audit_id = str(uuid.uuid4())
    query_profile = relevance.build_query_profile(question, [])
    governance_context = {}
    evidence_check = {}

    try:
        pre_gate = controlled_failure.select_pre_generation_output_mode(question, query_profile)
        if pre_gate.get("decision") == "controlled_failure":
            cf = pre_gate["controlled_failure"]
            msg = cf.get("safeOutput") or "The request cannot be answered safely."
            evidence_check = {"decision": "controlled_failure", "controlled_failure": cf, "output_mode": cf["status"], "output_gate": pre_gate.get("trace", {})}
            log_chat_event(db, user_id, question, msg, [], [], cf["status"], query_profile, {}, evidence_check, cf, cf["status"], audit_id)
            return controlled_failure_payload(msg, query_profile, {}, evidence_check, cf, audit_id=audit_id)

        if query_profile.get("task_intent") == "current_action_list":
            payload, governance_context, sources_list, answer, cf = action_list_chat_result(
                db, user_id, question, query_profile, audit_id
            )
            output_mode = payload.get("output_mode")
            evidence_check = payload.get("evidence_check", {})
            log_chat_event(
                db, user_id, question, answer,
                query_profile.get("lexical_terms", []), sources_list,
                "action_reconstruction", query_profile, governance_context,
                evidence_check, cf, output_mode, audit_id,
            )
            return payload

        if query_profile.get("task_intent") == "document_inventory":
            payload, governance_context, sources_list, answer = document_inventory_chat_result(
                db, user_id, question, query_profile, audit_id
            )
            evidence_check = payload.get("evidence_check", {})
            log_chat_event(
                db,
                user_id,
                question,
                answer,
                query_profile.get("lexical_terms", []),
                sources_list,
                "document_inventory",
                query_profile,
                governance_context,
                evidence_check,
                None,
                controlled_failure.STATUS_METADATA_ONLY_ANSWER,
                audit_id,
            )
            return payload

        routing_scope_doc_ids = get_governance_scope_doc_ids(db)
        pre_routing_governance = policy_engine.resolve_document_access_bulk(
            db=db,
            user_id=user_id,
            doc_ids=routing_scope_doc_ids,
            purpose=query_profile.get("purpose", "grounded_question_answering"),
        )
        permitted_doc_ids = pre_routing_governance["usable_doc_ids"]
        if not permitted_doc_ids:
            output_gate = controlled_failure.select_rag_output_mode(
                question=question,
                sources=[],
                query_profile=query_profile,
                governance=pre_routing_governance,
                context_blocks_available=False,
            )
            cf = output_gate["controlled_failure"]
            msg = cf["safeOutput"]
            evidence_check = {"decision": "controlled_failure", "controlled_failure": cf, "output_mode": cf["status"]}
            log_chat_event(db, user_id, question, msg, [], [], "rejected", query_profile, pre_routing_governance, evidence_check, cf, cf["status"], audit_id)
            return controlled_failure_payload(msg, query_profile, pre_routing_governance, evidence_check, cf, audit_id=audit_id)

        owned_object_resolution = owned_object_context.resolve_owned_object_context(
            question,
            _full_permitted_document_contents(db, pre_routing_governance),
        )
        owned_object_trace = owned_object_resolution.public_trace()
        query_profile["owned_object_resolution_trace"] = owned_object_trace
        if owned_object_resolution.status == owned_object_context.STATUS_CLARIFICATION_REQUIRED:
            if owned_object_resolution.reason == "multiple_purchase_evidenced_objects":
                msg = (
                    "I found more than one permitted product with purchase evidence. "
                    "Please name the product or object you mean."
                )
            elif owned_object_resolution.reason.startswith("explicit_"):
                msg = (
                    "I could not uniquely match the requested product or object to the permitted documents. "
                    "Please check its product code or name the object more precisely."
                )
            else:
                msg = (
                    "I could not determine a unique owned object from the permitted purchase evidence. "
                    "Please name the product or provide a permitted receipt or purchase record."
                )
            cf = controlled_failure.make_controlled_failure(
                controlled_failure.STATUS_ASK_CLARIFICATION,
                controlled_failure.REASON_EPISTEMIC,
                controlled_failure.evidence_state([], query_profile, False),
                controlled_failure.safe_policy_state(pre_routing_governance),
                msg,
                ["Name the product, object type, or exact product code and try again."],
                {"gate": "owned_object_resolution", **owned_object_trace},
            )
            evidence_check = {
                "decision": "controlled_failure",
                "controlled_failure": cf,
                "output_mode": cf["status"],
            }
            log_chat_event(
                db, user_id, question, msg, [], [], "owned_object_clarification",
                query_profile, pre_routing_governance, evidence_check, cf, cf["status"], audit_id,
            )
            return controlled_failure_payload(
                msg, query_profile, pre_routing_governance, evidence_check, cf, audit_id=audit_id,
            )

        routing_input_doc_ids = (
            list(owned_object_resolution.candidate_document_ids)
            if owned_object_resolution.status == owned_object_context.STATUS_RESOLVED
            else list(permitted_doc_ids)
        )

        configured_routing_mode = runtime_routing_mode()
        document_keywords: dict[str, list[str]] = {}
        if configured_routing_mode == RoutingMode.ROUTING_OFF:
            question_keywords = []
            keyword_selection_trace = {
                "provider": "not_called",
                "adapter": "routing_off",
                "prompt_version": "not_applicable",
                "available_keyword_count": 0,
                "parsed_item_count": 0,
                "selected_keyword_count": 0,
                "rejected_item_count": 0,
                "selection_strategy_version": "infocom-keyword-selector-v2",
                "provider_outcome": "not_called",
                "provider_selected_keyword_count": 0,
                "deterministic_match_count": 0,
                "outcome": "routing_disabled",
            }
        else:
            keyword_rows = db.query(
                models.DocumentKeyword.document_id,
                models.Keyword.word,
            ).join(
                models.Keyword, models.Keyword.id == models.DocumentKeyword.keyword_id,
            ).filter(
                models.DocumentKeyword.document_id.in_(routing_input_doc_ids),
            ).all()
            document_keywords = {doc_id: [] for doc_id in routing_input_doc_ids}
            for doc_id, word in keyword_rows:
                document_keywords.setdefault(doc_id, []).append(word)
            permitted_keywords = sorted({word for _, word in keyword_rows}, key=lambda value: value.lower())
            routing_prompt_version = "routing-keyword-v1"
            try:
                question_keywords, keyword_selection_trace = ai_service.extract_provider_keywords_with_trace(
                    question,
                    available_keywords=permitted_keywords,
                    limit=3,
                    prompt=(
                        "Select exact permitted document tags that are semantically related to the question. "
                        "The supplied allowed list has already passed governance filtering."
                    ),
                    prompt_version=routing_prompt_version,
                )
            except Exception:
                provider = ai_service.get_ai_provider()
                question_keywords, keyword_selection_trace = keyword_provider_error_fallback(
                    question,
                    available_keywords=permitted_keywords,
                    limit=3,
                    provider=provider.provider_name,
                    adapter=provider.adapter_name,
                    prompt_version=routing_prompt_version,
                )
        query_profile = relevance.build_query_profile(question, question_keywords)
        query_profile["keyword_selection_trace"] = keyword_selection_trace
        query_profile["owned_object_resolution_trace"] = owned_object_trace
        scoped_routing_decision = route_documents(
            permitted_document_ids=routing_input_doc_ids,
            document_keywords=document_keywords,
            selected_keywords=question_keywords,
            mode=configured_routing_mode,
        )
        routing_decision = _routing_decision_in_governed_scope(
            scoped_routing_decision,
            permitted_doc_ids,
        )
        candidate_doc_ids = list(routing_decision.candidate_document_ids)
        query_profile["routing_trace"] = routing_decision.to_trace()
        if owned_object_resolution.status == owned_object_context.STATUS_RESOLVED and configured_routing_mode == RoutingMode.ROUTING_OFF:
            query_profile["retrieval_strategy"] = "owned_object_context"
        elif owned_object_resolution.status == owned_object_context.STATUS_RESOLVED and routing_decision.fallback_used:
            query_profile["retrieval_strategy"] = "owned_object_context_fallback"
        elif owned_object_resolution.status == owned_object_context.STATUS_RESOLVED:
            query_profile["retrieval_strategy"] = "owned_object_keyword_routed"
        elif configured_routing_mode == RoutingMode.ROUTING_OFF:
            query_profile["retrieval_strategy"] = "full_permitted_corpus"
        elif routing_decision.fallback_used:
            query_profile["retrieval_strategy"] = "permitted_corpus_fallback"
        else:
            query_profile["retrieval_strategy"] = "keyword_routed"

        if not candidate_doc_ids:
            msg = "No source available to this request matches the question, so no answer was generated."
            cf = controlled_failure.make_controlled_failure(
                controlled_failure.STATUS_REFUSE_NO_MATCH,
                controlled_failure.REASON_EPISTEMIC,
                controlled_failure.evidence_state([], query_profile, False),
                controlled_failure.safe_policy_state({}),
                msg,
                ["Upload or connect a permitted source that is relevant to the question."],
                {"gate": "candidate_retrieval"},
            )
            evidence_check = {"decision": "controlled_failure", "controlled_failure": cf, "output_mode": cf["status"]}
            log_chat_event(db, user_id, question, msg, question_keywords, [], "rejected", query_profile, {}, evidence_check, cf, cf["status"], audit_id)
            return controlled_failure_payload(msg, query_profile, {}, evidence_check, cf, audit_id=audit_id)

        governance_context = policy_engine.resolve_document_access_bulk(
            db=db,
            user_id=user_id,
            doc_ids=candidate_doc_ids,
            purpose=query_profile.get("purpose", "grounded_question_answering"),
        )
        governance_context["governance_before_routing"] = True
        governance_context["pre_routing_usable_count"] = len(permitted_doc_ids)
        governance_context["pre_routing_denied_count"] = len(pre_routing_governance["denied_doc_ids"])
        governance_context["routing_trace"] = routing_decision.to_trace()
        governance_context["owned_object_resolution_trace"] = owned_object_trace
        governance_context["fallback_used"] = routing_decision.fallback_used
        content_doc_ids = governance_context["content_doc_ids"]
        metadata_doc_ids = governance_context["metadata_only_doc_ids"]

        sources_list = [metadata_only_source(db, doc_id) for doc_id in metadata_doc_ids]
        context_blocks = []
        aggregate_contributions: list[AggregateContribution] = []

        if content_doc_ids:
            question_vector = ai_service.embed_text(question, model=ai_service.EMBEDDING_MODEL)

            primary_doc_ids = [
                doc_id for doc_id in content_doc_ids
                if governance_context["use_decisions"].get(doc_id) == relevance.USE_FULL
                and governance_context["source_roles"].get(doc_id) == relevance.SOURCE_ROLE_PRIMARY
            ]
            aggregate_doc_ids = [doc_id for doc_id in content_doc_ids if governance_context["use_decisions"].get(doc_id) == relevance.USE_AGGREGATE]
            other_content_doc_ids = [doc_id for doc_id in content_doc_ids if doc_id not in set(primary_doc_ids + aggregate_doc_ids)]

            retrieval_tiers = [
                ("primary_full", primary_doc_ids),
                ("other_full", other_content_doc_ids),
                ("aggregate_only", aggregate_doc_ids),
            ]
            for tier_name, tier_doc_ids in retrieval_tiers:
                tier_sources, tier_blocks, tier_aggregate = query_retrieved_sources(
                    db=db,
                    question=question,
                    question_vector=question_vector,
                    query_profile=query_profile,
                    governance_context=governance_context,
                    doc_ids=tier_doc_ids,
                    n_results=4,
                )
                if tier_sources:
                    sources_list.extend(tier_sources)
                    context_blocks.extend(tier_blocks)
                    aggregate_contributions.extend(tier_aggregate)
                    query_profile["retrieval_tier_used"] = tier_name
                    if tier_name != "aggregate_only":
                        break

        content_sources = [
            source for source in sources_list
            if source.get("use_decision") in {relevance.USE_FULL, relevance.USE_AGGREGATE}
        ]
        if governance_context.get("stale_index_rejections") and not content_sources:
            msg = "The request cannot be answered from the sources available for this purpose."
            cf = controlled_failure.make_controlled_failure(
                controlled_failure.STATUS_REFUSE,
                controlled_failure.REASON_GOVERNANCE,
                controlled_failure.evidence_state([], query_profile, False),
                controlled_failure.safe_policy_state({}),
                msg,
                ["Verify that an authorized, current source is available for this purpose, then retry."],
                {"gate": "policy_integrity"},
            )
            evidence_check = {
                "decision": "controlled_failure",
                "controlled_failure": cf,
                "output_mode": cf["status"],
            }
            log_chat_event(
                db, user_id, question, msg, question_keywords, [], "stale_index_denied",
                query_profile, governance_context, evidence_check, cf, cf["status"], audit_id,
            )
            # The public projection is deliberately indistinguishable from an
            # ordinary permission refusal; detailed identifiers remain in the
            # privileged audit context above.
            return controlled_failure_payload(msg, query_profile, {}, evidence_check, cf, [], audit_id)

        role_summary = relevance.summarize_source_roles(sources_list)
        relevance_level_summary = relevance.summarize_relevance_levels(sources_list)
        evidence_check = evidence_service.check_rag_evidence(sources_list, query_profile, governance_context)
        support_check = evidence_service.question_source_support(question, sources_list)
        evidence_check["question_source_support"] = support_check
        if support_check["reason"] == "wrong_object_identifier":
            msg = "No permitted source matches the requested object identifier, so no answer was generated."
            cf = controlled_failure.make_controlled_failure(
                controlled_failure.STATUS_REFUSE_NO_MATCH,
                controlled_failure.REASON_EPISTEMIC,
                controlled_failure.evidence_state([], query_profile, False),
                controlled_failure.safe_policy_state(governance_context),
                msg,
                ["Check the object identifier or add a permitted source for that exact object."],
                {"gate": "exact_object_match", "requested_identifier_count": len(support_check["requested_object_identifiers"])},
            )
            evidence_check.update({"decision": "controlled_failure", "controlled_failure": cf, "output_mode": cf["status"]})
            log_chat_event(
                db, user_id, question, msg, question_keywords, [], "wrong_object_no_match",
                query_profile, governance_context, evidence_check, cf, cf["status"], audit_id,
            )
            return controlled_failure_payload(msg, query_profile, governance_context, evidence_check, cf, [], audit_id)
        aggregate_request = is_aggregate_statistics_question(question)
        aggregate_execution = None
        if aggregate_request and governance_context.get("has_aggregate_evidence") and not governance_context.get("has_primary_evidence"):
            aggregate_execution = execute_aggregate(
                aggregate_contributions,
                governance_context["use_decisions"],
                aggregate_config_from_environment(),
            )
        output_gate = controlled_failure.select_rag_output_mode(
            question=question,
            sources=sources_list,
            query_profile=query_profile,
            governance=governance_context,
            context_blocks_available=bool(context_blocks) or bool(aggregate_execution and aggregate_execution["aggregate"]),
            aggregate_request=aggregate_request,
            support_check=support_check,
        )
        evidence_check["output_mode"] = output_gate.get("output_mode")
        evidence_check["output_gate"] = output_gate.get("trace", {})
        if output_gate.get("controlled_failure"):
            evidence_check["controlled_failure"] = output_gate["controlled_failure"]
            evidence_check["decision"] = output_gate.get("decision")

        if not content_doc_ids and metadata_doc_ids:
            cf = output_gate.get("controlled_failure")
            msg = cf.get("safeOutput") if cf else "Only metadata-level sources are available for this question; document content is withheld by policy, so the answer cannot be found in the document content."
            log_chat_event(db, user_id, question, msg, question_keywords, sources_list, "metadata_only", query_profile, governance_context, evidence_check, cf, output_gate.get("output_mode"), audit_id)
            return chat_success_payload(question, question_keywords, query_profile, governance_context, role_summary, relevance_level_summary, evidence_check, msg, sources_list, cf, output_gate.get("output_mode"), audit_id)

        if not content_doc_ids:
            cf = output_gate.get("controlled_failure")
            msg = cf.get("safeOutput") if cf else "There is no permitted source that can be used for this question in the InfoBank."
            log_chat_event(db, user_id, question, msg, question_keywords, sources_list, "rejected", query_profile, governance_context, evidence_check, cf, output_gate.get("output_mode"), audit_id)
            return controlled_failure_payload(msg, query_profile, governance_context, evidence_check, cf or {}, sources_list, audit_id)

        if aggregate_execution is not None:
            public_aggregate_governance = {
                "policy_enforced": True,
                "aggregate_threshold_applied": True,
                "individual_sources_withheld": True,
            }
            public_evidence_check = {
                "aggregate_execution": {
                "output_class": aggregate_execution["output_class"],
                "reason_code": aggregate_execution["reason_code"],
                "public_trace": aggregate_execution["public_trace"],
                "generation_skipped": True,
                }
            }
            answer = aggregate_execution["safe_output"]
            if aggregate_execution["output_class"] == "REFUSE_AGGREGATION_THRESHOLD":
                cf = controlled_failure.make_controlled_failure(
                    "REFUSE_AGGREGATION_THRESHOLD",
                    aggregate_execution["reason_code"],
                    controlled_failure.evidence_state([], query_profile, False),
                    controlled_failure.safe_policy_state({}),
                    answer,
                    ["Request a governed aggregate only after the configured privacy threshold can be satisfied."],
                    {"gate": "aggregate_threshold", **aggregate_execution["public_trace"]},
                )
                public_evidence_check["decision"] = "controlled_failure"
                public_evidence_check["controlled_failure"] = cf
                public_evidence_check["output_mode"] = aggregate_execution["output_class"]
                log_chat_event(db, user_id, question, answer, question_keywords, [], "aggregate_threshold", query_profile, public_aggregate_governance, public_evidence_check, cf, aggregate_execution["output_class"], audit_id)
                return controlled_failure_payload(answer, query_profile, public_aggregate_governance, public_evidence_check, cf, [], audit_id)
            public_evidence_check["decision"] = "aggregate_result"
            public_evidence_check["output_mode"] = aggregate_execution["output_class"]
            log_chat_event(db, user_id, question, answer, question_keywords, [], "aggregate_result", query_profile, public_aggregate_governance, public_evidence_check, None, aggregate_execution["output_class"], audit_id)
            return chat_success_payload(question, question_keywords, query_profile, public_aggregate_governance, {}, {}, public_evidence_check, answer, [], None, aggregate_execution["output_class"], audit_id)

        if output_gate.get("decision") == "controlled_failure":
            cf = output_gate["controlled_failure"]
            msg = cf.get("safeOutput") or "The answer cannot be found in the document."
            log_chat_event(db, user_id, question, msg, question_keywords, sources_list, cf.get("status", "not_found"), query_profile, governance_context, evidence_check, cf, output_gate.get("output_mode"), audit_id)
            return chat_success_payload(question, question_keywords, query_profile, governance_context, role_summary, relevance_level_summary, evidence_check, msg, sources_list, cf, output_gate.get("output_mode"), audit_id)

        generation_cf = output_gate.get("controlled_failure")
        output_mode = output_gate.get("output_mode", controlled_failure.STATUS_FULL_ANSWER)
        context_text = "\n\n---\n\n".join(context_blocks)
        system_instruction = (
            "You are a precise InfoBank data analysis expert. Answer ONLY based on the provided context. "
            "Answer in the same language as the question. Use the full usable-relevance profile. "
            "Primary sources may support direct claims. Aggregate-only sources are non-quotable and may support only governed aggregate/statistical statements. "
            "Aggregate-only sources must never reveal document-specific identifiers, codenames, project labels, names, or other individual content. "
            "Metadata-only sources must never support content claims. Contextual/activity sources must not create obligations by themselves. "
            "Contrastive sources may close, cancel, or weaken a candidate claim. Respect the Evidence Check warnings. "
            "Every relationship asserted in the answer must be explicitly stated by the permitted source text. "
            "Do not turn an exclusion, coverage rule, requirement, or correlation into a causal claim. "
            "If the Output mode gate contains a controlled_failure object, obey its safeOutput and nextSteps while still answering only within the allowed restriction. "
            "If information is missing or unclear, answer strictly with: 'The answer cannot be found in the document.' No hallucinations."
        )
        answer = ai_service.generate_answer(
            [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Question: {question}\n\nQuery profile:\n{json.dumps(query_profile, ensure_ascii=False)}\n\nGovernance/source-role summary:\n{json.dumps(governance_context, ensure_ascii=False)}\n\nSource role summary:\n{json.dumps(role_summary, ensure_ascii=False)}\n\nRelevance level summary:\n{json.dumps(relevance_level_summary, ensure_ascii=False)}\n\nEvidence check:\n{json.dumps(evidence_check, ensure_ascii=False)}\n\nOutput mode gate:\n{json.dumps(output_gate, ensure_ascii=False)}\n\nContext from the document(s):\n{context_text}"},
            ],
            model=ai_service.MODEL_NAME,
            temperature=0.1,
        )
        final_cf = generation_cf
        if is_browser_history_action_rule_question(question):
            answer = "No. Browser history or activity traces can provide contextual support, refine details, or help prioritize an existing task, but they cannot create an action item by themselves without primary evidence such as an official request, assignment, calendar obligation, or user commitment."
            final_cf = controlled_failure.make_controlled_failure(
                controlled_failure.STATUS_RESTRICTED_ANSWER,
                controlled_failure.REASON_EVIDENTIAL,
                controlled_failure.evidence_state(sources_list, query_profile, bool(context_blocks)),
                controlled_failure.safe_policy_state(governance_context),
                answer,
                ["Use browser history only as contextual support and connect a primary source before creating an obligation."],
                {"gate": "output_mode_selection", "rule": "browser_history_contextual_only"},
            )
            output_mode = final_cf["status"]
            evidence_check.setdefault("warnings", []).append("browser_history_contextual_only_rule_applied")
            evidence_check["decision"] = "restricted_answer"
            evidence_check["controlled_failure"] = final_cf
            evidence_check["output_mode"] = output_mode

        final_status = "not_found" if "The answer cannot be found in the document." in answer else "success"
        grounding_failure_applied = False
        if final_status == "success":
            answer_support = evidence_service.answer_source_support(answer, sources_list)
            evidence_check["answer_source_support"] = answer_support
            if not answer_support["sufficient"]:
                final_cf = controlled_failure.from_unsupported_generated_answer(
                    question,
                    sources_list,
                    query_profile,
                    governance_context,
                    answer_support,
                )
                answer = final_cf["safeOutput"]
                output_mode = final_cf["status"]
                final_status = "not_found"
                grounding_failure_applied = True
                evidence_check["decision"] = "controlled_failure"
                evidence_check["controlled_failure"] = final_cf
                evidence_check["output_mode"] = output_mode
        if final_status == "not_found":
            if not grounding_failure_applied:
                final_cf = controlled_failure.from_not_found_answer(question, sources_list, query_profile, governance_context)
                output_mode = final_cf["status"]
                evidence_check["decision"] = "controlled_failure"
                evidence_check["controlled_failure"] = final_cf
                evidence_check["output_mode"] = output_mode
        elif final_cf:
            evidence_check["controlled_failure"] = final_cf
            evidence_check["output_mode"] = output_mode
            evidence_check["decision"] = output_gate.get("decision", "restricted_generation_allowed")
        log_chat_event(db, user_id, question, answer, question_keywords, sources_list, final_status, query_profile, governance_context, evidence_check, final_cf, output_mode, audit_id)
        return chat_success_payload(question, question_keywords, query_profile, governance_context, role_summary, relevance_level_summary, evidence_check, answer, sources_list, final_cf, output_mode, audit_id)
    except Exception as e:
        db.rollback()
        log_chat_event(db, user_id, question, str(e), [], [], "error", query_profile, governance_context, evidence_check, None, None, audit_id)
        raise HTTPException(status_code=500, detail=str(e))
