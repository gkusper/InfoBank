"""Deterministic source-bound entity matching and support status evaluation; 0 API calls.

Evaluates whether multiple sources or dependent/subject-linked claims refer to the
same real-world entity using application-supplied trusted entity identifiers, and
maps evidence state to SUPPORTED, INSUFFICIENT, CONTRADICTED, or UNRESOLVED.
"""
from .adapters.local import canonical, digest
from .contracts import (
    Claim,
    DocumentRefAudit,
    EntityBindingAudit,
    EntityBindingStatus,
    GovernedEvidenceContract,
    LLMProposal,
    SupportStatus,
)
from .gate import ContractError


def normalize_entity_id(entity_id: str | None) -> str | None:
    """Normalizes an application entity identifier; empty strings become None."""
    if not isinstance(entity_id, str):
        return None
    stripped = entity_id.strip()
    return stripped if stripped else None


def resolve_source_entity_map(evidence: GovernedEvidenceContract) -> dict[str, str | None]:
    """Validates entity binding integrity and returns authorized source_id -> entity_id."""
    if evidence.entity_signature:
        expected = digest(canonical([b.model_dump(mode="json") for b in evidence.entity_bindings]))
        if evidence.entity_signature != expected:
            raise ContractError("STALE_ENTITY_BINDING")

    permitted_ids = {v.source_id for v in evidence.views} | {i.source_id for i in evidence.inventory}
    mapping: dict[str, str | None] = {v.source_id: None for v in evidence.views}
    seen: set[str] = set()

    for binding in evidence.entity_bindings:
        if binding.source_id in seen or binding.source_id not in permitted_ids:
            raise ContractError("DUPLICATE_OR_UNKNOWN_ENTITY_BINDING")
        seen.add(binding.source_id)
        if binding.source_id in mapping:
            mapping[binding.source_id] = normalize_entity_id(binding.entity_id)

    return mapping


def collect_involved_sources(
    claim: Claim,
    claims_by_id: dict[str, Claim],
    subject_groups: dict[str, list[Claim]],
) -> tuple[list[str], bool]:
    """Collects all source_ids linked to a claim directly, via dependencies, or via shared subject_key.

    Returns:
        (ordered_unique_source_ids, has_invalid_dependency)
    """
    sources: list[str] = [ref.source_id for ref in claim.evidence]
    invalid_dependency = False
    visited: set[str] = {claim.claim_id}

    def _walk_dependencies(current: Claim) -> None:
        nonlocal invalid_dependency
        for dep in current.dependencies:
            pid = dep.parent_claim_id
            parent = claims_by_id.get(pid)
            if parent is None:
                invalid_dependency = True
                continue
            if pid in visited:
                continue
            visited.add(pid)
            sources.extend(ref.source_id for ref in parent.evidence)
            _walk_dependencies(parent)

    _walk_dependencies(claim)

    if claim.subject_key and claim.subject_key.strip():
        norm_subject = claim.subject_key.strip().casefold()
        for peer in subject_groups.get(norm_subject, []):
            if peer.claim_id != claim.claim_id:
                sources.extend(ref.source_id for ref in peer.evidence)

    return list(dict.fromkeys(sources)), invalid_dependency


def evaluate_entity_binding(
    claim: Claim,
    involved_sources: list[str],
    source_entity_map: dict[str, str | None],
    *,
    require_entity_binding: bool = False,
) -> EntityBindingAudit:
    """Determines MATCHED, MISMATCHED, MISSING, or NOT_APPLICABLE from trusted source entity IDs."""
    authorized_involved = [sid for sid in involved_sources if sid in source_entity_map]
    bound_ids: dict[str, str | None] = {sid: source_entity_map[sid] for sid in authorized_involved}

    any_global_entity = any(eid is not None for eid in source_entity_map.values())
    has_subject_or_dep = bool((claim.subject_key and claim.subject_key.strip()) or claim.dependencies)
    needs_entity_check = (
        require_entity_binding
        or len(authorized_involved) >= 2
        or has_subject_or_dep
        or any_global_entity
    )

    if not authorized_involved or not needs_entity_check:
        return EntityBindingAudit(
            status=EntityBindingStatus.NOT_APPLICABLE,
            claim_entity_id=None,
            source_entity_ids=bound_ids,
            error=None,
        )

    non_null_ids = {eid for eid in bound_ids.values() if eid is not None}
    has_missing = any(eid is None for eid in bound_ids.values())

    if len(non_null_ids) > 1:
        return EntityBindingAudit(
            status=EntityBindingStatus.MISMATCHED,
            claim_entity_id=None,
            source_entity_ids=bound_ids,
            error="ENTITY_ID_MISMATCH",
        )

    if has_missing or not non_null_ids:
        return EntityBindingAudit(
            status=EntityBindingStatus.MISSING,
            claim_entity_id=None,
            source_entity_ids=bound_ids,
            error="MISSING_SOURCE_ENTITY_ID",
        )

    matched_id = next(iter(non_null_ids))
    return EntityBindingAudit(
        status=EntityBindingStatus.MATCHED,
        claim_entity_id=matched_id,
        source_entity_ids=bound_ids,
        error=None,
    )


def evaluate_claim_support_status(
    claim: Claim,
    *,
    query_anchors_valid: bool,
    document_refs: list[DocumentRefAudit],
    entity_binding: EntityBindingAudit,
    invalid_dependency: bool,
    involved_sources: list[str],
    source_entity_map: dict[str, str | None],
    proposal: LLMProposal,
) -> SupportStatus:
    """Maps validated anchors, document references, entity binding, and assessments to SupportStatus."""
    if (
        not query_anchors_valid
        or invalid_dependency
        or not document_refs
        or any(not ref.valid for ref in document_refs)
    ):
        return SupportStatus.INSUFFICIENT

    if entity_binding.status in {EntityBindingStatus.MISMATCHED, EntityBindingStatus.MISSING}:
        return SupportStatus.UNRESOLVED

    assessments = {a.source_id: a for a in proposal.source_assessments}
    any_global_entity = any(eid is not None for eid in source_entity_map.values())

    for sid in involved_sources:
        assessment = assessments.get(sid)
        if assessment is not None and assessment.relation == "CONTRADICTS":
            return SupportStatus.CONTRADICTED

    if entity_binding.claim_entity_id is not None:
        for sid, eid in source_entity_map.items():
            if eid == entity_binding.claim_entity_id:
                assessment = assessments.get(sid)
                if assessment is not None and assessment.relation == "CONTRADICTS":
                    return SupportStatus.CONTRADICTED
    elif not any_global_entity:
        for sid in source_entity_map:
            assessment = assessments.get(sid)
            if assessment is not None and assessment.relation == "CONTRADICTS":
                return SupportStatus.CONTRADICTED

    for ref in document_refs:
        assessment = assessments.get(ref.source_id)
        if assessment is None or assessment.role != "PRIMARY" or assessment.relation != "SUPPORTS":
            return SupportStatus.INSUFFICIENT

    supports_by_req = {s.requirement_id: s for s in proposal.requirement_support}
    for rid in claim.requirement_ids:
        sup = supports_by_req.get(rid)
        if sup is not None and sup.status != "SUFFICIENT":
            return SupportStatus.INSUFFICIENT

    return SupportStatus.SUPPORTED
