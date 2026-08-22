# WoLaLa 2026 Pilot Protocol v4

## Status

This protocol is frozen before collecting any `heldout_pilot_v3` model outputs.
It supersedes `WOLALA2026_PILOT_PROTOCOL_v3.md` only for the final CFAF-focused
WoLaLa held-out experiment after the shared-retrieval repair. Protocol v1, v2,
and v3 remain historical artifacts.

Protocol v4 preserves the research questions, compared modes, prompts, parser,
scorer, statistical semantics, latency semantics, retry policy, invalid-run
policy, and no-result-driven-rerun rule from Protocol v3. It changes only the
held-out dataset, case prefix, dataset/generation manifests, and execution
specification needed for `heldout_pilot_v3`.

This experiment validates the evidential and governance instantiation of CFAF.
It does not evaluate the complete InfoBank, full action-list reconstruction,
general safety triggers, prompt-injection resistance, production security, or
cross-domain generality.

## Historical Attempt Record

`heldout_pilot_v1` is retired after the pre-execution implementation guard
failure. No model saw `heldout_pilot_v1`.

`heldout_pilot_v2` attempt 1 is preserved as an invalidated scientific-integrity
failure because the runner used one retrieval embedding per case per repetition
instead of one shared retrieval per unique case. It is not a confirmatory result
and must not be rerun or reused as publication evidence.

## Research Questions

RQ1, external enforcement: does the explicit CFAF pipeline reduce prohibited
answering and leakage relative to Standard RAG and a prompt-only abstention
control?

RQ2, request relativity: does the system select `FULL` or `CFAF` according to
the requested output, not only according to source type?

RQ3, non-leaking explanations: does public-trace filtering prevent protected
content and protected source-existence disclosure?

RQ4, runtime overhead: what diagnostic user-visible latency and model-call
overhead does the explicit CFAF pipeline add relative to the two baselines?

## Compared Configurations

1. `standard_rag`: raw retrieved synthetic candidates and user query only.
2. `prompt_only_control`: same raw retrieved candidates plus the frozen
   prompt-only abstain/restrict instruction.
3. `cfaf_pipeline`: explicit eight-stage CFAF pipeline with external policy,
   evidence, permitted-output, trace, and validation gates.

All modes consume one shared retrieval snapshot per unique held-out case. That
snapshot is reused across all three modes and all three repetitions.

## Frozen Dataset And Prompts

- Held-out dataset: `heldout_pilot_v3`
- Held-out case ID prefix: `HELD3_`
- Held-out pair ID prefix: `H3PAIR_`
- Held-out cases: `40`
- Matched pairs: `20`
- Scenario families: `P1`, `P2`, `P3`, `P4`, `P5`
- Fixed generation seed: `20261017`
- Held-out dataset checksum: `d73fc26e9f622db2bf396b4f1cb21ddc2f9b49c41e1e357c32294bff9976f197`
- Runtime case file checksum: `ead302c8a8e18a9e1a77ee3fe53bba0cfa7968fc010e3629e986fb74f422399e`
- Gold scorer-only file checksum: `837d1223628130608280b15996c5b644d76fc2be9c1d72fbcdcef674d3361112`
- Generation manifest checksum: `1b55d46f55f7e26b6755ee888d1ae1c9666c79d3e5447850ef9b8f8bca2f6ac7`
- Pair-design manifest checksum: `b298aa671e36f0e32bb05084f39d05ee4f463f96d25bd304d92bc6e5dad676a3`
- Overlap audit checksum: `37efa2c0a6563003be137bdf2c213dfa479b118ee24098cdc764f24aca52997a`
- Protocol v1 checksum: `91c6e3279821abdd0c5b92006a4ce572293fc5ed29a77e7edbf5d1b47147f93e`
- Protocol v2 checksum: `34907efae5197fa9df610a5da6fdf50067d018c56b5885d8dbdb194d7fff58ba`
- Protocol v3 checksum: `36e4f06e2381811058c291de5e6692e5b027ed02e846ab00f094a9d63784239a`
- Prompt-only prompt checksum: `77d2d8ff8042f94fd7381580d6034deb19827d3502e06bf67a96b87103fb0af6`
- CFAF generator prompt checksum: `0f6d54a1c9f5ccf3f0b4a1559cdb18c4dcd4a68f0c5f22895a440f50e45ba765`

`cases.jsonl` is runtime-visible only. `gold.jsonl` is scorer-only and is merged
only after raw run outputs have been frozen. The generator-visible gold-hint
scanner count is `0`.

Do not modify `heldout_pilot_v3`, `prompt_only_v1.txt`,
`cfaf_generator_v1.txt`, Protocol v1, v2, or v3 for this final held-out run.

## Frozen Provider And Model Configuration

- Provider: `openai`
- Provider implementation: repository direct HTTPS OpenAI provider wrapper
- Embedding model: `text-embedding-3-small`
- Generator model: `gpt-4o-mini`
- Temperature: `0`
- Top-k retrieval: `4`
- Maximum output tokens: `160`

No model or provider replacement is permitted.

Frozen implementation checksums:

- Provider wrapper `real_api.py`: `f25ef1896b0e8f53138ba09a52940b98734b1152806bc1d76b2c1bbee3386f08`
- Adapters and parser `adapters.py`: `d11892deeec0dc3bd46de3fac7a5591d2f2a44460187e0f30cb4d3ab5739a2c9`
- Runner `run_pilot.py`: `19a9fde78d9b17db610b4c7dd1be58179fabb6aacdcbf301c20181179a1a21e4`
- Retrieval `retrieval.py`: `77a712af26215581359260f92caa492bf63c5fea0d43787d67dbcc7a9aa04513`
- Scorer `score_pilot.py`: `5c8349ce5b690cff29b6f2948f6e01fa38eb15f921cdd76a7bbc121d1f86c0a2`
- Execution-spec validator `execution_spec.py`: `d62908213683979b2b3eb93a865f7e75bcc7ca92f35f75d8cca767a86adc63d5`

## Frozen Execution Counts

The held-out experiment has 40 cases, 3 modes, and 3 measured repetitions per
case and mode:

- `planned_mode_executions = 360`
- `planned_unique_embedding_requests = 40`
- `planned_generation_requests_maximum = 360`
- `planned_external_requests_without_retries_maximum = 400`

Retrieval and query embedding are shared once per unique case and reused across
all modes and repetitions.

## Frozen Hard Caps

- `max_mode_executions = 360`
- `max_embedding_calls = 60`
- `max_generation_calls = 380`
- `max_total_external_calls = 420`
- `max_total_retry_attempts = 20`
- `max_retries_per_logical_request = 1`
- `external_warmup_calls = 0`

Every retry counts as an external call. Caps must not be increased
automatically.

## Warm-Up And Retry Policy

No unmeasured provider warm-up request is permitted. Every embedding and
generation call must be recorded, count against the call caps, appear in the
run manifest, and contribute to documented latency records.

Retry behavior is inherited unchanged from Protocol v3 and implemented by
`retry_policy.py`, checksum `1faac809f583a3bc435474151331b71a5cb96069791d4d8af583ad0efb0e6ad8`.

## Invalid-Run And Rerun Policy

Wrong answers, false CFAF, refusals, over-refusals, leakage, poor latency, poor
baseline performance, poor CFAF performance, and unfavorable statistical
results are valid empirical outcomes and must not trigger invalidation.

`INVALIDATED_SCIENTIFIC_INTEGRITY_FAILURE` must be assigned for checksum drift,
wrong model or provider, wrong prompt, wrong dataset, gold-label contamination,
baseline receipt of CFAF decision labels, shared-retrieval mismatch, scorer or
parser defect affecting a primary metric, manifest defect affecting auditability,
incorrect case/mode/repetition coverage, held-out data corruption,
cap-enforcement defect, or non-frozen code used for execution.

No rerun is permitted because results are unfavorable.

## Primary Sample Units And Metrics

Primary sample units and metric denominators are inherited unchanged from
Protocol v3. Use unique held-out cases for primary inferential metrics, matched
P5 pairs for source-existence leakage, and case-mode medians across repetitions
for latency.

## Statistical Analysis Plan

Protocol v4 incorporates:

- File: `WOLALA2026_STATISTICAL_ANALYSIS_PLAN_v1.md`
- Checksum: `2639906b515589ba3fe15487567cc53aaf875823909eb077a2bd06f8ee149b1e`
- Implementation: `analyze_heldout.py`
- Implementation checksum: `bcdd676aba0e73fe3f336dee77e3e7c95148ad9304720c01ec363be6670dd0e0`

Use `alpha = 0.05`, two-sided tests, bootstrap seed `20261012`, and 10,000
bootstrap samples. Apply one Holm correction family across the four primary
tests.

## Latency Definition

Protocol v4 incorporates:

- File: `WOLALA2026_LATENCY_DEFINITION_v1.md`
- Checksum: `4c0c87f6267ab18f68677479439d4347d8449f36ed850e87d7d94b89e02b02a7`
- Implementation: `latency_analysis.py`
- Implementation checksum: `76af2eafaf82e60377bf2151a11ba7d2f82562c1fb064961d2ae9fec1c9ac160`

For every case, mode, and repetition:
`user_visible_end_to_end_ms = shared_retrieval_ms + mode_processing_ms`.

## Machine-Readable Execution Specification

The machine-readable Protocol v4 execution specification is
`HELDOUT_EXECUTION_SPEC_v4.json`. The runner's plan-only path must load and
validate it before any later held-out execution.

Plan-only validation may read held-out metadata, schema, case IDs, and
checksums, but it must perform no retrieval, embedding, adapter execution,
generation, or model-output scoring. It must not require an API key.

Actual held-out execution requires `--allow-real-api`, `--allow-heldout`, and
`--execution-spec HELDOUT_EXECUTION_SPEC_v4.json`; the output directory must be
empty; a matching authorization artifact must exist; and all call caps must
validate before provider initialization.

The execution-spec file checksum is recorded in
`PRE_HELDOUT_V3_FREEZE_MANIFEST.json` to avoid a circular checksum dependency
between this protocol file and the machine-readable spec.

## Held-Out Authorization And Execution Lock

No held-out model output may be generated before the Protocol v4 freeze commit
and tag have been pushed. A later authorization commit must record
`AUTHORIZED_NOT_STARTED` for `heldout_pilot_v3` attempt 1 before execution.

No full D1-D8 benchmark run is part of this protocol.

## Protocol v4 Change Log From Protocol v3

- Replaces retired `heldout_pilot_v2` with `heldout_pilot_v3`.
- Replaces case prefix `HELD2_` with `HELD3_`.
- Uses pair prefix `H3PAIR_`.
- Physically separates runtime cases from scorer-only gold labels.
- Adds deterministic generation, pair-design, overlap, and gold-hint audit
  manifests for `heldout_pilot_v3`.
- Uses `HELDOUT_EXECUTION_SPEC_v4.json`.
- Preserves the shared-retrieval repair and requires tag
  `wolala2026-shared-retrieval-fix-v1` as an ancestor of the freeze state.
