# WoLaLa 2026 Latency Definition v1

## Status

Frozen before any `heldout_pilot_v1` model output exists. This definition is
incorporated by `WOLALA2026_PILOT_PROTOCOL_v2.md` and must not be revised after
viewing held-out output.

## Shared Retrieval Latency

`case_retrieval_start` is immediately before the case's query embedding request
or first retrieval work.

`case_retrieval_end` is after the shared candidate snapshot is complete and
immutable.

`shared_retrieval_ms = case_retrieval_end - case_retrieval_start`.

This duration includes query embedding API time, local candidate retrieval,
snapshot construction, and snapshot serialization required before adapter
execution. It is measured once per unique case and reused across all modes and
repetitions.

When legacy timing records lack explicit start/end timestamps,
`shared_retrieval_ms` is derived deterministically as:
`embedding_api_ms + candidate_retrieval_ms + snapshot_serialization_ms`, with
missing fields treated as zero.

## Mode-Specific Processing Latency

`mode_processing_start` is immediately before adapter-specific processing
begins using the frozen shared retrieval snapshot.

`mode_processing_end` is after the final validated public response and mode
result envelope are complete.

`mode_processing_ms = mode_processing_end - mode_processing_start`.

This includes query-profile processing not already included before the shared
snapshot, governance checks, evidence labelling, sufficiency calculation,
FULL/CFAF mode selection, prompt or response-contract construction, generation,
validation, fallback, final public-trace construction, and result serialization
required for the response.

When legacy timing records lack explicit mode start/end timestamps,
`mode_processing_ms` is derived as
`max(0, end_to_end_ms - shared_retrieval_ms)`.

## Primary User-Visible Latency

For every case, mode, and repetition:

`user_visible_end_to_end_ms = shared_retrieval_ms + mode_processing_ms`.

Shared retrieval is added once to each mode execution for comparability and
must not be added more than once.

The primary user-visible latency begins when the user query starts embedding or
retrieval and ends when the final validated public response is ready.

## External API Latency

Record individual API call durations separately:

- `embedding_api_call_ms`
- `generation_api_call_ms`
- `retry_api_call_ms`

Define:

`user_visible_external_api_ms = shared_embedding_api_ms + mode_generation_api_ms + applicable_retry_api_ms`.

The distribution of individual API-call durations is diagnostic only. Never
compare a call-level API percentile directly with a case-mode-level
user-visible percentile without explicitly stating the different sample units.

## Repetition Aggregation

For each unique case and mode:

`case_mode_latency_ms = median(3 user_visible_end_to_end_ms repetition values)`.

The primary latency distribution for each mode contains 40 case-mode latency
values.

Report by mode:

- P50;
- P95;
- minimum;
- maximum;
- median absolute deviation;
- number of case-mode units.

Also report separate descriptive summaries for expected-`FULL` cases,
expected-`CFAF` cases, generation-used executions, and generation-skipped
executions.

Do not perform confirmatory significance testing on latency.

## Cold-Start Handling

No external warm-up calls are permitted. Record which request was the first
embedding call, which request was the first generation call, cache state when
available, and cold-start indicator when available.

Do not remove cold-start observations after seeing results.

## Implementation

The deterministic implementation is `evaluation/wolala2026/latency_analysis.py`.
It preserves raw timing fields, derives shared retrieval latency,
mode-processing latency, user-visible end-to-end latency, external API latency,
sample units, case-mode medians, and percentile summaries.
