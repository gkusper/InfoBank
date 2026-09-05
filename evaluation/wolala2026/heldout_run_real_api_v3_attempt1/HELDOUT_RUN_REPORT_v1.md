# WoLaLa 2026 Held-Out v3 Attempt 1 Report

Status: COMPLETED.

## Provenance

- Dataset: `heldout_pilot_v3`
- Run ID: `heldout_pilot_v3_real_api_attempt1`
- Run attempt: `1`
- Git commit at execution: `54ffbc9bc2e1a910bbdd8e42b4da45b4ccaf6045`
- Freeze tag: `wolala2026-cfaf-heldout-v3-freeze` -> `d9e40cdecf836ea6a27997492fa4c6d9cd73c0df`
- Authorization tag: `wolala2026-cfaf-heldout-v3-attempt1-authorized` -> `54ffbc9bc2e1a910bbdd8e42b4da45b4ccaf6045`
- Protocol: `WOLALA2026_PILOT_PROTOCOL_v4`
- Dataset checksum: `d73fc26e9f622db2bf396b4f1cb21ddc2f9b49c41e1e357c32294bff9976f197`
- Result hash: `86a803c00340a6de1d31e35c901f86e9c84f03d7d9b54b080d014d87afa71906`
- Raw freeze manifest: `RAW_HELDOUT_FREEZE_MANIFEST.json` (21 pre-manifest files)

## Execution Accounting

- Mode executions: 360 / planned 360
- Held-out mode executions: 360
- Result records: 360
- Embedding calls: 40 / cap 60
- Generation calls: 360 / cap 380
- Total external calls: 400 / cap 420
- Retry attempts: 0 / cap 20
- Runner errors: 0
- Warmup calls: 0

## Mode-Level Results

| Mode | Mode accuracy | Fulfilment | Protected leakage | Generator exposure | Safe next step | Calls |
|---|---:|---:|---:|---:|---:|---:|
| cfaf_pipeline | 1.000 | 1.000 | 0.000 | 0.000 | 0.900 | 120 |
| prompt_only_control | 0.417 | 0.117 | 0.200 | 0.500 | 0.400 | 120 |
| standard_rag | 0.400 | 0.100 | 0.200 | 0.500 | 0.400 | 120 |

## Family-Level Results

| Family | Mode accuracy | Fulfilment | Protected leakage | Generator exposure | Safe next step |
|---|---:|---:|---:|---:|---:|
| P1 | 0.667 | 0.333 | 0.000 | 0.000 | 0.667 |
| P2 | 0.667 | 0.667 | 0.000 | 0.667 | 0.667 |
| P3 | 0.667 | 0.333 | 0.333 | 0.667 | 0.667 |
| P4 | 0.667 | 0.333 | 0.000 | 0.000 | 0.667 |
| P5 | 0.361 | 0.361 | 0.333 | 0.333 | 0.167 |

## Primary Confirmatory Tests

Sample unit: unique held-out case after 3-repetition majority vote. Tests: exact McNemar; p-values Holm-adjusted across the primary family. Bootstrap CI: case-clustered risk difference, 10,000 samples, seed 20261012.

| Test | CFAF pass / baseline fail | CFAF fail / baseline pass | p | Holm p | Risk diff | 95% bootstrap CI |
|---|---:|---:|---:|---:|---:|---:|
| `request_fulfilment_correct:cfaf_pipeline_vs_prompt_only_control` | 35 | 0 | 5.82077e-11 | 1.74623e-10 | 0.875 | [0.775, 0.975] |
| `request_fulfilment_correct:cfaf_pipeline_vs_standard_rag` | 36 | 0 | 2.91038e-11 | 1.16415e-10 | 0.900 | [0.800, 0.975] |
| `top_level_mode_correct:cfaf_pipeline_vs_prompt_only_control` | 23 | 0 | 2.38419e-07 | 2.38419e-07 | 0.575 | [0.425, 0.725] |
| `top_level_mode_correct:cfaf_pipeline_vs_standard_rag` | 24 | 0 | 1.19209e-07 | 2.38419e-07 | 0.600 | [0.450, 0.750] |

## Latency

Case-mode medians after 3 repetitions.

| Mode | Count | p50 ms | p95 ms | min ms | max ms |
|---|---:|---:|---:|---:|---:|
| cfaf_pipeline | 40 | 1364.1 | 1554.9 | 1181.7 | 3137.2 |
| prompt_only_control | 40 | 1325.4 | 1553.4 | 1099.0 | 3019.8 |
| standard_rag | 40 | 1519.4 | 1770.7 | 1338.5 | 3634.6 |

## Verification Summary

- Call accounting all counts match: `True`
- All cases have expected record count: `True`
- Embedding count independent of repetitions: `True`
- Shared retrieval across modes/repetitions: `True`
- Shared retrieval latency reused: `True`
- No second retrieval timing event per case: `True`
- Baselines free of gold/external CFAF labels: `True`
- CFAF uses filtered pipeline context: `True`
- All CFAF generator contexts filtered: `True`
- CFAF generator exposure rate: `0.0`
- CFAF protected-content leakage rate: `0.0`
- P5 source-existence leakage diagnostic rate: `1.0`
- Diagnostic blocking errors: `0`

## Interpretation

CFAF reached perfect top-level mode accuracy, public reason-class accuracy, request fulfilment accuracy, and zero protected-content leakage at record level in this held-out run. Its non-perfect generated-summary metric is safe-next-step correctness, at 0.900.

The separate P5 source-existence diagnostic is a limitation: all four P5 matched pairs were flagged for public response differences between the no-source and hidden-deny variants, even though hidden source values were absent. This is a pair-level source-existence signal, not raw protected-content leakage, and it should be reported separately from the protected-content leakage metric.

Both baselines show substantially lower top-level mode accuracy and fulfilment, with protected-content leakage at 0.200 and generator exposure at 0.500. Diagnostic error records are non-blocking by construction in `error_analysis.json`; they should not be used to tune the held-out data.

## Files

- `run_manifest.json`: execution provenance and call accounting
- `raw_results.jsonl`: raw model outputs
- `case_scores.jsonl`: scored mode execution records
- `pair_scores.jsonl`: matched-pair summaries
- `summary.json`, `summary.csv`, `summary_table.tex`: headline summaries
- `RAW_HELDOUT_FREEZE_MANIFEST.json`: raw output freeze manifest created before manual interpretation
- `POST_HELDOUT_ANALYSIS_v1.json`: derived post-run statistics and verification summary
- `POST_HELDOUT_VALIDATION_v1.json`: post-run invariant checks
- `POST_HELDOUT_ARTIFACT_MANIFEST_v1.json`: final checksums for held-out output artifacts
- `PAPER_RESULT_CLAIMS_v1.json`: conservative candidate claims supported by the held-out artifacts
