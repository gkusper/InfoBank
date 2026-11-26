"""Deterministic source-bound entity matching and support status evaluation; 0 API calls.

Evaluates whether multiple sources or dependent/subject-linked claims refer to the
same real-world entity using application-supplied trusted entity identifiers bound
to exact document SHA-256 hashes and authorized snapshots, and maps evidence state
to SUPPORTED, INSUFFICIENT, CONTRADICTED, or UNRESOLVED.
"""
from .adapters.local import digest, entity_binding_signature
from .contracts import (
    Claim,
    DocumentRefAudit,
    EntityBindingAudit,
    EntityBindingStatus,
    GovernedEvidenceContract,
    LLMProposal,
    Requirement,
    SourceAssessment,
    SupportStatus,
    ValueType,
)
from .gate import ContractError


def normalize_entity_id(entity_id: str | None) -> str | None:
    """Normalizes an application entity identifier; empty strings become None."""
    if not isinstance(entity_id, str):
        return None
    stripped = entity_id.strip()
    return stripped if stripped else None


def resolve_source_entity_map(evidence: GovernedEvidenceContract) -> dict[str, str | None]:
    """Validates snapshot- and hash-bound entity bindings and returns source_id -> entity_id."""
    view_hashes: dict[str, str] = {}
    for view in evidence.views:
        if digest(view.text) != view.content_sha256:
            raise ContractError("SOURCE_HASH_MISMATCH")
        view_hashes[view.source_id] = view.content_sha256

    inv_hashes: dict[str, str] = {i.source_id: i.content_sha256 for i in evidence.inventory}

    if evidence.entity_bindings and not evidence.entity_signature:
        raise ContractError("STALE_ENTITY_BINDING")

    if evidence.entity_signature:
        expected_sig = entity_binding_signature(
            evidence.authority,
            evidence.processing_version,
            evidence.complete_scope,
            evidence.views,
            evidence.inventory,
            evidence.entity_bindings,
        )
        if evidence.entity_signature != expected_sig:
            raise ContractError("STALE_ENTITY_BINDING")

    permitted_ids = set(view_hashes) | set(inv_hashes)
    mapping: dict[str, str | None] = {v.source_id: None for v in evidence.views}
    seen: set[str] = set()

    for binding in evidence.entity_bindings:
        if binding.source_id in seen or binding.source_id not in permitted_ids:
            raise ContractError("DUPLICATE_OR_UNKNOWN_ENTITY_BINDING")
        seen.add(binding.source_id)

        expected_sha = view_hashes.get(binding.source_id) or inv_hashes.get(binding.source_id)
        if not binding.content_sha256 or binding.content_sha256 != expected_sha:
            raise ContractError("STALE_ENTITY_BINDING")

        if binding.source_id in mapping:
            mapping[binding.source_id] = normalize_entity_id(binding.entity_id)

    return mapping


def collect_involved_sources(
    claim: Claim,
    claims_by_id: dict[str, Claim],
    subject_groups: dict[str, list[Claim]],
    valid_reqs: dict[str, Requirement],
    claims_by_req: dict[str, list[Claim]],
) -> tuple[list[str], bool, bool]:
    """Collects all source_ids linked to a claim directly, via claim dependencies,
    via validated requirement dependencies (depends_on), or via shared subject_key.

    Returns:
        (ordered_unique_source_ids, has_invalid_dependency, has_mandatory_req_dependency)
    """
    sources: list[str] = [ref.source_id for ref in claim.evidence]
    invalid_dependency = False
    has_mandatory_req_dep = False
    visited_claims: set[str] = {claim.claim_id}
    visited_reqs: set[str] = set()

    def _walk_claim_deps(current: Claim) -> None:
        nonlocal invalid_dependency
        for dep in current.dependencies:
            pid = dep.parent_claim_id
            parent = claims_by_id.get(pid)
            if parent is None:
                invalid_dependency = True
                continue
            if pid in visited_claims:
                continue
            visited_claims.add(pid)
            sources.extend(ref.source_id for ref in parent.evidence)
            _walk_claim_deps(parent)

    def _walk_req_deps(rid: str) -> None:
        nonlocal invalid_dependency, has_mandatory_req_dep
        req = valid_reqs.get(rid)
        if req is None:
            return
        for parent_rid in req.depends_on:
            has_mandatory_req_dep = True
            if parent_rid in visited_reqs:
                continue
            visited_reqs.add(parent_rid)
            parent_claims = claims_by_req.get(parent_rid, [])
            if not parent_claims:
                invalid_dependency = True
            else:
                for pclaim in parent_claims:
                    if not pclaim.evidence:
                        invalid_dependency = True
                    sources.extend(ref.source_id for ref in pclaim.evidence)
                    if pclaim.claim_id not in visited_claims:
                        visited_claims.add(pclaim.claim_id)
                        _walk_claim_deps(pclaim)
            _walk_req_deps(parent_rid)

    _walk_claim_deps(claim)
    for rid in claim.requirement_ids:
        visited_reqs.add(rid)
        _walk_req_deps(rid)

    if claim.subject_key and claim.subject_key.strip():
        norm_subject = claim.subject_key.strip().casefold()
        for peer in subject_groups.get(norm_subject, []):
            if peer.claim_id != claim.claim_id:
                sources.extend(ref.source_id for ref in peer.evidence)

    return list(dict.fromkeys(sources)), invalid_dependency, has_mandatory_req_dep


def evaluate_entity_binding(
    claim: Claim,
    involved_sources: list[str],
    source_entity_map: dict[str, str | None],
    *,
    has_mandatory_req_dep: bool = False,
    require_entity_binding: bool = False,
) -> EntityBindingAudit:
    """Determines MATCHED, MISMATCHED, MISSING, or NOT_APPLICABLE from trusted source entity IDs."""
    authorized_involved = [sid for sid in involved_sources if sid in source_entity_map]
    bound_ids: dict[str, str | None] = {sid: source_entity_map[sid] for sid in authorized_involved}

    any_global_entity = any(eid is not None for eid in source_entity_map.values())
    has_subject_or_dep = bool(
        (claim.subject_key and claim.subject_key.strip())
        or claim.dependencies
        or has_mandatory_req_dep
    )
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


def _entity_compatible_for_contradiction(
    claim_entity_id: str | None,
    assessment_source_id: str,
    source_entity_map: dict[str, str | None],
    any_global_entity: bool,
) -> bool:
    """Checks whether a contradicting source applies to the same entity context."""
    if assessment_source_id not in source_entity_map:
        return False
    src_eid = source_entity_map[assessment_source_id]
    if claim_entity_id is not None:
        return src_eid == claim_entity_id
    if any_global_entity:
        return False
    return True


def _is_claim_contradicted(
    claim: Claim,
    *,
    entity_binding: EntityBindingAudit,
    source_entity_map: dict[str, str | None],
    valid_reqs: dict[str, Requirement],
    claims_by_req: dict[str, list[Claim]],
    claim_entities: dict[str, str | None],
    proposal: LLMProposal,
) -> bool:
    """Determines whether a contradiction specifically targets this claim or its requirement."""
    assessments: dict[str, SourceAssessment] = {a.source_id: a for a in proposal.source_assessments}
    supports_by_req = {s.requirement_id: s for s in proposal.requirement_support}
    any_global_entity = any(eid is not None for eid in source_entity_map.values())
    own_sources = [ref.source_id for ref in claim.evidence]

    # 1. Direct contradiction on one of this claim's own cited sources
    for sid in own_sources:
        assessment = assessments.get(sid)
        if assessment is not None and assessment.relation == "CONTRADICTS":
            return True

    # 2. Conflicting claims on the same scalar requirement for the same entity / subject
    for rid in claim.requirement_ids:
        req_obj = valid_reqs.get(rid)
        is_scalar = req_obj is not None and req_obj.value_type != ValueType.LIST and not req_obj.exhaustive
        for peer in claims_by_req.get(rid, []):
            if peer.claim_id == claim.claim_id:
                continue
            peer_eid = claim_entities.get(peer.claim_id)
            same_entity = (
                entity_binding.claim_entity_id is not None
                and peer_eid == entity_binding.claim_entity_id
            )
            same_subject = bool(
                not any_global_entity
                and claim.subject_key
                and peer.subject_key
                and claim.subject_key.strip().casefold() == peer.subject_key.strip().casefold()
            )
            peer_cites_contradicts = any(
                assessments.get(r.source_id) is not None
                and assessments[r.source_id].relation == "CONTRADICTS"
                for r in peer.evidence
            )
            if (same_entity or same_subject) and peer_cites_contradicts:
                return True
            if (
                is_scalar
                and (same_entity or same_subject)
                and claim.value is not None
                and peer.value is not None
                and claim.value.strip().casefold() != peer.value.strip().casefold()
            ):
                return True

    # 3. Assessment-level CONTRADICTS scoped to specific claim_id or requirement_id
    all_cited_sources = {r.source_id for c in proposal.claims for r in c.evidence}
    for assessment in proposal.source_assessments:
        if assessment.relation != "CONTRADICTS":
            continue
        if not _entity_compatible_for_contradiction(
            entity_binding.claim_entity_id,
            assessment.source_id,
            source_entity_map,
            any_global_entity,
        ):
            continue

        has_explicit_target = bool(
            assessment.contradicts_claim_ids or assessment.contradicts_requirement_ids
        )
        if has_explicit_target:
            if claim.claim_id in assessment.contradicts_claim_ids:
                return True
            if set(claim.requirement_ids) & set(assessment.contradicts_requirement_ids):
                return True
            continue

        # Unscoped CONTRADICTS assessment: only applies if it is not already attached to another
        # claim's evidence, AND either this claim's requirement is non-sufficient or there is
        # only a single requirement and single claim in the entire request/proposal.
        if assessment.source_id in all_cited_sources:
            continue
        if any(
            supports_by_req.get(rid) is not None and supports_by_req[rid].status != "SUFFICIENT"
            for rid in claim.requirement_ids
        ):
            return True
        if len(valid_reqs) == 1 and len(proposal.claims) == 1:
            return True

    return False


def evaluate_claim_support_status(
    claim: Claim,
    *,
    query_anchors_valid: bool,
    document_refs: list[DocumentRefAudit],
    entity_binding: EntityBindingAudit,
    invalid_dependency: bool,
    involved_sources: list[str],
    source_entity_map: dict[str, str | None],
    valid_reqs: dict[str, Requirement],
    claims_by_req: dict[str, list[Claim]],
    claim_entities: dict[str, str | None],
    proposal: LLMProposal,
) -> SupportStatus:
    """Maps validated anchors, document references, entity binding, and assessments to SupportStatus."""
    if (
        not query_anchors_valid
        or invalid_dependency
        or not document_refs
        or any(not ref.valid for ref in document_refs)
        or any(sid not in source_entity_map for sid in involved_sources)
    ):
        return SupportStatus.INSUFFICIENT

    if entity_binding.status in {EntityBindingStatus.MISMATCHED, EntityBindingStatus.MISSING}:
        return SupportStatus.UNRESOLVED

    if _is_claim_contradicted(
        claim,
        entity_binding=entity_binding,
        source_entity_map=source_entity_map,
        valid_reqs=valid_reqs,
        claims_by_req=claims_by_req,
        claim_entities=claim_entities,
        proposal=proposal,
    ):
        return SupportStatus.CONTRADICTED

    assessments = {a.source_id: a for a in proposal.source_assessments}
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
