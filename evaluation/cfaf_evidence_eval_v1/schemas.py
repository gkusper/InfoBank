from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

EntityBindingStatus = Literal["MATCHED", "MISMATCHED", "MISSING", "NOT_APPLICABLE"]
SupportStatus = Literal[
    "SUPPORTED",
    "INSUFFICIENT",
    "CONTRADICTED",
    "UNRESOLVED",
    "NOT_EVALUATED",
]
AnnotatorStatus = Literal["APPROVED", "PENDING", "REJECTED"]


class QueryAnchor(BaseModel):
    requirement_id: str | None = None
    start: int | None = None
    end: int | None = None
    snippet: str | None = None
    valid: bool
    error: str | None = None


class DocumentRef(BaseModel):
    source_id: str
    span_id: str | None = None
    start: int | None = None
    end: int | None = None
    quote: str | None = None
    matched_snippet: str | None = None
    content_sha256: str | None = None
    valid: bool
    error: str | None = None


class EntityBinding(BaseModel):
    status: EntityBindingStatus
    claim_entity_id: str | None = None
    source_entity_ids: dict[str, str | None] = Field(default_factory=dict)
    error: str | None = None


class SystemClaimRecord(BaseModel):
    case_id: str
    requirement_id: str
    claim_id: str | None = None
    query_anchor: QueryAnchor
    document_refs: list[DocumentRef] = Field(default_factory=list)
    entity_binding: EntityBinding
    support_status: SupportStatus
    runtime_error: str | None = None


class HumanAnnotationRecord(BaseModel):
    case_id: str
    requirement_id: str
    claim_id: str | None = None
    expected_query_anchor_valid: bool
    expected_document_refs_valid: bool
    expected_entity_binding: EntityBindingStatus
    expected_support_status: SupportStatus
    annotator_status: AnnotatorStatus = "APPROVED"


class DimensionMetrics(BaseModel):
    evaluated_count: int
    correct_count: int
    accuracy: float | None


class CaseMismatchDetail(BaseModel):
    case_id: str
    requirement_id: str
    claim_id: str | None = None
    dimension: str
    expected: str | bool
    actual: str | bool


class EvaluationReport(BaseModel):
    evaluator_version: str = "cfaf_evidence_eval_v1"
    total_system_records: int
    total_annotations: int
    evaluated_records: int
    missing_annotations: int
    unapproved_annotations: int
    unmatched_annotations: int
    runtime_errors: int
    runtime_error_codes: dict[str, int]
    metrics: dict[str, DimensionMetrics]
    mismatches: list[CaseMismatchDetail] = Field(default_factory=list)
