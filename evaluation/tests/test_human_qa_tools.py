from __future__ import annotations

import pytest

from evaluation.human_qa_tools import (
    agreement, export_adjudication, import_adjudication, prepare_assignments,
    validate_assignments, validate_citation_audit, validate_gold_qa,
    validate_no_health_signoff, validate_required_human_fields,
)


def _assignments() -> list[dict]:
    return prepare_assignments([f"item-{index:02d}" for index in range(10)], primary_annotators=["p1"], secondary_annotators=["s1"], seed="qa-v1")


def test_exact_twenty_percent_blinded_assignments_and_role_separation() -> None:
    rows = _assignments()
    result = validate_assignments(rows)
    assert result["status"] == "PASS" and result["secondary_count"] == 2 and result["secondary_fraction"] == 0.2
    assert all(row["primary_annotator_id"] != row["secondary_annotator_id"] for row in rows if row["secondary_annotator_id"])
    assert [row["item_id"] for row in rows] == [row["item_id"] for row in _assignments()]


def test_missing_human_field_rejected_and_machine_suggestion_never_counts() -> None:
    row = {"item_id": "one", "human_label": "", "machine_suggestion": "FULL_ANSWER"}
    result = validate_required_human_fields([row], required_fields=["human_label"])
    assert result["status"] == "PENDING" and result["complete_count"] == 0


def test_same_annotator_cannot_fill_both_roles_and_duplicates_fail() -> None:
    rows = _assignments()
    rows[0]["secondary_annotator_id"] = rows[0]["primary_annotator_id"]
    rows.append(dict(rows[1]))
    result = validate_assignments(rows)
    assert "PRIMARY_SECONDARY_NOT_SEPARATE" in result["errors"]
    assert "DUPLICATE_ITEM_ID" in result["errors"]


def test_disagreement_routes_to_adjudication_and_import_requires_human_fields() -> None:
    rows = _assignments()
    paired = [row for row in rows if row["secondary_annotator_id"]]
    paired[0].update(primary_label="A", secondary_label="B")
    paired[1].update(primary_label="A", secondary_label="A")
    pending = export_adjudication(rows)
    assert [row["item_id"] for row in pending] == [paired[0]["item_id"]]
    with pytest.raises(ValueError):
        import_adjudication(rows, pending)
    pending[0].update(adjudicator_id="adjudicator-1", adjudicated_label="A", adjudication_reason="Reviewed source evidence")
    imported = import_adjudication(rows, pending)
    assert next(row for row in imported if row["item_id"] == paired[0]["item_id"])["status"] == "ADJUDICATED"


def test_agreement_not_computed_until_all_paired_labels_complete_then_reports_both_metrics() -> None:
    rows = _assignments()
    assert agreement(rows)["status"] == "NOT_COMPUTED_INCOMPLETE_LABELS"
    for index, row in enumerate(item for item in rows if item["secondary_annotator_id"]):
        row["primary_label"] = "A"
        row["secondary_label"] = "A" if index == 0 else "B"
    result = agreement(rows)
    assert result["status"] == "COMPUTED" and result["raw_percent_agreement"] == 50.0
    assert result["cohen_kappa"] is not None and result["acceptance_threshold"] is None


def test_citation_no_health_and_gold_validators_remain_pending() -> None:
    citation = {"audit_row_id": "a1", "support_yes_no": "PENDING", "correct_page_yes_no": "PENDING", "missing_citation": "PENDING", "inaccessible_citation": "PENDING", "reviewer_id": ""}
    signoff = {"item_id": "owned-object", "signer_id": "", "decision": "PENDING", "signed_at": ""}
    gold = {"query_id": "q1", "reviewer_decision": "PENDING_HUMAN_REVIEW"}
    assert validate_citation_audit([citation])["status"] == "PENDING"
    assert validate_no_health_signoff([signoff])["status"] == "PENDING"
    assert validate_gold_qa([gold])["status"] == "PENDING"
