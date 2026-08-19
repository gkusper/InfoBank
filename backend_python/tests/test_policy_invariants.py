from __future__ import annotations

import datetime as dt

import pytest

import models
import policy_engine
import relevance


USER_ID = "00000000-0000-0000-0000-000000000001"


def add_user(db) -> None:
    db.add(models.User(id=USER_ID, email="policy@example.invalid", username="policy-user", password_hash="not-used"))
    db.flush()


def add_document(db, doc_id: str, *, visibility: str = "Private") -> models.Document:
    document = models.Document(id=doc_id, file_path=f"{doc_id}.pdf", visibility=visibility)
    db.add(document)
    db.flush()
    return document


def add_permission(db, doc_id: str, permission: models.PermissionType) -> None:
    db.add(
        models.UserDocumentPermission(
            id=f"permission-{doc_id}-{permission.value}",
            user_id=USER_ID,
            document_id=doc_id,
            permission_type=permission,
        )
    )
    db.flush()


def add_rule(
    db,
    doc_id: str,
    mode: models.PolicyAccessMode,
    *,
    purpose: str = "grounded_question_answering",
    valid_from: dt.datetime | None = None,
    valid_until: dt.datetime | None = None,
) -> None:
    db.add(
        models.PolicyRule(
            id=f"rule-{doc_id}-{mode.value}-{purpose}-{valid_from}-{valid_until}",
            owner_user_id=USER_ID,
            target_type=policy_engine.TARGET_DOCUMENT,
            target_id=doc_id,
            purpose=purpose,
            access_mode=mode,
            valid_from=valid_from,
            valid_until=valid_until,
        )
    )
    db.flush()


def test_missing_document_is_denied(db_session) -> None:
    resolved = policy_engine.resolve_document_access(db_session, USER_ID, "missing")
    assert resolved["use_decision"] == relevance.USE_DENY
    assert resolved["reason"] == "document_not_found"


@pytest.mark.parametrize(
    ("permission", "expected"),
    [
        (models.PermissionType.Owner, relevance.USE_FULL),
        (models.PermissionType.Reader, relevance.USE_FULL),
        (models.PermissionType.Aggregate, relevance.USE_AGGREGATE),
        (models.PermissionType.Metadata, relevance.USE_METADATA),
    ],
)
def test_persistent_permissions_map_to_expected_query_decisions(db_session, permission, expected) -> None:
    add_user(db_session)
    add_document(db_session, "permission-doc")
    add_permission(db_session, "permission-doc", permission)
    resolved = policy_engine.resolve_document_access(db_session, USER_ID, "permission-doc")
    assert resolved["use_decision"] == expected


def test_private_document_without_permission_is_denied(db_session) -> None:
    add_user(db_session)
    add_document(db_session, "private-doc")
    resolved = policy_engine.resolve_document_access(db_session, USER_ID, "private-doc")
    assert resolved["use_decision"] == relevance.USE_DENY
    assert resolved["reason"] == "private_no_permission"


def test_explicit_deny_overrides_other_active_rules(db_session) -> None:
    add_user(db_session)
    add_document(db_session, "deny-doc")
    add_permission(db_session, "deny-doc", models.PermissionType.Owner)
    add_rule(db_session, "deny-doc", models.PolicyAccessMode.Full)
    add_rule(db_session, "deny-doc", models.PolicyAccessMode.Deny)
    resolved = policy_engine.resolve_document_access(db_session, USER_ID, "deny-doc")
    assert resolved["use_decision"] == relevance.USE_DENY
    assert resolved["reason"] == "explicit_policy_deny"


def test_inactive_purpose_future_and_expired_rules_do_not_apply(db_session) -> None:
    add_user(db_session)
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    for doc_id in ("purpose-doc", "future-doc", "expired-doc"):
        add_document(db_session, doc_id)
    add_rule(db_session, "purpose-doc", models.PolicyAccessMode.Full, purpose="action_reconstruction")
    add_rule(db_session, "future-doc", models.PolicyAccessMode.Full, valid_from=now + dt.timedelta(days=1))
    add_rule(db_session, "expired-doc", models.PolicyAccessMode.Full, valid_until=now - dt.timedelta(days=1))
    for doc_id in ("purpose-doc", "future-doc", "expired-doc"):
        resolved = policy_engine.resolve_document_access(db_session, USER_ID, doc_id, "grounded_question_answering")
        assert resolved["use_decision"] == relevance.USE_DENY
        assert resolved["reason"] == "private_no_permission"


def test_bulk_resolution_withholds_metadata_and_denied_content_deterministically(db_session) -> None:
    add_user(db_session)
    add_document(db_session, "a-denied")
    add_document(db_session, "m-metadata")
    add_document(db_session, "z-full")
    add_permission(db_session, "m-metadata", models.PermissionType.Metadata)
    add_permission(db_session, "z-full", models.PermissionType.Owner)
    doc_ids = ["z-full", "a-denied", "m-metadata", "z-full"]
    first = policy_engine.resolve_document_access_bulk(db_session, USER_ID, doc_ids, "grounded_question_answering")
    second = policy_engine.resolve_document_access_bulk(db_session, USER_ID, reversed(doc_ids), "grounded_question_answering")
    assert first == second
    assert list(first["use_decisions"]) == ["a-denied", "m-metadata", "z-full"]
    assert first["content_doc_ids"] == ["z-full"]
    assert first["metadata_only_doc_ids"] == ["m-metadata"]
    assert first["denied_doc_ids"] == ["a-denied"]
    assert "m-metadata" not in first["content_doc_ids"]
    assert "a-denied" not in first["usable_doc_ids"]
    assert "a-denied" not in first["content_doc_ids"]

    for unit_id in ("m-owned", "z-owned"):
        db_session.add(
            models.EvidenceUnit(
                id=unit_id,
                user_id=USER_ID,
                source_type=models.EvidenceSourceType.Other,
                title=unit_id,
                content="Synthetic policy-test evidence.",
                created_at=dt.datetime(2026, 8, 19, 12, 0),
            )
        )
    db_session.flush()
    unit_ids = ["z-owned", "a-missing", "m-owned", "z-owned"]
    first_units = policy_engine.resolve_evidence_unit_access_bulk(
        db_session, USER_ID, unit_ids, "action_reconstruction"
    )
    second_units = policy_engine.resolve_evidence_unit_access_bulk(
        db_session, USER_ID, reversed(unit_ids), "action_reconstruction"
    )
    assert first_units == second_units
    assert list(first_units["use_decisions"]) == ["a-missing", "m-owned", "z-owned"]
    assert first_units["content_unit_ids"] == ["m-owned", "z-owned"]
    assert first_units["denied_unit_ids"] == ["a-missing"]
