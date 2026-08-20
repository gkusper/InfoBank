# Real-provider evaluation readiness

Status: `PENDING_EXPLICIT_PROVIDER_RUN_APPROVAL`

No real provider run occurred while preparing this gate. The implementation
does not call a network provider by default and never falls back from a
requested OpenAI run to a mock.

## Fixed configuration

- provider must be explicitly `openai`;
- generation model: `gpt-4o-mini`;
- embedding model: `text-embedding-3-small`;
- temperature: `0.0`;
- generation prompt: `actual-pipeline-answer-v1`;
- routing prompt: `routing-keyword-v1`;
- readiness config: `real-provider-readiness-v1`;
- config hash: `56d8ed701f154e84c615944e34c4d5ff843c28b2c72e404311e3762e79404908`.

`scripts/run_real_provider_evaluation.py` exposes `--provider openai`,
`--allow-network-provider`, `--max-cases`, `--estimate-only` (with the legacy
`--estimated-cost-only` alias), `--repeats`, `--modes`,
`--include-scale-subset`, `--pricing-config`,
`--average-provider-latency-ms`, `--max-estimated-cost`, and `--output`. An actual OpenAI execution requires both the provider
selection and network-approval flag. Missing credentials or provider errors
are hard failures. The sealed runner records provider/model identifiers,
prompt versions, temperature, retry count, provider-reported token usage,
local-price-derived cost when supplied, and actual generation wall-clock time
in the separate stage-timing sidecar.

Provider outputs are cached under an explicit ignored cache directory. Each
cache identity contains the input hash, provider, model, prompt version, and
evaluation config hash. Keyword, embedding, and generation operations use
separate cache namespaces.

## Network-free complete E1 estimates

The full estimator reads and verifies the current pre-freeze manifest, query
file, source manifest and PDF hashes. The estimate path returns before runtime
provider imports and does not read an API key. It produced:

- 45 candidate-holdout queries, 4 modes and 180/360/540 cases for one/two/three repeats;
- 272632/545264/817896 estimated total generation tokens;
- 406/812/1218 estimated provider requests under the documented cold, repeat-scoped cache model;
- a separate optional 24-query, two-routing-mode, 1000-document scale subset: 48 cases and 121 estimated requests.

No pricing configuration or latency assumption was supplied. Projected costs
are `null` with `NO_LOCAL_PRICING_CONFIG`; provider runtime is `UNKNOWN`. The
method and commands are in `E1_ESTIMATE_ONLY_PLAN.md`. No price or latency was
invented and no provider call occurred.

## Approval-only command shape

After explicit human approval, supply isolated database/runtime paths, gold
annotations, cache/output paths, local pricing if cost capping is required,
and run:

```powershell
backend_python\.venv_r1a\Scripts\python.exe scripts\run_real_provider_evaluation.py `
  --provider openai --allow-network-provider --max-cases 20 `
  --max-estimated-cost <approved-cap> --pricing-config <local-pricing.json> `
  --query-input <query-input.jsonl> --corpus-fixture <corpus-fixture.json> `
  --gold-annotations <gold-annotations.jsonl> --output <ignored-output> `
  --cache-dir <ignored-cache> --chroma-dir <isolated-chroma> `
  --source-storage-dir <isolated-source-store> --database-url <isolated-eval-url>
```

This document is readiness evidence only. It is not provider-run approval, a
dataset/config freeze, or final E1 evidence.

`DO_NOT_RUN_FINAL_E1_YET`
