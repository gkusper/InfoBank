# Held-Out v3 Attempt 1 Plan Validation

Status: PASS.

- Dataset: `heldout_pilot_v3`
- Protocol: `WOLALA2026_PILOT_PROTOCOL_v4.md`
- Execution spec: `HELDOUT_EXECUTION_SPEC_v4.json`
- Planned mode executions: `360`
- Planned unique embedding requests: `40`
- Planned generation requests maximum: `360`
- Planned external requests without retries: `400`
- Hard total external cap: `420`
- Retry budget: `20`
- External warmup calls: `0`
- Plan-only external API calls: `0`
- Held-out model execution count: `0`
- Held-out embedding calls: `0`
- Held-out generation calls: `0`

The plan-only command created only `execution_plan.json`. It performed no
retrieval, embedding, adapter execution, generation, model-output scoring, or
real-API provider initialization.

Runner return summary:

```json
{
  "completion_status": "PLANNED",
  "execution_plan_path": "C:\\Users\\EKKE\\Documents\\Codex\\2026-08-17\\files-mentioned-by-the-user-you\\work\\InfoBank-shared-retrieval-fix\\evaluation\\wolala2026\\preheldout_v3_attempt1\\execution_plan.json",
  "external_api_calls_in_plan_only": 0,
  "hard_total_external_cap": 420,
  "heldout_mode_execution_count": 0,
  "heldout_model_execution_count": 0,
  "mode_execution_count": 360,
  "planned_external_requests_without_retries_maximum": 400,
  "planned_generation_requests_maximum": 360,
  "planned_mode_executions": 360,
  "planned_unique_embedding_requests": 40
}
```

Spec validation returned:

```json
{
  "cases": 40,
  "external_warmup_calls": 0,
  "hard_total_external_cap": 420,
  "mode_count": 3,
  "planned_external_requests_without_retries_maximum": 400,
  "planned_generation_requests_maximum": 360,
  "planned_mode_executions": 360,
  "planned_unique_embedding_requests": 40,
  "repetitions": 3,
  "retry_budget": 20,
  "valid": true
}
```
