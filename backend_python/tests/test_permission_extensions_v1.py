from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import controlled_failure
import models
import policy_engine
import relevance
from routers import admin, chat, documents, policy
from routers.analytics import _build_governed_graph


OWNER_ID = "00000000-0000-0000-0000-000000001001"
READER_ID = "00000000-0000-0000-0000-000000001002"
AUDITOR_ID = "00000000-0000-0000-0000-000000001003"
OTHER_ID = "00000000-0000-0000-0000-000000001004"
DOC_ID = "00000000-0000-0000-0000-000000001100"


def add_user(db, user_id: str, username: str) -> None:
    db.add(models.User(
        id=user_id,
        email=f"{username}@example.invalid",
        username=username,
        password_hash="not-used",
    ))


def add_document(db, doc_id: str = DOC_ID, *, visibility: str = "Private") -> models.Document:
    document = models.Document(
        id=doc_id,
        file_path=f"{doc_id}.pdf",
        original_filename=f"{doc_id}.pdf",
        visibility=visibility,
        source_status="ACTIVE",
        processing_status="COMPLETE",
    )
    db.add(document)
    db.flush()
    return document


def add_owner_relation(db, doc_id: str = DOC_ID) -> None:
    db.add(models.UserDocumentPermission(
        id=f"owner-{doc_id}",
        user_id=OWNER_ID,
        document_id=doc_id,
        permission_type=models.PermissionType.Owner,
    ))
    db.flush()


def setup_document_with_users(db, doc_id: str = DOC_ID, *, visibility: str = "Private") -> None:
    add_user(db, OWNER_ID, "owner")
    add_user(db, READER_ID, "reader")
    add_user(db, AUDITOR_ID, "auditor")
    add_user(db, OTHER_ID, "other")
    add_document(db, doc_id, visibility=visibility)
    add_owner_relation(db, doc_id)


def grant(
    db,
    *,
    user_id: str = READER_ID,
    permission_type: models.PermissionType = models.PermissionType.Reader,
    doc_id: str = DOC_ID,
    **kwargs,
) -> models.UserDocumentPermission:
    return policy_engine.grant_document_permission(
        db,
        owner_user_id=OWNER_ID,
        document_id=doc_id,
        target_user_id=user_id,
        permission_type=permission_type,
        **kwargs,
    )


def test_query_limited_grant_consumes_once_per_request_and_then_denies(db_session) -> None:
    setup_document_with_users(db_session)
    relation = grant(db_session, max_queries=2)
    assert relation.queries_used == 0

    for request_index in range(2):
        governance = policy_engine.resolve_document_access_bulk(
            db_session,
            READER_ID,
            [DOC_ID],
            "grounded_question_answering",
        )
        assert governance["use_decisions"][DOC_ID] == relevance.USE_FULL
        result = policy_engine.consume_query_quotas_for_governance(
            db_session,
            governance,
            request_id=f"ask-{request_index}",
        )
        assert result["ok"] is True
        assert result["consumed_count"] == 1

    db_session.refresh(relation)
    assert relation.queries_used == 2
    exhausted = policy_engine.resolve_document_access(db_session, READER_ID, DOC_ID)
    assert exhausted["use_decision"] == relevance.USE_DENY
    assert exhausted["reason"] == "persistent_permission_quota_exhausted"

    stale_governance = {
        "quota_limited_doc_ids": [DOC_ID],
        "permission_ids": {DOC_ID: relation.id},
        "permission_types": {DOC_ID: models.PermissionType.Reader.value},
    }
    failed = policy_engine.consume_query_quotas_for_governance(
        db_session,
        stale_governance,
        request_id="stale-race-loser",
    )
    db_session.refresh(relation)
    assert failed["ok"] is False
    assert failed["reason_code"] == policy_engine.QUERY_LIMIT_EXHAUSTED
    assert relation.queries_used == 2


def test_resolvers_and_diagnostics_do_not_consume_quota_and_independent_paths_still_work(db_session) -> None:
    setup_document_with_users(db_session)
    relation = grant(db_session, max_queries=1)

    first = policy_engine.resolve_document_access_bulk(db_session, READER_ID, [DOC_ID], "grounded_question_answering")
    second = policy_engine.resolve_document_access_bulk(db_session, READER_ID, [DOC_ID], "grounded_question_answering")
    diagnostic = policy_engine.resolve_document_access(db_session, READER_ID, DOC_ID)
    db_session.refresh(relation)
    assert first == second
    assert diagnostic["use_decision"] == relevance.USE_FULL
    assert relation.queries_used == 0

    assert policy_engine.consume_query_quotas_for_governance(db_session, first, request_id="ask-1")["ok"]
    assert policy_engine.resolve_document_access(db_session, READER_ID, DOC_ID)["use_decision"] == relevance.USE_DENY

    db_session.add(models.PolicyRule(
        id="quota-override-policy",
        owner_user_id=OWNER_ID,
        target_type=policy_engine.TARGET_DOCUMENT,
        target_id=DOC_ID,
        purpose="grounded_question_answering",
        access_mode=models.PolicyAccessMode.Full,
    ))
    db_session.flush()
    policy_allowed = policy_engine.resolve_document_access(db_session, READER_ID, DOC_ID)
    assert policy_allowed["use_decision"] == relevance.USE_FULL
    assert policy_allowed["authorization_path"] == "policy_rule"

    public_doc = "00000000-0000-0000-0000-000000001101"
    add_document(db_session, public_doc, visibility="Metadata")
    db_session.add(models.UserDocumentPermission(
        id="exhausted-public-reader",
        user_id=READER_ID,
        document_id=public_doc,
        permission_type=models.PermissionType.Reader,
        max_queries=1,
        queries_used=1,
    ))
    db_session.flush()
    visibility_allowed = policy_engine.resolve_document_access(db_session, READER_ID, public_doc)
    assert visibility_allowed["use_decision"] == relevance.USE_METADATA
    assert visibility_allowed["authorization_path"] == "document_visibility"
    assert visibility_allowed["inactive_permission_reason"] == "persistent_permission_quota_exhausted"


def test_query_quota_concurrent_consumers_do_not_overspend(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'quota.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as setup:
        setup_document_with_users(setup)
        grant(setup, max_queries=1)
        setup.commit()

    barrier = threading.Barrier(2)
    results: list[dict] = []

    def consume() -> None:
        with SessionLocal() as session:
            governance = policy_engine.resolve_document_access_bulk(
                session,
                READER_ID,
                [DOC_ID],
                "grounded_question_answering",
            )
            barrier.wait(timeout=10)
            result = policy_engine.consume_query_quotas_for_governance(
                session,
                governance,
                request_id=str(uuid.uuid4()),
            )
            if result["ok"]:
                session.commit()
            else:
                session.rollback()
            results.append(result)

    threads = [threading.Thread(target=consume), threading.Thread(target=consume)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    with SessionLocal() as check:
        relation = check.query(models.UserDocumentPermission).filter(
            models.UserDocumentPermission.user_id == READER_ID,
            models.UserDocumentPermission.document_id == DOC_ID,
        ).one()
        assert relation.queries_used == 1
    assert sorted(result["ok"] for result in results) == [False, True]
    engine.dispose()


def test_existing_document_level_policy_rules_keep_purpose_and_time_conditions(db_session) -> None:
    setup_document_with_users(db_session)
    policy_doc = "00000000-0000-0000-0000-000000001120"
    future_doc = "00000000-0000-0000-0000-000000001121"
    expired_doc = "00000000-0000-0000-0000-000000001122"
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    for doc_id in (policy_doc, future_doc, expired_doc):
        add_document(db_session, doc_id)
    db_session.add_all([
        models.PolicyRule(
            id="existing-policy-purpose-time",
            owner_user_id=OWNER_ID,
            target_type=policy_engine.TARGET_DOCUMENT,
            target_id=policy_doc,
            purpose="publication_review",
            access_mode=models.PolicyAccessMode.Full,
            valid_from=now - dt.timedelta(minutes=5),
            valid_until=now + dt.timedelta(minutes=5),
        ),
        models.PolicyRule(
            id="existing-policy-future",
            owner_user_id=OWNER_ID,
            target_type=policy_engine.TARGET_DOCUMENT,
            target_id=future_doc,
            purpose="grounded_question_answering",
            access_mode=models.PolicyAccessMode.Full,
            valid_from=now + dt.timedelta(minutes=5),
        ),
        models.PolicyRule(
            id="existing-policy-expired",
            owner_user_id=OWNER_ID,
            target_type=policy_engine.TARGET_DOCUMENT,
            target_id=expired_doc,
            purpose="grounded_question_answering",
            access_mode=models.PolicyAccessMode.Full,
            valid_until=now - dt.timedelta(minutes=5),
        ),
    ])
    db_session.flush()

    matched = policy_engine.resolve_document_access(db_session, READER_ID, policy_doc, "publication_review")
    mismatched = policy_engine.resolve_document_access(db_session, READER_ID, policy_doc, "grounded_question_answering")
    future = policy_engine.resolve_document_access(db_session, READER_ID, future_doc, "grounded_question_answering")
    expired = policy_engine.resolve_document_access(db_session, READER_ID, expired_doc, "grounded_question_answering")
    assert matched["use_decision"] == relevance.USE_FULL
    assert matched["authorization_path"] == "policy_rule"
    assert mismatched["reason"] == "private_no_permission"
    assert future["reason"] == "private_no_permission"
    assert expired["reason"] == "private_no_permission"


def test_persistent_grants_do_not_include_out_of_scope_purpose_or_time_columns() -> None:
    columns = set(models.UserDocumentPermission.__table__.columns.keys())
    assert {"purpose", "valid_from", "valid_until"}.isdisjoint(columns)
    assert {"max_queries", "queries_used", "requires_explainability"} <= columns


def test_explainability_required_helper_accepts_traceable_sources_and_rejects_legacy_full_sources() -> None:
    governance = {
        "explainability_required_doc_ids": ["traceable", "legacy", "metadata", "aggregate"],
    }
    traceable = {
        "document_id": "traceable",
        "use_decision": relevance.USE_FULL,
        "citation": {"available": True, "chunk_id": "chunk-1", "page_number": 1},
    }
    legacy = {
        "document_id": "legacy",
        "use_decision": relevance.USE_FULL,
        "citation": {"available": False, "reason": "traceability_unavailable"},
    }
    metadata = {
        "document_id": "metadata",
        "use_decision": relevance.USE_METADATA,
        "citation": {"available": False, "reason": "metadata_only_content_withheld"},
    }
    aggregate = {
        "document_id": "aggregate",
        "use_decision": relevance.USE_AGGREGATE,
        "citation": {"available": False, "reason": "raw_source_not_permitted"},
    }

    assert policy_engine.evaluate_explainability_requirements(governance, [traceable])["ok"] is True
    failed = policy_engine.evaluate_explainability_requirements(governance, [legacy])
    assert failed["ok"] is False
    assert failed["reason_code"] == policy_engine.EXPLAINABILITY_REQUIRED_UNSATISFIED
    assert policy_engine.evaluate_explainability_requirements(governance, [metadata])["ok"] is True
    aggregate_ok = policy_engine.evaluate_explainability_requirements(
        governance,
        [aggregate],
        aggregate_execution={"output_class": "AGGREGATE_RESULT"},
    )
    assert aggregate_ok["ok"] is True
    public = policy_engine.public_explainability_state(failed)
    assert "legacy" not in json.dumps(public)
    assert public["unsatisfied_source_count"] == 1


def test_audit_permission_does_not_grant_content_metadata_source_or_graph_access(db_session) -> None:
    setup_document_with_users(db_session)
    db_session.add(models.Keyword(id=1, word="private-keyword"))
    db_session.flush()
    db_session.add(models.DocumentKeyword(document_id=DOC_ID, keyword_id=1))
    grant(db_session, user_id=AUDITOR_ID, permission_type=models.PermissionType.Audit)
    db_session.flush()

    resolved = policy_engine.resolve_document_access(db_session, AUDITOR_ID, DOC_ID)
    assert resolved["use_decision"] == relevance.USE_DENY
    assert resolved["reason"] == "audit_only_no_content_access"

    listing = documents.build_document_list(AUDITOR_ID, db_session)
    [row] = listing["documents"]
    assert row["permission"] == "Audit"
    assert row["file_name"] == "[audit-only document]"
    assert row["keywords"] == []
    assert row["source_sha256"] is None
    assert row["provenance"] == []

    graph = _build_governed_graph(AUDITOR_ID, db_session)
    assert graph["nodes"] == []
    with pytest.raises(HTTPException) as source_error:
        documents.view_document_source(DOC_ID, page=None, user_id=AUDITOR_ID, db=db_session)
    assert source_error.value.status_code == 404


def test_document_audit_endpoint_redacts_raw_content_and_requires_audit_or_owner(db_session) -> None:
    setup_document_with_users(db_session)
    grant(db_session, user_id=AUDITOR_ID, permission_type=models.PermissionType.Audit)
    audit_id = "00000000-0000-0000-0000-00000000aa01"
    raw_details = {
        "question": "What is in private.pdf?",
        "answer": "secret answer body",
        "status": "success",
        "output_mode": "FULL_ANSWER",
        "sources_used": ["private.pdf"],
        "governance": {
            "use_decisions": {DOC_ID: relevance.USE_FULL},
            "source_roles": {DOC_ID: relevance.SOURCE_ROLE_PRIMARY},
            "policy_reasons": {DOC_ID: "direct_permission_full"},
            "authorization_paths": {DOC_ID: "persistent_permission"},
        },
        "evidence_check": {"source_excerpt": "chunk text"},
    }
    db_session.add(models.AuditLog(
        id=audit_id,
        user_id=READER_ID,
        action="CHAT_ASK",
        target_id=None,
        details=json.dumps(raw_details),
    ))
    policy_engine.record_document_audit_links(db_session, audit_id, {"source": [DOC_ID]})
    db_session.flush()

    payload = admin.get_document_audit_records(DOC_ID, user_id=AUDITOR_ID, db=db_session)
    rendered = json.dumps(payload, sort_keys=True)
    assert payload["count"] == 1
    assert payload["logs"][0]["summary"]["document_policy"]["reason"] == "direct_permission_full"
    assert "private.pdf" not in rendered
    assert "secret answer body" not in rendered
    assert "chunk text" not in rendered
    assert READER_ID not in rendered

    with pytest.raises(HTTPException) as other_error:
        admin.get_document_audit_records(DOC_ID, user_id=OTHER_ID, db=db_session)
    assert other_error.value.status_code == 404

    assert policy_engine.revoke_document_permission(
        db_session,
        owner_user_id=OWNER_ID,
        document_id=DOC_ID,
        target_user_id=AUDITOR_ID,
    )
    with pytest.raises(HTTPException) as revoked_error:
        admin.get_document_audit_records(DOC_ID, user_id=AUDITOR_ID, db=db_session)
    assert revoked_error.value.status_code == 404


def test_policy_grant_endpoint_accepts_query_and_explainability_controls_without_consuming(db_session) -> None:
    setup_document_with_users(db_session)
    response = policy.grant_persistent_document_permission(
        DOC_ID,
        target_username="reader",
        permission_type="Reader",
        max_queries=3,
        requires_explainability=True,
        user_id=OWNER_ID,
        db=db_session,
    )
    relation = db_session.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.user_id == READER_ID,
        models.UserDocumentPermission.document_id == DOC_ID,
    ).one()
    assert response["max_queries"] == 3
    assert response["requires_explainability"] is True
    assert db_session.query(models.AuditLog).filter(
        models.AuditLog.action == "DOCUMENT_PERMISSION_GRANTED",
        models.AuditLog.target_id == DOC_ID,
    ).count() == 1
    assert db_session.query(models.DocumentAuditLink).filter(
        models.DocumentAuditLink.document_id == DOC_ID,
        models.DocumentAuditLink.relation_type == "permission_grant",
    ).count() == 1
    diagnostic = policy_engine.resolve_document_access(db_session, READER_ID, DOC_ID)
    db_session.refresh(relation)
    assert diagnostic["requires_explainability"] is True
    assert diagnostic["permission_constraints"]["queries_remaining"] == 3
    assert relation.queries_used == 0


def test_public_failure_redacts_new_permission_extension_identifiers() -> None:
    denied_doc_id = "11111111-1111-1111-1111-111111111111"
    permission_id = "22222222-2222-2222-2222-222222222222"
    governance = {
        "usable_doc_ids": [],
        "content_doc_ids": [],
        "metadata_only_doc_ids": [],
        "denied_doc_ids": [denied_doc_id],
        "permission_ids": {denied_doc_id: permission_id},
        "permission_constraints": {denied_doc_id: {"max_queries": 1, "queries_used": 1}},
        "inactive_permission_reasons": {denied_doc_id: "persistent_permission_quota_exhausted"},
    }
    cf = controlled_failure.make_controlled_failure(
        controlled_failure.STATUS_REFUSE,
        controlled_failure.REASON_GOVERNANCE,
        controlled_failure.evidence_state([], {}, False),
        controlled_failure.safe_policy_state(governance),
        "The request cannot be answered from the sources available for this purpose.",
        [],
        {"gate": "query_limit", "reason_code": policy_engine.QUERY_LIMIT_EXHAUSTED},
    )
    payload = chat.controlled_failure_payload(
        cf["safeOutput"],
        {},
        governance,
        {"decision": "controlled_failure", "controlled_failure": cf},
        cf,
    )
    serialized = json.dumps(payload, sort_keys=True)
    assert denied_doc_id not in serialized
    assert permission_id not in serialized
    assert "queries_used" not in serialized
