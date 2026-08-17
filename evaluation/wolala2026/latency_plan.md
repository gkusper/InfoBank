# WoLaLa 2026 Latency Plan

## Current Instrumentation

Every top-level stage is wrapped with `time.perf_counter_ns()` and emitted as a
non-negative millisecond duration in the serialized `PipelineState`:

- `query_profiling_ms`
- `candidate_retrieval_ms`
- `access_and_safety_resolution_ms`
- `evidence_labelling_ms`
- `sufficiency_and_permitted_output_ms`
- `top_level_mode_selection_ms`
- `response_realization_ms`
- `validation_trace_and_feedback_ms`
- `end_to_end_ms`

The state also records:

- `embedding_api_ms`
- `generation_api_ms`
- `external_api_ms`
- `model_call_count`
- `generation_skipped`
- `input_tokens`
- `output_tokens`

The deterministic smoke suite records local timings only. It verifies that P50
and P95 aggregation code works, but those values are not statistically
meaningful because there are only 13 smoke cases.

## Later Experiment Separation

A later small experiment should report latency separately for:

- `FULL` versus `CFAF`
- cold versus warm runs
- generation-used versus generation-skipped cases
- local gate time versus external embedding/generation/tool API time
- prompt-only control versus external CFAF pipeline

If stages later run in parallel, `end_to_end_ms` should remain the authoritative
wall-clock latency. It does not need to equal the arithmetic sum of individual
stage durations.

## Guardrails

Do not run D1-D8 or any large real-API benchmark for latency collection from
this preparation branch. Use a later explicit opt-in command with a small case
cap, fixed model, fixed temperature, and sanitized per-case records.
