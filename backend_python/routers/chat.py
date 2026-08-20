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
import security
import policy_engine
import controlled_failure
import citation_service
from aggregate_executor import AggregateConfig, AggregateContribution, execute_aggregate
from routing import RoutingMode, route_documents
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


def _public_query_profile(query_profile: dict | None) -> dict:
    public = dict(query_profile or {})
    if "routing_trace" in public:
        public["routing_trace"] = _public_routing_trace(public.get("routing_trace"))
    return public


def _public_governance_context(governance: dict | None) -> dict:
    governance = governance or {}
    public = {
        "policy_enforced": True,
        **controlled_failure.safe_policy_state(governance),
    }
    if governance.get("routing_trace"):
        public["routing_trace"] = _public_routing_trace(governance.get("routing_trace"))
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


def query_retrieved_sources(db: Session, question: str, question_vector: list[float], query_profile: dict, governance_context: dict, doc_ids: list[str], n_results: int = 4) -> tuple[list[dict], list[str], list[AggregateContribution]]:
    if not doc_ids:
        return [], [], []
    where_clause = {"document_id": doc_ids[0]} if len(doc_ids) == 1 else {"document_id": {"$in": doc_ids}}
    results = ai_service.collection.query(query_embeddings=[question_vector], n_results=n_results, where=where_clause)
    sources: list[dict] = []
    blocks: list[str] = []
    aggregate_contributions: list[AggregateContribution] = []
    if not results.get('documents') or not results['documents'][0]:
        return sources, blocks, aggregate_contributions

    seen = set()
    result_ids = results.get("ids", [[]])[0]
    for vector_id, chunk_text, meta in zip(result_ids, results['documents'][0], results['metadatas'][0]):
        doc_id = meta.get("document_id")
        chunk_id = meta.get("chunk_id") or vector_id
        dedupe_key = (doc_id, chunk_id)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        doc_record = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if not doc_record or doc_record.source_status != "ACTIVE":
            continue
        chunk_record = db.query(models.DocumentChunk).filter(
            models.DocumentChunk.id == chunk_id,
            models.DocumentChunk.document_id == doc_id,
        ).first()
        file_name = (doc_record.original_filename or doc_record.file_path) if doc_record else "Unknown document"
        base_role = governance_context["source_roles"].get(doc_id, relevance.SOURCE_ROLE_CONTEXTUAL)
        use_decision = governance_context["use_decisions"].get(doc_id, relevance.USE_DENY)
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
            numeric = re.search(r"(?<![A-Za-z0-9])(-?\d+(?:\.\d+)?)(?![A-Za-z0-9])", chunk_text)
            if numeric:
                aggregate_contributions.append(
                    AggregateContribution(source_id=doc_id, contributor_id=doc_id, value=float(numeric.group(1)))
                )
        else:
            blocks.append(relevance.make_context_block(source_profile, file_name, safe_chunk_text))
        sources.append({
            "document_id": doc_id,
            "file_name": file_name,
            "role": role,
            "use_decision": use_decision,
            "usable_relevance": source_profile,
            "text": relevance.public_source_text(role, chunk_text),
            "citation": citation,
        })
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
        "query_profile": query_profile,
        "governance": governance_context,
        "source_role_summary": role_summary,
        "relevance_level_summary": relevance_level_summary,
        "evidence_check": evidence_check,
        "controlled_failure": controlled_failure_obj,
        "output_mode": output_mode,
        "audit_id": audit_id,
        "searched_documents_count": len(governance_context.get("usable_doc_ids", [])),
        "answer": answer,
        "sources": sources_list,
    }


def controlled_failure_payload(message: str, query_profile: dict, governance_context: dict, evidence_check: dict, cf: dict, sources_list: list | None = None, audit_id: str | None = None) -> dict:
    return {
        "status": "controlled_failure",
        "message": message,
        "answer": message,
        "query_profile": _public_query_profile(query_profile),
        "governance": _public_governance_context(governance_context),
        "evidence_check": evidence_check,
        "controlled_failure": cf,
        "output_mode": cf.get("status"),
        "audit_id": audit_id,
        "sources": sources_list or [],
    }


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
            background_tasks.add_task(log_chat_event, db, user_id, question, msg, [], [], cf["status"], query_profile, {}, evidence_check, cf, cf["status"], audit_id)
            return controlled_failure_payload(msg, query_profile, {}, evidence_check, cf, audit_id=audit_id)

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
            background_tasks.add_task(log_chat_event, db, user_id, question, msg, [], [], "rejected", query_profile, pre_routing_governance, evidence_check, cf, cf["status"], audit_id)
            return controlled_failure_payload(msg, query_profile, pre_routing_governance, evidence_check, cf, audit_id=audit_id)

        keyword_rows = db.query(
            models.DocumentKeyword.document_id,
            models.Keyword.word,
        ).join(
            models.Keyword, models.Keyword.id == models.DocumentKeyword.keyword_id,
        ).filter(
            models.DocumentKeyword.document_id.in_(permitted_doc_ids),
        ).all()
        document_keywords: dict[str, list[str]] = {doc_id: [] for doc_id in permitted_doc_ids}
        for doc_id, word in keyword_rows:
            document_keywords.setdefault(doc_id, []).append(word)
        permitted_keywords = sorted({word for _, word in keyword_rows}, key=lambda value: value.lower())
        question_keywords = ai_service.extract_provider_keywords(
            question,
            available_keywords=permitted_keywords,
            limit=3,
            prompt=(
                "Select exact permitted document tags that are semantically related to the question. "
                "The supplied allowed list has already passed governance filtering."
            ),
            prompt_version="routing-keyword-v1",
        )
        query_profile = relevance.build_query_profile(question, question_keywords)
        routing_decision = route_documents(
            permitted_document_ids=permitted_doc_ids,
            document_keywords=document_keywords,
            selected_keywords=question_keywords,
            mode=RoutingMode.KEYWORD_ROUTING,
        )
        candidate_doc_ids = list(routing_decision.candidate_document_ids)
        query_profile["routing_trace"] = routing_decision.to_trace()
        if routing_decision.fallback_used:
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
            background_tasks.add_task(log_chat_event, db, user_id, question, msg, question_keywords, [], "rejected", query_profile, {}, evidence_check, cf, cf["status"], audit_id)
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
            background_tasks.add_task(
                log_chat_event, db, user_id, question, msg, question_keywords, [], "wrong_object_no_match",
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
            context_blocks_available=(bool(context_blocks) and support_check["sufficient"]) or bool(aggregate_execution and aggregate_execution["aggregate"]),
            aggregate_request=aggregate_request,
        )
        evidence_check["output_mode"] = output_gate.get("output_mode")
        evidence_check["output_gate"] = output_gate.get("trace", {})
        if output_gate.get("controlled_failure"):
            evidence_check["controlled_failure"] = output_gate["controlled_failure"]
            evidence_check["decision"] = output_gate.get("decision")

        if not content_doc_ids and metadata_doc_ids:
            cf = output_gate.get("controlled_failure")
            msg = cf.get("safeOutput") if cf else "Only metadata-level sources are available for this question; document content is withheld by policy, so the answer cannot be found in the document content."
            background_tasks.add_task(log_chat_event, db, user_id, question, msg, question_keywords, sources_list, "metadata_only", query_profile, governance_context, evidence_check, cf, output_gate.get("output_mode"), audit_id)
            return chat_success_payload(question, question_keywords, query_profile, governance_context, role_summary, relevance_level_summary, evidence_check, msg, sources_list, cf, output_gate.get("output_mode"), audit_id)

        if not content_doc_ids:
            cf = output_gate.get("controlled_failure")
            msg = cf.get("safeOutput") if cf else "There is no permitted source that can be used for this question in the InfoBank."
            background_tasks.add_task(log_chat_event, db, user_id, question, msg, question_keywords, sources_list, "rejected", query_profile, governance_context, evidence_check, cf, output_gate.get("output_mode"), audit_id)
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
                background_tasks.add_task(log_chat_event, db, user_id, question, answer, question_keywords, [], "aggregate_threshold", query_profile, public_aggregate_governance, public_evidence_check, cf, aggregate_execution["output_class"], audit_id)
                return controlled_failure_payload(answer, query_profile, public_aggregate_governance, public_evidence_check, cf, [], audit_id)
            public_evidence_check["decision"] = "aggregate_result"
            public_evidence_check["output_mode"] = aggregate_execution["output_class"]
            background_tasks.add_task(log_chat_event, db, user_id, question, answer, question_keywords, [], "aggregate_result", query_profile, public_aggregate_governance, public_evidence_check, None, aggregate_execution["output_class"], audit_id)
            return chat_success_payload(question, question_keywords, query_profile, public_aggregate_governance, {}, {}, public_evidence_check, answer, [], None, aggregate_execution["output_class"], audit_id)

        if output_gate.get("decision") == "controlled_failure":
            cf = output_gate["controlled_failure"]
            msg = cf.get("safeOutput") or "The answer cannot be found in the document."
            background_tasks.add_task(log_chat_event, db, user_id, question, msg, question_keywords, sources_list, cf.get("status", "not_found"), query_profile, governance_context, evidence_check, cf, output_gate.get("output_mode"), audit_id)
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
        if final_status == "not_found":
            final_cf = controlled_failure.from_not_found_answer(question, sources_list, query_profile, governance_context)
            output_mode = final_cf["status"]
            evidence_check["decision"] = "controlled_failure"
            evidence_check["controlled_failure"] = final_cf
            evidence_check["output_mode"] = output_mode
        elif final_cf:
            evidence_check["controlled_failure"] = final_cf
            evidence_check["output_mode"] = output_mode
            evidence_check["decision"] = output_gate.get("decision", "restricted_generation_allowed")
        background_tasks.add_task(log_chat_event, db, user_id, question, answer, question_keywords, sources_list, final_status, query_profile, governance_context, evidence_check, final_cf, output_mode, audit_id)
        return chat_success_payload(question, question_keywords, query_profile, governance_context, role_summary, relevance_level_summary, evidence_check, answer, sources_list, final_cf, output_mode, audit_id)
    except Exception as e:
        db.rollback()
        background_tasks.add_task(log_chat_event, db, user_id, question, str(e), [], [], "error", query_profile, governance_context, evidence_check, None, None, audit_id)
        raise HTTPException(status_code=500, detail=str(e))
