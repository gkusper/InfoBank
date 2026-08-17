# Preregistration: InfoBank D1-D8 Large-Scale Evaluation v1

## Research Questions

RQ1: Does role-aware RAG improve safety on restricted D1-D5 document tasks
relative to standard RAG and governance-only RAG while preserving utility on
permitted tasks?

RQ2: Does the frozen production EvidenceUnit action-reconstruction path recover
open actions, reject browser-only pseudo-actions, and link later closure
evidence on a held-out D6-D8 benchmark?

RQ3: What are the computational trade-offs in generation calls, skipped
generation, tokens, latency, retries, and errors?

## Benchmarks

D1-D5 uses `evaluation/fixtures/document_rag_v3.yaml` with exactly 400 unique
cases:

- D1 Full: 80
- D2 Metadata: 80
- D3 Aggregate: 80, consisting of 40 aggregate-safe and 40 individual-restricted
  cases
- D4 Deny: 80
- D5 Mixed/contextual: 80, consisting of 40 mixed-primary and 40
  contextual-only cases

D6-D8 uses `data/benchmarks/evidence_unit_v2_holdout/` with exactly 340 unique
cases:

- D6 open action: 100
- D7 browser-only counterpart: 100
- D8 closure: 100
- D8 non-closing control: 40

## Configurations

D1-D5 modes:

- `standard_rag`
- `governance_only_rag`
- `role_aware_rag`

D6-D8 mode:

- `role_aware_action_reconstruction`

Models and generation settings:

- Embedding model: `text-embedding-3-small`
- Generator model: `gpt-4o-mini`
- Temperature: `0.0`
- Retrieval top-k: `4`
- Maximum output tokens: `160`

## Repetitions and Independence

D1-D5 runs five repetitions for every case/mode pair:

```text
400 cases x 3 modes x 5 repetitions = 6000 measured records
```

D6-D8 runs three clean database repetitions:

```text
340 cases x 3 clean repetitions = 1020 measured records
```

Repeated outputs from the same case are not treated as independent samples in
inferential statistics. Primary inferential analyses aggregate to the case
level before paired tests. Repetition-aware sensitivity analyses resample at the
case cluster level while retaining all repetitions within a sampled case.

## Primary Metrics

D1-D5 primary metrics:

- retrieval target recall@4;
- permitted-answer accuracy, defined only over answer-permitted cases;
- prohibited-disclosure rate, defined only over restricted cases;
- generator-exposure rate, defined only over restricted cases;
- safe-withholding rate, defined only over restricted cases;
- exact output-class conformance;
- source-role conformance.

D6-D8 primary metrics:

- D6 open-action accuracy;
- D7 browser-only false-action rate;
- D8 closure-status accuracy;
- D8 non-closing open-status accuracy;
- EvidenceUnit role accuracy;
- OPEN/CLOSED/ABSENT status accuracy;
- triplet consistency.

## Secondary Metrics

Secondary D1-D5 metrics include aggregate-safe answer accuracy, contextual-only
false-answer rate, controlled-failure correctness, generation-skipping rate,
API error rate, retry rate, literal marker occurrence as a diagnostic only, and
mode-level token/latency summaries.

Secondary D6-D8 metrics include closure-subtype accuracy, natural-versus-
synthetic strata, clean-run determinism, action precision/recall/F1, and
failure-category distribution.

## Statistical Tests

For proportions, report Wilson 95% confidence intervals. For paired D1-D5 mode
comparisons, use exact McNemar tests on case-level majority outcomes, with
Holm correction across preregistered pairwise comparisons. Report paired risk
differences as effect sizes. Use a case-clustered bootstrap with seed
`20260817` and 10,000 samples for repetition-aware sensitivity intervals.

Efficiency comparisons use paired non-parametric tests where both modes have
case-level efficiency summaries. Skipped generation is represented explicitly as
zero generation calls and zero generation tokens, not as missing data.

## Retry and Failure Policy

API calls may be retried only by the repository's existing API wrapper behavior.
The runner records retry counts and errors. Completed successful calls must not
be rerun unnecessarily; checkpoint/resume should reuse successful records.

A valid final run must produce:

- 6000 D1-D5 measured records;
- 1020 D6-D8 measured records;
- complete manifests, scores, aggregate metrics, statistical tests, failure
  reports, and sanitized publication artifacts.

A run is failed or invalidated if result-affecting production code, prompts,
scorers, gold labels, or benchmark text are changed after benchmark freeze. If a
result-affecting error is discovered after inspecting final outcomes, the run is
invalidated and a new disjoint benchmark must be created after a new code
freeze.

## Exclusions

No case may be excluded because the system fails it. Exclusions before
benchmark freeze are allowed only for deterministic validation failures:
duplicate IDs, marker collisions, source overlap with development material,
gold leakage, malformed timestamps, unresolved evidence references, or failed
retrieval qualification.

## Natural and Synthetic Strata

D1-D5 is synthetic. D7 is synthetic by design. D8 closure and non-closing
controls distinguish natural MailEx-derived examples from controlled synthetic
later messages. Natural and synthetic strata are reported separately.

## Environment Isolation

The final run must use:

- MariaDB database: `infobank_eval`
- MariaDB host/port: `127.0.0.1:3307`
- Chroma directory: `backend_python/chroma_eval`
- Python environment: `backend_python/.venv_eval`

The normal development database and Chroma path are disallowed. The API key must
be visible only as a process environment variable and must never be serialized.

## Token-Usage Safety Threshold

Before the real D1-D5 run, estimate the maximum planned generation calls and
record the estimate in the run manifest. The run should stop before execution if
the operator-specified token or call ceiling would be exceeded. In the absence
of an operator override, the planned configuration is 6000 measured records and
only those records should be generated.
