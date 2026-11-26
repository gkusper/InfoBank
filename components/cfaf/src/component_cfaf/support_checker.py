"""Deterministic local support and reference checker; 0 API calls.

This module implements the SupportChecker protocol for offline, deterministic
validation of source citations and claim evidence within the CFAF framework.
"""
from graphlib import CycleError, TopologicalSorter
from typing import Any
from .contracts import (
    GovernedEvidenceContract,
    LLMProposal,
    RequestContract,
    Requirement,
    ValueType,
)
from .gate import ContractError, resolve_evidence


class ReferenceSupportChecker:
    """Local shadow checker for validating factual claim references.

    Adheres strictly to the CFAF constraints:
    - local_only = True: 0 external API calls allowed.
    - Deterministic evaluation using existing gate contracts and resolvers.
    - Pure shadow verification: output is written only to private audit traces.
    """
    local_only: bool = True

    def __init__(self) -> None:
        pass

    @staticmethod
    def _validate_requirements(
        request: RequestContract,
        proposal: LLMProposal,
    ) -> tuple[dict[str, Requirement], dict[str, str], dict[str, dict[str, Any]], list[dict[str, Any]]]:
        """Validates proposal requirements against the original request contract.

        Returns:
            - valid_reqs: mapping of validated requirement_id -> Requirement (both base and added)
            - invalid_reasons: mapping of invalid requirement_id -> error reason code
            - req_rejections_by_id: mapping of invalid/missing requirement_id -> rejection dict
            - global_rejections: structural requirement rejections not tied to a single ID
        """
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

    def check(
        self,
        request: RequestContract,
        evidence: GovernedEvidenceContract,
        proposal: LLMProposal,
    ) -> dict[str, Any]:
        """Performs deterministic verification of all claim citations in the proposal.

        Evaluates each claim's requirement anchors and evidence references:
        - Validates both original request requirements and proposal-added anchored
          requirements (query_start:query_end bounds and non-empty slices), rejecting
          unknown requirement IDs or invalid query spans.
        - Reuses gate.resolve_evidence() to verify source existence, SHA-256 integrity,
          exact quote matching, and span uniqueness.
        - Records verified document snippets and flags invalid or unauthorized sources.
        """
        valid_reqs, invalid_reasons, req_rejections_by_id, global_rejections = (
            self._validate_requirements(request, proposal)
        )

        claims_checked = 0
        references_valid = 0
        references_invalid = 0
        rejections: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        seen_claim_ids: set[str] = set()
        reported_invalid_rids: set[str] = set()

        for claim in proposal.claims:
            claims_checked += 1
            requirement_snippets: list[str] = []
            claim_valid = True

            if not claim.claim_id or not claim.text.strip():
                claim_valid = False
                rejections.append({
                    "claim_id": claim.claim_id,
                    "reason": "INVALID_CLAIM_REQUIREMENT",
                    "error_type": "ContractError",
                })
            elif claim.claim_id in seen_claim_ids:
                claim_valid = False
                rejections.append({
                    "claim_id": claim.claim_id,
                    "reason": "DUPLICATE_CLAIM",
                    "error_type": "ContractError",
                })
            seen_claim_ids.add(claim.claim_id)

            if not claim.requirement_ids:
                claim_valid = False
                rejections.append({
                    "claim_id": claim.claim_id,
                    "reason": "INVALID_CLAIM_REQUIREMENT",
                    "error_type": "ContractError",
                })
            else:
                for rid in claim.requirement_ids:
                    key = rid or "<empty>"
                    if rid in valid_reqs:
                        req = valid_reqs[rid]
                        requirement_snippets.append(request.query[req.query_start:req.query_end])
                    elif key in invalid_reasons:
                        claim_valid = False
                        reported_invalid_rids.add(key)
                        rejections.append({
                            "claim_id": claim.claim_id,
                            "requirement_id": rid,
                            "reason": invalid_reasons[key],
                            "error_type": "ContractError",
                        })
                    else:
                        claim_valid = False
                        rejections.append({
                            "claim_id": claim.claim_id,
                            "requirement_id": rid,
                            "reason": "UNKNOWN_REQUIREMENT_ID",
                            "error_type": "ContractError",
                        })

            claim_detail: dict[str, Any] = {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "requirement_ids": list(claim.requirement_ids),
                "requirement_snippets": requirement_snippets,
                "references": [],
                "valid": claim_valid,
            }

            if not claim.evidence:
                claim_detail["valid"] = False
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
                    references_valid += 1
                except ContractError as exc:
                    references_invalid += 1
                    claim_detail["valid"] = False
                    reason = str(exc)
                    ref_record.update({
                        "valid": False,
                        "error": reason,
                    })
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
                    ref_record.update({
                        "valid": False,
                        "error": reason,
                    })
                    rejections.append({
                        "claim_id": claim.claim_id,
                        "source_id": ref.source_id,
                        "quote": ref.quote,
                        "span_id": ref.span_id,
                        "reason": reason,
                        "error_type": type(exc).__name__,
                    })

                claim_detail["references"].append(ref_record)

            details.append(claim_detail)

        for key, rej in req_rejections_by_id.items():
            if key not in reported_invalid_rids:
                rejections.append(rej)
        rejections.extend(global_rejections)

        if rejections or references_invalid > 0:
            status = "REJECTED"
        elif claims_checked == 0:
            status = "EMPTY_PROPOSAL"
        else:
            status = "ACCEPTED"

        return {
            "status": status,
            "local_only": self.local_only,
            "claims_checked": claims_checked,
            "references_valid": references_valid,
            "references_invalid": references_invalid,
            "details": details,
            "rejections": rejections,
        }
