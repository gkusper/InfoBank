from __future__ import annotations

import datetime as dt
import json
import uuid

import pytest
from fastapi import HTTPException

import controlled_failure
import models
import policy_engine
import relevance
from aggregate_executor import AggregateConfig, AggregateContribution, execute_aggregate
from document_processing import sha256_text
from routers import admin, chat, documents


OWNER_ID = "00000000-0000-0000-0000-000000002001"
READER_ID = "00000000-0000-0000-0000-000000002002"
AUDITOR_ID = "00000000-0000-0000-0000-000000002003"
OTHER_ID = "00000000-0000-0000-0000-000000002004"


def _id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:unit-spec:{label}"))


def add_user(db, user_id: str, username: str) -> None:
    db.add(
        models.User(
            id=user_id,
            email=f"{username}@example.invalid",
            username=username,
            password_hash="not-used",
        )
    )


def add_users(db) -> None:
    add_user(db, OWNER_ID, "owner")
    add_user(db, READER_ID, "reader")
    add_user(db, AUDITOR_ID, "auditor")
    add_user(db, OTHER_ID, "other")
    db.flush()


def add_document(
    db,
    doc_id: str,
    *,
    visibility: str = "Private",
    source_status: str = "ACTIVE",
    original_filename: str | None = None,
    text: str | None = None,
) -> models.Document:
    document = models.Document(
        id=doc_id,
        file_path=f"{doc_id}.pdf",
        original_filename=original_filename,
        source_storage_path=f"{doc_id}/source.pdf",
        source_sha256="1" * 64,
        source_mime_type="application/pdf",
        page_count=1,
        visibility=visibility,
        source_status=source_status,
        processing_status="COMPLETE",
    )
    db.add(document)
    if text is not None:
        db.add(
            models.DocumentChunk(
                id=_id(f"chunk:{doc_id}"),
                document_id=doc_id,
                chunk_index=0,
                page_number=1,
                char_start=0,
                char_end=len(text),
                text_content=text,
                content_sha256=sha256_text(text),
                source_sha256=document.source_sha256,
                chunk_config_hash="2" * 64,
                vector_id=_id(f"vector:{doc_id}"),
            )
        )
    db.flush()
    return document


def add_permission(
    db,
    user_id: str,
    doc_id: str,
    permission_type: models.PermissionType,
    **kwargs,
) -> models.UserDocumentPermission:
    relation = models.UserDocumentPermission(
        id=_id(f"permission:{user_id}:{doc_id}:{permission_type.value}"),
        user_id=user_id,
        document_id=doc_id,
        permission_type=permission_type,
        **kwargs,
    )
    db.add(relation)
    db.flush()
    return relation


def add_owner_document(db, doc_id: str, **document_kwargs) -> models.Document:
    document = add_document(db, doc_id, **document_kwargs)
    add_permission(db, OWNER_ID, doc_id, models.PermissionType.Owner)
    return document


def add_policy_rule(
    db,
    doc_id: str,
    mode: models.PolicyAccessMode,
    *,
    purpose: str = policy_engine.DEFAULT_DOCUMENT_PURPOSE,
    valid_from: dt.datetime | None = None,
    valid_until: dt.datetime | None = None,
) -> models.PolicyRule:
    rule = models.PolicyRule(
        id=_id(f"rule:{doc_id}:{mode.value}:{purpose}:{valid_from}:{valid_until}"),
        owner_user_id=OWNER_ID,
        target_type=policy_engine.TARGET_DOCUMENT,
        target_id=doc_id,
        purpose=purpose,
        access_mode=mode,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    db.add(rule)
    db.flush()
    return rule


def test_resolution_matrix_for_core_persistent_permissions__perm_own_01_read_01_meta_05_deny_01_aud_03_05_06(
    db_session,
) -> None:
    add_users(db_session)
    cases = [
        ("owner-doc", OWNER_ID, models.PermissionType.Owner, relevance.USE_FULL, "direct_permission_full"),
        ("reader-doc", READER_ID, models.PermissionType.Reader, relevance.USE_FULL, "direct_permission_full"),
        ("aggregate-doc", READER_ID, models.PermissionType.Aggregate, relevance.USE_AGGREGATE, "direct_permission_aggregate"),
        ("metadata-doc", READER_ID, models.PermissionType.Metadata, relevance.USE_METADATA, "direct_permission_metadata"),
        ("audit-doc", AUDITOR_ID, models.PermissionType.Audit, relevance.USE_DENY, "audit_only_no_content_access"),
    ]
    for doc_id, user_id, permission_type, expected_decision, expected_reason in cases:
        add_document(db_session, doc_id)
        add_permission(db_session, user_id, doc_id, permission_type)

    add_document(db_session, "private-doc")
    add_document(db_session, "archived-doc", source_status="ARCHIVED")
    add_permission(db_session, READER_ID, "archived-doc", models.PermissionType.Reader)

    for doc_id, user_id, _permission, expected_decision, expected_reason in cases:
        resolved = policy_engine.resolve_document_access(db_session, user_id, doc_id)
        assert resolved["use_decision"] == expected_decision
        assert resolved["reason"] == expected_reason

    no_permission = policy_engine.resolve_document_access(db_session, READER_ID, "private-doc")
    archived = policy_engine.resolve_document_access(db_session, READER_ID, "archived-doc")
    assert no_permission["use_decision"] == relevance.USE_DENY
    assert no_permission["reason"] == "private_no_permission"
    assert archived["use_decision"] == relevance.USE_DENY
    assert archived["reason"] == "document_archived"


@pytest.mark.parametrize(
    "permission_type",
    [
        models.PermissionType.Reader,
        models.PermissionType.Aggregate,
        models.PermissionType.Metadata,
        models.PermissionType.Audit,
    ],
)
def test_non_owner_permissions_cannot_administer_document__perm_own_07_read_04_aud_07(
    db_session,
    permission_type,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "admin-doc")
    add_permission(db_session, READER_ID, "admin-doc", permission_type)

    with pytest.raises(HTTPException) as owner_error:
        documents.require_owner(db_session, "admin-doc", READER_ID)
    assert owner_error.value.status_code == 403

    with pytest.raises(PermissionError):
        policy_engine.grant_document_permission(
            db_session,
            owner_user_id=READER_ID,
            document_id="admin-doc",
            target_user_id=OTHER_ID,
            permission_type=models.PermissionType.Reader,
        )

    with pytest.raises(PermissionError):
        policy_engine.revoke_document_permission(
            db_session,
            owner_user_id=READER_ID,
            document_id="admin-doc",
            target_user_id=OWNER_ID,
        )

    with pytest.raises(PermissionError):
        policy_engine.transfer_document_ownership(
            db_session,
            owner_user_id=READER_ID,
            document_id="admin-doc",
            target_user_id=OTHER_ID,
        )


@pytest.mark.parametrize(
    "permission_type",
    [
        models.PermissionType.Reader,
        models.PermissionType.Aggregate,
        models.PermissionType.Metadata,
        models.PermissionType.Audit,
    ],
)
def test_owner_can_grant_each_non_owner_permission__perm_own_04_aud_02(
    db_session,
    permission_type,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "grant-doc")

    relation = policy_engine.grant_document_permission(
        db_session,
        owner_user_id=OWNER_ID,
        document_id="grant-doc",
        target_user_id=READER_ID,
        permission_type=permission_type,
        max_queries=3,
        requires_explainability=True,
    )

    assert relation.permission_type == permission_type
    assert relation.max_queries == 3
    assert relation.queries_used == 0
    assert relation.requires_explainability is True


def test_owner_grant_endpoint_rejects_owner_and_self_replacement__perm_own_04(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "invalid-grant-doc")

    with pytest.raises(ValueError, match="Owner"):
        policy_engine.grant_document_permission(
            db_session,
            owner_user_id=OWNER_ID,
            document_id="invalid-grant-doc",
            target_user_id=OWNER_ID,
            permission_type=models.PermissionType.Reader,
        )

    with pytest.raises(ValueError, match="Grant type"):
        policy_engine.grant_document_permission(
            db_session,
            owner_user_id=OWNER_ID,
            document_id="invalid-grant-doc",
            target_user_id=READER_ID,
            permission_type=models.PermissionType.Owner,
        )


def test_transfer_ownership_replaces_existing_relation_and_is_immediate__perm_own_06(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "transfer-doc")
    old_relation = add_permission(db_session, READER_ID, "transfer-doc", models.PermissionType.Metadata)

    transferred = policy_engine.transfer_document_ownership(
        db_session,
        owner_user_id=OWNER_ID,
        document_id="transfer-doc",
        target_user_id=READER_ID,
    )

    assert transferred.user_id == READER_ID
    assert transferred.permission_type == models.PermissionType.Owner
    assert db_session.get(models.UserDocumentPermission, old_relation.id) is None
    assert policy_engine.resolve_document_access(db_session, OWNER_ID, "transfer-doc")["use_decision"] == relevance.USE_DENY
    assert policy_engine.resolve_document_access(db_session, READER_ID, "transfer-doc")["use_decision"] == relevance.USE_FULL


def test_active_policy_rule_precedes_direct_permission_and_deny_wins__perm_deny_02_pol_01_pol_05(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "policy-first-doc")
    add_permission(
        db_session,
        READER_ID,
        "policy-first-doc",
        models.PermissionType.Reader,
        max_queries=1,
        queries_used=1,
    )
    add_policy_rule(db_session, "policy-first-doc", models.PolicyAccessMode.Aggregate)

    resolved = policy_engine.resolve_document_access(db_session, READER_ID, "policy-first-doc")
    assert resolved["use_decision"] == relevance.USE_AGGREGATE
    assert resolved["authorization_path"] == "policy_rule"
    assert resolved["reason"] == "explicit_policy_aggregate"

    add_policy_rule(db_session, "policy-first-doc", models.PolicyAccessMode.Deny)
    denied = policy_engine.resolve_document_access(db_session, READER_ID, "policy-first-doc")
    assert denied["use_decision"] == relevance.USE_DENY
    assert denied["reason"] == "explicit_policy_deny"


def test_policy_rule_purpose_and_time_remain_document_level_only__pol_02_03_04_06(
    db_session,
) -> None:
    add_users(db_session)
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    for doc_id in ("active-rule-doc", "future-rule-doc", "expired-rule-doc", "purpose-rule-doc"):
        add_owner_document(db_session, doc_id)

    add_policy_rule(
        db_session,
        "active-rule-doc",
        models.PolicyAccessMode.Full,
        purpose="publication_review",
        valid_from=now - dt.timedelta(minutes=5),
        valid_until=now + dt.timedelta(minutes=5),
    )
    add_policy_rule(
        db_session,
        "future-rule-doc",
        models.PolicyAccessMode.Full,
        valid_from=now + dt.timedelta(minutes=5),
    )
    add_policy_rule(
        db_session,
        "expired-rule-doc",
        models.PolicyAccessMode.Full,
        valid_until=now - dt.timedelta(minutes=5),
    )
    add_policy_rule(
        db_session,
        "purpose-rule-doc",
        models.PolicyAccessMode.Full,
        purpose="action_reconstruction",
    )

    first_user = policy_engine.resolve_document_access(db_session, READER_ID, "active-rule-doc", "publication_review")
    second_user = policy_engine.resolve_document_access(db_session, OTHER_ID, "active-rule-doc", "publication_review")
    assert first_user["use_decision"] == relevance.USE_FULL
    assert second_user["use_decision"] == relevance.USE_FULL
    assert first_user["authorization_path"] == second_user["authorization_path"] == "policy_rule"

    for doc_id in ("future-rule-doc", "expired-rule-doc", "purpose-rule-doc"):
        resolved = policy_engine.resolve_document_access(
            db_session,
            READER_ID,
            doc_id,
            policy_engine.DEFAULT_DOCUMENT_PURPOSE,
        )
        assert resolved["use_decision"] == relevance.USE_DENY
        assert resolved["reason"] == "private_no_permission"

    persistent_columns = set(models.UserDocumentPermission.__table__.columns.keys())
    assert {"purpose", "valid_from", "valid_until"}.isdisjoint(persistent_columns)


def test_unlimited_grant_preserves_legacy_behavior__ql_01(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "unlimited-doc")
    relation = policy_engine.grant_document_permission(
        db_session,
        owner_user_id=OWNER_ID,
        document_id="unlimited-doc",
        target_user_id=READER_ID,
        permission_type=models.PermissionType.Reader,
    )

    for request_index in range(3):
        governance = policy_engine.resolve_document_access_bulk(
            db_session,
            READER_ID,
            ["unlimited-doc"],
            policy_engine.DEFAULT_DOCUMENT_PURPOSE,
        )
        assert governance["use_decisions"]["unlimited-doc"] == relevance.USE_FULL
        assert governance["quota_limited_doc_ids"] == []
        consumed = policy_engine.consume_query_quotas_for_governance(
            db_session,
            governance,
            request_id=f"unlimited-{request_index}",
        )
        assert consumed["ok"] is True
        assert consumed["consumed_count"] == 0

    db_session.refresh(relation)
    assert relation.queries_used == 0


def test_quota_consumes_once_per_permission_and_allows_exactly_n_uses__ql_02_03_04_05(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "limited-doc")
    relation = policy_engine.grant_document_permission(
        db_session,
        owner_user_id=OWNER_ID,
        document_id="limited-doc",
        target_user_id=READER_ID,
        permission_type=models.PermissionType.Reader,
        max_queries=2,
    )
    duplicate_governance = {
        "quota_limited_doc_ids": ["limited-doc", "limited-doc"],
        "permission_ids": {"limited-doc": relation.id},
        "permission_types": {"limited-doc": models.PermissionType.Reader.value},
    }

    first = policy_engine.consume_query_quotas_for_governance(
        db_session,
        duplicate_governance,
        request_id="first-request",
    )
    second = policy_engine.consume_query_quotas_for_governance(
        db_session,
        duplicate_governance,
        request_id="second-request",
    )
    third = policy_engine.consume_query_quotas_for_governance(
        db_session,
        duplicate_governance,
        request_id="third-request",
    )

    db_session.refresh(relation)
    assert first["ok"] is True and first["consumed_count"] == 1
    assert second["ok"] is True and second["consumed_count"] == 1
    assert third["ok"] is False
    assert third["reason_code"] == policy_engine.QUERY_LIMIT_EXHAUSTED
    assert relation.queries_used == 2
    assert policy_engine.resolve_document_access(db_session, READER_ID, "limited-doc")["use_decision"] == relevance.USE_DENY


def test_diagnostics_and_inventory_do_not_consume_quota__ql_06_07(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "inventory-limited-doc", original_filename="Visible name.pdf")
    relation = policy_engine.grant_document_permission(
        db_session,
        owner_user_id=OWNER_ID,
        document_id="inventory-limited-doc",
        target_user_id=READER_ID,
        permission_type=models.PermissionType.Reader,
        max_queries=1,
    )

    diagnostic = policy_engine.resolve_document_access(db_session, READER_ID, "inventory-limited-doc")
    document_list = documents.build_document_list(READER_ID, db_session)
    chat_inventory = chat._document_inventory_rows(db_session, READER_ID)

    db_session.refresh(relation)
    assert diagnostic["use_decision"] == relevance.USE_FULL
    assert len(document_list["documents"]) == 1
    assert len(chat_inventory) == 1
    assert relation.queries_used == 0


def test_exhausted_grant_does_not_override_independent_policy_authorization__ql_09(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "exhausted-with-policy-doc")
    add_permission(
        db_session,
        READER_ID,
        "exhausted-with-policy-doc",
        models.PermissionType.Reader,
        max_queries=1,
        queries_used=1,
    )
    add_policy_rule(db_session, "exhausted-with-policy-doc", models.PolicyAccessMode.Full)

    resolved = policy_engine.resolve_document_access(db_session, READER_ID, "exhausted-with-policy-doc")
    assert resolved["use_decision"] == relevance.USE_FULL
    assert resolved["authorization_path"] == "policy_rule"


def test_query_limit_and_policy_projection_do_not_leak_restricted_identifiers__ql_10_sec_04(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "secret-quota-doc", original_filename="Secret Budget.pdf")
    relation = add_permission(
        db_session,
        READER_ID,
        "secret-quota-doc",
        models.PermissionType.Reader,
        max_queries=1,
        queries_used=1,
    )
    governance = policy_engine.resolve_document_access_bulk(
        db_session,
        READER_ID,
        ["secret-quota-doc"],
        policy_engine.DEFAULT_DOCUMENT_PURPOSE,
    )
    cf = controlled_failure.make_controlled_failure(
        controlled_failure.STATUS_REFUSE,
        controlled_failure.REASON_GOVERNANCE,
        controlled_failure.evidence_state([], {}, False),
        controlled_failure.safe_policy_state(governance),
        "The request cannot be answered from the sources available for this purpose.",
        [],
        {"gate": "query_limit", "reason_code": policy_engine.QUERY_LIMIT_EXHAUSTED},
    )

    public_governance = chat._public_governance_context(governance)
    payload = chat.controlled_failure_payload(
        cf["safeOutput"],
        {},
        governance,
        {"decision": "controlled_failure", "controlled_failure": cf},
        cf,
        [],
    )
    serialized = json.dumps({"governance": public_governance, "payload": payload}, sort_keys=True)
    assert "secret-quota-doc" not in serialized
    assert relation.id not in serialized
    assert "Secret Budget.pdf" not in serialized
    assert "queries_used" not in serialized
    assert public_governance["usable_source_count"] == 0


def test_explainability_gate_accepts_traceable_full_and_rejects_untraceable_full__ex_02_03_05_sec_03(
) -> None:
    document = models.Document(
        id="traceable-doc",
        file_path="traceable.pdf",
        original_filename="traceable.pdf",
        source_storage_path="traceable-doc/source.pdf",
        source_status="ACTIVE",
    )
    traceable_chunk = models.DocumentChunk(
        id=_id("traceable-chunk"),
        document_id="traceable-doc",
        chunk_index=0,
        page_number=1,
        char_start=0,
        char_end=12,
        text_content="Traceable text",
        content_sha256="a" * 64,
        vector_id="traceable-vector",
    )
    legacy_chunk = models.DocumentChunk(
        id=_id("legacy-chunk"),
        document_id="traceable-doc",
        chunk_index=1,
        page_number=None,
        text_content="Legacy text",
        vector_id="legacy-vector",
    )
    governance = {"explainability_required_doc_ids": ["traceable-doc"]}

    valid_source = {
        "document_id": "traceable-doc",
        "use_decision": relevance.USE_FULL,
        "citation": chat.citation_from_chunk(document, traceable_chunk, relevance.USE_FULL),
    }
    invalid_source = {
        "document_id": "traceable-doc",
        "use_decision": relevance.USE_FULL,
        "citation": chat.citation_from_chunk(document, legacy_chunk, relevance.USE_FULL),
    }

    assert policy_engine.evaluate_explainability_requirements(governance, [valid_source])["ok"] is True
    failed = policy_engine.evaluate_explainability_requirements(governance, [invalid_source])
    assert failed["ok"] is False
    assert failed["reason_code"] == policy_engine.EXPLAINABILITY_REQUIRED_UNSATISFIED
    assert invalid_source["citation"] == {"available": False, "reason": "traceability_unavailable"}

    for non_full_decision in (relevance.USE_AGGREGATE, relevance.USE_METADATA, relevance.USE_DENY):
        citation = chat.citation_from_chunk(document, traceable_chunk, non_full_decision)
        assert citation == {"available": False, "reason": "raw_source_not_permitted"}


def test_explainability_required_aggregate_preserves_anonymity_and_suppresses_citations__ex_06_07(
) -> None:
    contributions = [
        AggregateContribution("source-a", "person-a", 5.0),
        AggregateContribution("source-b", "person-b", 7.0),
        AggregateContribution("source-c", "person-c", 11.0),
    ]
    decisions = {
        "source-a": relevance.USE_AGGREGATE,
        "source-b": relevance.USE_AGGREGATE,
        "source-c": relevance.USE_AGGREGATE,
    }
    aggregate = execute_aggregate(contributions, decisions, AggregateConfig(k_threshold=3, operation="sum"))
    governance = {"explainability_required_doc_ids": ["source-a", "source-b", "source-c"]}
    sources = [
        {
            "document_id": source_id,
            "use_decision": relevance.USE_AGGREGATE,
            "citation": {"available": False, "reason": "raw_source_not_permitted"},
        }
        for source_id in decisions
    ]

    explainability = policy_engine.evaluate_explainability_requirements(
        governance,
        sources,
        aggregate_execution=aggregate,
    )

    assert explainability["ok"] is True
    assert aggregate["citations"] == []
    serialized_public = json.dumps(
        {
            "safe_output": aggregate["safe_output"],
            "public_trace": aggregate["public_trace"],
            "citations": aggregate["citations"],
            "explainability": policy_engine.public_explainability_state(explainability),
        },
        sort_keys=True,
    )
    for restricted in ("source-a", "source-b", "source-c", "person-a", "person-b", "person-c"):
        assert restricted not in serialized_public


def test_metadata_explainability_stays_metadata_only__perm_meta_01_02_03_ex_08_sec_06(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(
        db_session,
        "metadata-doc",
        original_filename="Metadata Only.pdf",
        text="SECRET BODY VALUE",
    )
    add_permission(db_session, READER_ID, "metadata-doc", models.PermissionType.Metadata, requires_explainability=True)

    governance = policy_engine.resolve_document_access_bulk(
        db_session,
        READER_ID,
        ["metadata-doc"],
        policy_engine.DEFAULT_DOCUMENT_PURPOSE,
    )
    source = chat.metadata_only_source(db_session, "metadata-doc")
    explainability = policy_engine.evaluate_explainability_requirements(governance, [source])

    serialized = json.dumps(source, sort_keys=True)
    assert governance["use_decisions"]["metadata-doc"] == relevance.USE_METADATA
    assert governance["metadata_only_doc_ids"] == ["metadata-doc"]
    assert governance["content_doc_ids"] == []
    assert source["citation"] == {"available": False, "reason": "metadata_only_content_withheld"}
    assert explainability["ok"] is True
    assert "SECRET BODY VALUE" not in serialized
    assert "metadata-only: document content withheld" in serialized


def test_explainability_condition_is_recorded_in_document_audit_summary__ex_09(
) -> None:
    log = models.AuditLog(
        id="audit-explainability-log",
        user_id=READER_ID,
        action="CHAT_ASK",
        details=json.dumps(
            {
                "status": "success",
                "output_mode": "FULL_ANSWER",
                "question": "What is the finding?",
                "answer": "Sensitive generated body",
                "query_profile": {"purpose": policy_engine.DEFAULT_DOCUMENT_PURPOSE},
                "governance": {
                    "use_decisions": {"explain-doc": relevance.USE_FULL},
                    "source_roles": {"explain-doc": relevance.SOURCE_ROLE_PRIMARY},
                    "policy_reasons": {"explain-doc": "direct_permission_full"},
                    "authorization_paths": {"explain-doc": "persistent_permission"},
                    "explainability_required_doc_ids": ["explain-doc"],
                },
                "evidence_check": {
                    "explainability": {"required": True, "ok": True},
                    "source_excerpt": "Sensitive chunk",
                },
            }
        ),
    )

    projected = admin.serialize_document_audit_log(log, "explain-doc", ["source"])
    serialized = json.dumps(projected, sort_keys=True)
    assert projected["summary"]["document_policy"]["explainability_required"] is True
    assert projected["summary"]["question_recorded"] is True
    assert projected["summary"]["answer_recorded"] is True
    assert "Sensitive generated body" not in serialized
    assert "Sensitive chunk" not in serialized


def test_audit_access_is_owner_or_document_scoped_and_revocation_is_immediate__aud_01_02_12_13(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(db_session, "audit-doc-1")
    add_owner_document(db_session, "audit-doc-2")
    policy_engine.grant_document_permission(
        db_session,
        owner_user_id=OWNER_ID,
        document_id="audit-doc-1",
        target_user_id=AUDITOR_ID,
        permission_type=models.PermissionType.Audit,
    )

    owner_access = policy_engine.resolve_document_audit_access(db_session, OWNER_ID, "audit-doc-1")
    scoped_access = policy_engine.resolve_document_audit_access(db_session, AUDITOR_ID, "audit-doc-1")
    out_of_scope = policy_engine.resolve_document_audit_access(db_session, AUDITOR_ID, "audit-doc-2")
    assert owner_access["allowed"] is True
    assert owner_access["reason"] == "owner_audit_access"
    assert scoped_access["allowed"] is True
    assert scoped_access["reason"] == "direct_permission_audit"
    assert out_of_scope["allowed"] is False
    assert out_of_scope["reason"] == "audit_permission_required"

    assert policy_engine.revoke_document_permission(
        db_session,
        owner_user_id=OWNER_ID,
        document_id="audit-doc-1",
        target_user_id=AUDITOR_ID,
    )
    revoked = policy_engine.resolve_document_audit_access(db_session, AUDITOR_ID, "audit-doc-1")
    assert revoked["allowed"] is False
    assert revoked["reason"] == "audit_permission_required"


def test_audit_only_inventory_and_document_list_redact_metadata__aud_06(
    db_session,
) -> None:
    add_users(db_session)
    add_owner_document(
        db_session,
        "audit-inventory-doc",
        original_filename="Private M&A Plan.pdf",
        text="Confidential transaction details",
    )
    keyword = models.Keyword(id=1, word="private-deal")
    db_session.add(keyword)
    db_session.flush()
    db_session.add(models.DocumentKeyword(document_id="audit-inventory-doc", keyword_id=keyword.id))
    add_permission(db_session, AUDITOR_ID, "audit-inventory-doc", models.PermissionType.Audit)
    db_session.flush()

    document_list = documents.build_document_list(AUDITOR_ID, db_session)
    chat_inventory = chat._document_inventory_rows(db_session, AUDITOR_ID)

    serialized = json.dumps(document_list, sort_keys=True)
    assert chat_inventory == []
    assert document_list["documents"][0]["file_name"] == "[audit-only document]"
    assert document_list["documents"][0]["keywords"] == []
    assert "Private M&A Plan.pdf" not in serialized
    assert "private-deal" not in serialized
    assert "Confidential transaction details" not in serialized


def test_audit_projection_redacts_raw_text_answers_values_and_paths__aud_08_09_10_11(
) -> None:
    log = models.AuditLog(
        id="audit-redaction-log",
        user_id=READER_ID,
        action="CHAT_ASK",
        details=json.dumps(
            {
                "status": "aggregate_result",
                "output_mode": "AGGREGATE_RESULT",
                "question": "What is the private aggregate?",
                "answer": "Sensitive generated answer body",
                "sources_used": ["Private Source.pdf"],
                "query_profile": {"purpose": policy_engine.DEFAULT_DOCUMENT_PURPOSE},
                "governance": {
                    "use_decisions": {"audit-redaction-doc": relevance.USE_AGGREGATE},
                    "source_roles": {"audit-redaction-doc": relevance.SOURCE_ROLE_AGGREGATE_ONLY},
                    "policy_reasons": {"audit-redaction-doc": "direct_permission_aggregate"},
                    "authorization_paths": {"audit-redaction-doc": "persistent_permission"},
                },
                "evidence_check": {
                    "source_excerpt": "Raw document chunk text",
                    "aggregate_execution": {
                        "individual_values": [13.37, 42.0],
                        "private_path": r"C:\private\source.pdf",
                    },
                },
            },
            sort_keys=True,
        ),
    )

    projected = admin.serialize_document_audit_log(log, "audit-redaction-doc", ["source"])
    serialized = json.dumps(projected, sort_keys=True)
    for restricted in (
        "Sensitive generated answer body",
        "Private Source.pdf",
        "Raw document chunk text",
        "13.37",
        "42.0",
        r"C:\private\source.pdf",
        READER_ID,
    ):
        assert restricted not in serialized
    assert projected["summary"]["raw_text_redacted"] is True
    assert projected["summary"]["answer_recorded"] is True
