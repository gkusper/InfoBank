from __future__ import annotations

import datetime as dt
import asyncio
import json

from fastapi import BackgroundTasks

import evidence_service
import models
from action_closure import CLOSED_CANCELLED, CLOSED_COMPLETED, OPEN, SUPERSEDED
from routers import chat


USER_ID = "00000000-0000-0000-0000-000000000002"


def add_user(db) -> None:
    db.add(models.User(id=USER_ID, email="evidence@example.invalid", username="evidence-user", password_hash="not-used"))
    db.flush()


def test_null_metadata_is_normalized_before_evidence_deduplication(db_session) -> None:
    add_user(db_session)
    unit = models.EvidenceUnit(
        id="null-metadata-unit",
        user_id=USER_ID,
        source_type=models.EvidenceSourceType.Email,
        title="Synthetic support request",
        content="Action: send a diagnostic log.",
        metadata_json="null",
    )
    db_session.add(unit)
    db_session.commit()
    assert evidence_service.dedupe_evidence_units([unit]) == [unit]


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
    assert action["status"] == OPEN
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
    assert result["closed_items"][0]["status"] == CLOSED_COMPLETED
    assert result["closed_items"][0]["R"]["contrastive"] == 1


def test_runtime_action_list_uses_explicit_cancellation_and_supersession_states(db_session) -> None:
    add_user(db_session)
    scenarios = [
        ("cancelled", "The request was cancelled and is no longer needed.", CLOSED_CANCELLED),
        ("superseded", "The request was superseded by the revised request instead.", SUPERSEDED),
    ]
    for index, (suffix, closure_text, expected) in enumerate(scenarios):
        relation_key = f"runtime-{suffix}"
        add_unit(
            db_session,
            f"request-{index}",
            models.EvidenceSourceType.Email,
            "Please review the synthetic package.",
            relation_key,
            dt.datetime(2026, 8, 20, 9, index),
        )
        add_unit(
            db_session,
            f"closure-{index}",
            models.EvidenceSourceType.Email,
            closure_text,
            relation_key,
            dt.datetime(2026, 8, 21, 9, index),
        )

    result = evidence_service.reconstruct_action_list(db_session, USER_ID)
    assert result["engine_version"] == "infocom-action-closure-v1"
    assert result["closure_states"] == [OPEN, CLOSED_COMPLETED, CLOSED_CANCELLED, SUPERSEDED]
    assert {item["status"] for item in result["closed_items"]} == {CLOSED_CANCELLED, SUPERSEDED}
    assert result["actions"] == sorted(result["closed_items"], key=lambda item: item["action_id"])
    assert all(item["linked_evidence_ids"] == item["E"] for item in result["actions"])


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


def test_denied_evidence_is_indistinguishable_from_absence_in_public_action_list(db_session) -> None:
    add_user(db_session)
    add_unit(
        db_session,
        "permitted-action",
        models.EvidenceSourceType.Email,
        "Please review the public budget by 2026-08-25.",
        "public-budget",
        dt.datetime(2026, 8, 20, 9, 0),
    )
    db_session.commit()
    without_denied = evidence_service.reconstruct_action_list(db_session, USER_ID)

    add_unit(
        db_session,
        "denied-secret",
        models.EvidenceSourceType.Email,
        "TOP SECRET ACTION: transfer the hidden acquisition file by 2026-08-26.",
        "hidden-acquisition",
        dt.datetime(2026, 8, 20, 10, 0),
    )
    db_session.add(models.PolicyRule(
        id="deny-secret-rule",
        owner_user_id=USER_ID,
        target_type="EvidenceUnit",
        target_id="denied-secret",
        purpose="action_reconstruction",
        access_mode=models.PolicyAccessMode.Deny,
    ))
    db_session.commit()

    with_denied = evidence_service.reconstruct_action_list(db_session, USER_ID)
    assert with_denied == without_denied
    serialized = json.dumps(with_denied, sort_keys=True)
    assert "denied-secret" not in serialized
    assert "TOP SECRET" not in serialized
    assert "hidden acquisition" not in serialized


def test_aggregate_only_evidence_cannot_create_or_describe_individual_action(db_session) -> None:
    add_user(db_session)
    unit = add_unit(
        db_session,
        "aggregate-secret",
        models.EvidenceSourceType.Email,
        "PRIVATE ACTION: disclose an individual salary by 2026-08-27.",
        "individual-salary",
        dt.datetime(2026, 8, 20, 11, 0),
    )
    policy = {
        "use_decision": "aggregate",
        "source_role": "aggregate_only",
        "reason": "explicit_policy_aggregate",
        "policy_rule_id": "aggregate-rule",
    }
    classified = evidence_service.classify_evidence_unit(unit, policy)
    assert classified["status"] == "aggregate_only"
    assert classified["action"] is None
    assert classified["object"] is None
    serialized = json.dumps(classified, sort_keys=True)
    assert "PRIVATE ACTION" not in serialized
    assert "individual salary" not in serialized


def test_action_list_question_uses_server_side_audited_ask_workflow(db_session) -> None:
    add_user(db_session)
    add_unit(
        db_session,
        "audited-action",
        models.EvidenceSourceType.Email,
        "Please review the roadmap by 2026-08-28.",
        "roadmap-review",
        dt.datetime(2026, 8, 21, 9, 0),
    )
    db_session.commit()
    background = BackgroundTasks()
    result = asyncio.run(chat.ask_infobank(
        background,
        question="Mik a jelenlegi teendőim?",
        user_id=USER_ID,
        db=db_session,
    ))

    assert result["status"] == "success"
    assert result["output_mode"] == "FULL_ANSWER"
    assert result["audit_id"]
    assert result["query_profile"]["task_intent"] == "current_action_list"
    assert result["query_profile"]["retrieval_strategy"] == "evidence_reconstruction"
    assert "jelenlegi teendőlistád" in result["answer"]
    assert result["evidence_check"]["decision"] == "answer_allowed"
    assert result["sources"][0]["document_id"] == "audited-action"

    audit = db_session.query(models.AuditLog).filter(models.AuditLog.id == result["audit_id"]).one()
    assert audit.action == "CHAT_ASK"
    assert json.loads(audit.details)["output_mode"] == "FULL_ANSWER"


def test_browser_only_action_question_returns_server_controlled_constraint(db_session) -> None:
    add_user(db_session)
    add_unit(
        db_session,
        "browser-context",
        models.EvidenceSourceType.BrowserHistory,
        "Visited the roadmap dashboard.",
        "roadmap-review",
        dt.datetime(2026, 8, 21, 10, 0),
    )
    db_session.commit()
    result = asyncio.run(chat.ask_infobank(
        BackgroundTasks(),
        question="What is my current action list?",
        user_id=USER_ID,
        db=db_session,
    ))
    assert result["status"] == "success"
    assert result["output_mode"] == "CONSTRAINED_ANSWER"
    assert result["controlled_failure"]["trace"]["gate"] == "action_evidence_reconstruction"
    assert "cannot create an action item by itself" in result["answer"]
