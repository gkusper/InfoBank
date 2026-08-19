# Citation audit guide

Automatic scorer: `infocom-citation-scorer-v1` in `evaluation/d_gate.py`.

## Automatic metrics

- citation support precision: cited responses whose claim is supported by the cited source;
- citation coverage: answerable cases with at least one supporting citation;
- wrong-page rate: citations outside the case's gold page/message range;
- unsupported-claim rate: full answers for cases that require withholding/refusal;
- invalid chunk/document association: chunk metadata document ID differs from cited document ID;
- inaccessible citation rate: citation points to a source unavailable under the evaluated policy.

The automatic scorer checks case identity before scoring. It does not judge prose nuance or whether all material clauses in a long answer are supported.

## Pending manual audit

`scripts/run_d_gate.py` preselects 40 B3 candidate responses into ignored `artifacts/d_gate/b0_b3/manual_citation_audit_40.csv`. Rows contain fixed case/mode/output/citation fields and blank human fields:

- `support_label`;
- `coverage_label`;
- `wrong_page`;
- `unsupported_claim`;
- `reviewer_id`;
- `review_status`;
- `reviewer_notes`.

All rows begin with `PENDING_HUMAN_AUDIT`. Do not change that status until a person has opened the cited source and reviewed the response.

## Human procedure

1. Open the exact cited document and page/message range from the candidate package.
2. Decompose the response into material factual claims.
3. Mark each claim supported, contradicted, or unsupported by the cited span.
4. Mark whether every material supported claim has a citation.
5. Confirm cited page, chunk/document association, and policy accessibility.
6. Record a short factual note for any failure.
7. A second reviewer or adjudicator resolves disagreements before final freeze.

The generated sheet is a template and preselection only. This repository does not claim the 40-row manual audit is complete.
