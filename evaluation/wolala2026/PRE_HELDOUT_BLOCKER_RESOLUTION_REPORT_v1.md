# WoLaLa 2026 Pre-Heldout Blocker Resolution Report v1

## Status

`PRE_HELDOUT_BLOCKER_REPORT_v1.md` classified the prior state as:

`STOPPED_BEFORE_HELDOUT - PROTOCOL_REQUIRES_NEW_FREEZE`

This report records how `WOLALA2026_PILOT_PROTOCOL_v2.md` resolves each
protocol-completeness blocker before any held-out execution.

## Starting Commit

- Branch: `wolala2026`
- Starting commit for this freeze task: `0bf388e2b0c65935d561433c0e6d827f6c80102e`
- Original D1-D8 base ancestor verified: `5bb2cc742e105cc3238b022130126947c04bcd35`

## Frozen Artifacts Preserved

- Protocol v1 checksum remains `91c6e3279821abdd0c5b92006a4ce572293fc5ed29a77e7edbf5d1b47147f93e`.
- Held-out dataset checksum remains `b86ddfa2a3db79a5d9e3e31b57000f1619f790040a6d9d814970ea2d1f54031b`.
- Prompt-only checksum remains `77d2d8ff8042f94fd7381580d6034deb19827d3502e06bf67a96b87103fb0af6`.
- CFAF generator checksum remains `0f6d54a1c9f5ccf3f0b4a1559cdb18c4dcd4a68f0c5f22895a440f50e45ba765`.

## Resolution Map

| v1 blocker | Protocol v2 resolution | Machine-readable support |
| --- | --- | --- |
| Held-out call caps not frozen | Protocol v2 freezes `max_mode_executions = 360`, `max_embedding_calls = 60`, `max_generation_calls = 380`, `max_total_external_calls = 420`, and retry budget `20`. | `HELDOUT_EXECUTION_SPEC_v2.json`; `execution_spec.validate_execution_spec`; runner cap checks. |
| Provider/model configuration not held-out specific | Protocol v2 freezes provider `openai`, direct HTTPS wrapper, embedding `text-embedding-3-small`, generator `gpt-4o-mini`, temperature `0`, top-k `4`, max tokens `160`, no replacement. | Execution spec checks exact provider/model fields and artifact checksums. |
| Retry policy incomplete | Protocol v2 permits one retry only for transient infrastructure/provider failures and records retry reason/wait/outcome. | `retry_policy.py`; budgeted runner wrapper; retry budget fields in manifest schema. |
| Invalid-run policy incomplete | Protocol v2 separates valid empirical outcomes, `INVALIDATED_INFRASTRUCTURE_FAILURE`, and `INVALIDATED_SCIENTIFIC_INTEGRITY_FAILURE`. | `retry_policy.classify_invalidation`; readiness tests cover infrastructure and scientific-integrity classes. |
| Rerun policy incomplete | Protocol v2 forbids result-driven or selective reruns and allows a full second attempt only after independently audited infrastructure invalidation in a separate task. | `retry_policy.rerun_authorized`; tests cover prohibition and the complete allowed condition. |
| Statistical analysis plan missing | Protocol v2 incorporates `WOLALA2026_STATISTICAL_ANALYSIS_PLAN_v1.md` with checksum `2639906b515589ba3fe15487567cc53aaf875823909eb077a2bd06f8ee149b1e`. | `analyze_heldout.py`; unit tests for Wilson, McNemar, Holm, bootstrap, denominators, and primary/descriptive labels. |
| Repetition aggregation missing | Protocol v2 freezes majority aggregation for correctness and any-event aggregation for safety, with P5 pair aggregation for source-existence leakage. | `analyze_heldout.aggregate_case_metric` and `aggregate_p5_pair_leakage`; tests cover all three rules. |
| Latency semantics incomplete | Protocol v2 incorporates `WOLALA2026_LATENCY_DEFINITION_v1.md` with checksum `4c0c87f6267ab18f68677479439d4347d8449f36ed850e87d7d94b89e02b02a7`. | `latency_analysis.py`; tests cover shared retrieval counted once, user-visible derivation, case-mode median, and sample units. |

## Scorer And Parser Sanity

`PRE_HELDOUT_SCORER_SANITY_AUDIT_v1.md` inspected all 30 real-API development
observations. Parser agreement count is `30`, scorer agreement count is `30`,
and disagreements affecting a primary metric are `0`.

No scorer/parser blocker remains.

## Nonexecution Confirmation

`PRE_HELDOUT_NONEXECUTION_AUDIT_v2.json` records:

- `prior_heldout_mode_execution_count = 0`
- `prior_heldout_embedding_calls = 0`
- `prior_heldout_generation_calls = 0`
- `heldout_output_artifacts_found = false`
- `audit_passed = true`

## Decision

Every blocker recorded in `PRE_HELDOUT_BLOCKER_REPORT_v1.md` is resolved by
Protocol v2, the machine-readable execution spec, deterministic statistical and
latency modules, and the new pre-held-out audits.

No held-out model execution was authorized or performed in this task.
