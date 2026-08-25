# Human Confirmation Pass v1

Review date: 2026-08-25

Review type: author lightweight human confirmation

Overall status: HUMAN_CONFIRMATION_STATUS: APPROVED_WITH_DOCUMENTED_LIMITATIONS

Human-QA status: HUMAN_QA_STATUS: APPROVED

Benchmark status at confirmation: BENCHMARK_STATUS: NOT_YET_FROZEN

Reference run: `../s1s2_c3_20260824_reverted_baseline_01`

This artifact records the author's completed confirmation decisions for all 12 S1/S2 benchmark cases. It distinguishes fully confirmed cases from cases where the answer content is accepted but the runtime citation set is incomplete. It does not change gold, scorer semantics, or implementation behavior.

## Decision Table

| Case ID | Author decision | Citation status | Limitation | Human confirmation record |
|---|---|---|---|---|
| S1-Q1 | CONFIRMED | complete | none | Coffee-spill cleaning answer is grounded in `lunara-s3-care-guide.pdf` page 1. |
| S1-Q2 | CONFIRMED | complete | none | Purchase-date answer is grounded in `lunara-s3-purchase-receipt.pdf` page 1. |
| S1-Q3 | CONFIRMED | complete | none | Chlorine-bleach answer is grounded in `lunara-s3-care-guide.pdf` page 1. |
| S1-Q4 | CONFIRMED | no citation required | none | Correctly returns `REFUSE_INSUFFICIENT_EVIDENCE`; no misleading citation is emitted. |
| S1-Q5 | CONFIRMED | complete | none | Price answer is grounded only in `lunara-s3-purchase-receipt.pdf` page 1; unsupported care-guide citation is absent. |
| S1-Q6 | NOT_CONFIRMED_AS_FULLY_CORRECT | incomplete | MULTI_DOCUMENT_CITATION_COMPLETENESS | Answer content accepted, but both `lunara-s3-care-guide.pdf` page 1 and `lunara-s3-purchase-receipt.pdf` page 1 are required; runtime cites only the purchase receipt. Scorer FAIL is legitimate. |
| S2-Q1 | CONFIRMED | complete | none | Model, purchase date, and price are grounded in `velora-v55-purchase-receipt.pdf` page 1. |
| S2-Q2 | NOT_CONFIRMED_AS_FULLY_CORRECT | incomplete | MULTI_DOCUMENT_CITATION_COMPLETENESS | Answer content accepted, but both the purchase receipt page 1 and manufacturer warranty terms page 2 are required; runtime cites only the purchase receipt. Scorer FAIL is legitimate. |
| S2-Q3 | CONFIRMED | complete | none | E06 meaning and recovery answer is grounded in `velora-v55-user-manual.pdf` page 17. |
| S2-Q4 | CONFIRMED | complete | none | Connection/port answer is grounded in `velora-v55-product-specification.pdf` page 3; unsupported manual page-10 citation is absent. |
| S2-Q5 | NOT_CONFIRMED_AS_FULLY_CORRECT | incomplete | MULTI_DOCUMENT_CITATION_COMPLETENESS | Answer content accepted, but both `velora-v55-manufacturer-warranty-terms.pdf` page 2 and `velora-v55-regional-service-notice.pdf` page 1 are required; runtime cites only the warranty terms. Scorer FAIL is legitimate. |
| S2-Q6 | CONFIRMED | complete | none | Runtime cites `velora-v55-user-manual.pdf` page 20; human-approved gold accepts page 17 or page 20. |

## Summary

Fully confirmed cases:

- S1-Q1
- S1-Q2
- S1-Q3
- S1-Q4
- S1-Q5
- S2-Q1
- S2-Q3
- S2-Q4
- S2-Q6

Confirmed as correct answer content but with documented citation-completeness limitation:

- S1-Q6
- S2-Q2
- S2-Q5

Unsupported extra citations: 0

Wrong-page citations: 0

MULTI_DOCUMENT_CITATION_COMPLETENESS: DOCUMENTED_LIMITATION

HUMAN_CONFIRMATION_STATUS: APPROVED_WITH_DOCUMENTED_LIMITATIONS
