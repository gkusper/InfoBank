"""Generic deterministic preparation and validation tools for pending human QA."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


TOOLS_VERSION = "infobank-human-qa-tools-v1"
PENDING = {"", "PENDING", "PENDING_HUMAN_REVIEW", "PENDING_HUMAN_AUDIT", "PENDING_HUMAN_SIGNOFF"}


def anonymized_annotator_id(value: str, *, salt: str) -> str:
    return "annotator-" + hashlib.sha256(f"{salt}|{value}".encode("utf-8")).hexdigest()[:12]


def deterministic_blinded_order(item_ids: Iterable[str], *, seed: str) -> list[str]:
    values = list(item_ids)
    if len(values) != len(set(values)):
        raise ValueError("Duplicate item IDs are not allowed")
    return sorted(values, key=lambda item_id: (hashlib.sha256(f"{seed}|{item_id}".encode()).hexdigest(), item_id))


def prepare_assignments(item_ids: Iterable[str], *, primary_annotators: list[str], secondary_annotators: list[str], seed: str, secondary_fraction: float = 0.20) -> list[dict[str, Any]]:
    ordered = deterministic_blinded_order(item_ids, seed=seed)
    if not primary_annotators or not secondary_annotators:
        raise ValueError("Primary and secondary annotator pools are required")
    exact_secondary = len(ordered) * secondary_fraction
    if int(exact_secondary) != exact_secondary:
        raise ValueError("Item count does not permit exact requested secondary coverage")
    assignments = []
    secondary_count = int(exact_secondary)
    for index, item_id in enumerate(ordered):
        primary = primary_annotators[index % len(primary_annotators)]
        secondary = secondary_annotators[index % len(secondary_annotators)] if index < secondary_count else ""
        if secondary and secondary == primary:
            raise ValueError("Primary and secondary annotator must be different")
        assignments.append({
            "blind_index": index + 1,
            "item_id": item_id,
            "primary_annotator_id": primary,
            "secondary_annotator_id": secondary,
            "primary_label": "",
            "secondary_label": "",
            "human_notes": "",
            "machine_suggestion": "",
            "status": "PENDING_HUMAN_REVIEW",
        })
    return assignments


def validate_assignments(rows: list[dict[str, Any]], *, expected_secondary_fraction: float = 0.20) -> dict[str, Any]:
    ids = [row.get("item_id", "") for row in rows]
    duplicates = sorted(item_id for item_id, count in Counter(ids).items() if item_id and count > 1)
    same_role = sorted(row["item_id"] for row in rows if row.get("secondary_annotator_id") and row.get("primary_annotator_id") == row.get("secondary_annotator_id"))
    secondary = sum(bool(row.get("secondary_annotator_id")) for row in rows)
    actual_fraction = secondary / len(rows) if rows else 0.0
    errors = []
    if not rows:
        errors.append("NO_ASSIGNMENTS")
    if any(not value for value in ids):
        errors.append("MISSING_ITEM_ID")
    if duplicates:
        errors.append("DUPLICATE_ITEM_ID")
    if same_role:
        errors.append("PRIMARY_SECONDARY_NOT_SEPARATE")
    if abs(actual_fraction - expected_secondary_fraction) > 1e-12:
        errors.append("SECONDARY_COVERAGE_MISMATCH")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "duplicate_item_ids": duplicates,
        "same_role_item_ids": same_role,
        "secondary_count": secondary,
        "secondary_fraction": actual_fraction,
        "expected_secondary_fraction": expected_secondary_fraction,
    }


def validate_required_human_fields(rows: list[dict[str, Any]], *, required_fields: list[str]) -> dict[str, Any]:
    incomplete = []
    for row in rows:
        missing = [field for field in required_fields if str(row.get(field, "")).strip() in PENDING]
        if missing:
            incomplete.append({"item_id": row.get("item_id") or row.get("query_id") or row.get("audit_row_id"), "missing": missing})
    return {"status": "COMPLETE" if not incomplete else "PENDING", "incomplete": incomplete, "complete_count": len(rows) - len(incomplete), "total_count": len(rows)}


def agreement(rows: list[dict[str, Any]], *, primary_field: str = "primary_label", secondary_field: str = "secondary_label") -> dict[str, Any]:
    paired = [row for row in rows if row.get("secondary_annotator_id")]
    incomplete = [row.get("item_id") for row in paired if str(row.get(primary_field, "")).strip() in PENDING or str(row.get(secondary_field, "")).strip() in PENDING]
    if incomplete or not paired:
        return {"status": "NOT_COMPUTED_INCOMPLETE_LABELS", "raw_percent_agreement": None, "cohen_kappa": None, "incomplete_item_ids": incomplete}
    labels = sorted({str(row[primary_field]) for row in paired} | {str(row[secondary_field]) for row in paired})
    observed = sum(row[primary_field] == row[secondary_field] for row in paired) / len(paired)
    primary_counts, secondary_counts = Counter(row[primary_field] for row in paired), Counter(row[secondary_field] for row in paired)
    expected = sum(primary_counts[label] / len(paired) * secondary_counts[label] / len(paired) for label in labels)
    kappa = 1.0 if expected == 1.0 and observed == 1.0 else ((observed - expected) / (1 - expected) if expected != 1.0 else None)
    return {"status": "COMPUTED", "pair_count": len(paired), "raw_percent_agreement": observed * 100.0, "cohen_kappa": kappa, "acceptance_threshold": None}


def export_adjudication(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "item_id": row["item_id"], "primary_label": row["primary_label"], "secondary_label": row["secondary_label"],
        "adjudicator_id": "", "adjudicated_label": "", "adjudication_reason": "", "status": "PENDING_ADJUDICATION",
    } for row in rows if row.get("secondary_annotator_id") and row.get("primary_label") not in PENDING and row.get("secondary_label") not in PENDING and row.get("primary_label") != row.get("secondary_label")]


def import_adjudication(assignments: list[dict[str, Any]], adjudications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["item_id"]: dict(row) for row in assignments}
    for decision in adjudications:
        if decision.get("item_id") not in by_id:
            raise ValueError("Adjudication item is not part of the assignment package")
        for field in ("adjudicator_id", "adjudicated_label", "adjudication_reason"):
            if str(decision.get(field, "")).strip() in PENDING:
                raise ValueError(f"Incomplete adjudication field: {field}")
        by_id[decision["item_id"]].update({key: decision[key] for key in ("adjudicator_id", "adjudicated_label", "adjudication_reason")})
        by_id[decision["item_id"]]["status"] = "ADJUDICATED"
    return [by_id[row["item_id"]] for row in assignments]


def validate_citation_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return validate_required_human_fields(rows, required_fields=["support_yes_no", "correct_page_yes_no", "missing_citation", "inaccessible_citation", "reviewer_id"])


def validate_no_health_signoff(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return validate_required_human_fields(blocks, required_fields=["signer_id", "decision", "signed_at"])


def validate_gold_qa(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return validate_required_human_fields(rows, required_fields=["reviewer_decision"])


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Refusing to write an empty package")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
