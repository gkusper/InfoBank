# heldout_pilot_v2 Attempt 1 Failed-Run Report

## Status

`heldout_pilot_v2` attempt 1 was started after the required remote
authorization gate passed. The run completed as a recorded failed attempt.

This artifact is not a manuscript result package. The attempt is not valid for
confirmatory analysis because the frozen case/mode/repetition coverage was not
completed.

## Pre-Run Gate

- Branch: `wolala2026`
- Remote authorization commit: `66caca55756f8204c6b9b4596255d6d5a565eb63`
- Remote authorization tag: `wolala2026-cfaf-heldout-v2-attempt1-authorized`
- Authorization tag object: `3e6da406c6162778eeeedf9ae8bbb2b5a717da5e`
- Authorization tag peeled commit: `66caca55756f8204c6b9b4596255d6d5a565eb63`
- Freeze commit: `548415ba2135e309edb6c2f0cf52d6017b06d295`
- Freeze tag: `wolala2026-cfaf-heldout-v2-freeze`
- Held-out output directory before execution: absent
- `OPENAI_API_KEY` visible before execution: true

## Execution Command

```powershell
python -m evaluation.wolala2026.run_pilot --dataset heldout_pilot_v2 --modes standard_rag,prompt_only_control,cfaf_pipeline --repetitions 3 --execution-spec evaluation/wolala2026/HELDOUT_EXECUTION_SPEC_v3.json --output-dir evaluation/wolala2026/heldout_run_real_api_v2_attempt1 --max-mode-executions 360 --max-embedding-calls 60 --max-generation-calls 380 --max-total-external-calls 420 --allow-real-api --allow-heldout
```

The command was invoked once. No second held-out run was started.

## Run Manifest Summary

- Run ID: `heldout_pilot_v2_real_api_attempt1`
- Manifest status: `FAILED`
- Start time: `2026-08-22T19:15:50Z`
- End time: `2026-08-22T19:20:07Z`
- Dataset: `heldout_pilot_v2`
- Dataset checksum: `e4c73178a3fa3d86b11b8b4dcfce50217c8c758a29bc4bebe5d54027f121e10e`
- Protocol checksum: `36e4f06e2381811058c291de5e6692e5b027ed02e846ab00f094a9d63784239a`
- Execution spec checksum: `c3c9645c38f12da3048e6a537cf2494452cc4963532a456b76445aeb923e6dab`
- Provider: `openai`
- Embedding model: `text-embedding-3-small`
- Generator model: `gpt-4o-mini`
- Mock or stub used: false
- External warm-up calls: 0
- Retry attempts: 0

## Failure

The run stopped with this recorded provider/cap error:

```json
{"case_count_completed":40,"category":"PROVIDER_ERROR","message":"Embedding call cap exceeded: requested 61, cap 60."}
```

The root cause is a runner/protocol-plan mismatch. Protocol v3 froze
`planned_unique_embedding_requests = 40` and required retrieval to be shared
once per case across modes and repetitions. The real-API runner recomputed the
retrieval embedding inside the repetition loop. It therefore consumed one
embedding per case per repetition, reached 60 embedding calls after all 40
first repetitions plus the first 20 second repetitions, and refused the 61st
embedding request under the frozen hard cap.

## Coverage

- Planned mode executions: 360
- Raw result rows written: 180
- Case score rows written: 180
- Shared retrieval snapshots written: 60
- Unique cases with at least one output: 40
- Cases with three repetitions: 0
- Cases with two repetitions: 20
- Cases with one repetition: 20
- Repetition 1 mode rows: 120
- Repetition 2 mode rows: 60
- Repetition 3 mode rows: 0

The frozen statistical analysis plan requires three repetitions per case and
mode before case-level majority or any-event aggregation. Because no case has
all three repetitions, no confirmatory McNemar, Holm, Wilson, or bootstrap
analysis is valid for this attempt.

## External Calls

- Actual embedding calls: 60
- Actual generation calls: 180
- Actual provider attempts: 240
- Actual retry attempts: 0
- Actual total external calls: 240
- Hard total external-call cap: 420

## Partial Descriptive Scores

These are record-level partial diagnostics only and must not be presented as
held-out confirmatory results.

| Mode | Rows | Top-level accuracy | Request fulfilment | Generator exposure | Protected leakage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cfaf_pipeline` | 60 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| `prompt_only_control` | 60 | 0.4333 | 0.3333 | 0.5333 | 0.0667 |
| `standard_rag` | 60 | 0.4333 | 0.3333 | 0.5333 | 0.0667 |

Partial score result hash: `0ebc72e7453fa3354dd453192f2ce7447ee94c6efbde317ce49c4926dd93a75d`

## Verification Summary

- Adapter integrity: baselines free of gold/CFAF labels = true
- CFAF filtered context verification = true
- CFAF generator exposure rate in partial rows = 0.0
- CFAF protected-content leakage rate in partial rows = 0.0
- P5 source-existence leakage rate in partial rows = 0.0
- Shared retrieval verification: false, because snapshot hashes changed across
  repetitions for cases with more than one retrieval snapshot

## Invalidation Classification

Assigned post-run classification:
`INVALIDATED_SCIENTIFIC_INTEGRITY_FAILURE`.

Reason: incorrect case/mode/repetition coverage, shared-retrieval mismatch, and
cap-enforcement failure caused by experimental runner behavior rather than by
an external infrastructure outage.

Under Protocol v3, this failed attempt must be preserved. No rerun of this
attempt, no selective rerun, and no attempt 2 execution is authorized in this
task.

## Frozen Output Directory

The generated attempt artifacts are preserved at:

`evaluation/wolala2026/heldout_run_real_api_v2_attempt1/`

The run-generated checksum file is:

`evaluation/wolala2026/heldout_run_real_api_v2_attempt1/checksums.sha256`

This report was written after the run without modifying the generated raw
output files.
