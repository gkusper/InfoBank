# WoLaLa 2026 Held-out Attempt 1 Plan Validation

- Timestamp UTC: `2026-08-22T14:48:58Z`
- Branch: `wolala2026`
- Freeze commit: `182f9d6c256526701ead65901fed0e90e2ff5e6a`
- Freeze tag: `wolala2026-heldout-protocol-v2-freeze`
- Execution spec: `evaluation/wolala2026/HELDOUT_EXECUTION_SPEC_v2.json`
- Plan artifact: `evaluation/wolala2026/preheldout_attempt1/execution_plan.json`

## Result

PASS: plan-only completed without held-out execution, retrieval, embedding, adapter execution, generation, scoring, or external API calls.

## Observed Plan

| Field | Expected | Observed | Status |
| --- | ---: | ---: | --- |
| `schema_version` | `wolala-heldout-plan-only-v2` | `wolala-heldout-plan-only-v2` | PASS |
| `dataset` | `heldout_pilot_v1` | `heldout_pilot_v1` | PASS |
| `cases` | `40` | `40` | PASS |
| `mode_count` | `3` | `3` | PASS |
| `repetitions` | `3` | `3` | PASS |
| `planned_mode_executions` | `360` | `360` | PASS |
| `planned_unique_embedding_requests` | `40` | `40` | PASS |
| `planned_generation_requests_maximum` | `360` | `360` | PASS |
| `planned_external_requests_without_retries_maximum` | `400` | `400` | PASS |
| `max_mode_executions` | `360` | `360` | PASS |
| `max_embedding_calls` | `60` | `60` | PASS |
| `max_generation_calls` | `380` | `380` | PASS |
| `hard_total_external_cap` | `420` | `420` | PASS |
| `max_total_retry_attempts` | `20` | `20` | PASS |
| `max_retries_per_logical_request` | `1` | `1` | PASS |
| `external_warmup_calls` | `0` | `0` | PASS |
| `heldout_model_execution_count` | `0` | `0` | PASS |
| `heldout_embedding_calls` | `0` | `0` | PASS |
| `heldout_generation_calls` | `0` | `0` | PASS |
| `external_api_calls_in_plan_only` | `0` | `0` | PASS |
| `no_retrieval_embedding_adapter_generation_or_scoring_performed` | `True` | `True` | PASS |
| `not_a_heldout_result` | `True` | `True` | PASS |
| `modes` | `['standard_rag', 'prompt_only_control', 'cfaf_pipeline']` | `['standard_rag', 'prompt_only_control', 'cfaf_pipeline']` | PASS |
| `case_ids_count` | `40` | `40` | PASS |

## External Calls

- Plan-only external API calls: `0`
- Held-out model executions: `0`
- External warm-up calls: `0`

## Verdict

PASS: plan matches Protocol v2 held-out attempt 1 configuration.
