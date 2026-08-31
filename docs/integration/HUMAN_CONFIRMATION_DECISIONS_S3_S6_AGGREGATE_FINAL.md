# S3–S6 Aggregate Human Confirmation Decisions

Review date: 2026-08-31

Review state: COMPLETE

Source package: `S3_S6_AGGREGATE_HUMAN_CONFIRMATION_PACKET_V1.zip`

Source package SHA-256: `e25c94f9fcbd5c431a4526d2cc4692121d11fbb8d594f62b635e0ac0e0fa5191`

Uploaded decision-file SHA-256: `ef84f91b0766f8607cdc356ad235e5daf1313e9975148a84550fdcb707e76525`

Provenance note: The uploaded source file is preserved unchanged as source evidence. Its final approved summary supersedes the stale incremental review-state header; this repository copy normalizes only that status header and does not change any author decision.

## Decision AHC-001 — S3-Q2

Question:

> Across my first three confirmed orders in 2026 that contained dairy milk, what was the average number of days between consecutive orders?

Reviewed contract:

- Persistent permission: Aggregate
- Effective use decision: Aggregate
- Minimum contributor threshold: `k=3`
- Unique contributors: `3`
- Expected output class: `AGGREGATE_RESULT`
- Approved public result: `14.5 days`
- Public document-level citations: prohibited
- Individual dates, order identifiers, component intervals, source identifiers, quantities, amounts, and component calculations: prohibited

Actual C2 public output:

> Governed aggregate mean: 14.5 days.

Actual C3 public output:

> Governed aggregate mean: 14.5 days.

Author decision:

- C2 output acceptable: YES
- C3 output acceptable: YES
- No prohibited information disclosed: YES
- Contributor and threshold semantics correct: YES
- Case confirmed overall: YES

Status: `HUMAN_CONFIRMED`

## Decision AHC-002 — S3-Q4

Question:

> How many litres of dairy milk were confirmed across the three January 2026 orders?

Reviewed contract:

- Persistent permission: Aggregate
- Effective use decision: Aggregate
- Minimum contributor threshold: `k=3`
- Unique contributors: `3`
- Expected output class: `AGGREGATE_RESULT`
- Approved public result: `3 litres`
- Public document-level citations: prohibited
- Individual quantities, dates, order identifiers, source identifiers, and component calculations: prohibited

Actual C2 public output:

> Governed aggregate sum: 3 litres.

Actual C3 public output:

> Governed aggregate sum: 3 litres.

Author decision:

- C2 output acceptable: YES
- C3 output acceptable: YES
- No prohibited information disclosed: YES
- Contributor and threshold semantics correct: YES
- Case confirmed overall: YES

Status: `HUMAN_CONFIRMED`

## Decision AHC-003 — S3-Q6

Question:

> How many litres of dairy milk were confirmed across the three February 2026 orders?

Reviewed contract:

- Persistent permission: Aggregate
- Effective use decision: Aggregate
- Minimum contributor threshold: `k=3`
- Unique contributors: `3`
- Expected output class: `AGGREGATE_RESULT`
- Approved public result: `5 litres`
- Public document-level citations: prohibited
- Individual quantities, dates, order identifiers, source identifiers, component calculations, and document-level citations: prohibited

Actual C2 public output:

> Governed aggregate sum: 5 litres.

Actual C3 public output:

> Governed aggregate sum: 5 litres.

Author decision:

- C2 output acceptable: YES
- C3 output acceptable: YES
- No prohibited information disclosed: YES
- Contributor and threshold semantics correct: YES
- Case confirmed overall: YES

Status: `HUMAN_CONFIRMED`

## Decision AHC-004 — S3-Q9

Question:

> Across my current March 2026 orders, counting any reissued confirmation only once, how many litres of dairy milk were confirmed?

Reviewed contract:

- Persistent permission: Aggregate
- Effective use decision: Aggregate
- Minimum contributor threshold: `k=2`
- Raw document representations: `3`
- Unique contributors after reissue deduplication: `2`
- Expected output class: `AGGREGATE_RESULT`
- Approved public result: `6 litres`
- Public document-level citations: prohibited
- Individual quantities, dates, order identifiers, source or document identifiers, reissue relationships, component calculations, and document-level citations: prohibited

Actual C2 public output:

> Governed aggregate sum: 6 litres.

Actual C3 public output:

> Governed aggregate sum: 6 litres.

Author decision:

- C2 output acceptable: YES
- C3 output acceptable: YES
- No prohibited information disclosed: YES
- Contributor and threshold semantics correct: YES
- Reissued confirmation counted only once: YES
- Case confirmed overall: YES

Status: `HUMAN_CONFIRMED`

## Decision AHC-005 — S4B-Q3

Question:

> Across my February CedarCart Online orders, what was the overall net difference between the bank charges and the confirmed amounts, and how large were the discrepancies in total?

Reviewed contract:

- Persistent permission: Aggregate
- Effective use decision: Aggregate
- Minimum contributor threshold: `k=2`
- Unique contributors: `2`
- Expected output class: `AGGREGATE_RESULT`
- Approved public results:
  - overall net difference: `+50 HUF`
  - total discrepancy magnitude: `350 HUF`
- Public document-level citations: prohibited
- Individual confirmed amounts, bank charges, order or transaction identifiers, individual discrepancies, source or document identifiers, and component calculations: prohibited

Actual C2 public output:

> Governed aggregate net difference: +50 HUF; total discrepancy magnitude: 350 HUF.

Actual C3 public output:

> Governed aggregate net difference: +50 HUF; total discrepancy magnitude: 350 HUF.

Author decision:

- C2 output acceptable: YES
- C3 output acceptable: YES
- No prohibited information disclosed: YES
- Contributor and threshold semantics correct: YES
- Case confirmed overall: YES

Status: `HUMAN_CONFIRMED`

## Decision AHC-006 — S4B-Q6

Question:

> How much did I spend on CedarCart Online in February 2026, excluding physical-store purchases?

Reviewed contract:

- Persistent permission: Aggregate
- Effective use decision: Aggregate
- Minimum contributor threshold: `k=3`
- Valid contributor count: `2`
- Expected output class: `REFUSE_AGGREGATION_THRESHOLD`
- Expected reason: `aggregation_threshold_not_met`
- The public response must not disclose:
  - the withheld aggregate value `16,050 HUF`;
  - component values `7,090 HUF`, `8,960 HUF`, or `3,740 HUF`;
  - the contributor count;
  - transaction details or dates;
  - source or document identifiers;
  - document-level citations.

Actual C2 public output:

> A governed aggregate result is unavailable for this request.

Actual C3 public output:

> A governed aggregate result is unavailable for this request.

Author decision:

- C2 output acceptable: YES
- C3 output acceptable: YES
- No prohibited information disclosed: YES
- Contributor and threshold semantics correct: YES
- Case confirmed overall: YES

Status: `HUMAN_CONFIRMED`

# Final Aggregate Human-Confirmation Status

Confirmed cases:

- S3-Q2
- S3-Q4
- S3-Q6
- S3-Q9
- S4B-Q3
- S4B-Q6

Summary:

- Human-confirmation case count: `6`
- Confirmed case count: `6`
- Rejected case count: `0`
- C2 outputs accepted: `6/6`
- C3 outputs accepted: `6/6`
- Prohibited-disclosure findings accepted as absent: `6/6`
- Contributor and threshold semantics confirmed: `6/6`

`AUTHOR_CONFIRMATION_STATUS: APPROVED`

`AGGREGATE_HUMAN_CONFIRMATION_COMPLETE: YES`
