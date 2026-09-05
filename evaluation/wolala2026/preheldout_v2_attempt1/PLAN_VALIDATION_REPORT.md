# heldout_pilot_v2 Attempt 1 Plan Validation Report

## Status

Plan-only validation passed.

No retrieval, embedding, adapter execution, generation, scoring, raw-result
creation, or external API call was performed.

## Frozen Plan

| Item | Value |
| --- | --- |
| Dataset | `heldout_pilot_v2` |
| Case count | `40` |
| Case prefix | `HELD2_` |
| Modes | `standard_rag`, `prompt_only_control`, `cfaf_pipeline` |
| Repetitions | `3` |
| Planned mode executions | `360` |
| Unique shared embeddings | `40` |
| Generation requests maximum | `360` |
| External requests without retries maximum | `400` |
| Hard total external-call cap | `420` |
| Model executions in plan-only | `0` |
| External calls in plan-only | `0` |
| External warm-up calls | `0` |

## Validation

The plan was produced by:

```powershell
python -m evaluation.wolala2026.run_pilot --dataset heldout_pilot_v2 --modes standard_rag,prompt_only_control,cfaf_pipeline --repetitions 3 --execution-spec evaluation/wolala2026/HELDOUT_EXECUTION_SPEC_v3.json --output-dir evaluation/wolala2026/preheldout_v2_attempt1 --max-mode-executions 360 --max-embedding-calls 60 --max-generation-calls 380 --max-total-external-calls 420 --plan-only
```

The output file is:

`evaluation/wolala2026/preheldout_v2_attempt1/execution_plan.json`

The plan is not a held-out result and is not publication-ready empirical output.
