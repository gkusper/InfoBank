"""Deterministic local support and reference checker; 0 API calls.

This module implements the SupportChecker protocol for offline, deterministic
validation of source citations and claim evidence within the CFAF framework.
"""
from typing import Any
from .contracts import (
    RequestContract,
    GovernedEvidenceContract,
    LLMProposal,

)
from .gate import resolve_evidence, ContractError


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

    def check(
        self,
        request: RequestContract,
        evidence: GovernedEvidenceContract,
        proposal: LLMProposal
    ) -> dict[str, Any]:
        """Performs deterministic verification of all claim citations in the proposal.
        
        Evaluates each claim's evidence references against permitted views:
        - Reuses gate.resolve_evidence() to verify source existence, SHA-256 integrity,
          exact quote matching, and span uniqueness.
        - Links requirements to the original query snippets (query_start:query_end).
        - Records verified document snippets and flags invalid or unauthorized sources.
        """
        requirements_by_id = {r.requirement_id: r for r in request.requirements}

        claims_checked = 0
        references_valid = 0
        references_invalid = 0
        rejections: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []

        for claim in proposal.claims:
            claims_checked += 1
            claim_detail: dict[str, Any] = {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "requirement_ids": claim.requirement_ids,
                "requirement_snippets": [
                    request.query[requirements_by_id[rid].query_start:requirements_by_id[rid].query_end]
                    for rid in claim.requirement_ids
                    if rid in requirements_by_id
                ],
                "references": [],
                "valid": True,
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

        status = "ACCEPTED" if (claims_checked > 0 and references_invalid == 0 and not rejections) else "REJECTED"
        if claims_checked == 0:
            status = "EMPTY_PROPOSAL"

        return {
            "status": status,
            "local_only": self.local_only,
            "claims_checked": claims_checked,
            "references_valid": references_valid,
            "references_invalid": references_invalid,
            "details": details,
            "rejections": rejections,
        }
