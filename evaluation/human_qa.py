"""Generate pending human-QA work packages without fabricating decisions."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .actual_pipeline_gold import load_gold_annotations
from .reviewer_v2_candidate import build_gold_queries


PENDING_REVIEW = "PENDING_HUMAN_REVIEW"
PENDING_AUDIT = "PENDING_HUMAN_AUDIT"
PENDING_SIGNOFF = "PENDING_HUMAN_SIGNOFF"


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _stratum(case_id: str, expected_class: str, gold_document_count: int) -> str:
    numeric = int(case_id.rsplit("-", 1)[-1]) if case_id.rsplit("-", 1)[-1].isdigit() else -1
    if numeric in {15, 16}:
        return "wrong_object"
    if expected_class == "FULL_ANSWER":
        return "multi_document" if gold_document_count > 1 else "direct_answer"
    if expected_class in {"CONSTRAINED_ANSWER", "REFUSE_CONFLICT"}:
        return "constrained_conflict"
    if expected_class == "METADATA_ONLY":
        return "metadata"
    if expected_class in {"AGGREGATE_RESULT", "REFUSE_AGGREGATION_THRESHOLD"}:
        return "aggregate"
    if expected_class == "REFUSE_PERMISSION":
        return "permission_refusal"
    return "no_answer"


def build_human_qa_package(
    *,
    output_dir: Path,
    actual_gold_path: Path,
    actual_raw_run_paths: Iterable[Path],
    mailex_candidate_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to mix human-QA output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    owned_rows = []
    for item in build_gold_queries():
        owned_rows.append({
            "query_id": item["query_id"],
            "query_text": item["query"],
            "expected_output_class": item["expected_output_class"],
            "reason_code": item["reason_code"],
            "gold_document_ids": json.dumps(item["gold_document_ids"], sort_keys=True),
            "gold_page_ranges": json.dumps(item["gold_page_or_message_ranges"], sort_keys=True),
            "reference_answer_or_factual_atoms": item.get("reference_answer") or "",
            "evidence_role": item["evidence_role"],
            "reviewer_decision": PENDING_REVIEW,
            "corrected_output_class": "",
            "corrected_reason_code": "",
            "corrected_document_ids": "",
            "corrected_page_ranges": "",
            "corrected_reference_answer": "",
            "notes": "",
        })
    _write_csv(output_dir / "owned_object_gold_qa.csv", owned_rows, list(owned_rows[0]))

    gold = load_gold_annotations(actual_gold_path)
    gold_by_id = {item.case_id: item for item in gold}
    citation_rows: list[dict[str, Any]] = []
    for run_index, raw_path in enumerate(actual_raw_run_paths, start=1):
        records = [item for item in _load_jsonl(raw_path) if item.get("mode") == "C3_FULL_ROLE_AWARE"]
        for record in records:
            annotation = gold_by_id[record["case_id"]]
            citations = record.get("actual_citations") or []
            claim_units = [item.strip() for item in re.split(r"(?<=[.!?])\s+", record.get("actual_output_text") or "") if item.strip()]
            source_refs = [item.get("source_view_url") for item in citations if item.get("source_view_url")]
            citation_rows.append({
                "audit_row_id": f"citation-audit-{run_index:02d}-{record['case_id']}",
                "run_index": run_index,
                "case_id": record["case_id"],
                "selection_stratum": _stratum(record["case_id"], annotation.expected_output_class, len(annotation.gold_document_ids)),
                "answer_text": record.get("actual_output_text") or "",
                "claim_units": json.dumps(claim_units, ensure_ascii=False),
                "cited_document_page_chunk": json.dumps(citations, ensure_ascii=False, sort_keys=True),
                "rendered_source_excerpt_reference": json.dumps(source_refs, sort_keys=True),
                "support_yes_no": "PENDING",
                "correct_page_yes_no": "PENDING",
                "missing_citation": "PENDING",
                "inaccessible_citation": "PENDING",
                "reviewer_id": "",
                "human_notes": "",
                "review_status": PENDING_AUDIT,
            })
    citation_rows = sorted(citation_rows, key=lambda item: item["audit_row_id"])
    if len(citation_rows) != 40:
        raise RuntimeError(f"Expected exactly 40 deterministic citation-audit rows, got {len(citation_rows)}")
    _write_csv(output_dir / "citation_audit_40.csv", citation_rows, list(citation_rows[0]))

    required_strata = {
        "direct_answer",
        "constrained_conflict",
        "metadata",
        "aggregate",
        "no_answer",
        "permission_refusal",
        "wrong_object",
    }
    actual_strata = {item["selection_stratum"] for item in citation_rows}
    if not required_strata <= actual_strata:
        raise RuntimeError(f"Citation audit is missing strata: {sorted(required_strata - actual_strata)}")

    mail_manifest = json.loads((mailex_candidate_dir / "candidate_manifest.json").read_text(encoding="utf-8"))
    checklist = (
        "# Manual no-health sign-off\n\n"
        f"Status: {PENDING_SIGNOFF}\n\n"
        "Reviewer: __________\n\nDate: __________\n\n"
        "- [ ] All owned-object PDFs reviewed.\n"
        f"- [ ] All {mail_manifest['selected_thread_count']} pseudonymized MailEx candidate threads reviewed.\n"
        "- [ ] All reviewer screenshots reviewed.\n"
        "- [ ] All example traces reviewed.\n"
        "- [ ] All publication-facing result excerpts reviewed.\n\n"
        "Decision: __________\n\nNotes: __________\n"
    )
    (output_dir / "manual_no_health_signoff.md").write_text(checklist, encoding="utf-8")
    status = {
        "status": "READY_FOR_HUMAN_QA_NOT_COMPLETE",
        "owned_object_gold_rows": len(owned_rows),
        "citation_audit_rows": len(citation_rows),
        "citation_audit_strata": sorted(actual_strata),
        "mailex_primary_annotation_rows": mail_manifest["primary_annotation_count"],
        "mailex_second_annotation_rows": mail_manifest["second_annotation_count"],
        "licence_status": mail_manifest["licence_status"],
        "human_gold_qa_complete": False,
        "human_citation_audit_complete": False,
        "human_mail_annotation_complete": False,
        "agreement_calculated": False,
        "adjudication_complete": False,
        "manual_no_health_signoff_complete": False,
    }
    (output_dir / "human_qa_status.json").write_text(json.dumps(status, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return status
