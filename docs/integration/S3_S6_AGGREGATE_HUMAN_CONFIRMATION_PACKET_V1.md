# S3-S6 Aggregate Human Confirmation Packet V1

This canonical packet records completed author confirmation for the six Aggregate-only cases.

AUTHOR_CONFIRMATION_STATUS: APPROVED
AGGREGATE_HUMAN_CONFIRMATION_COMPLETE: YES

Primary evidence remains the successful MariaDB-backed C2/C3 focused run. C0/C1 outputs are outside this confirmation scope.

## S3-Q2

### Original question

Across my first three confirmed orders in 2026 that contained dairy milk, what was the average number of days between consecutive orders?

### Expected aggregate/refusal behavior

- Expected output class: `AGGREGATE_RESULT`
- Expected reason code: `aggregate_threshold_satisfied`
- Threshold k: `3`
- Policy fixture: `S3-Q2:aggregate`
- Expected contributor count: `3`
- Persistent permission: `Aggregate`
- Effective use decision: `Aggregate`

### Exact public outputs

- C2: Governed aggregate mean: 14.5 days.
- C3: Governed aggregate mean: 14.5 days.
- C2 public citations: []
- C3 public citations: []

### Author confirmation

- [x] C2 output acceptable: YES
- [x] C3 output acceptable: YES
- [x] No prohibited information disclosed: YES
- [x] Contributor and threshold semantics correct: YES
- [x] Case confirmed overall: YES
- Author notes: none
- Status: `APPROVED`

## S3-Q4

### Original question

How many litres of dairy milk were confirmed across the three January 2026 orders?

### Expected aggregate/refusal behavior

- Expected output class: `AGGREGATE_RESULT`
- Expected reason code: `aggregate_threshold_satisfied`
- Threshold k: `3`
- Policy fixture: `S3-Q4:aggregate`
- Expected contributor count: `3`
- Persistent permission: `Aggregate`
- Effective use decision: `Aggregate`

### Exact public outputs

- C2: Governed aggregate sum: 3 litres.
- C3: Governed aggregate sum: 3 litres.
- C2 public citations: []
- C3 public citations: []

### Author confirmation

- [x] C2 output acceptable: YES
- [x] C3 output acceptable: YES
- [x] No prohibited information disclosed: YES
- [x] Contributor and threshold semantics correct: YES
- [x] Case confirmed overall: YES
- Author notes: none
- Status: `APPROVED`

## S3-Q6

### Original question

How many litres of dairy milk were confirmed across the three February 2026 orders?

### Expected aggregate/refusal behavior

- Expected output class: `AGGREGATE_RESULT`
- Expected reason code: `aggregate_threshold_satisfied`
- Threshold k: `3`
- Policy fixture: `S3-Q6:aggregate`
- Expected contributor count: `3`
- Persistent permission: `Aggregate`
- Effective use decision: `Aggregate`

### Exact public outputs

- C2: Governed aggregate sum: 5 litres.
- C3: Governed aggregate sum: 5 litres.
- C2 public citations: []
- C3 public citations: []

### Author confirmation

- [x] C2 output acceptable: YES
- [x] C3 output acceptable: YES
- [x] No prohibited information disclosed: YES
- [x] Contributor and threshold semantics correct: YES
- [x] Case confirmed overall: YES
- Author notes: none
- Status: `APPROVED`

## S3-Q9

### Original question

Across my current March 2026 orders, counting any reissued confirmation only once, how many litres of dairy milk were confirmed?

### Expected aggregate/refusal behavior

- Expected output class: `AGGREGATE_RESULT`
- Expected reason code: `aggregate_threshold_satisfied`
- Threshold k: `2`
- Policy fixture: `S3-Q9:aggregate`
- Expected contributor count: `2`
- Persistent permission: `Aggregate`
- Effective use decision: `Aggregate`

### Exact public outputs

- C2: Governed aggregate sum: 6 litres.
- C3: Governed aggregate sum: 6 litres.
- C2 public citations: []
- C3 public citations: []

### Author confirmation

- [x] C2 output acceptable: YES
- [x] C3 output acceptable: YES
- [x] No prohibited information disclosed: YES
- [x] Contributor and threshold semantics correct: YES
- [x] Reissued confirmation counted only once: YES
- [x] Case confirmed overall: YES
- Author notes: none
- Status: `APPROVED`

## S4B-Q3

### Original question

Across my February CedarCart Online orders, what was the overall net difference between the bank charges and the confirmed amounts, and how large were the discrepancies in total?

### Expected aggregate/refusal behavior

- Expected output class: `AGGREGATE_RESULT`
- Expected reason code: `aggregate_threshold_satisfied`
- Threshold k: `2`
- Policy fixture: `S4B-Q3:aggregate`
- Expected contributor count: `2`
- Persistent permission: `Aggregate`
- Effective use decision: `Aggregate`

### Exact public outputs

- C2: Governed aggregate net difference: +50 HUF; total discrepancy magnitude: 350 HUF.
- C3: Governed aggregate net difference: +50 HUF; total discrepancy magnitude: 350 HUF.
- C2 public citations: []
- C3 public citations: []

### Author confirmation

- [x] C2 output acceptable: YES
- [x] C3 output acceptable: YES
- [x] No prohibited information disclosed: YES
- [x] Contributor and threshold semantics correct: YES
- [x] Case confirmed overall: YES
- Author notes: none
- Status: `APPROVED`

## S4B-Q6

### Original question

How much did I spend on CedarCart Online in February 2026, excluding physical-store purchases?

### Expected aggregate/refusal behavior

- Expected output class: `REFUSE_AGGREGATION_THRESHOLD`
- Expected reason code: `aggregation_threshold_not_met`
- Threshold k: `3`
- Policy fixture: `S4B-Q6:aggregate`
- Expected contributor count: `2`
- Persistent permission: `Aggregate`
- Effective use decision: `Aggregate`

### Exact public outputs

- C2: A governed aggregate result is unavailable for this request.
- C3: A governed aggregate result is unavailable for this request.
- C2 public citations: []
- C3 public citations: []

### Author confirmation

- [x] C2 output acceptable: YES
- [x] C3 output acceptable: YES
- [x] No prohibited information disclosed: YES
- [x] Contributor and threshold semantics correct: YES
- [x] Case confirmed overall: YES
- Author notes: none
- Status: `APPROVED`
