from __future__ import annotations

from backend_python.action_closure import (
    CLOSED_CANCELLED,
    CLOSED_COMPLETED,
    OPEN,
    SUPERSEDED,
    MessageEvidence,
    classify_event,
    normalized_action_key,
    reconstruct_actions,
)


def message(identifier: str, body: str, *, thread: str = "thread-1", source: str = "Email", timestamp: str | None = None) -> MessageEvidence:
    return MessageEvidence(
        evidence_id=identifier,
        source_type=source,
        timestamp=timestamp or f"2026-08-19T10:{identifier[-1]}0:00Z",
        sender="sender@example.invalid",
        recipients=("recipient@example.invalid",),
        subject="Review synthetic package",
        body=body,
        thread_id=thread,
    )


def test_normalized_action_key_and_event_vocabulary() -> None:
    assert normalized_action_key("Please review the synthetic package") == "review synthetic package"
    assert classify_event(message("m1", "Please review this.")) == "request"
    assert classify_event(message("m2", "I will review it.")) == "acceptance"
    assert classify_event(message("m3", "Status update: in progress.")) == "status_update"
    assert classify_event(message("m4", "The request is postponed.")) == "postponement"
    assert classify_event(message("m5", "Reminder to review.")) == "reminder"
    assert classify_event(message("m6", "Received and acknowledged.")) == "acknowledgement"


def test_completion_cancellation_and_supersession_have_explicit_states() -> None:
    scenarios = [
        ("completed", CLOSED_COMPLETED),
        ("cancelled", CLOSED_CANCELLED),
        ("superseded by the new request instead", SUPERSEDED),
    ]
    for index, (closure, expected) in enumerate(scenarios):
        result = reconstruct_actions([
            message(f"r{index}", "Please review this.", thread=f"t-{index}", timestamp="2026-08-19T10:00:00Z"),
            message(f"c{index}", closure, thread=f"t-{index}", timestamp="2026-08-19T11:00:00Z"),
        ])
        assert len(result["actions"]) == 1
        assert result["actions"][0]["status"] == expected


def test_acceptance_postponement_reminder_and_status_do_not_close_action() -> None:
    result = reconstruct_actions([
        message("e1", "Please review this.", timestamp="2026-08-19T10:00:00Z"),
        message("e2", "I will review it.", timestamp="2026-08-19T11:00:00Z"),
        message("e3", "Status update: working on it.", timestamp="2026-08-19T12:00:00Z"),
        message("e4", "Postponed to a later date.", timestamp="2026-08-19T13:00:00Z"),
        message("e5", "Reminder: review it.", timestamp="2026-08-19T14:00:00Z"),
    ])
    assert result["actions"][0]["status"] == OPEN
    assert set(result["actions"][0]["event_types"]) >= {"request", "acceptance", "status_update", "postponement", "reminder"}


def test_browser_history_alone_never_creates_action() -> None:
    result = reconstruct_actions([
        message("b1", "Please review comparison page", source="BrowserHistory", thread="browser"),
        message("b2", "Reminder task page", source="ActivityTrace", thread="browser"),
    ])
    assert result["actions"] == []
    assert result["browser_only_false_actions"] == 0
    assert result["contextual_only_evidence_ids"] == ["b1", "b2"]


def test_participant_temporal_and_semantic_secondary_linking() -> None:
    request = message("p1", "Please review synthetic package delta.", thread=None, timestamp="2026-08-19T10:00:00Z")
    completion = MessageEvidence(
        evidence_id="p2", source_type="Email", timestamp="2026-08-19T11:00:00Z",
        sender="recipient@example.invalid", recipients=("sender@example.invalid",),
        subject="Synthetic package delta", body="Completed the review.", thread_id=None,
    )
    result = reconstruct_actions([request, completion])
    assert result["actions"][0]["status"] == CLOSED_COMPLETED
    assert "participant_temporal_semantic" in result["actions"][0]["link_signals"]
