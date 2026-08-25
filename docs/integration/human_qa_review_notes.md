# Human QA Review Notes

Review date: 2026-08-24

Review type: author human review

Overall status: HUMAN_QA_STATUS: APPROVED

Benchmark status: BENCHMARK_STATUS: NOT_YET_FROZEN

These notes record author human validation for all 12 S1/S2 benchmark cases. They do not claim multiple independent annotators, inter-annotator agreement, benchmark freeze, final E1, or publication evaluation completion.

## S1-Q1

Status: HUMAN_VALIDATED

Question: I spilled coffee on my sofa. How should I clean it?

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- lunara-s3-care-guide.pdf

Acceptable pages:
- lunara-s3-care-guide.pdf: 1

Rationale: The care guide contains the approved cleaning instructions for the coffee-spill question.

## S1-Q2

Status: HUMAN_VALIDATED

Question: When did I buy this sofa?

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- lunara-s3-purchase-receipt.pdf

Acceptable pages:
- lunara-s3-purchase-receipt.pdf: 1

Rationale: The purchase receipt establishes the approved purchase date.

## S1-Q3

Status: HUMAN_VALIDATED

Question: Can I use chlorine bleach?

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- lunara-s3-care-guide.pdf

Acceptable pages:
- lunara-s3-care-guide.pdf: 1

Rationale: The care guide contains the approved bleach prohibition evidence.

## S1-Q4

Status: HUMAN_VALIDATED

Question: How long is the manufacturer's warranty?

Expected output class: REFUSE_INSUFFICIENT_EVIDENCE

Reason code: insufficient_evidence

Required documents:
- none

Acceptable pages:
- none

Rationale: The available Lunara S3 documents do not establish the manufacturer's warranty duration.

## S1-Q5

Status: HUMAN_VALIDATED

Question: How much did I pay for the sofa?

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- lunara-s3-purchase-receipt.pdf

Acceptable pages:
- lunara-s3-purchase-receipt.pdf: 1

Rationale: The purchase receipt establishes the approved paid amount.

## S1-Q6

Status: HUMAN_VALIDATED

Question: Do the care guide and purchase receipt refer to the same sofa?

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- lunara-s3-care-guide.pdf
- lunara-s3-purchase-receipt.pdf

Acceptable pages:
- lunara-s3-care-guide.pdf: 1
- lunara-s3-purchase-receipt.pdf: 1

Rationale: The question asks for a relationship between two separate documents, so both documents must be inspected and compared.

## S2-Q1

Status: HUMAN_VALIDATED

Question: Which television do I own, when did I purchase it, and what was the price?

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- velora-v55-purchase-receipt.pdf

Acceptable pages:
- velora-v55-purchase-receipt.pdf: 1

Rationale: The purchase receipt establishes the approved model, purchase date, and price.

## S2-Q2

Status: HUMAN_VALIDATED

Question: Is my Velora V55 still covered by the manufacturer warranty on 21 August 2026? Explain using the purchase record and the manufacturer warranty terms.

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- velora-v55-purchase-receipt.pdf
- velora-v55-manufacturer-warranty-terms.pdf

Acceptable pages:
- velora-v55-purchase-receipt.pdf: 1
- velora-v55-manufacturer-warranty-terms.pdf: 2

Rationale: The receipt establishes the purchase date, and the warranty terms establish the applicable warranty duration/rule.

## S2-Q3

Status: HUMAN_VALIDATED

Question: My Velora V55 shows error E06 while I am using an HDMI source. What does E06 mean, and what should I do first?

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- velora-v55-user-manual.pdf

Acceptable pages:
- velora-v55-user-manual.pdf: 17

Rationale: The user manual page 17 contains the approved E06 meaning and first recovery step.

## S2-Q4

Status: HUMAN_VALIDATED

Question: How many HDMI and USB-A ports does the Velora V55 have, and what other wired connections are listed?

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- velora-v55-product-specification.pdf

Acceptable pages:
- velora-v55-product-specification.pdf: 3

Rationale: The product specification page 3 contains the approved port and wired-connection facts.

## S2-Q5

Status: HUMAN_VALIDATED

Question: Do the documents establish that the 18-month regional service period replaces the 24-month manufacturer warranty for my Velora V55? Explain the two periods without assuming that one supersedes the other.

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- velora-v55-manufacturer-warranty-terms.pdf
- velora-v55-regional-service-notice.pdf

Acceptable pages:
- velora-v55-manufacturer-warranty-terms.pdf: 2
- velora-v55-regional-service-notice.pdf: 1

Rationale: The complete request asks to explain both periods, so evidence is required for both the manufacturer warranty and regional service period.

## S2-Q6

Status: HUMAN_VALIDATED

Question: For the Velora V55, product code VEL-V55-2025, does error E06 mean a temperature-sensor fault as described in the Aster M55 manual, or does it mean something else? Use only the matching product documents.

Expected output class: FULL_ANSWER

Reason code: supported

Required documents:
- velora-v55-user-manual.pdf

Acceptable pages:
- velora-v55-user-manual.pdf: 17
- velora-v55-user-manual.pdf: 20

Rationale: Page 17 provides the detailed E06 definition. Page 20 also establishes, within the matching Velora V55 manual, that E06 is an HDMI-related error and is sufficient to distinguish it from the Aster M55 temperature-sensor interpretation.
