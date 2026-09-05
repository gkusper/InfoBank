# WoLaLa 2026 Pre-Heldout Blocker Report v1

## Status

STOPPED_BEFORE_HELDOUT - PROTOCOL_REQUIRES_NEW_FREEZE

No held-out model execution was performed. No held-out retrieval, embedding,
generation, scoring, or latency output was created in this task.

## Starting State

- Repository branch: `wolala2026`
- Starting commit: `9ed1afe9e33cfe7d74c0e4460aa70450d4b13a73`
- Current readiness before this task: `READY_FOR_SMALL_WOLALA_PILOT`
- Phase 2 tag present: `wolala2026-pilot-readiness-v0.2`
- Phase 3 real-API tag present: `wolala2026-real-api-development-v1`
- Phase 3 ready tag present: `wolala2026-small-pilot-ready-v1`
- Original D1-D8 base ancestor verified: `5bb2cc742e105cc3238b022130126947c04bcd35`

## Frozen Checksum Verification

- Protocol checksum: `91c6e3279821abdd0c5b92006a4ce572293fc5ed29a77e7edbf5d1b47147f93e` - MATCH
- Held-out dataset checksum: `b86ddfa2a3db79a5d9e3e31b57000f1619f790040a6d9d814970ea2d1f54031b` - MATCH
- Prompt-only checksum: `77d2d8ff8042f94fd7381580d6034deb19827d3502e06bf67a96b87103fb0af6` - MATCH
- CFAF generator checksum: `0f6d54a1c9f5ccf3f0b4a1559cdb18c4dcd4a68f0c5f22895a440f50e45ba765` - MATCH

The checksum gate passed. The held-out execution was stopped by protocol
completeness requirements, not by checksum drift.

## Prior Held-Out Nonexecution Audit

`PRE_HELDOUT_NONEXECUTION_AUDIT_v1.json` records:

- `prior_heldout_mode_execution_count = 0`
- `prior_heldout_embedding_calls = 0`
- `prior_heldout_generation_calls = 0`
- `heldout_output_artifacts_found = false`
- `audit_passed = true`

The frozen held-out dataset contains `HELD_*` IDs by design. No `HELD_*` IDs
were found in development run output artifacts, and no held-out run output
directory existed before this audit.

## Blocking Finding

The Phase 4 instructions require stopping before held-out execution if the
frozen protocol does not unambiguously specify repetition count, statistical
analysis, retry policy, latency semantics, call caps, invalid-run policy, or
rerun policy.

`WOLALA2026_PILOT_PROTOCOL_v1.md` is not sufficiently complete for the first
held-out execution.

### Held-Out Call Caps Are Not Frozen

The protocol's `API Call Caps` section freezes only development integration
caps:

- `max_mode_executions: 30`
- `max_embedding_calls: 10`
- `max_generation_calls: 30`
- `max_total_external_calls: 40`

Those caps cannot apply to a 40-case held-out pilot with three modes and three
measured repetitions. The protocol does not state exact held-out caps for:

- maximum mode executions;
- maximum embedding calls;
- maximum generation calls;
- maximum total external calls;
- whether warm-up calls are inside or outside those caps.

### Provider And Model Configuration Are Not Held-Out Specific

The protocol records deterministic-local development defaults and says a future
real-API development run may use `text-embedding-3-small` and `gpt-4o-mini` or
explicitly recorded replacements. It does not explicitly freeze the held-out
provider/model configuration in protocol text.

Phase 3 artifacts used OpenAI, `text-embedding-3-small`, and `gpt-4o-mini`, but
Phase 4 explicitly says not to infer missing values from earlier reports or
conversation. Therefore this cannot be treated as an unambiguous frozen
held-out protocol value.

### Retry, Invalid-Run, And Rerun Policies Are Incomplete

The protocol describes general failure handling and exclusion criteria, but it
does not define an exact held-out retry policy or whether any infrastructure
failure would permit a rerun. Phase 4 requires those semantics before any
held-out attempt.

### Statistical Analysis Plan Is Missing

The protocol defines primary and diagnostic metrics, but it does not define:

- Wilson confidence intervals;
- exact McNemar comparisons;
- multiplicity correction;
- bootstrap intervals;
- case-level aggregation with repetitions;
- adjusted and unadjusted reporting rules;
- which metrics are inferential versus descriptive only.

Phase 4 requires using exactly the frozen statistical analysis plan. Since no
such plan is frozen, the held-out run cannot proceed.

### Latency Semantics Are Not Sufficiently Frozen

The protocol says to record monotonic stage timings, external-API timings, and
end-to-end latency, but does not explicitly define:

- the exact start event for user-visible end-to-end latency;
- the exact end event;
- whether shared embedding/retrieval is included once per case, once per mode,
  or derived into mode-level user-visible latency;
- the sample unit for external-API P50/P95;
- the relationship between shared retrieval timing and per-mode timing.

Phase 4 allows a deterministic latency definition before held-out execution
only if it can be frozen before the execution plan. Because the protocol also
has independent blockers above, no latency-definition change was made in this
task.

## Decision

Held-out execution is blocked. Running `heldout_pilot_v1` now would violate the
Phase 4 hard freeze because the exact held-out execution and analysis protocol
is not fully specified.

Required next step: create a separate pre-heldout protocol revision/freeze task
before any held-out model output is generated. That task should define exact
held-out caps, provider/model values, retry/invalid-run/rerun policy,
statistical analysis plan, repetition aggregation, and latency semantics, then
freeze the revised protocol with new checksums.

## Confirmations

- No held-out API call was made.
- No held-out output directory was created.
- No protocol, prompt, scorer, parser, gold label, or held-out dataset file was
  modified.
- No WoLaLa manuscript file was modified.
- No full D1-D8 benchmark was executed.

## Final Classification

STOPPED_BEFORE_HELDOUT - PROTOCOL_REQUIRES_NEW_FREEZE
