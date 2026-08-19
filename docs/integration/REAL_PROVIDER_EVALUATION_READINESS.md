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
`--allow-network-provider`, `--max-cases`, `--estimated-cost-only`, and
`--max-estimated-cost`. An actual OpenAI execution requires both the provider
selection and network-approval flag. Missing credentials or provider errors
are hard failures. The sealed runner records provider/model identifiers,
prompt versions, temperature, retry count, provider-reported token usage,
local-price-derived cost when supplied, and actual generation wall-clock time
in the separate stage-timing sidecar.

Provider outputs are cached under an explicit ignored cache directory. Each
cache identity contains the input hash, provider, model, prompt version, and
evaluation config hash. Keyword, embedding, and generation operations use
separate cache namespaces.

## Network-free estimate

The following development estimate was executed without an API key or network
provider call:

```powershell
backend_python\.venv_r1a\Scripts\python.exe scripts\run_real_provider_evaluation.py `
  --provider openai --estimated-cost-only --max-cases 20 `
  --query-input artifacts\actual_pipeline\development-20260819\dataset\query_inputs.jsonl `
  --corpus-fixture artifacts\actual_pipeline\development-20260819\dataset\corpus_fixture.json
```

Result: 20 cases, estimated 13,273 input tokens and 10,240 output tokens. The
method is an explicitly labelled local character-count estimate, not provider
billing data. No pricing configuration was supplied, so projected cost is
`null` with status `NO_LOCAL_PRICING_CONFIG`; no price was invented.

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
