# Reviewer-v2 candidate annotation guideline

This guideline applies to the non-frozen reviewer-v2 candidate. It does not assert that human annotation or adjudication is complete.

## Required fields

Each case must record:

- `case_id`, split, object family, template family, and document package;
- query class: direct answer, multi-document, no-answer, conflict, citation, hard-negative, Aggregate threshold, purpose/expiry, stale-index, or permission lifecycle;
- expected output class from the controlled-failure vocabulary;
- gold document IDs and exact page/message ranges;
- reference answer for supported cases, otherwise a refusal reason and reason code;
- evidence role: primary, contextual, contrastive, aggregate-only, or governance-excluded;
- action status where applicable: OPEN, CLOSED_COMPLETED, CLOSED_CANCELLED, SUPERSEDED, or not applicable;
- source type, licence/provenance, and redistribution status.

## Decision rules

1. Apply authorization before evidence scoring. Deny and archived sources never support an output or citation.
2. Metadata permits only declared metadata fields and never document-content claims.
3. Aggregate individual content is never copied into a reference answer. Below the configured distinct-contributor threshold, label `REFUSE_AGGREGATION_THRESHOLD` without revealing a source count.
4. A direct answer must be entailed by all cited claims and use the exact gold page/message range.
5. Multi-document cases require every indispensable source. Missing one indispensable source is insufficient evidence.
6. Unresolved contradiction uses `REFUSE_CONFLICT` or a constrained answer only when the configuration explicitly permits a bounded conflict summary.
7. No-answer and wrong-object hard negatives must not inherit facts from a similar model or device family.
8. Browser history is contextual only and cannot create a new action.

## Human workflow

Annotators work from source packages rather than model output. Disagreements are placed in the adjudication sheet with both labels and a short factual rationale. Candidate-holdout labels must not be used to tune thresholds. A later freeze records annotator IDs, completion status, second-annotation assignment, adjudication state, and sign-off; none is fabricated by the builder.
