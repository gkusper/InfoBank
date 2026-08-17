from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from statistics import quantiles
from typing import Any, Protocol

from .labels import (
    AccessMode,
    CFAFDecision,
    CFAFRealization,
    ClaimAssessment,
    Disposition,
    EvidenceCandidate,
    EvidenceState,
    EvidentialRole,
    ExistenceVisibility,
    FulfilmentStatus,
    PipelineState,
    ReasonClass,
    RelationLabel,
    ResponseContract,
    StageName,
    TopLevelMode,
    ValidationResult,
    ValidationStatus,
    json_safe,
)


PUBLIC_NO_SUPPORT_REASON = "The currently usable evidence does not support the requested content."
PUBLIC_RESTRICTED_REASON = "The request exceeds the currently permitted evidence view."
SAFE_FALLBACK = PUBLIC_NO_SUPPORT_REASON


class PipelineStage(Protocol):
    name: StageName

    def run(self, state: PipelineState, context: "RunContext") -> PipelineState:
        ...


@dataclass
class RunContext:
    case: dict[str, Any]
    adapter_mode: str = "cfaf_pipeline"
    trace_id: str | None = None

    def __post_init__(self) -> None:
        if self.trace_id is None:
            self.trace_id = f"trace-{uuid.uuid4()}"


def _enum(enum_type: type, value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, enum_type):
        return value
    return enum_type(str(value))


def _timing_key(stage: StageName) -> str:
    return stage.value.lower() + "_ms"


def run_pipeline(case: dict[str, Any], *, adapter_mode: str = "cfaf_pipeline") -> PipelineState:
    state = PipelineState(
        case_id=case["case_id"],
        query_id=case.get("query_id", f"query-{case['case_id']}"),
        query=case["query"],
    )
    context = RunContext(case=case, adapter_mode=adapter_mode)
    stages: list[PipelineStage] = [
        QueryProfilingStage(),
        CandidateRetrievalStage(),
        AccessAndSafetyResolutionStage(),
        EvidenceLabellingStage(),
        SufficiencyAndPermittedOutputStage(),
        TopLevelModeSelectionStage(),
        ResponseRealizationStage(),
        ValidationTraceAndFeedbackStage(),
    ]
    start_ns = time.perf_counter_ns()
    for stage in stages:
        stage_start = time.perf_counter_ns()
        state = stage.run(state, context)
        elapsed_ms = (time.perf_counter_ns() - stage_start) / 1_000_000
        state.stage_timings[_timing_key(stage.name)] = max(0.0, elapsed_ms)
        json.loads(state.to_json())
    state.stage_timings["end_to_end_ms"] = max(0.0, (time.perf_counter_ns() - start_ns) / 1_000_000)
    _finalize_traces(state, context)
    json.loads(state.to_json())
    return state


class QueryProfilingStage:
    name = StageName.QUERY_PROFILING

    def run(self, state: PipelineState, context: RunContext) -> PipelineState:
        case = context.case
        fields = [
            "task",
            "purpose",
            "requested_content",
            "requested_granularity",
            "requested_action",
            "time_horizon",
            "required_evidence_strength",
            "source_scope",
        ]
        state.query_profile = {field: case[field] for field in fields}
        state.required_claims = case.get("required_claims") or [{"claim_id": "claim-1", "requested_content": case["requested_content"]}]
        for key, value in state.query_profile.items():
            state.add_label(
                dimension=f"query_profile.{key}",
                value=value,
                producer="wolala_query_profiler",
                method="fixture_declared_deterministic",
                subject={"query_id": state.query_id},
                stage=self.name,
                rule_id="WOLALA-QP-001",
            )
        return state


class CandidateRetrievalStage:
    name = StageName.CANDIDATE_RETRIEVAL

    def run(self, state: PipelineState, context: RunContext) -> PipelineState:
        retrieved = [source for source in context.case.get("sources", []) if source.get("retrieved", True)]
        candidates: list[EvidenceCandidate] = []
        for index, source in enumerate(retrieved, start=1):
            candidate = EvidenceCandidate(
                candidate_id=source.get("candidate_id", f"{state.case_id}-cand-{index}"),
                source_id=source["source_id"],
                source_type=source.get("source_type", "Document"),
                retrieval_rank=int(source.get("retrieval_rank", index)),
                retrieval_score=source.get("retrieval_score", 1.0 / index),
                retriever_name=source.get("retriever_name", "deterministic_smoke_retriever"),
                retrieval_reason=source.get("retrieval_reason", "fixture_scope_match"),
                title=source.get("title", source["source_id"]),
                content=source.get("content", ""),
                metadata=dict(source.get("metadata") or {}),
                claim_id=source.get("claim_id", "claim-1"),
                protected_markers=list(source.get("protected_markers") or []),
                aggregate_view=source.get("aggregate_view"),
            )
            candidates.append(candidate)
            for dimension in [
                "candidate_id",
                "source_id",
                "source_type",
                "retrieval_rank",
                "retrieval_score",
                "retriever_name",
                "retrieval_reason",
            ]:
                state.add_label(
                    dimension=f"retrieval.{dimension}",
                    value=getattr(candidate, dimension),
                    producer="wolala_candidate_retrieval",
                    method="deterministic_fixture_candidate",
                    subject={"query_id": state.query_id, "candidate_id": candidate.candidate_id, "source_id": candidate.source_id},
                    stage=self.name,
                    rule_id="WOLALA-RET-001",
                )
        state.candidates = candidates
        return state


class AccessAndSafetyResolutionStage:
    name = StageName.ACCESS_AND_SAFETY_RESOLUTION

    def run(self, state: PipelineState, context: RunContext) -> PipelineState:
        by_source_id = {source["source_id"]: source for source in context.case.get("sources", [])}
        for candidate in state.candidates:
            source = by_source_id[candidate.source_id]
            candidate.access_mode = _enum(AccessMode, source.get("access_mode"), AccessMode.DENY)
            candidate.existence_visibility = _enum(ExistenceVisibility, source.get("existence_visibility"), ExistenceVisibility.PUBLIC)
            candidate.policy_rule_id = source.get("policy_rule_id", f"policy-{candidate.access_mode.value.lower()}")
            candidate.policy_version = source.get("policy_version", "wolala-smoke-policy-v1")
            candidate.purpose_compatibility = source.get("purpose_compatibility", "compatible")
            candidate.security_status = source.get("security_status", "clean")
            candidate.allowed_metadata_fields = list(source.get("allowed_metadata_fields") or [])
            labels = {
                "access_mode": candidate.access_mode,
                "existence_visibility": candidate.existence_visibility,
                "policy_rule_id": candidate.policy_rule_id,
                "policy_version": candidate.policy_version,
                "purpose_compatibility": candidate.purpose_compatibility,
                "security_status": candidate.security_status,
            }
            for dimension, value in labels.items():
                state.add_label(
                    dimension=f"access.{dimension}",
                    value=value,
                    producer="wolala_policy_gate",
                    method="authoritative_fixture_policy",
                    subject={"query_id": state.query_id, "source_id": candidate.source_id},
                    stage=self.name,
                    rule_id=candidate.policy_rule_id,
                )
        return state


class EvidenceLabellingStage:
    name = StageName.EVIDENCE_LABELLING

    def run(self, state: PipelineState, context: RunContext) -> PipelineState:
        by_source_id = {source["source_id"]: source for source in context.case.get("sources", [])}
        for candidate in state.candidates:
            source = by_source_id[candidate.source_id]
            if candidate.access_mode == AccessMode.DENY and not source.get("trusted_evidential_role"):
                candidate.evidential_role = EvidentialRole.UNKNOWN
            else:
                candidate.evidential_role = _enum(EvidentialRole, source.get("evidential_role"), EvidentialRole.UNKNOWN)
            candidate.evidence_state = _enum(EvidenceState, source.get("evidence_state"), EvidenceState.CURRENT)
            candidate.relation = _enum(RelationLabel, source.get("relation"), RelationLabel.NONE)
            scoped_subject = {"query_id": state.query_id, "claim_id": candidate.claim_id, "source_id": candidate.source_id}
            for dimension, value in {
                "evidential_role": candidate.evidential_role,
                "evidence_state": candidate.evidence_state,
                "relation": candidate.relation,
            }.items():
                state.add_label(
                    dimension=f"evidence.{dimension}",
                    value=value,
                    producer="wolala_evidence_labeller",
                    method="trusted_fixture_label" if candidate.access_mode != AccessMode.DENY else "withheld_or_trusted_metadata_only",
                    subject=scoped_subject,
                    stage=self.name,
                    rule_id="WOLALA-EVID-001",
                )
        return state


class SufficiencyAndPermittedOutputStage:
    name = StageName.SUFFICIENCY_AND_PERMITTED_OUTPUT

    def run(self, state: PipelineState, context: RunContext) -> PipelineState:
        for candidate in state.candidates:
            candidate.disposition = _derive_disposition(candidate)
            state.add_label(
                dimension="disposition",
                value=candidate.disposition,
                producer="wolala_disposition_deriver",
                method="access_role_state_query_rule",
                subject={"query_id": state.query_id, "claim_id": candidate.claim_id, "source_id": candidate.source_id},
                stage=self.name,
                rule_id="WOLALA-DISP-001",
            )
        state.claim_assessments = [_assess_claim(state, context.case, claim) for claim in state.required_claims]
        for assessment in state.claim_assessments:
            state.add_label(
                dimension="claim.can_fulfil_request",
                value=assessment.can_fulfil_request,
                producer="wolala_sufficiency_gate",
                method="request_relative_rule",
                subject={"query_id": state.query_id, "claim_id": assessment.claim_id},
                stage=self.name,
                rule_id=assessment.reason_code or "WOLALA-SUFF-FULL",
            )
        return state


class TopLevelModeSelectionStage:
    name = StageName.TOP_LEVEL_MODE_SELECTION

    def run(self, state: PipelineState, context: RunContext) -> PipelineState:
        failing = [assessment for assessment in state.claim_assessments if not assessment.can_fulfil_request]
        if not failing:
            mode = TopLevelMode.FULL
            fulfilment = FulfilmentStatus.FULL
            reason_class = None
            reason_code = None
            permitted_output = "REQUESTED_OUTPUT"
            public_reason = ""
            next_steps: list[str] = []
            realization = None
        else:
            first = failing[0]
            mode = TopLevelMode.CFAF
            fulfilment = FulfilmentStatus.RESTRICTED if first.permitted_content not in {"NONE", "EXCLUDED"} else FulfilmentStatus.NONE
            reason_class = first.reason_class
            reason_code = first.reason_code
            permitted_output = first.permitted_content
            public_reason = _public_reason_text(first, state)
            next_steps = _next_steps(first)
            realization = first.cfaf_realization or CFAFRealization.ABSTAIN
        state.mode_decision = CFAFDecision(
            execution_status="SUCCESS",
            fulfilment_status=fulfilment,
            mode=mode,
            reason_class=reason_class,
            reason_code=reason_code,
            permitted_output=permitted_output,
            public_reason=public_reason,
            next_steps=next_steps,
            internal_trace_id=context.trace_id or "",
            cfaf_realization=realization,
        )
        state.add_label(
            dimension="top_level_mode",
            value=mode,
            producer="wolala_mode_selector",
            method="permitted_output_meets_requested_output_rule",
            subject={"query_id": state.query_id},
            stage=self.name,
            rule_id="WOLALA-MODE-001",
        )
        return state


class ResponseRealizationStage:
    name = StageName.RESPONSE_REALIZATION

    def run(self, state: PipelineState, context: RunContext) -> PipelineState:
        contract = _build_response_contract(state)
        state.response_contract = contract
        state.generator_context = [
            {
                "response_contract": {
                    "mode": contract.mode.value,
                    "fulfilment_status": contract.fulfilment_status.value,
                    "cfaf_realization": contract.cfaf_realization.value if contract.cfaf_realization else None,
                    "allowed_claims": contract.allowed_claims,
                    "allowed_evidence_views": contract.allowed_evidence_views,
                    "forbidden_fields": contract.forbidden_fields,
                    "public_reason_class": contract.public_reason_class.value if contract.public_reason_class else None,
                    "public_reason_text": contract.public_reason_text,
                    "allowed_next_steps": contract.allowed_next_steps,
                }
            }
        ]
        if contract.mode == TopLevelMode.FULL:
            state.generation_skipped = False
            state.model_call_count = 1
            state.token_usage = {"input_tokens": _rough_token_count(state.generator_context), "output_tokens": None}
            if context.case.get("force_invalid_generation"):
                state.draft_response = context.case.get("invalid_generated_output", "Invalid generated output.")
            else:
                answers = [claim.get("answer") for claim in contract.allowed_claims if claim.get("answer")]
                state.draft_response = " ".join(answers) if answers else context.case.get("gold_answer", "")
            state.token_usage["output_tokens"] = len((state.draft_response or "").split())
        else:
            state.generation_skipped = True
            state.model_call_count = 0
            state.token_usage = {"input_tokens": 0, "output_tokens": len(contract.public_reason_text.split())}
            state.draft_response = contract.public_reason_text
        state.final_response = state.draft_response
        return state


class ValidationTraceAndFeedbackStage:
    name = StageName.VALIDATION_TRACE_AND_FEEDBACK

    def run(self, state: PipelineState, context: RunContext) -> PipelineState:
        violations = validate_state_exposure(state, context.case)
        fallback_used = False
        if violations:
            state.final_response = context.case.get("safe_fallback", SAFE_FALLBACK)
            fallback_used = True
        state.validation = ValidationResult(
            status=ValidationStatus.FAIL if violations else ValidationStatus.PASS,
            violation_codes=violations,
            fallback_used=fallback_used,
        )
        return state


def _derive_disposition(candidate: EvidenceCandidate) -> Disposition:
    if candidate.access_mode == AccessMode.DENY:
        return Disposition.EXCLUDED
    if candidate.access_mode == AccessMode.METADATA:
        return Disposition.METADATA_ONLY
    if candidate.access_mode == AccessMode.AGGREGATE:
        return Disposition.AGGREGATE_ONLY
    if candidate.evidential_role == EvidentialRole.IRRELEVANT:
        return Disposition.EXCLUDED
    return Disposition.DIRECT_USE


def _assess_claim(state: PipelineState, case: dict[str, Any], claim: dict[str, Any]) -> ClaimAssessment:
    claim_id = claim.get("claim_id", "claim-1")
    candidates = [candidate for candidate in state.candidates if candidate.claim_id == claim_id and candidate.evidential_role != EvidentialRole.IRRELEVANT]
    requested_content = state.query_profile.get("requested_content")
    requested_granularity = state.query_profile.get("requested_granularity")
    primary = [c for c in candidates if c.access_mode == AccessMode.FULL and c.evidential_role == EvidentialRole.PRIMARY and c.evidence_state == EvidenceState.CURRENT]
    contextual = [c for c in candidates if c.access_mode == AccessMode.FULL and c.evidential_role == EvidentialRole.CONTEXTUAL]
    aggregate = [c for c in candidates if c.access_mode == AccessMode.AGGREGATE]
    metadata = [c for c in candidates if c.access_mode == AccessMode.METADATA]
    denied = [c for c in candidates if c.access_mode == AccessMode.DENY]
    closing = [
        c
        for c in candidates
        if c.access_mode == AccessMode.FULL and c.evidential_role == EvidentialRole.CONTRASTIVE and c.relation == RelationLabel.CLOSES
    ]

    if aggregate:
        if requested_granularity == "aggregate":
            return _supported(claim_id, aggregate, [], "AGGREGATE_ONLY", "aggregate", requested_granularity, case)
        return _unsupported(
            claim_id,
            aggregate,
            ReasonClass.GOVERNANCE_PRIVACY,
            "REQUESTED_GRANULARITY_EXCEEDS_AGGREGATE_ACCESS",
            "AGGREGATE_ONLY",
            "aggregate",
            requested_granularity,
            CFAFRealization.RESTRICT_GRANULARITY,
        )

    if metadata:
        if requested_content == "metadata" or requested_granularity == "metadata":
            return _supported(claim_id, metadata, [], "METADATA_ONLY", "metadata", requested_granularity, case)
        return _unsupported(
            claim_id,
            metadata,
            ReasonClass.GOVERNANCE_PRIVACY,
            "REQUESTED_CONTENT_EXCEEDS_METADATA_ACCESS",
            "METADATA_ONLY",
            "metadata",
            requested_granularity,
            CFAFRealization.RESTRICT_CONTENT,
        )

    if primary and closing:
        return _supported(claim_id, primary, closing, "CONTENT", requested_granularity, requested_granularity, case, support_status="CLOSED")
    if primary:
        return _supported(claim_id, primary, [], "CONTENT", requested_granularity, requested_granularity, case)

    if contextual and not primary:
        return _unsupported(
            claim_id,
            contextual,
            ReasonClass.EVIDENTIAL,
            "CONTEXTUAL_ONLY_EVIDENCE_CANNOT_ESTABLISH_CLAIM",
            "NONE",
            "none",
            requested_granularity,
            CFAFRealization.ABSTAIN,
        )

    if denied:
        return _unsupported(
            claim_id,
            denied,
            ReasonClass.GOVERNANCE_PRIVACY,
            "REQUESTED_CONTENT_DENIED_OR_INACCESSIBLE",
            "EXCLUDED",
            "none",
            requested_granularity,
            CFAFRealization.ABSTAIN,
        )

    return _unsupported(
        claim_id,
        [],
        ReasonClass.EVIDENTIAL,
        "NO_RELEVANT_SOURCE",
        "NONE",
        "none",
        requested_granularity,
        CFAFRealization.ABSTAIN,
    )


def _supported(
    claim_id: str,
    supporting: list[EvidenceCandidate],
    contrastive: list[EvidenceCandidate],
    permitted_content: str,
    maximum_granularity: str,
    requested_granularity: str,
    case: dict[str, Any],
    *,
    support_status: str = "SUPPORTED",
) -> ClaimAssessment:
    return ClaimAssessment(
        claim_id=claim_id,
        support_status=support_status,
        supporting_evidence_ids=[candidate.source_id for candidate in supporting],
        contrastive_evidence_ids=[candidate.source_id for candidate in contrastive],
        sufficient=True,
        permitted_content=permitted_content,
        maximum_granularity=maximum_granularity,
        requested_granularity=requested_granularity,
        can_fulfil_request=True,
        answer=case.get("gold_answer"),
    )


def _unsupported(
    claim_id: str,
    evidence: list[EvidenceCandidate],
    reason_class: ReasonClass,
    reason_code: str,
    permitted_content: str,
    maximum_granularity: str,
    requested_granularity: str,
    cfaf_realization: CFAFRealization,
) -> ClaimAssessment:
    return ClaimAssessment(
        claim_id=claim_id,
        support_status="INSUFFICIENT",
        supporting_evidence_ids=[candidate.source_id for candidate in evidence if candidate.evidential_role != EvidentialRole.CONTRASTIVE],
        contrastive_evidence_ids=[candidate.source_id for candidate in evidence if candidate.evidential_role == EvidentialRole.CONTRASTIVE],
        sufficient=False,
        permitted_content=permitted_content,
        maximum_granularity=maximum_granularity,
        requested_granularity=requested_granularity,
        can_fulfil_request=False,
        answer=None,
        reason_class=reason_class,
        reason_code=reason_code,
        cfaf_realization=cfaf_realization,
    )


def _public_reason_text(assessment: ClaimAssessment, state: PipelineState) -> str:
    if _only_internal_sources_for_assessment(assessment, state):
        return PUBLIC_NO_SUPPORT_REASON
    if assessment.reason_class == ReasonClass.GOVERNANCE_PRIVACY:
        return PUBLIC_RESTRICTED_REASON
    return PUBLIC_NO_SUPPORT_REASON


def _public_reason_class(assessment: ClaimAssessment | None, state: PipelineState) -> ReasonClass | None:
    if not assessment:
        return None
    if _only_internal_sources_for_assessment(assessment, state):
        return ReasonClass.EVIDENTIAL
    return assessment.reason_class


def _only_internal_sources_for_assessment(assessment: ClaimAssessment, state: PipelineState) -> bool:
    evidence_ids = set(assessment.supporting_evidence_ids + assessment.contrastive_evidence_ids)
    if not evidence_ids:
        return False
    matching = [candidate for candidate in state.candidates if candidate.source_id in evidence_ids]
    return bool(matching) and all(candidate.existence_visibility == ExistenceVisibility.INTERNAL_ONLY for candidate in matching)


def _next_steps(assessment: ClaimAssessment) -> list[str]:
    if assessment.reason_code == "REQUESTED_CONTENT_EXCEEDS_METADATA_ACCESS":
        return ["Request content-level access."]
    if assessment.reason_code == "REQUESTED_GRANULARITY_EXCEEDS_AGGREGATE_ACCESS":
        return ["Ask for aggregate output or request individual-level access."]
    if assessment.reason_class == ReasonClass.GOVERNANCE_PRIVACY:
        return ["Request access to a permitted source."]
    return ["Provide primary evidence or ask a narrower supported question."]


def _build_response_contract(state: PipelineState) -> ResponseContract:
    assert state.mode_decision is not None
    failing = next((assessment for assessment in state.claim_assessments if not assessment.can_fulfil_request), None)
    public_reason_class = _public_reason_class(failing, state)
    allowed_claims = [
        {
            "claim_id": assessment.claim_id,
            "support_status": assessment.support_status,
            "answer": assessment.answer,
            "permitted_content": assessment.permitted_content,
            "maximum_granularity": assessment.maximum_granularity,
        }
        for assessment in state.claim_assessments
        if assessment.can_fulfil_request
    ]
    return ResponseContract(
        mode=state.mode_decision.mode,
        fulfilment_status=state.mode_decision.fulfilment_status,
        cfaf_realization=state.mode_decision.cfaf_realization,
        allowed_claims=allowed_claims,
        allowed_evidence_views=_allowed_evidence_views(state),
        forbidden_fields=[
            "denied_content",
            "raw_aggregate_individual_content",
            "metadata_disallowed_content",
            "hidden_source_identifier",
            "protected_validation_marker",
        ],
        public_reason_class=public_reason_class,
        public_reason_text=state.mode_decision.public_reason,
        allowed_next_steps=state.mode_decision.next_steps,
    )


def _allowed_evidence_views(state: PipelineState) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for candidate in state.candidates:
        if candidate.disposition == Disposition.EXCLUDED:
            continue
        if candidate.existence_visibility == ExistenceVisibility.INTERNAL_ONLY:
            continue
        if candidate.disposition == Disposition.DIRECT_USE:
            views.append(
                {
                    "view_type": "content",
                    "source_ref": candidate.source_id,
                    "source_type": candidate.source_type,
                    "evidential_role": candidate.evidential_role.value,
                    "evidence_state": candidate.evidence_state.value,
                    "relation": candidate.relation.value,
                    "content": candidate.content,
                }
            )
        elif candidate.disposition == Disposition.AGGREGATE_ONLY:
            views.append(
                {
                    "view_type": "aggregate",
                    "source_ref": candidate.source_id,
                    "aggregate_view": candidate.aggregate_view or candidate.metadata.get("aggregate_summary") or "Aggregate view available.",
                }
            )
        elif candidate.disposition == Disposition.METADATA_ONLY:
            allowed = {key: candidate.metadata.get(key) for key in candidate.allowed_metadata_fields if key in candidate.metadata}
            views.append({"view_type": "metadata", "source_ref": candidate.source_id, "metadata": allowed})
    return views


def _rough_token_count(value: Any) -> int:
    return len(json.dumps(json_safe(value), sort_keys=True).split())


def validate_state_exposure(state: PipelineState, case: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    context_text = json.dumps(json_safe(state.generator_context), sort_keys=True)
    final_text = state.final_response or ""
    for candidate in state.candidates:
        if candidate.access_mode == AccessMode.DENY and candidate.content and candidate.content in context_text:
            violations.append("DENIED_CONTENT_IN_GENERATOR_CONTEXT")
        if candidate.access_mode == AccessMode.METADATA and candidate.content and candidate.content in context_text:
            violations.append("METADATA_CONTENT_IN_GENERATOR_CONTEXT")
        if candidate.access_mode == AccessMode.AGGREGATE and candidate.content and candidate.content in context_text:
            violations.append("RAW_AGGREGATE_CONTENT_IN_GENERATOR_CONTEXT")
        if candidate.existence_visibility == ExistenceVisibility.INTERNAL_ONLY:
            public_text = json.dumps(json_safe(state.public_trace), sort_keys=True) + final_text
            if candidate.source_id in public_text or candidate.title in public_text:
                violations.append("INTERNAL_ONLY_SOURCE_REVEALED")
        for marker in candidate.protected_markers:
            if marker and marker in context_text:
                violations.append("PROTECTED_MARKER_IN_GENERATOR_CONTEXT")
            if marker and marker in final_text:
                violations.append("PROTECTED_MARKER_IN_RESPONSE")
    for marker in case.get("protected_markers", []):
        if marker and marker in context_text:
            violations.append("PROTECTED_MARKER_IN_GENERATOR_CONTEXT")
        if marker and marker in final_text:
            violations.append("PROTECTED_MARKER_IN_RESPONSE")
    return sorted(set(violations))


def assert_pipeline_invariants(state: PipelineState) -> None:
    json.loads(state.to_json())
    timings = state.stage_timings
    for stage in StageName:
        key = _timing_key(stage)
        assert key in timings, f"missing timing {key}"
        assert timings[key] >= 0, f"negative timing {key}"
    assert "end_to_end_ms" in timings and timings["end_to_end_ms"] >= 0
    context_text = json.dumps(json_safe(state.generator_context), sort_keys=True)
    for candidate in state.candidates:
        if candidate.access_mode == AccessMode.DENY:
            assert candidate.content not in context_text
        if candidate.access_mode == AccessMode.METADATA:
            assert candidate.content not in context_text
        if candidate.access_mode == AccessMode.AGGREGATE:
            assert candidate.content not in context_text
    if any(candidate.evidential_role == EvidentialRole.CONTEXTUAL for candidate in state.candidates) and not any(
        candidate.evidential_role == EvidentialRole.PRIMARY for candidate in state.candidates
    ):
        assert all(not assessment.can_fulfil_request for assessment in state.claim_assessments)


def _finalize_traces(state: PipelineState, context: RunContext) -> None:
    contract = state.response_contract
    public_reason_class = contract.public_reason_class.value if contract and contract.public_reason_class else None
    state.internal_trace = {
        "trace_id": context.trace_id,
        "case_id": state.case_id,
        "adapter_mode": context.adapter_mode,
        "stage_sequence": [stage.value for stage in StageName],
        "query_profile": state.query_profile,
        "labels": [label for label in state.labels],
        "candidates": [candidate for candidate in state.candidates],
        "claim_assessments": state.claim_assessments,
        "mode_decision": state.mode_decision,
        "response_contract": state.response_contract,
        "generator_context": state.generator_context,
        "validation": state.validation,
        "stage_timings": state.stage_timings,
        "api_timings": state.api_timings,
        "model_call_count": state.model_call_count,
        "generation_skipped": state.generation_skipped,
        "token_usage": state.token_usage,
    }
    state.public_trace = {
        "case_id": state.case_id,
        "mode": state.mode_decision.mode.value if state.mode_decision else None,
        "fulfilment_status": state.mode_decision.fulfilment_status.value if state.mode_decision else None,
        "public_reason_class": public_reason_class,
        "public_reason_text": contract.public_reason_text if contract else "",
        "visible_source_count": len(
            [
                candidate
                for candidate in state.candidates
                if candidate.existence_visibility == ExistenceVisibility.PUBLIC and candidate.disposition != Disposition.EXCLUDED
            ]
        ),
        "validation_status": state.validation.status.value if state.validation else None,
    }


def latency_summary(states: list[PipelineState]) -> dict[str, Any]:
    by_key: dict[str, list[float]] = {}
    for state in states:
        for key, value in state.stage_timings.items():
            by_key.setdefault(key, []).append(value)
    return {key: _percentiles(values) for key, values in sorted(by_key.items())}


def _percentiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "p50_ms": 0.0, "p95_ms": 0.0}
    if len(ordered) == 1:
        return {"count": 1, "p50_ms": ordered[0], "p95_ms": ordered[0]}
    p95 = quantiles(ordered, n=100, method="inclusive")[94]
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        p50 = ordered[midpoint]
    else:
        p50 = (ordered[midpoint - 1] + ordered[midpoint]) / 2
    return {"count": len(ordered), "p50_ms": p50, "p95_ms": p95}


def write_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(json_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
