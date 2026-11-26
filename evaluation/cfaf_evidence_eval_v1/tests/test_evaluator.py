from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest
from pydantic import TypeAdapter
from evaluation.cfaf_evidence_eval_v1.evaluator import evaluate_records
from evaluation.cfaf_evidence_eval_v1.schemas import (
    DocumentRef,
    EntityBinding,
    HumanAnnotationRecord,
    QueryAnchor,
    SystemClaimRecord,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_evaluate_synthetic_fixtures() -> None:
    sys_adapter = TypeAdapter(list[SystemClaimRecord])
    ann_adapter = TypeAdapter(list[HumanAnnotationRecord])

    sys_records = sys_adapter.validate_json(
        (FIXTURES_DIR / "synthetic_system_outputs.json").read_text(encoding="utf-8")
    )
    annotations = ann_adapter.validate_json(
        (FIXTURES_DIR / "synthetic_annotations.json").read_text(encoding="utf-8")
    )

    report = evaluate_records(sys_records, annotations)

    assert report.total_system_records == 5
    assert report.total_annotations == 4
    assert report.evaluated_records == 3
    assert report.missing_annotations == 1
    assert report.unapproved_annotations == 0
    assert report.unmatched_annotations == 0
    assert report.runtime_errors == 1
    assert report.runtime_error_codes == {"PROVIDER_TIMEOUT": 1}

    assert report.metrics["requirement_recognition"].accuracy == 1.0
    assert report.metrics["reference_validity"].accuracy == 1.0
    assert report.metrics["entity_binding"].accuracy == 1.0
    assert report.metrics["support_status"].accuracy == 1.0
    assert report.mismatches == []


def test_mismatches_unmatched_unapproved_and_pr2_nullable_fields() -> None:
    sys_records = [
        # Abstention record from PR2 (claim_id=None, nullable ref/entity fields)
        SystemClaimRecord(
            case_id="c-abst",
            requirement_id="req-1",
            claim_id=None,
            query_anchor=QueryAnchor(requirement_id="req-1", start=0, end=10, snippet="Who leads?", valid=True),
            document_refs=[],
            entity_binding=EntityBinding(status="NOT_APPLICABLE", source_entity_ids={"view-0001": None}),
            support_status="INSUFFICIENT",
            runtime_error=None,
        ),
        # Mismatch on entity_binding and support_status, plus rejected citation with null span_id
        SystemClaimRecord(
            case_id="c-mis",
            requirement_id="req-1",
            claim_id="c1",
            query_anchor=QueryAnchor(requirement_id="req-1", start=None, end=None, snippet=None, valid=False, error="INVALID_QUERY_SPAN"),
            document_refs=[DocumentRef(source_id="view-0001", span_id=None, quote="bad quote", valid=False, error="QUOTE_NOT_FOUND")],
            entity_binding=EntityBinding(status="MATCHED", claim_entity_id="e1", source_entity_ids={"view-0001": "e1"}),
            support_status="SUPPORTED",
            runtime_error=None,
        ),
        # Pending annotation should be skipped into unapproved_annotations
        SystemClaimRecord(
            case_id="c-pend",
            requirement_id="req-1",
            claim_id="c1",
            query_anchor=QueryAnchor(valid=True),
            document_refs=[],
            entity_binding=EntityBinding(status="NOT_APPLICABLE"),
            support_status="INSUFFICIENT",
        ),
        # Unannotated runtime error must still increment runtime_errors AND missing_annotations
        SystemClaimRecord(
            case_id="c-crash",
            requirement_id="req-1",
            claim_id="c1",
            query_anchor=QueryAnchor(valid=False),
            document_refs=[],
            entity_binding=EntityBinding(status="NOT_APPLICABLE"),
            support_status="NOT_EVALUATED",
            runtime_error="STALE_ENTITY_BINDING",
        ),
    ]
    annotations = [
        HumanAnnotationRecord(
            case_id="c-abst",
            requirement_id="req-1",
            claim_id=None,
            expected_query_anchor_valid=True,
            expected_document_refs_valid=False,
            expected_entity_binding="NOT_APPLICABLE",
            expected_support_status="INSUFFICIENT",
            annotator_status="APPROVED",
        ),
        HumanAnnotationRecord(
            case_id="c-mis",
            requirement_id="req-1",
            claim_id="c1",
            expected_query_anchor_valid=True,
            expected_document_refs_valid=True,
            expected_entity_binding="MISMATCHED",
            expected_support_status="UNRESOLVED",
            annotator_status="APPROVED",
        ),
        HumanAnnotationRecord(
            case_id="c-pend",
            requirement_id="req-1",
            claim_id="c1",
            expected_query_anchor_valid=True,
            expected_document_refs_valid=False,
            expected_entity_binding="NOT_APPLICABLE",
            expected_support_status="INSUFFICIENT",
            annotator_status="PENDING",
        ),
        # Unmatched approved annotation: system completely missed this requirement
        HumanAnnotationRecord(
            case_id="c-missed-req",
            requirement_id="req-2",
            claim_id="c2",
            expected_query_anchor_valid=True,
            expected_document_refs_valid=True,
            expected_entity_binding="MATCHED",
            expected_support_status="SUPPORTED",
            annotator_status="APPROVED",
        ),
    ]

    report = evaluate_records(sys_records, annotations)
    assert report.evaluated_records == 2
    assert report.missing_annotations == 1
    assert report.unapproved_annotations == 1
    assert report.unmatched_annotations == 1
    assert report.runtime_errors == 1
    assert report.runtime_error_codes == {"STALE_ENTITY_BINDING": 1}

    # requirement_recognition: 1 correct out of (2 evaluated + 1 unmatched = 3)
    assert report.metrics["requirement_recognition"].evaluated_count == 3
    assert report.metrics["requirement_recognition"].correct_count == 1
    assert report.metrics["requirement_recognition"].accuracy == round(1 / 3, 4)

    assert report.metrics["reference_validity"].accuracy == 0.5
    assert report.metrics["entity_binding"].accuracy == 0.5
    assert report.metrics["support_status"].accuracy == 0.5
    assert len(report.mismatches) == 4


def test_duplicate_annotation_keys_raise_error() -> None:
    dup = HumanAnnotationRecord(
        case_id="c1",
        requirement_id="req-1",
        claim_id="c1",
        expected_query_anchor_valid=True,
        expected_document_refs_valid=True,
        expected_entity_binding="MATCHED",
        expected_support_status="SUPPORTED",
    )
    with pytest.raises(ValueError, match="Duplicate annotation key"):
        evaluate_records([], [dup, dup])


def test_cli_reproducibility_and_jsonl(tmp_path: Path) -> None:
    out_json_1 = tmp_path / "report1.json"
    out_json_2 = tmp_path / "report2.json"
    out_md = tmp_path / "report.md"

    # Also write JSONL copy of synthetic inputs to verify JSONL loader
    raw_inputs = json.loads((FIXTURES_DIR / "synthetic_system_outputs.json").read_text(encoding="utf-8"))
    jsonl_inputs = tmp_path / "inputs.jsonl"
    jsonl_inputs.write_text("\n".join(json.dumps(item) for item in raw_inputs) + "\n", encoding="utf-8")

    base_cmd = [
        sys.executable,
        "-m",
        "evaluation.cfaf_evidence_eval_v1.run_eval",
        "--inputs",
        str(FIXTURES_DIR / "synthetic_system_outputs.json"),
        "--annotations",
        str(FIXTURES_DIR / "synthetic_annotations.json"),
    ]

    subprocess.run([*base_cmd, "--out", str(out_json_1), "--md-out", str(out_md)], check=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation.cfaf_evidence_eval_v1.run_eval",
            "--inputs",
            str(jsonl_inputs),
            "--annotations",
            str(FIXTURES_DIR / "synthetic_annotations.json"),
            "--out",
            str(out_json_2),
        ],
        check=True,
    )

    assert out_json_1.read_text(encoding="utf-8") == out_json_2.read_text(encoding="utf-8")
    assert out_md.exists()

    parsed = json.loads(out_json_1.read_text(encoding="utf-8"))
    assert parsed["evaluated_records"] == 3
    assert parsed["missing_annotations"] == 1
    assert parsed["runtime_errors"] == 1
