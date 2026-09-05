# Shared Retrieval Fix Report v1

## 1. Executive Summary

This repair fixes the WoLaLa 2026 runner defect that recomputed retrieval and
query embedding once per case per repetition. The corrected runner now creates
one retrieval snapshot per unique case and reuses that immutable snapshot for
all modes and all repetitions.

The repair is limited to runner integrity, call accounting, verification, and
focused tests. It does not change CFAF semantics, prompts, parser behavior,
scorer behavior, statistical definitions, latency definitions, datasets, or the
WoLaLa manuscript.

## 2. Failed-Attempt Status And Preservation

- Dataset: `heldout_pilot_v2`
- Attempt: `1`
- Recorded status: `INVALIDATED_SCIENTIFIC_INTEGRITY_FAILURE`
- Failed run directory: `evaluation/wolala2026/heldout_run_real_api_v2_attempt1/`
- Failed report: `evaluation/wolala2026/HELDOUT_V2_ATTEMPT1_FAILED_RUN_REPORT_v1.md`
- Failed audit: `evaluation/wolala2026/HELDOUT_V2_ATTEMPT1_FAILED_RUN_AUDIT_v1.json`

Preservation checks:

- Failed report SHA256: `2762d379c6eb756c4dd8596054d0e3b0ef849c8bdd60a326929f3ba364c713b7`
- Failed audit SHA256: `8e0467064c5fa0d6caed6615dbba389c5868c47935a3d45794f518d0b3c27689`
- Failed run checksum file SHA256: `a64e1b9c95deb03f8be5d6bea2bbbaeac2d7b076d02f547c7f293ae14b920273`

The failed attempt remains preserved and was not edited, continued, completed,
or reclassified. Its partial values remain diagnostic only.

## 3. Starting Branch And Commit

- Branch: `wolala2026`
- Starting local HEAD: `aed8cdb9d4cc9e6d90103804b6aeb87e6f5f144f`
- Starting remote `origin/wolala2026`: `aed8cdb9d4cc9e6d90103804b6aeb87e6f5f144f`
- Starting commit summary: `aed8cdb Record CFAF held-out pilot v2 attempt 1 failure`
- Historical ancestor verified: `5bb2cc742e105cc3238b022130126947c04bcd35`

## 4. Root-Cause Location

Exact location:

- File: `evaluation/wolala2026/run_pilot.py`
- Function: `run_pilot`

The old execution loop called `_real_retrieval_snapshot(...)` inside the
repetition loop. That helper performs `provider.embed_query(case["query"])`.

## 5. Old Loop Structure

```text
for repetition in repetitions:
    for case in cases:
        snapshot = retrieve(case)
        for mode in modes:
            execute_mode(case, repetition, mode, snapshot)
```

This shared retrieval across modes within one repetition, but not across
repetitions.

## 6. Corrected Loop Structure

```text
for case in cases:
    shared_snapshot = retrieve_once(case)

    for repetition in repetitions:
        for mode in modes:
            execute_mode(
                case=case,
                repetition=repetition,
                mode=mode,
                retrieval_snapshot=shared_snapshot,
            )
```

The snapshot cache key includes dataset checksum, case ID, query,
retriever version, and `top_k`.

## 7. Exact Changed Files

Primary code and schema changes:

- `evaluation/wolala2026/run_pilot.py`
- `evaluation/wolala2026/run_manifest.py`
- `evaluation/wolala2026/run_manifest_schema.json`
- `evaluation/wolala2026/pilot_data.py`
- `evaluation/wolala2026/readiness_baseline_manifest.json`

Tests:

- `evaluation/tests/test_wolala_shared_retrieval_repair.py`
- `evaluation/tests/test_wolala_final_experiment_v2.py`

New audit and readiness records:

- `evaluation/wolala2026/HELDOUT_PILOT_V2_RETIREMENT_RECORD.md`
- `evaluation/wolala2026/SHARED_RETRIEVAL_ROOT_CAUSE_REPORT_v1.md`
- `evaluation/wolala2026/SHARED_RETRIEVAL_INVARIANT_SPEC_v1.md`
- `evaluation/wolala2026/SHARED_RETRIEVAL_FIX_REPORT_v1.md`
- `evaluation/wolala2026/SHARED_RETRIEVAL_REPAIR_READINESS_REPORT_v1.md`

New development regression artifacts:

- `evaluation/wolala2026/development_shared_retrieval_regression_v1/`
- `evaluation/wolala2026/development_shared_retrieval_real_api_v1/`

Files deliberately not changed:

- `evaluation/wolala2026/retrieval.py`
- `evaluation/wolala2026/real_api.py`
- `evaluation/wolala2026/adapters.py`
- prompts, parser, scorer, statistical-analysis files, D1-D8 fixtures, and
  manuscript/publication artifacts

## 8. Why The Defect Was Not Caught Earlier

The previous development and real-API integration tests used one repetition.
With `repetitions = 1`, the old loop still produced one retrieval snapshot per
case and one snapshot hash across the three modes. The defect appears only
when `repetitions > 1`, because the old outer repetition loop re-entered
retrieval for the same case.

## 9. Shared-Retrieval Invariants

The repair implements the invariants recorded in
`SHARED_RETRIEVAL_INVARIANT_SPEC_v1.md`:

- one logical retrieval per unique case;
- one immutable snapshot per case;
- `M * R` result-record references per snapshot;
- embedding attempts independent of mode count and repetition count;
- cap checks based on unique case count;
- shared retrieval latency measured once per case;
- no mode-specific retrieval;
- no gold label influence on retrieval.

## 10. Call-Accounting Semantics

For `N` unique cases, `M` modes, and `R` repetitions:

```text
planned_logical_embedding_requests = N
successful_logical_embedding_requests = N
actual_embedding_attempts = N + embedding_retry_attempts
retrieval_snapshot_count = N
snapshot_reuse_count = N * M * R
result_record_count = N * M * R
```

The manifest now records:

- `successful_logical_embedding_requests`
- `actual_embedding_attempts`
- `embedding_retry_attempts`
- `retrieval_cache_hits`
- `retrieval_snapshot_count`
- `snapshot_reuse_count`
- `unique_retrieval_snapshot_hashes`
- `result_record_count`

Old preserved runs were not retroactively redefined or regenerated.

## 11. Latency Implications

The repair preserves the existing user-visible latency definition:

```text
user_visible_end_to_end_ms = shared_retrieval_ms + mode_processing_ms
```

The change is where retrieval is measured: once per case, then referenced by
each mode/repetition record. The runner now emits `shared_retrieval_ms` and
`mode_processing_ms` so verification can distinguish the shared retrieval
component from mode execution.

## 12. Unit-Test List And Results

New focused tests in
`evaluation/tests/test_wolala_shared_retrieval_repair.py`:

- T1: `test_t1_retrieval_once_per_case_across_repetitions` - PASS
- T2: `test_t2_snapshot_hash_stability` - PASS
- T3: `test_t3_repetition_count_does_not_affect_embedding_count` - PASS
- T4: `test_t4_mode_count_does_not_affect_embedding_count` - PASS
- T5: `test_t5_exact_embedding_cap_succeeds` - PASS
- T6: `test_t6_insufficient_embedding_cap_fails_before_provider_use` - PASS
- T7: `test_t7_retry_accounting` - PASS
- T8: `test_t8_existing_one_repetition_behavior_remains_unchanged` - PASS
- T9: `test_t9_retired_heldout_pilot_v2_is_blocked` - PASS
- T10: `test_t10_plan_only_and_runtime_accounting_agree` - PASS
- T11: `test_t11_shared_retrieval_latency_is_reused` - PASS
- T12: `test_t12_no_heldout_execution_in_repair_tests` - PASS

Focused test command:

```text
python -m unittest evaluation.tests.test_wolala_shared_retrieval_repair -v
```

Result: `Ran 12 tests ... OK`.

No external API call was used by the unit tests.

## 13. Existing-Test Results

WoLaLa test command:

```text
python -m unittest discover -s evaluation/tests -p "test_wolala*.py" -v
```

Result: `Ran 65 tests ... OK`.

Relevant InfoBank test command:

```text
python -m unittest evaluation.tests.test_harness evaluation.tests.test_d1_d8_evidence_loader_and_action_logic -v
```

Result: `Ran 24 tests ... OK`.

## 14. Deterministic 10-Case x 3-Mode x 3-Repetition Regression

Output directory:

`evaluation/wolala2026/development_shared_retrieval_regression_v1/`

Configuration:

- dataset: `development_integration_v1`
- cases: 10
- modes: `standard_rag`, `prompt_only_control`, `cfaf_pipeline`
- repetitions: 3
- provider: `deterministic-local`
- external API calls: 0

Results:

- completion status: `COMPLETED`
- mode executions: 90
- result records: 90
- planned logical embedding requests: 10
- successful logical embedding requests: 10
- actual embedding attempts: 0
- embedding retry attempts: 0
- retrieval snapshots: 10
- unique retrieval snapshot hashes: 10
- snapshot reuse count: 90
- retrieval cache hits: 80
- held-out mode executions: 0

Required verification:

- `all_cases_share_retrieval = true`
- `all_cases_have_expected_record_count = true`
- `embedding_count_independent_of_repetitions = true`
- `no_heldout_case_executed = true`
- `shared_retrieval_latency_reused = true`

Accuracy and leakage values from this run are development diagnostics only and
are not manuscript results.

## 15. Real-API Four-Case Development Regression

Output directory:

`evaluation/wolala2026/development_shared_retrieval_real_api_v1/`

Selected before execution in `selected_cases.json`:

- `DEV_P2_01A`
- `DEV_P2_01B`
- `DEV_P5_01A`
- `DEV_P5_01B`

Configuration:

- dataset: `development_integration_v1`
- cases: 4
- modes: `standard_rag`, `prompt_only_control`, `cfaf_pipeline`
- repetitions: 3
- provider: `openai`
- embedding model: `text-embedding-3-small`
- generator model: `gpt-4o-mini`
- temperature: 0
- top_k: 4
- max_output_tokens: 160
- `--allow-heldout`: not used

Results:

- completion status: `COMPLETED`
- mode executions: 36
- result records: 36
- planned logical embedding requests: 4
- successful logical embedding requests: 4
- actual embedding attempts: 4
- embedding retry attempts: 0
- actual generation calls: 36
- actual total external calls: 40
- retrieval snapshots: 4
- unique retrieval snapshot hashes: 4
- snapshot reuse count: 36
- retrieval cache hits: 32
- held-out mode executions: 0

Required verification:

- `all_cases_share_retrieval = true`
- `all_cases_have_expected_record_count = true`
- `embedding_count_independent_of_repetitions = true`
- `no_heldout_case_executed = true`
- `shared_retrieval_latency_reused = true`

This is a development regression only. Model-answer quality values are not
confirmatory results.

## 16. Planned Versus Actual Embedding Counts

Deterministic regression:

- planned logical embedding requests: 10
- successful logical embedding requests: 10
- actual embedding attempts: 0, because deterministic-local does not call an
  external embedding provider

Real-API regression:

- planned logical embedding requests: 4
- successful logical embedding requests: 4
- actual embedding attempts: 4
- embedding retries: 0

## 17. Planned Versus Actual Generation Counts

Deterministic regression:

- planned generation requests: 0 external calls
- actual generation calls: 0

Real-API regression:

- planned generation requests maximum: 36
- actual generation calls: 36

## 18. Snapshot Counts And Reuse Counts

Deterministic regression:

- retrieval snapshots: 10
- snapshot reuse count: 90
- records per case: 9

Real-API regression:

- retrieval snapshots: 4
- snapshot reuse count: 36
- records per case: 9

## 19. Snapshot-Hash Verification

Both development regressions verified:

- every case had exactly one `retrieval_snapshot_hash`;
- all modes for a case used that hash;
- all three repetitions for a case used that hash;
- candidate IDs, candidate order, metadata, and retrieval scores remained tied
  to the same shared snapshot.

## 20. Adapter-Integrity Verification

Both development regressions generated
`adapter_integrity_verification.json`. The existing adapter-integrity checks
passed in the full WoLaLa test suite. No adapter was changed.

## 21. heldout_pilot_v2 Remained Unexecuted After Retirement

`heldout_pilot_v2` is registered as
`RETIRED_AFTER_SCIENTIFIC_INTEGRITY_FAILURE` in `pilot_data.py`. The runner now
fails closed before retrieval, provider initialization, or output-directory
creation for any execution attempt against the retired dataset.

The new deterministic and real-API development artifacts contain no
`HELD_*`, `HELD2_*`, or `HELD3_*` case IDs.

## 22. No New Held-Out Dataset Was Created

No `heldout_pilot_v3` or other new held-out dataset was created in this task.

## 23. No WoLaLa Manuscript Was Modified

No manuscript or publication-result file was modified. Generated
`summary_table.tex` files exist only inside the new development regression
artifact directories.

## 24. No Full D1-D8 Run Occurred

No full D1-D8 benchmark was run. The requested relevant D1-D8 loader/action
logic tests were run and passed.

## 25. Known Limitations

- The failed `heldout_pilot_v2` remains invalidated and cannot be repaired by
  appending missing repetitions.
- The real-API four-case regression is a development integrity check, not a
  confirmatory experiment.
- The run manifests were produced before the final repair commit, so their
  embedded `git_working_tree_status` records the repair as an uncommitted
  working tree at run time. The final response records the committed SHA.

## 26. Remaining Steps Before A New Held-Out Freeze

Before any new final CFAF held-out run:

- generate a new untouched `heldout_pilot_v3`;
- freeze the new dataset, protocol, execution spec, statistical plan, and
  latency definition;
- create a new non-execution audit and authorization gate;
- run plan-only validation;
- only then authorize a new held-out execution.

## 27. Git Diff And Changed-File List

The repair diff is intentionally limited to runner integrity, call accounting,
retirement guard, tests, reports, and development regression artifacts.

Expected changed-file groups:

- runner: `run_pilot.py`
- manifest schema/accounting: `run_manifest.py`, `run_manifest_schema.json`,
  `readiness_baseline_manifest.json`
- dataset retirement registry: `pilot_data.py`
- tests: `test_wolala_shared_retrieval_repair.py`,
  `test_wolala_final_experiment_v2.py`
- reports: five new WoLaLa audit/readiness markdown files
- artifacts: two new development regression directories

## 28. Final Readiness Classification

`READY_TO_CREATE_NEW_CFAF_HELDOUT_FREEZE`
