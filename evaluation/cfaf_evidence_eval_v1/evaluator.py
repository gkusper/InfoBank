from __future__ import annotations

from collections import Counter
from .schemas import (
    CaseMismatchDetail,
    DimensionMetrics,
    EvaluationReport,
    HumanAnnotationRecord,
    SystemClaimRecord,
)


def _build_metric(correct: int, total: int) -> DimensionMetrics:
    return DimensionMetrics(
        evaluated_count=total,
        correct_count=correct,
        accuracy=round(correct / total, 4) if total > 0 else None,
    )


def evaluate_records(
    system_records: list[SystemClaimRecord],
    annotations: list[HumanAnnotationRecord],
) -> EvaluationReport:
    ann_index: dict[tuple[str, str, str | None], HumanAnnotationRecord] = {}
    for ann in annotations:
        key = (ann.case_id, ann.requirement_id, ann.claim_id)
        if key in ann_index:
            raise ValueError(f"Duplicate annotation key: {key}")
        ann_index[key] = ann

    seen_ann_keys: set[tuple[str, str, str | None]] = set()

    missing_annotations = 0
    unapproved_annotations = 0
    runtime_errors = 0
    runtime_error_codes: Counter[str] = Counter()

    evaluated_count = 0
    req_rec_correct = 0
    ref_val_correct = 0
    ent_bind_correct = 0
    sup_stat_correct = 0
    mismatches: list[CaseMismatchDetail] = []

    for rec in system_records:
        key = (rec.case_id, rec.requirement_id, rec.claim_id)
        ann = ann_index.get(key)

        if rec.runtime_error is not None:
            runtime_errors += 1
            runtime_error_codes[rec.runtime_error] += 1
            if ann is None:
                missing_annotations += 1
            else:
                seen_ann_keys.add(key)
            continue

        if ann is None:
            missing_annotations += 1
            continue

        seen_ann_keys.add(key)

        if ann.annotator_status != "APPROVED":
            unapproved_annotations += 1
            continue

        evaluated_count += 1

        docs_valid = (
            all(ref.valid for ref in rec.document_refs)
            if len(rec.document_refs) > 0
            else False
        )
        query_ok = rec.query_anchor.valid == ann.expected_query_anchor_valid
        docs_ok = docs_valid == ann.expected_document_refs_valid

        if query_ok:
            req_rec_correct += 1

        if query_ok and docs_ok:
            ref_val_correct += 1
        else:
            if not query_ok:
                mismatches.append(
                    CaseMismatchDetail(
                        case_id=rec.case_id,
                        requirement_id=rec.requirement_id,
                        claim_id=rec.claim_id,
                        dimension="query_anchor_valid",
                        expected=ann.expected_query_anchor_valid,
                        actual=rec.query_anchor.valid,
                    )
                )
            if not docs_ok:
                mismatches.append(
                    CaseMismatchDetail(
                        case_id=rec.case_id,
                        requirement_id=rec.requirement_id,
                        claim_id=rec.claim_id,
                        dimension="document_refs_valid",
                        expected=ann.expected_document_refs_valid,
                        actual=docs_valid,
                    )
                )

        if rec.entity_binding.status == ann.expected_entity_binding:
            ent_bind_correct += 1
        else:
            mismatches.append(
                CaseMismatchDetail(
                    case_id=rec.case_id,
                    requirement_id=rec.requirement_id,
                    claim_id=rec.claim_id,
                    dimension="entity_binding",
                    expected=ann.expected_entity_binding,
                    actual=rec.entity_binding.status,
                )
            )

        if rec.support_status == ann.expected_support_status:
            sup_stat_correct += 1
        else:
            mismatches.append(
                CaseMismatchDetail(
                    case_id=rec.case_id,
                    requirement_id=rec.requirement_id,
                    claim_id=rec.claim_id,
                    dimension="support_status",
                    expected=ann.expected_support_status,
                    actual=rec.support_status,
                )
            )

    unmatched_annotations = sum(
        1
        for k, ann in ann_index.items()
        if k not in seen_ann_keys and ann.annotator_status == "APPROVED"
    )
    req_rec_total = evaluated_count + unmatched_annotations

    return EvaluationReport(
        total_system_records=len(system_records),
        total_annotations=len(annotations),
        evaluated_records=evaluated_count,
        missing_annotations=missing_annotations,
        unapproved_annotations=unapproved_annotations,
        unmatched_annotations=unmatched_annotations,
        runtime_errors=runtime_errors,
        runtime_error_codes=dict(sorted(runtime_error_codes.items())),
        metrics={
            "requirement_recognition": _build_metric(req_rec_correct, req_rec_total),
            "reference_validity": _build_metric(ref_val_correct, evaluated_count),
            "entity_binding": _build_metric(ent_bind_correct, evaluated_count),
            "support_status": _build_metric(sup_stat_correct, evaluated_count),
        },
        mismatches=mismatches,
    )
