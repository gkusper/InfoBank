# Public grounding trace v1 — experimental

Phase C runs deterministically after cached/live comparisons. No new prompt/schema or model API. Primary runtime sidecars record NOT_EXECUTED_PRIMARY_COMPARISON.

Eligibility requires contract-valid FULL, valid semantic assessment, exact response/candidate match, explicit sufficient/complete/referent/relation requirement properties, matching global/requirement/role span references and explicit PRIMARY/SUPPORTS roles. References are checked against the authorized request, offsets and source hash. Stable neutral marker and answer hash identify the candidate-group association.

This establishes reference validity and traceable assertion provenance, not independent claim entailment. It does not attach all PRIMARY sources to all sentences. A control paraphrase is not silently equated to the candidate. Unsupported claims with valid references remain possible and are tested.

The sidecar separates citations, eligible for verified rendering, from unverified_associations. Candidate-group associations get CITATION_SUPPORT_UNVERIFIED and render_as_verified_claim_citation=false. No independent per-claim mapping proves entailment in this version, so citations stays empty. Coverage is zero; missing citations/citationless FULL remain explicit. Zero invalid emitted citations is not success.

Actual run: 26 T3 and 19 control mechanically valid unverified associations, zero verified claim citations and zero actual inline/rendered citations. Different counts reflect exact-copy eligibility, not factuality. This component remains experimental until separately tested claim mapping/realization exists.
