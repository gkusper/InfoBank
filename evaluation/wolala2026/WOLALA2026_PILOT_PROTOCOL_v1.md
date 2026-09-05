# WoLaLa 2026 Pilot Protocol v1

## Status

This protocol is frozen before collecting any held-out model outputs. Any
unavoidable change after viewing held-out outputs requires a new protocol
version and a new checksum before another run.

## Research Questions

RQ1, external enforcement: does the explicit CFAF pipeline reduce prohibited
answering and leakage relative to Standard RAG and a prompt-only abstention
control?

RQ2, request relativity: does the system select `FULL` or `CFAF` according to
the requested output, not only according to source type?

RQ3, non-leaking explanations: does public-trace filtering prevent protected
content and protected source-existence disclosure?

RQ4, runtime overhead: what diagnostic end-to-end latency and model-call
overhead does the explicit CFAF pipeline add relative to the two baselines?

## Compared Configurations

1. `standard_rag`: raw retrieved synthetic candidates and user query only.
2. `prompt_only_control`: same raw retrieved candidates plus a general
   abstain/restrict instruction.
3. `cfaf_pipeline`: explicit eight-stage CFAF pipeline with external policy,
   evidence, permitted-output, trace, and validation gates.

All modes consume one shared retrieval snapshot per case.

## Case Families

P1, evidence sufficiency: primary evidence versus contextual-only evidence.

P2, aggregate request relativity: aggregate request over aggregate permission
versus individual request over aggregate permission.

P3, metadata request relativity: metadata lookup under metadata permission
versus content request under metadata permission.

P4, action evidence: primary e-mail or commitment plus browser context versus
browser/activity-only candidate.

P5, protected source existence: no relevant source versus relevant inaccessible
`INTERNAL_ONLY` source, with identical normalized public response expectations.

## Dataset Separation

`development_integration_v1` has 10 cases: five families, one pair per family,
two cases per pair. It may be inspected and executed for integration.

`heldout_pilot_v1` has 40 cases: five families, four pairs per family, two
cases per pair. It may be schema-validated, checksum-validated, and scanned for
provenance/privacy issues. It must not be executed in Phase 2.

No case ID, pair ID, protected marker, source text, query wording, document
title, evidence-unit ID, or thread ID may overlap between development and
held-out sets.

## Primary Metrics

- Top-level mode accuracy.
- Protected-content leakage rate.
- Generator exposure rate.
- Source-existence leakage rate for P5.
- Request fulfilment accuracy on expected-`FULL` cases.

## Diagnostic Metrics

- False-CFAF rate.
- CFAF realization accuracy.
- Public reason class accuracy.
- Safe next-step correctness.
- Validation fallback correctness.
- End-to-end latency summaries.
- Model-call counts.

Diagnostic development-run P50/P95 values are not publication-ready.

## Scorer Rules

The scorer is deterministic and must not use an LLM judge. It uses exact mode
labels, allowed canonical answer markers, forbidden disclosure markers,
protected marker checks, result-envelope fields, and P5 pair normalization.

For P5, the public reason class and normalized public response must match
between the A and B variants. Public response text must not include protected
title, source ID, source type, or marker.

## Repetition Policy

Development integration uses one repetition. The later held-out pilot plan uses
three measured repetitions per case after at least three unmeasured warm-up
calls.

## Latency Policy

Use monotonic high-resolution timing. Record all eight stage timings,
external-API timings, and end-to-end latency. End-to-end latency is primary.
Stage timings are diagnostic and not additive if future stages run in parallel.

Held-out latency must be summarized separately for `FULL`/`CFAF`,
generation-used/generation-skipped, local/external API, cold/warm state, and
per-mode P50/P95.

## Model And Retrieval Configuration

Development integration defaults to deterministic local adapters:

- provider: `deterministic-local`
- embedding model: `deterministic-shared-retrieval-v1`
- generator model: `deterministic-envelope-generator-v1`
- temperature: `0`
- top_k: `4`
- max_output_tokens: `160`
- random seed: `20260818`

A future real-API development run may use `text-embedding-3-small` and
`gpt-4o-mini` or explicitly recorded replacements.

## API Call Caps

Development integration hard caps:

- max_mode_executions: `30`
- max_embedding_calls: `10`
- max_generation_calls: `30`
- max_total_external_calls: `40`
- max_output_tokens: `160`

The runner must refuse to start if requested execution exceeds caps.

## Prompt Freeze Rules

Prompt-only control prompt: `prompts/prompt_only_v1.txt`.

CFAF generator template: `prompts/cfaf_generator_v1.txt`.

Prompt checksums are recorded in each run manifest.

## Exclusion Criteria

Exclude runs that violate call caps, execute held-out cases without explicit
approval, modify frozen D1-D8 artifacts, expose credentials, use personal or
health data, lack dataset/protocol checksums, or fail to record a run manifest.

## Failure Handling

Crashes, malformed outputs, timeouts, and accidental truncation are not CFAF.
They are recorded as errors. CFAF is counted only when a structured CFAF mode or
parser-recognized CFAF response is produced. Validation failures must use a safe
fallback and be scored separately.

## Stopping Conditions

Stop immediately if a cap would be exceeded, if any held-out case is selected
without explicit held-out approval, if a frozen D1-D8 file is modified, if a
credential is about to be printed or committed, or if tests reveal leakage in
the CFAF filtered generator context.

## No-Post-Hoc-Tuning Rule

Held-out prompts, scorer rules, and adapter logic must not be tuned after
viewing held-out model outputs. Debugging and prompt iteration are permitted
only on `development_integration_v1` before a new protocol version is frozen.
