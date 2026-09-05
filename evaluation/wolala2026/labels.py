from __future__ import annotations

import dataclasses
import datetime as dt
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JsonEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class StageName(JsonEnum):
    QUERY_PROFILING = "QUERY_PROFILING"
    CANDIDATE_RETRIEVAL = "CANDIDATE_RETRIEVAL"
    ACCESS_AND_SAFETY_RESOLUTION = "ACCESS_AND_SAFETY_RESOLUTION"
    EVIDENCE_LABELLING = "EVIDENCE_LABELLING"
    SUFFICIENCY_AND_PERMITTED_OUTPUT = "SUFFICIENCY_AND_PERMITTED_OUTPUT"
    TOP_LEVEL_MODE_SELECTION = "TOP_LEVEL_MODE_SELECTION"
    RESPONSE_REALIZATION = "RESPONSE_REALIZATION"
    VALIDATION_TRACE_AND_FEEDBACK = "VALIDATION_TRACE_AND_FEEDBACK"


class AccessMode(JsonEnum):
    FULL = "FULL"
    AGGREGATE = "AGGREGATE"
    METADATA = "METADATA"
    DENY = "DENY"


class ExistenceVisibility(JsonEnum):
    PUBLIC = "PUBLIC"
    OWNER_OR_AUDITOR = "OWNER_OR_AUDITOR"
    INTERNAL_ONLY = "INTERNAL_ONLY"


class EvidentialRole(JsonEnum):
    PRIMARY = "PRIMARY"
    CONTEXTUAL = "CONTEXTUAL"
    CONTRASTIVE = "CONTRASTIVE"
    IRRELEVANT = "IRRELEVANT"
    UNKNOWN = "UNKNOWN"


class EvidenceState(JsonEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    DEFEATED = "DEFEATED"
    SUPERSEDED = "SUPERSEDED"


class RelationLabel(JsonEnum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    CLOSES = "CLOSES"
    QUALIFIES = "QUALIFIES"
    NONE = "NONE"


class Disposition(JsonEnum):
    DIRECT_USE = "DIRECT_USE"
    AGGREGATE_ONLY = "AGGREGATE_ONLY"
    METADATA_ONLY = "METADATA_ONLY"
    EXCLUDED = "EXCLUDED"


class TopLevelMode(JsonEnum):
    FULL = "FULL"
    CFAF = "CFAF"


class FulfilmentStatus(JsonEnum):
    FULL = "FULL"
    RESTRICTED = "RESTRICTED"
    NONE = "NONE"
    DEFERRED = "DEFERRED"


class CFAFRealization(JsonEnum):
    RESTRICT_CONTENT = "RESTRICT_CONTENT"
    RESTRICT_GRANULARITY = "RESTRICT_GRANULARITY"
    ABSTAIN = "ABSTAIN"
    REFUSE = "REFUSE"
    CLARIFY = "CLARIFY"
    ESCALATE = "ESCALATE"


class ReasonClass(JsonEnum):
    EPISTEMIC = "EPISTEMIC"
    EVIDENTIAL = "EVIDENTIAL"
    GOVERNANCE_PRIVACY = "GOVERNANCE_PRIVACY"
    SAFETY = "SAFETY"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    OPERATIONAL_SECURITY = "OPERATIONAL_SECURITY"


class ValidationStatus(JsonEnum):
    PASS = "PASS"
    FAIL = "FAIL"


def now_utc() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class LabelRecord:
    dimension: str
    value: Any
    producer: str
    method: str
    subject: dict[str, Any]
    stage: StageName
    confidence: float | None = 1.0
    rule_id: str | None = None
    model_version: str | None = None
    timestamp: str = field(default_factory=now_utc)


@dataclass
class EvidenceCandidate:
    candidate_id: str
    source_id: str
    source_type: str
    retrieval_rank: int
    retrieval_score: float | None
    retriever_name: str
    retrieval_reason: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    access_mode: AccessMode | None = None
    existence_visibility: ExistenceVisibility = ExistenceVisibility.PUBLIC
    policy_rule_id: str | None = None
    policy_version: str | None = None
    purpose_compatibility: str | None = None
    security_status: str = "clean"
    allowed_metadata_fields: list[str] = field(default_factory=list)
    evidential_role: EvidentialRole = EvidentialRole.UNKNOWN
    evidence_state: EvidenceState = EvidenceState.CURRENT
    relation: RelationLabel = RelationLabel.NONE
    claim_id: str = "claim-1"
    disposition: Disposition | None = None
    protected_markers: list[str] = field(default_factory=list)
    aggregate_view: str | None = None


@dataclass
class ClaimAssessment:
    claim_id: str
    support_status: str
    supporting_evidence_ids: list[str]
    contrastive_evidence_ids: list[str]
    sufficient: bool
    permitted_content: str
    maximum_granularity: str
    requested_granularity: str
    can_fulfil_request: bool
    answer: str | None
    reason_class: ReasonClass | None = None
    reason_code: str | None = None
    cfaf_realization: CFAFRealization | None = None


@dataclass
class CFAFDecision:
    execution_status: str
    fulfilment_status: FulfilmentStatus
    mode: TopLevelMode
    reason_class: ReasonClass | None
    reason_code: str | None
    permitted_output: str
    public_reason: str
    next_steps: list[str]
    internal_trace_id: str
    cfaf_realization: CFAFRealization | None = None


@dataclass
class ResponseContract:
    mode: TopLevelMode
    fulfilment_status: FulfilmentStatus
    cfaf_realization: CFAFRealization | None
    allowed_claims: list[dict[str, Any]]
    allowed_evidence_views: list[dict[str, Any]]
    forbidden_fields: list[str]
    public_reason_class: ReasonClass | None
    public_reason_text: str
    allowed_next_steps: list[str]


@dataclass
class ValidationResult:
    status: ValidationStatus
    violation_codes: list[str]
    fallback_used: bool


@dataclass
class PipelineState:
    case_id: str
    query_id: str
    query: str
    query_profile: dict[str, Any] = field(default_factory=dict)
    labels: list[LabelRecord] = field(default_factory=list)
    candidates: list[EvidenceCandidate] = field(default_factory=list)
    required_claims: list[dict[str, Any]] = field(default_factory=list)
    claim_assessments: list[ClaimAssessment] = field(default_factory=list)
    mode_decision: CFAFDecision | None = None
    response_contract: ResponseContract | None = None
    generator_context: list[dict[str, Any]] = field(default_factory=list)
    draft_response: str | None = None
    final_response: str | None = None
    validation: ValidationResult | None = None
    internal_trace: dict[str, Any] = field(default_factory=dict)
    public_trace: dict[str, Any] = field(default_factory=dict)
    stage_timings: dict[str, float] = field(default_factory=dict)
    api_timings: dict[str, float] = field(default_factory=lambda: {"embedding_api_ms": 0.0, "generation_api_ms": 0.0, "external_api_ms": 0.0})
    model_call_count: int = 0
    generation_skipped: bool = True
    token_usage: dict[str, int | None] = field(default_factory=lambda: {"input_tokens": None, "output_tokens": None})

    def add_label(
        self,
        *,
        dimension: str,
        value: Any,
        producer: str,
        method: str,
        subject: dict[str, Any],
        stage: StageName,
        confidence: float | None = 1.0,
        rule_id: str | None = None,
        model_version: str | None = None,
    ) -> None:
        self.labels.append(
            LabelRecord(
                dimension=dimension,
                value=value,
                producer=producer,
                method=method,
                subject=subject,
                stage=stage,
                confidence=confidence,
                rule_id=rule_id,
                model_version=model_version,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return json_safe(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True)


def json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value):
        return {field.name: json_safe(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return value
