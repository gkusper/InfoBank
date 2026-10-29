"""Four application contracts and an internal, untrusted model proposal."""
from __future__ import annotations
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

class ValueType(str, Enum):
    TEXT='TEXT'
    ENTITY='ENTITY'
    NUMBER='NUMBER'
    DATE_TIME='DATE_TIME'
    BOOLEAN='BOOLEAN'
    LIST='LIST'
    UNKNOWN='UNKNOWN'

class Requirement(Contract):
    requirement_id: str
    query_start: int
    query_end: int
    required: bool
    value_type: ValueType
    qualifiers: list[str]
    depends_on: list[str]
    exhaustive: bool

class RequestContract(Contract):
    query: str
    as_of: str | None
    language: str
    logic: str
    requirements: list[Requirement]
    profile_origin: str = 'LOCAL_QUERY_ONLY'

class Authority(Contract):
    principal: str
    purpose: str
    policy_version: str
    revocation_version: str
    request_id: str

class RawSource(Contract):
    private_id: str
    content: str
    metadata: dict
    public_metadata: dict
    source_type: str = 'Document'
    private_markers: list[str] = []
    catalogue_title: str | None = None

class AccessDecision(Contract):
    access: str
    existence_public: bool = True
    metadata_fields: list[str] = []
    aggregate_view: str | None = None
    compatible: bool = True
    clean: bool = True
    target_names: list[str] = []
    aggregate_spec: dict | None = None

class Span(Contract):
    span_id: str
    start: int
    end: int
    content_sha256: str

class View(Contract):
    source_id: str
    view_kind: str
    text: str
    content_sha256: str
    spans: list[Span]
    public_metadata: dict

class InventoryEntry(Contract):
    source_id: str
    view_kind: str
    content_sha256: str
    supplied: bool
    assessment: str = 'NOT_ASSESSED'

class GovernedEvidenceContract(Contract):
    authority: Authority
    views: list[View]
    inventory: list[InventoryEntry]
    cache_key: str
    processing_version: str
    complete_scope: bool = False
    request_signature: str | None = None
    structured_bindings: list[dict] = []
    structured_signature: str | None = None

class SourceAssessment(Contract):
    source_id: str
    role: Literal['PRIMARY','CONTEXTUAL','CONTRASTIVE','IRRELEVANT']
    relation: Literal['SUPPORTS','CONTRADICTS','NONE']
    grounding_span_ids: list[str]
    note: str
    grounding_quotes: list[str] = []

class EvidenceRef(Contract):
    source_id: str
    span_id: str | None = None
    quote: str | None = None

class DependencyBinding(Contract):
    parent_requirement_id: str
    parent_claim_id: str
    subject_key: str

class Claim(Contract):
    claim_id: str
    requirement_ids: list[str]
    text: str
    value_type: ValueType
    value: str | None
    subject_key: str | None
    dependencies: list[DependencyBinding]
    evidence: list[EvidenceRef]

class RequirementSupport(Contract):
    requirement_id: str
    status: Literal['SUFFICIENT','MISSING','PARTIAL','UNKNOWN']
    claim_ids: list[str]
    missing: str

class LLMProposal(Contract):
    requirements: list[Requirement]
    source_assessments: list[SourceAssessment]
    claims: list[Claim]
    requirement_support: list[RequirementSupport]
    interpretation_limit: str

class DecisionContract(Contract):
    mode: str
    execution_status: str
    gate_status: str
    realization: str | None
    reason: str | None
    accepted_claim_ids: list[str]
    missing_requirement_ids: list[str]
    support_origin: str

class Citation(Contract):
    claim_id: str
    source_id: str
    span_id: str
    start: int
    end: int
    content_sha256: str
    labels: list[str]
    quote: str | None = None
    public_metadata: dict

class PublicResponseContract(Contract):
    text: str
    mode: str
    execution_status: str
    reason: str | None
    realization: str | None
    next_steps: list[str]
    citations: list[Citation]
    examined_sources: list[str]

class ProviderResult(Contract):
    proposal: LLMProposal | None
    status: str
    usage: dict
    raw: str | None

class RunResult(Contract):
    response: PublicResponseContract
    decision: DecisionContract
    private_trace: dict
    usage: dict

class StandardAnswer(Contract):
    mode: Literal['FULL','CFAF']
    answer: str
