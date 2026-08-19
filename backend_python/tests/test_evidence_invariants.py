from __future__ import annotations

import datetime as dt
import json

import evidence_service
import models


USER_ID = "00000000-0000-0000-0000-000000000002"


def add_user(db) -> None:
    db.add(models.User(id=USER_ID, email="evidence@example.invalid", username="evidence-user", password_hash="not-used"))
    db.flush()


def add_unit(
    db,
    unit_id: str,
    source_type: models.EvidenceSourceType,
    content: str,
    relation_key: str,
    timestamp: dt.datetime,
    *,
    metadata: dict | None = None,
) -> models.EvidenceUnit:
    unit = models.EvidenceUnit(
        id=unit_id,
        user_id=USER_ID,
        source_type=source_type,
        title=unit_id,
        content=content,
        source_timestamp=timestamp,
        relation_key=relation_key,
        metadata_json=json.dumps(metadata or {}),
        created_at=timestamp,
    )
    db.add(unit)
    db.flush()
    return unit


def test_browser_history_only_cannot_create_action(db_session) -> None:
    add_user(db_session)
    add_unit(
        db_session,
        "browser-only",
        models.EvidenceSourceType.BrowserHistory,
        "Visited a budget review dashboard.",
        "budget-review",
        dt.datetime(2026, 8, 20, 9, 0),
    )
    result = evidence_service.reconstruct_action_list(db_session, USER_ID)
    assert result["open_items"] == []
    assert result["closed_items"] == []
    assert len(result["contextual_only"]) == 1


def test_primary_evidence_creates_action_and_context_cannot_replace_it(db_session) -> None:
    add_user(db_session)
    add_unit(
        db_session,
        "primary",
        models.EvidenceSourceType.Email,
        "Please review the budget by 2026-08-25.",
        "budget-review",
        dt.datetime(2026, 8, 20, 9, 0),
    )
    add_unit(
        db_session,
        "context",
        models.EvidenceSourceType.BrowserHistory,
        "Visited the budget dashboard for background information.",
        "budget-review",
        dt.datetime(2026, 8, 20, 10, 0),
    )
    result = evidence_service.reconstruct_action_list(db_session, USER_ID)
    assert len(result["open_items"]) == 1
    action = result["open_items"][0]
    assert action["status"] == "open"
    assert action["R"]["primary"] == 1
    assert action["R"]["contextual"] == 1
    assert action["evidence"]["primary"][0]["id"] == "primary"


def test_linked_later_contrastive_evidence_closes_action(db_session) -> None:
    add_user(db_session)
    add_unit(
        db_session,
        "primary",
        models.EvidenceSourceType.Email,
        "Please review the budget by 2026-08-25.",
        "budget-review",
        dt.datetime(2026, 8, 20, 9, 0),
    )
    add_unit(
        db_session,
        "closure",
        models.EvidenceSourceType.Email,
        "Completed the budget review and sent the result.",
        "budget-review",
        dt.datetime(2026, 8, 21, 9, 0),
    )
    result = evidence_service.reconstruct_action_list(db_session, USER_ID)
    assert result["open_items"] == []
    assert len(result["closed_items"]) == 1
    assert result["closed_items"][0]["R"]["contrastive"] == 1


def test_unrelated_or_earlier_contrastive_evidence_does_not_close_action(db_session) -> None:
    add_user(db_session)
    add_unit(
        db_session,
        "primary",
        models.EvidenceSourceType.Email,
        "Please review the budget by 2026-08-25.",
        "budget-review",
        dt.datetime(2026, 8, 20, 9, 0),
    )
    add_unit(
        db_session,
        "unrelated-closure",
        models.EvidenceSourceType.Email,
        "Completed the travel booking.",
        "travel-booking",
        dt.datetime(2026, 8, 21, 9, 0),
    )
    add_unit(
        db_session,
        "earlier-closure",
        models.EvidenceSourceType.Email,
        "Completed the budget review.",
        "budget-review",
        dt.datetime(2026, 8, 19, 9, 0),
    )
    result = evidence_service.reconstruct_action_list(db_session, USER_ID)
    assert len(result["open_items"]) == 1
    assert result["closed_items"] == []


def test_repeated_processing_and_external_dedupe_are_idempotent(db_session) -> None:
    add_user(db_session)
    older = add_unit(
        db_session,
        "gmail-old",
        models.EvidenceSourceType.Email,
        "Please submit the summary.",
        "summary",
        dt.datetime(2026, 8, 20, 9, 0),
        metadata={"connector": "gmail", "message_id": "message-1"},
    )
    newer = add_unit(
        db_session,
        "gmail-new",
        models.EvidenceSourceType.Email,
        "Please submit the summary.",
        "summary",
        dt.datetime(2026, 8, 20, 10, 0),
        metadata={"connector": "gmail", "message_id": "message-1"},
    )
    assert evidence_service.dedupe_evidence_units([older, newer]) == [newer]
    first = evidence_service.reconstruct_action_list(db_session, USER_ID)
    second = evidence_service.reconstruct_action_list(db_session, USER_ID)
    assert first == second
    assert len(first["open_items"]) == 1
