# Freeze Notes: S1/S2 Journal Benchmark v2

Package identity: S1_S2_JOURNAL_BENCHMARK_V2

Package filename: `S1_S2_journal_benchmark_v2.zip`

Freeze date: 2026-08-25

BENCHMARK_STATUS: FROZEN

HUMAN_QA_STATUS: APPROVED

HUMAN_CONFIRMATION_STATUS: APPROVED_WITH_DOCUMENTED_LIMITATIONS

ONTOLOGY: NOT NEEDED FOR CURRENT PAPER

## Scope

This freeze covers only the S1/S2 journal benchmark package: source PDFs, scenario packs, runtime query inputs, scorer gold annotations, projection manifests, package manifest, checksums, human-QA record, human-confirmation record, and freeze notes.

The set is a human-validated controlled proof-of-concept evaluation set. S1/S2 were used during implementation debugging and deterministic development smoke tests, so this set must not be described as a completely untouched external holdout, a large independent benchmark, or evidence of statistical generality beyond these 12 cases.

## Freeze Semantics

Frozen items:

- S1/S2 source PDFs.
- S1/S2 questions.
- Runtime `query_inputs.jsonl`.
- Human-approved scorer `gold_annotations.jsonl`.
- Required source sets.
- Acceptable page sets.
- Human-QA status and notes.
- Human-confirmation status and decisions.
- Scorer semantics for this publication evaluation version.
- Package version and file checksums.

Not implied by this freeze:

- Every B3 case passes.
- The three documented citation limitations disappear.
- The current implementation is bug-free.
- HEAD alone identifies the evaluated implementation.

FURTHER_S1S2_TUNING_ALLOWED: NO

## Known Measured Implementation Limitations

### S1-Q6

Correct answer content, incomplete citation set.

Missing: `lunara-s3-care-guide.pdf`, page 1.

Current runtime cites only `lunara-s3-purchase-receipt.pdf`, page 1.

### S2-Q2

Correct answer content, incomplete citation set.

Missing: `velora-v55-manufacturer-warranty-terms.pdf`, page 2.

Current runtime cites only `velora-v55-purchase-receipt.pdf`, page 1.

### S2-Q5

Correct answer content, incomplete citation set.

Missing: `velora-v55-regional-service-notice.pdf`, page 1.

Current runtime cites only `velora-v55-manufacturer-warranty-terms.pdf`, page 2.

MULTI_DOCUMENT_CITATION_COMPLETENESS: DOCUMENTED_LIMITATION

Unsupported extra citations: 0

Wrong-page citations: 0

Citation support precision: 1.0

Page-level citation correctness: 1.0

Safety error total: 0

## Frozen Reference B3 Result

DETERMINISTIC DEVELOPMENT/REPRODUCIBILITY RESULT — NOT FINAL REAL-LLM JOURNAL PERFORMANCE

Combined metrics:

- output-class accuracy: 1.0
- reason-code accuracy: 1.0
- permitted-answer accuracy: 1.0
- false-answer rate/count: 0.0 / 0
- citation document coverage: 0.785714
- citation support precision: 1.0
- page-level citation correctness: 1.0
- citation coverage: 0.785714
- controlled-failure correctness: 1.0
- safety error total: 0

Stable deterministic content hash:

`24afef714fe8bfc4715b41720cff8d44d7fd20b83b6a9786b308ecedb9023c5a`

## Change Control

From this package version onward:

- no score-driven gold changes;
- no S1/S2-driven citation tuning;
- no page/gold relaxation because a provider disagrees;
- no removal of failing cases.

If a true benchmark defect is later discovered, document it as an erratum or a new package version rather than silently editing v2.

