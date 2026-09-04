# Offline Scoring Postmortem v2

Final recommendation: `OFFLINE SCORING PIPELINE FIXED — NO NEW API RUN REQUIRED`

## Scope

- Strictly offline: no Claude/OpenAI/embedding/API rerun was performed.
- Frozen raw run and seal were not modified.
- The scorer defect was in repeated-run orchestration: plain `case_id` uniqueness was applied across repetitions instead of within each `(mode, repetition)` group.
- The P1/S2-Q2 failures remain protocol failures: each provider response contained a valid first JSON block plus non-whitespace suffix content.

## Raw Integrity

- HEAD: `cee5faf799c160349b09cefbe90d90365bae4a68`
- Expected HEAD: `cee5faf799c160349b09cefbe90d90365bae4a68`
- Raw record count: 630
- Composite keys unique: True
- Mode x repetition groups: 15
- Prepared base integrity: PASS
- No-reprocessing counters: PASS
- Payload boundary: PASS

## Corrected Metrics

| Mode | Raw accuracy | Balanced accuracy | Strict permitted-answer accuracy | Governed-output correctness | Aggregate-only correctness | Aggregate numerical correctness | Citation recall | Citation precision | Page precision | Safety findings | Runtime errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C0 | 0.690476 | 0.166667 | 0.351351 | 0.0 | 0.0 | 0.0 | 0.555556 | 0.3861 | 0.281853 | 9 | 0 |
| C1 | 0.690476 | 0.166667 | 0.342342 | 0.0 | 0.0 | 0.0 | 0.533333 | 0.417391 | 0.295652 | 9 | 0 |
| C2 | 0.738095 | 0.52682 | 0.486486 | 0.538462 | 1.0 | 1.0 | 0.544444 | 0.541436 | 0.403315 | 0 | 0 |
| C3 | 0.690476 | 0.515326 | 0.495495 | 0.538462 | 1.0 | 1.0 | 0.488889 | 0.661654 | 0.503759 | 0 | 0 |
| P1 | 0.555556 | 0.444189 | 0.378378 | 0.410256 | 0.666667 | 0.6 | 0.505556 | 0.595376 | 0.410405 | 114 | 3 |

## Technical Failures

- Technical failure records: 3
- Taxonomy: `{"P1ParseError": 3}`
- P1 R1 S2-Q2: P1ParseError / VALID_JSON_WITH_PREFIX_OR_SUFFIX / provider status success
- P1 R2 S2-Q2: P1ParseError / VALID_JSON_WITH_PREFIX_OR_SUFFIX / provider status success
- P1 R3 S2-Q2: P1ParseError / VALID_JSON_WITH_PREFIX_OR_SUFFIX / provider status success

## Safety Delta Versus Frozen OpenAI

| Mode | Claude findings | OpenAI findings | Finding delta | Claude affected records | OpenAI affected records | Affected-record delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C0 | 9 | 9 | 0 | 9 | 9 | 0 |
| C1 | 9 | 9 | 0 | 9 | 9 | 0 |
| C2 | 0 | 0 | 0 | 0 | 0 | 0 |
| C3 | 0 | 0 | 0 | 0 | 0 | 0 |
| P1 | 114 | 132 | -18 | 48 | 48 | 0 |

## Artifacts

- Raw records: `evaluation/results/claude_full_20260904T190415Z_cee5faf/raw/raw_records.jsonl`
- Seal: `evaluation/results/claude_full_20260904T190415Z_cee5faf/raw/run_seal.json`
- Repetition-aware scorer output: `artifacts/anthropic_provider_readiness/full_claude_experiment_20260904T190415Z_cee5faf/offline_scoring_postmortem_v2/scores`
- Publication metrics: `artifacts/anthropic_provider_readiness/full_claude_experiment_20260904T190415Z_cee5faf/offline_scoring_postmortem_v2/publication_metrics`
- Postmortem payload: `artifacts/anthropic_provider_readiness/full_claude_experiment_20260904T190415Z_cee5faf/offline_scoring_postmortem_v2/postmortem_summary.json`
- SHA-256 manifest: `artifacts/anthropic_provider_readiness/full_claude_experiment_20260904T190415Z_cee5faf/offline_scoring_postmortem_v2/SHA256SUMS.txt`

## Notes

- Chroma count wording was repaired in source: the value is a vector count; the old key remains as a compatibility alias.
- Governed-output correctness now uses the frozen publication definition: non-FULL expected outputs only.
- Claude/OpenAI safety comparison now separates total finding activations from affected-record counts.
