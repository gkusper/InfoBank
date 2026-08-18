# WoLaLa 2026 Real-API Development Report v1

Not a held-out result.
Not a publication-ready empirical result.
Used only for real-API integration and pilot-readiness assessment.

## 1. Starting Commit

- Branch: `wolala2026`
- Starting commit: `cb62b2778c154125623a0c68b0a9d8f069cd7623`
- Phase 2 tag present: `wolala2026-pilot-readiness-v0.2`
- Original D1-D8 base ancestor verified: `5bb2cc742e105cc3238b022130126947c04bcd35`

## 2. Run ID And UTC Timestamps

- Run ID: `development_integration_v1_real_api_v1`
- Start UTC: `2026-08-18T06:05:48Z`
- End UTC: `2026-08-18T06:06:40Z`
- Completion status: `COMPLETED`

## 3. Protocol And Dataset Checksums

- Protocol: `WOLALA2026_PILOT_PROTOCOL_v1.md`
- Protocol checksum: `91c6e3279821abdd0c5b92006a4ce572293fc5ed29a77e7edbf5d1b47147f93e`
- Development dataset: `development_integration_v1`
- Development dataset checksum: `df847ef72fa28e55277f153989add2cf94b06471f1ff068cae4bbf15cc95f0f4`
- Held-out dataset checksum verified before the run: `b86ddfa2a3db79a5d9e3e31b57000f1619f790040a6d9d814970ea2d1f54031b`

## 4. Provider And Model Configuration

- Provider: `openai`
- Embedding model: `text-embedding-3-small`
- Generator model: `gpt-4o-mini`
- Temperature: `0`
- Top-k: `4`
- Max output tokens: `160`
- `real_api`: `true`
- `mock_or_stub_used`: `false`

The API key was checked only for presence. Its value was not printed, stored, or committed.

## 5. Prompt Versions

- Prompt-only: `prompt_only_v1`, checksum `77d2d8ff8042f94fd7381580d6034deb19827d3502e06bf67a96b87103fb0af6`
- CFAF generator: `cfaf_generator_v1`, checksum `0f6d54a1c9f5ccf3f0b4a1559cdb18c4dcd4a68f0c5f22895a440f50e45ba765`

## 6. Execution Plan

Archived at `development_run_real_api_v1/execution_plan.json`.

- Development cases: `10`
- Modes: `3`
- Repetitions: `1`
- Planned mode executions: `30`
- Held-out mode executions: `0`
- Maximum embedding calls: `10`
- Maximum generation calls: `30`
- Maximum total external calls: `40`
- Case IDs: all `DEV_*`

## 7. Actual Execution Counts

- Mode executions: `30`
- Embedding calls: `10`
- Generation calls: `30`
- Total external calls: `40`
- Retry count: `0`
- Held-out mode execution count: `0`

The run respected all configured caps.

## 8. Real Provider Proof

The manifest records `real_api = true`, `mock_or_stub_used = false`, provider `openai`, and nonzero external calls. The installed Python environment did not use the OpenAI SDK package; the run used the repository's direct HTTPS provider wrapper and stored no request headers.

## 9. Shared Retrieval Verification

`shared_retrieval_verification.json` reports:

- `all_cases_share_retrieval = true`
- one embedding/retrieval snapshot per development case
- identical retrieval snapshot hash across `standard_rag`, `prompt_only_control`, and `cfaf_pipeline` for every case

## 10. Adapter Integrity Verification

`adapter_integrity_verification.json` reports:

- `baselines_free_of_gold_or_external_cfaf_labels = true`
- `cfaf_uses_filtered_pipeline_context = true`

Standard RAG and prompt-only received the query plus raw synthetic retrieved candidates only. They did not receive expected modes, gold reasons, access-gate labels, permitted-output decisions, CFAF response contracts, or internal traces.

## 11. Generator-Context Exposure Verification

`generator_context_exposure_verification.json` reports:

- CFAF generator exposure rate: `0.0`
- CFAF protected-content leakage rate: `0.0`
- `all_cfaf_contexts_filtered = true`

The CFAF generator received the response contract and permitted evidence views only.

## 12. Source-Existence Leakage Verification

`source_existence_leakage_verification.json` reports:

- Source-existence leakage rate: `0.0`
- P5 public reason class identical across the no-source and hidden-source variants
- P5 normalized public response identical
- Hidden source values absent
- Internal traces differ

## 13. Request-Relative Mode Checks

For `cfaf_pipeline`, all ten deterministic top-level mode decisions matched gold:

- P1: primary sufficient evidence -> `FULL`; contextual-only -> `CFAF`
- P2: aggregate request -> `FULL`; individual request over aggregate permission -> `CFAF / RESTRICT_GRANULARITY`
- P3: metadata lookup -> `FULL`; content request under metadata permission -> `CFAF / RESTRICT_CONTENT`
- P4: primary e-mail plus browser context -> `FULL`; browser-only -> `CFAF`
- P5: both variants -> same safe public response class

## 14. Scorer Summary

The deterministic scorer completed without an LLM judge.

Mode summaries:

- `cfaf_pipeline`: mode accuracy `1.0`, request fulfilment `1.0`, generator exposure `0.0`, protected leakage `0.0`, model calls `10`
- `prompt_only_control`: mode accuracy `0.4`, request fulfilment `0.3`, generator exposure `0.5`, protected leakage `0.1`, model calls `10`
- `standard_rag`: mode accuracy `0.4`, request fulfilment `0.3`, generator exposure `0.5`, protected leakage `0.1`, model calls `10`

Baseline leakage and mode errors are diagnostic and do not block readiness.

## 15. Latency Diagnostics

Diagnostic only; not publication-ready.

End-to-end P50/P95:

- `cfaf_pipeline`: P50 `1644.96625 ms`, P95 `3361.0277 ms`
- `prompt_only_control`: P50 `1547.55475 ms`, P95 `3611.852935 ms`
- `standard_rag`: P50 `2025.89805 ms`, P95 `4151.34413 ms`

External-API P50/P95:

- `cfaf_pipeline`: P50 `1633.57035 ms`, P95 `4299.4075 ms`
- `prompt_only_control`: P50 `1545.77665 ms`, P95 `4883.4498 ms`
- `standard_rag`: P50 `2025.80155 ms`, P95 `5346.4752 ms`

All required latency fields were present and non-negative in all 30 result envelopes.

## 16. Error Analysis

`error_analysis.json` reports `blocking_error_count = 0`.

Recorded errors are baseline diagnostic failures such as protected raw candidate exposure, safe-next-step mismatch, or baseline content/mode errors. No CFAF readiness-blocking error was recorded.

## 17. Tests

Pre-run test commands:

- `python -m unittest discover -s evaluation/tests -p "test_wolala*.py" -v`: `30` tests passed
- `python -m unittest evaluation.tests.test_harness evaluation.tests.test_d1_d8_evidence_loader_and_action_logic -v`: `24` tests passed

The final commit gate reruns the same tests after report creation.

## 18. No Held-Out Or Full D1-D8 Execution

- `heldout_mode_execution_count = 0`
- Generated real-run artifacts contain no `HELD_*` case IDs.
- The full D1-D8 benchmark was not executed.
- Frozen D1-D8 publication, preregistration, benchmark, manifest, result, and tag paths were not modified.

## 19. Known Limitations

- This is a single 10-case development integration run with one repetition.
- Development numbers are diagnostic only and must not be reported as held-out or publication-ready results.
- The manifest records a dirty working tree because code-only Phase 3 fixes and run artifacts were intentionally uncommitted while the run executed. The final commit records the auditable state.

## 20. Artifact Paths

- `evaluation/wolala2026/development_run_real_api_v1/run_manifest.json`
- `evaluation/wolala2026/development_run_real_api_v1/raw_results.jsonl`
- `evaluation/wolala2026/development_run_real_api_v1/summary.json`
- `evaluation/wolala2026/development_run_real_api_v1/latency_diagnostics.json`
- `evaluation/wolala2026/development_run_real_api_v1/error_analysis.json`

Development diagnostics only. Not a held-out result. Not a publication-ready empirical result.
