"""Deterministic local support, reference, and entity-binding checker; 0 API calls.

This module implements the SupportChecker protocol for offline, deterministic
validation of requirement anchors, source citations, and trusted entity bindings
within the CFAF framework.
"""
from graphlib import CycleError, TopologicalSorter
from typing import Any
from .contracts import (
    Claim,
    ClaimAuditRecord,
    DocumentRefAudit,
    EntityBindingAudit,
    EntityBindingStatus,
    GovernedEvidenceContract,
    LLMProposal,
    QueryAnchorAudit,
    RequestContract,
    Requirement,
    SupportStatus,
    ValueType,
)
from .entity_binding import (
    collect_involved_sources,
    evaluate_claim_support_status,
    evaluate_entity_binding,
    resolve_source_entity_map,
)
from .gate import ContractError, resolve_evidence


class ReferenceSupportChecker:
    """Local shadow checker for validating query anchors, citations, and entity bindings.

    Adheres strictly to the CFAF constraints:
    - local_only = True: 0 external API calls allowed.
    - Deterministic evaluation using existing gate contracts, resolvers, and entity bindings.
    - Pure shadow verification: output is written only to private audit traces.
    """
    local_only: bool = True

    def __init__(self, *, require_entity_binding: bool = False) -> None:
        self.require_entity_binding = require_entity_binding

    @staticmethod
    def _validate_requirements(
        request: RequestContract,
        proposal: LLMProposal,
    ) -> tuple[dict[str, Requirement], dict[str, str], dict[str, dict[str, Any]], list[dict[str, Any]]]:
        """Validates proposal requirements against the original request contract."""
        base = {r.requirement_id: r for r in request.requirements}
        valid_reqs: dict[str, Requirement] = {}
        invalid_reasons: dict[str, str] = {}
        req_rejections_by_id: dict[str, dict[str, Any]] = {}
        global_rejections: list[dict[str, Any]] = []

        seen_ids: set[str] = set()
        duplicate_ids: set[str] = set()
        for r in proposal.requirements:
            if r.requirement_id in seen_ids:
                duplicate_ids.add(r.requirement_id)
            seen_ids.add(r.requirement_id)

        for dup_id in sorted(duplicate_ids):
            invalid_reasons[dup_id] = "REQUIRED_REQUEST_PART_REMOVED_OR_DUPLICATED"
            req_rejections_by_id[dup_id] = {
                "requirement_id": dup_id,
                "reason": "REQUIRED_REQUEST_PART_REMOVED_OR_DUPLICATED",
                "error_type": "ContractError",
            }

        for base_req in request.requirements:
            if base_req.requirement_id not in seen_ids:
                invalid_reasons[base_req.requirement_id] = "REQUIRED_REQUEST_PART_REMOVED_OR_DUPLICATED"
                req_rejections_by_id[base_req.requirement_id] = {
                    "requirement_id": base_req.requirement_id,
                    "reason": "REQUIRED_REQUEST_PART_REMOVED_OR_DUPLICATED",
                    "error_type": "ContractError",
                }

        for r in proposal.requirements:
            rid = r.requirement_id
            if rid in duplicate_ids:
                continue

            error: str | None = None
            if (
                not rid
                or not (0 <= r.query_start < r.query_end <= len(request.query))
                or not request.query[r.query_start:r.query_end].strip()
            ):
                error = "INVALID_QUERY_SPAN"
            elif not (set(r.depends_on) <= seen_ids):
                error = "UNKNOWN_REQUIREMENT_DEPENDENCY"
            elif rid in base:
                b = base[rid]
                if (
                    (b.query_start, b.query_end) != (r.query_start, r.query_end)
                    or (b.required and not r.required)
                    or not (set(b.depends_on) <= set(r.depends_on))
                    or (b.exhaustive and not r.exhaustive)
                ):
                    error = "EXPLICIT_REQUEST_WEAKENED"
                elif b.value_type != ValueType.UNKNOWN and b.value_type != r.value_type:
                    error = "EXPLICIT_VALUE_TYPE_CHANGED"

            if error is not None:
                key = rid or "<empty>"
                invalid_reasons[key] = error
                req_rejections_by_id[key] = {
                    "requirement_id": rid,
                    "reason": error,
                    "error_type": "ContractError",
                }
            else:
                valid_reqs[rid] = r

        if not duplicate_ids:
            try:
                tuple(
                    TopologicalSorter(
                        {r.requirement_id: set(r.depends_on) for r in proposal.requirements if r.requirement_id}
                    ).static_order()
                )
            except CycleError:
                global_rejections.append({
                    "reason": "CYCLIC_REQUIREMENTS",
                    "error_type": "ContractError",
                })

        return valid_reqs, invalid_reasons, req_rejections_by_id, global_rejections

    @staticmethod
    def _uncovered_requirement_record(
        case_id: str,
        req: Requirement,
        query: str,
        proposal: LLMProposal,
        source_entity_map: dict[str, str | None],
        claim_entities_by_req: dict[str, set[str]],
        all_cited_sources: set[str],
    ) -> ClaimAuditRecord:
        """Builds an audit record for a validated requirement that has no supporting claim."""
        anchor = QueryAnchorAudit(
            requirement_id=req.requirement_id,
            start=req.query_start,
            end=req.query_end,
            snippet=query[req.query_start:req.query_end],
            valid=True,
            error=None,
        )

        def _assessment_applies_to_req(a) -> bool:
            if a.relation != "CONTRADICTS" or a.source_id not in source_entity_map:
                return False
            if a.contradicts_claim_ids or a.contradicts_requirement_ids:
                return req.requirement_id in a.contradicts_requirement_ids
            return a.source_id not in all_cited_sources

        parent_entities: set[str] = set()
        for parent_rid in req.depends_on:
            parent_entities.update(claim_entities_by_req.get(parent_rid, set()))

        if parent_entities:
            other_non_null = {
                eid for eid in source_entity_map.values()
                if eid is not None and eid not in parent_entities
            }
            same_entity_sources = {
                sid for sid, eid in source_entity_map.items() if eid in parent_entities
            }
            if any(
                _assessment_applies_to_req(a) and a.source_id in same_entity_sources
                for a in proposal.source_assessments
            ):
                return ClaimAuditRecord(
                    case_id=case_id,
                    requirement_id=req.requirement_id,
                    claim_id=None,
                    query_anchor=anchor,
                    document_refs=[],
                    entity_binding=EntityBindingAudit(
                        status=EntityBindingStatus.MATCHED,
                        claim_entity_id=next(iter(parent_entities)) if len(parent_entities) == 1 else None,
                        source_entity_ids={sid: source_entity_map[sid] for sid in same_entity_sources},
                        error=None,
                    ),
                    support_status=SupportStatus.CONTRADICTED,
                    runtime_error=None,
                )
            if other_non_null:
                return ClaimAuditRecord(
                    case_id=case_id,
                    requirement_id=req.requirement_id,
                    claim_id=None,
                    query_anchor=anchor,
                    document_refs=[],
                    entity_binding=EntityBindingAudit(
                        status=EntityBindingStatus.MISMATCHED,
                        claim_entity_id=None,
                        source_entity_ids=dict(source_entity_map),
                        error="ENTITY_ID_MISMATCH",
                    ),
                    support_status=SupportStatus.UNRESOLVED,
                    runtime_error=None,
                )

        if any(_assessment_applies_to_req(a) for a in proposal.source_assessments):
            non_null_entities = {eid for eid in source_entity_map.values() if eid is not None}
            if len(non_null_entities) > 1:
                return ClaimAuditRecord(
                    case_id=case_id,
                    requirement_id=req.requirement_id,
                    claim_id=None,
                    query_anchor=anchor,
                    document_refs=[],
                    entity_binding=EntityBindingAudit(
                        status=EntityBindingStatus.MISMATCHED,
                        claim_entity_id=None,
                        source_entity_ids=dict(source_entity_map),
                        error="ENTITY_ID_MISMATCH",
                    ),
                    support_status=SupportStatus.UNRESOLVED,
                    runtime_error=None,
                )
            return ClaimAuditRecord(
                case_id=case_id,
                requirement_id=req.requirement_id,
                claim_id=None,
                query_anchor=anchor,
                document_refs=[],
                entity_binding=EntityBindingAudit(
                    status=EntityBindingStatus.MATCHED if len(non_null_entities) == 1 else EntityBindingStatus.NOT_APPLICABLE,
                    claim_entity_id=next(iter(non_null_entities)) if len(non_null_entities) == 1 else None,
                    source_entity_ids=dict(source_entity_map) if non_null_entities else {},
                    error=None,
                ),
                support_status=SupportStatus.CONTRADICTED,
                runtime_error=None,
            )

        return ClaimAuditRecord(
            case_id=case_id,
            requirement_id=req.requirement_id,
            claim_id=None,
            query_anchor=anchor,
            document_refs=[],
            entity_binding=EntityBindingAudit(status=EntityBindingStatus.NOT_APPLICABLE),
            support_status=SupportStatus.INSUFFICIENT,
            runtime_error=None,
        )

    def check(
        self,
        request: RequestContract,
        evidence: GovernedEvidenceContract,
        proposal: LLMProposal,
        *,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        """Performs deterministic verification of anchors, citations, and entity bindings."""
        resolved_case_id = case_id if case_id is not None else evidence.authority.request_id
        valid_reqs, invalid_reasons, req_rejections_by_id, global_rejections = (
            self._validate_requirements(request, proposal)
        )

        entity_map_error: str | None = None
        try:
            source_entity_map = resolve_source_entity_map(evidence)
        except ContractError as exc:
            entity_map_error = str(exc)
            source_entity_map = {v.source_id: None for v in evidence.views}

        claims_by_id: dict[str, Claim] = {}
        claims_by_req: dict[str, list[Claim]] = {}
        subject_groups: dict[str, list[Claim]] = {}
        for c in proposal.claims:
            if c.claim_id and c.claim_id not in claims_by_id:
                claims_by_id[c.claim_id] = c
            for rid in c.requirement_ids:
                claims_by_req.setdefault(rid, []).append(c)
            if c.subject_key and c.subject_key.strip():
                subject_groups.setdefault(c.subject_key.strip().casefold(), []).append(c)

        claims_checked = 0
        references_valid = 0
        references_invalid = 0
        rejections: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        audit_records: list[ClaimAuditRecord] = []
        seen_claim_ids: set[str] = set()
        reported_invalid_rids: set[str] = set()
        covered_rids: set[str] = set()
        claim_entities_by_req: dict[str, set[str]] = {}

        if entity_map_error is not None:
            rejections.append({
                "reason": entity_map_error,
                "error_type": "ContractError",
            })

        for assessment in proposal.source_assessments:
            if not (set(assessment.contradicts_claim_ids) <= set(claims_by_id)) or not (
                set(assessment.contradicts_requirement_ids) <= set(valid_reqs)
            ):
                rejections.append({
                    "source_id": assessment.source_id,
                    "reason": "UNKNOWN_CONTRADICTION_TARGET",
                    "error_type": "ContractError",
                })

        # Pass 1: Validate anchors, citations, and source-bound entity bindings per claim
        prepared_claims: list[dict[str, Any]] = []
        claim_entities: dict[str, str | None] = {}

        for claim in proposal.claims:
            claims_checked += 1
            requirement_snippets: list[str] = []
            query_anchors: list[QueryAnchorAudit] = []
            claim_valid = True
            claim_structural_error: str | None = None

            if not claim.claim_id or not claim.text.strip():
                claim_valid = False
                claim_structural_error = "INVALID_CLAIM_REQUIREMENT"
                rejections.append({
                    "claim_id": claim.claim_id,
                    "reason": "INVALID_CLAIM_REQUIREMENT",
                    "error_type": "ContractError",
                })
            elif claim.claim_id in seen_claim_ids:
                claim_valid = False
                claim_structural_error = "DUPLICATE_CLAIM"
                rejections.append({
                    "claim_id": claim.claim_id,
                    "reason": "DUPLICATE_CLAIM",
                    "error_type": "ContractError",
                })
            seen_claim_ids.add(claim.claim_id)

            if not claim.requirement_ids:
                claim_valid = False
                claim_structural_error = claim_structural_error or "INVALID_CLAIM_REQUIREMENT"
                rejections.append({
                    "claim_id": claim.claim_id,
                    "reason": "INVALID_CLAIM_REQUIREMENT",
                    "error_type": "ContractError",
                })
                query_anchors.append(
                    QueryAnchorAudit(
                        requirement_id="",
                        valid=False,
                        error="INVALID_CLAIM_REQUIREMENT",
                    )
                )
            else:
                for rid in claim.requirement_ids:
                    covered_rids.add(rid)
                    key = rid or "<empty>"
                    if rid in valid_reqs:
                        req = valid_reqs[rid]
                        snippet = request.query[req.query_start:req.query_end]
                        requirement_snippets.append(snippet)
                        query_anchors.append(
                            QueryAnchorAudit(
                                requirement_id=rid,
                                start=req.query_start,
                                end=req.query_end,
                                snippet=snippet,
                                valid=True,
                                error=None,
                            )
                        )
                    elif key in invalid_reasons:
                        claim_valid = False
                        reported_invalid_rids.add(key)
                        err = invalid_reasons[key]
                        rejections.append({
                            "claim_id": claim.claim_id,
                            "requirement_id": rid,
                            "reason": err,
                            "error_type": "ContractError",
                        })
                        query_anchors.append(
                            QueryAnchorAudit(
                                requirement_id=rid,
                                valid=False,
                                error=err,
                            )
                        )
                    else:
                        claim_valid = False
                        rejections.append({
                            "claim_id": claim.claim_id,
                            "requirement_id": rid,
                            "reason": "UNKNOWN_REQUIREMENT_ID",
                            "error_type": "ContractError",
                        })
                        query_anchors.append(
                            QueryAnchorAudit(
                                requirement_id=rid,
                                valid=False,
                                error="UNKNOWN_REQUIREMENT_ID",
                            )
                        )

            claim_detail: dict[str, Any] = {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "requirement_ids": list(claim.requirement_ids),
                "requirement_snippets": requirement_snippets,
                "references": [],
                "valid": claim_valid,
            }

            doc_ref_audits: list[DocumentRefAudit] = []
            first_ref_error: str | None = None

            if not claim.evidence:
                claim_detail["valid"] = False
                first_ref_error = "MISSING_EVIDENCE_REFERENCES"
                rejections.append({
                    "claim_id": claim.claim_id,
                    "reason": "MISSING_EVIDENCE_REFERENCES",
                    "error_type": "NO_EVIDENCE",
                })

            for ref in claim.evidence:
                ref_record: dict[str, Any] = {
                    "source_id": ref.source_id,
                    "quote": ref.quote,
                    "span_id": ref.span_id,
                }
                try:
                    view, span, meta = resolve_evidence(evidence, ref)
                    snippet = view.text[span.start:span.end]
                    ref_record.update({
                        "valid": True,
                        "span_id": span.span_id,
                        "start": span.start,
                        "end": span.end,
                        "content_sha256": span.content_sha256,
                        "matched_snippet": snippet,
                        "meta": meta,
                    })
                    doc_ref_audits.append(
                        DocumentRefAudit(
                            source_id=view.source_id,
                            span_id=span.span_id,
                            start=span.start,
                            end=span.end,
                            quote=ref.quote,
                            matched_snippet=snippet,
                            content_sha256=span.content_sha256,
                            valid=True,
                            error=None,
                        )
                    )
                    references_valid += 1
                except ContractError as exc:
                    references_invalid += 1
                    claim_detail["valid"] = False
                    reason = str(exc)
                    first_ref_error = first_ref_error or reason
                    ref_record.update({
                        "valid": False,
                        "error": reason,
                    })
                    doc_ref_audits.append(
                        DocumentRefAudit(
                            source_id=ref.source_id,
                            span_id=ref.span_id,
                            quote=ref.quote,
                            valid=False,
                            error=reason,
                        )
                    )
                    rejections.append({
                        "claim_id": claim.claim_id,
                        "source_id": ref.source_id,
                        "quote": ref.quote,
                        "span_id": ref.span_id,
                        "reason": reason,
                        "error_type": "ContractError",
                    })
                except Exception as exc:
                    references_invalid += 1
                    claim_detail["valid"] = False
                    reason = type(exc).__name__
                    first_ref_error = first_ref_error or reason
                    ref_record.update({
                        "valid": False,
                        "error": reason,
                    })
                    doc_ref_audits.append(
                        DocumentRefAudit(
                            source_id=ref.source_id,
                            span_id=ref.span_id,
                            quote=ref.quote,
                            valid=False,
                            error=reason,
                        )
                    )
                    rejections.append({
                        "claim_id": claim.claim_id,
                        "source_id": ref.source_id,
                        "quote": ref.quote,
                        "span_id": ref.span_id,
                        "reason": reason,
                        "error_type": type(exc).__name__,
                    })

                claim_detail["references"].append(ref_record)

            involved_sources, invalid_dependency, has_mandatory_req_dep = collect_involved_sources(
                claim, claims_by_id, subject_groups, valid_reqs, claims_by_req
            )
            entity_audit = evaluate_entity_binding(
                claim,
                involved_sources,
                source_entity_map,
                has_mandatory_req_dep=has_mandatory_req_dep,
                require_entity_binding=self.require_entity_binding,
            )
            if claim.claim_id:
                claim_entities[claim.claim_id] = entity_audit.claim_entity_id
            if entity_audit.claim_entity_id is not None:
                for rid in claim.requirement_ids:
                    claim_entities_by_req.setdefault(rid, set()).add(entity_audit.claim_entity_id)

            prepared_claims.append({
                "claim": claim,
                "claim_detail": claim_detail,
                "query_anchors": query_anchors,
                "doc_ref_audits": doc_ref_audits,
                "claim_valid": claim_valid,
                "claim_structural_error": claim_structural_error,
                "first_ref_error": first_ref_error,
                "involved_sources": involved_sources,
                "invalid_dependency": invalid_dependency,
                "entity_audit": entity_audit,
            })

        # Pass 2: Evaluate scoped contradictions and support statuses per claim
        for item in prepared_claims:
            claim = item["claim"]
            claim_detail = item["claim_detail"]
            query_anchors = item["query_anchors"]
            doc_ref_audits = item["doc_ref_audits"]
            claim_valid = item["claim_valid"]
            claim_structural_error = item["claim_structural_error"]
            first_ref_error = item["first_ref_error"]
            involved_sources = item["involved_sources"]
            invalid_dependency = item["invalid_dependency"]
            entity_audit = item["entity_audit"]

            all_anchors_valid = claim_valid and all(a.valid for a in query_anchors)
            all_refs_valid = bool(doc_ref_audits) and all(r.valid for r in doc_ref_audits)

            if entity_map_error is not None:
                claim_support_status = SupportStatus.UNRESOLVED
                claim_detail["valid"] = False
            else:
                claim_support_status = evaluate_claim_support_status(
                    claim,
                    query_anchors_valid=all_anchors_valid,
                    document_refs=doc_ref_audits,
                    entity_binding=entity_audit,
                    invalid_dependency=invalid_dependency,
                    involved_sources=involved_sources,
                    source_entity_map=source_entity_map,
                    valid_reqs=valid_reqs,
                    claims_by_req=claims_by_req,
                    claim_entities=claim_entities,
                    proposal=proposal,
                )

            if all_anchors_valid and all_refs_valid and entity_map_error is None:
                if invalid_dependency or any(sid not in source_entity_map for sid in involved_sources):
                    claim_detail["valid"] = False
                    rejections.append({
                        "claim_id": claim.claim_id,
                        "reason": "MISSING_OR_INVALID_DEPENDENCY",
                        "error_type": "ContractError",
                    })
                elif entity_audit.status == EntityBindingStatus.MISMATCHED:
                    claim_detail["valid"] = False
                    rejections.append({
                        "claim_id": claim.claim_id,
                        "reason": "ENTITY_ID_MISMATCH",
                        "error_type": "EntityBindingError",
                    })
                elif entity_audit.status == EntityBindingStatus.MISSING:
                    claim_detail["valid"] = False
                    rejections.append({
                        "claim_id": claim.claim_id,
                        "reason": "MISSING_SOURCE_ENTITY_ID",
                        "error_type": "EntityBindingError",
                    })
                elif claim_support_status == SupportStatus.CONTRADICTED:
                    claim_detail["valid"] = False
                    rejections.append({
                        "claim_id": claim.claim_id,
                        "reason": "SOURCE_CONTRADICTION",
                        "error_type": "SupportError",
                    })
                elif claim_support_status == SupportStatus.INSUFFICIENT:
                    claim_detail["valid"] = False
                    rejections.append({
                        "claim_id": claim.claim_id,
                        "reason": "INSUFFICIENT_EVIDENCE_SUPPORT",
                        "error_type": "SupportError",
                    })

            claim_detail["entity_binding"] = entity_audit.model_dump(mode="json")
            claim_detail["support_status"] = claim_support_status.value
            details.append(claim_detail)

            for anchor in query_anchors:
                per_anchor_status = (
                    SupportStatus.INSUFFICIENT
                    if not anchor.valid
                    else claim_support_status
                )
                audit_records.append(
                    ClaimAuditRecord(
                        case_id=resolved_case_id,
                        requirement_id=anchor.requirement_id,
                        claim_id=claim.claim_id,
                        query_anchor=anchor,
                        document_refs=doc_ref_audits,
                        entity_binding=entity_audit,
                        support_status=per_anchor_status,
                        runtime_error=entity_map_error,
                    )
                )

        for key, rej in req_rejections_by_id.items():
            if key not in reported_invalid_rids:
                rejections.append(rej)
        rejections.extend(global_rejections)

        all_cited_sources = {r.source_id for c in proposal.claims for r in c.evidence}
        for rid, req in valid_reqs.items():
            if rid not in covered_rids:
                audit_records.append(
                    self._uncovered_requirement_record(
                        resolved_case_id,
                        req,
                        request.query,
                        proposal,
                        source_entity_map,
                        claim_entities_by_req,
                        all_cited_sources,
                    )
                )

        # Flag any multi-requirement CONTRADICTS assessment on an active entity that failed to
        # specify which claim or requirement it contradicts (without poisoning unrelated claims).
        if entity_map_error is None and not any(r.support_status == SupportStatus.CONTRADICTED for r in audit_records):
            active_entities = {eid for eid in claim_entities.values() if eid is not None}
            any_global_entity = any(eid is not None for eid in source_entity_map.values())
            for assessment in proposal.source_assessments:
                if (
                    assessment.relation == "CONTRADICTS"
                    and assessment.source_id in source_entity_map
                    and not assessment.contradicts_claim_ids
                    and not assessment.contradicts_requirement_ids
                    and assessment.source_id not in all_cited_sources
                ):
                    src_eid = source_entity_map[assessment.source_id]
                    if (src_eid is not None and src_eid in active_entities) or (not any_global_entity and claims_checked > 0):
                        rejections.append({
                            "source_id": assessment.source_id,
                            "reason": "UNSCOPED_CONTRADICTION_ASSESSMENT",
                            "error_type": "ContractError",
                        })

        entity_summary = {
            "matched": sum(1 for r in audit_records if r.entity_binding.status == EntityBindingStatus.MATCHED),
            "mismatched": sum(1 for r in audit_records if r.entity_binding.status == EntityBindingStatus.MISMATCHED),
            "missing": sum(1 for r in audit_records if r.entity_binding.status == EntityBindingStatus.MISSING),
            "not_applicable": sum(1 for r in audit_records if r.entity_binding.status == EntityBindingStatus.NOT_APPLICABLE),
        }

        record_statuses = {r.support_status for r in audit_records}
        if SupportStatus.CONTRADICTED in record_statuses:
            overall_support = SupportStatus.CONTRADICTED
        elif SupportStatus.UNRESOLVED in record_statuses:
            overall_support = SupportStatus.UNRESOLVED
        elif rejections or references_invalid > 0 or claims_checked == 0 or SupportStatus.INSUFFICIENT in record_statuses:
            overall_support = SupportStatus.INSUFFICIENT
        else:
            overall_support = SupportStatus.SUPPORTED

        if rejections or references_invalid > 0:
            status = "REJECTED"
        elif claims_checked == 0:
            status = "EMPTY_PROPOSAL"
        else:
            status = "ACCEPTED"

        return {
            "status": status,
            "support_status": overall_support.value,
            "local_only": self.local_only,
            "claims_checked": claims_checked,
            "references_valid": references_valid,
            "references_invalid": references_invalid,
            "entity_binding_summary": entity_summary,
            "details": details,
            "records": [r.model_dump(mode="json") for r in audit_records],
            "rejections": rejections,
        }
