# Real-provider evaluation readiness

Status: `PENDING_EXPLICIT_PROVIDER_RUN_APPROVAL`

No real provider run occurred while preparing this gate. The implementation
does not call a network provider by default and never falls back from a
requested OpenAI or Anthropic run to a mock.

## Fixed configuration

- provider must be explicitly `openai` or `anthropic`;
- OpenAI generation model default: `gpt-4o-mini`;
- Anthropic generation model default: `claude-haiku-4-5-20251001`;
- embedding provider: `openai`;
- embedding model: `text-embedding-3-small`;
- OpenAI temperature: existing call-site value, `0.0` in the actual-pipeline runner;
- Anthropic sampling parameters: omitted by default, with no tools, batch API,
  extended thinking, or structured-response parameter;
- Anthropic default maximum output tokens: `512`, guarded at `<=1024` for real
  smoke runs;
- Anthropic default maximum automatic retries: `1`;
- generation prompt: `actual-pipeline-answer-v1`;
- routing prompt: `routing-keyword-v1`;
- keyword selection strategy: `infocom-keyword-selector-v2`;
- readiness config: `real-provider-readiness-v2`;
- config hash: derived per provider/model/embedding-provider configuration.

`scripts/run_real_provider_evaluation.py` exposes `--provider openai|anthropic`,
`--allow-network-provider`, `--max-cases`, `--estimate-only` (with the legacy
`--estimated-cost-only` alias), `--repeats`, `--modes`,
`--include-scale-subset`, `--pricing-config`,
`--average-provider-latency-ms`, `--max-estimated-cost`,
`--generation-model`, `--embedding-provider`, `--embedding-model`, `--output`,
`--max-provider-request-attempts`, `--max-anthropic-estimated-cost`,
`--max-provider-output-tokens`, `--max-provider-retries`,
`--full-experiment-preflight`, `--full-experiment-modes`, and
`--confirm-full-experiment`. An actual OpenAI or Anthropic execution requires
both the provider selection and network-approval flag. Anthropic execution also
requires `EMBEDDING_PROVIDER=openai` semantics and a compatible
`OPENAI_API_KEY` for embeddings. Missing credentials or provider errors are
hard failures. The default Anthropic smoke guard caps provider attempts at 70,
preliminary Anthropic spend at USD 2, output at 1024 tokens, and automatic
retries at one. The sealed runner records LLM provider/model and embedding provider/model
identifiers, prompt versions, temperature/sampling policy, retry count,
provider-reported token usage,
local-price-derived cost when supplied, and actual generation wall-clock time
in the separate stage-timing sidecar.

Provider outputs are cached under an explicit ignored cache directory. Each
LLM cache identity contains the input hash, provider, model, prompt version,
generation configuration hash, and evaluation config hash. Keyword, embedding,
and generation operations use separate cache namespaces.

## Network-free complete E1 estimates

The full estimator reads and verifies the current pre-freeze manifest, query
file, source manifest and PDF hashes. The estimate path returns before runtime
provider imports and does not read an API key. It produced:

- 45 candidate-holdout queries, 4 modes and 180/360/540 cases for one/two/three repeats;
- 272632/545264/817896 estimated total generation tokens;
- 406/812/1218 estimated provider requests under the documented cold, repeat-scoped cache model;
- a separate optional 24-query, two-routing-mode, 1000-document scale subset: 48 cases and 121 estimated requests.

No pricing configuration or latency assumption was supplied for the earlier
OpenAI E1 estimate. Projected costs are `null` with
`NO_LOCAL_PRICING_CONFIG`; provider runtime is `UNKNOWN`. Anthropic Haiku 4.5
preflight uses only the explicitly supplied preliminary prices, USD 1/MTok
input and USD 5/MTok output, and labels the result as a local estimate rather
than provider-billed usage. The method and commands are in
`E1_ESTIMATE_ONLY_PLAN.md`. No provider call occurred.

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

For a one-case Claude smoke, replace the provider/model flags with:

```powershell
backend_python\.venv_r1a\Scripts\python.exe scripts\run_real_provider_evaluation.py `
  --provider anthropic --allow-network-provider --max-cases 1 `
  --generation-model claude-haiku-4-5-20251001 --embedding-provider openai `
  --embedding-model text-embedding-3-small `
  --max-provider-request-attempts 70 --max-anthropic-estimated-cost 2 `
  --max-provider-output-tokens 1024 --max-provider-retries 1 `
  --query-input <query-input.jsonl> --corpus-fixture <corpus-fixture.json> `
  --gold-annotations <gold-annotations.jsonl> --output <ignored-output> `
  --cache-dir <ignored-cache> --chroma-dir <isolated-chroma> `
  --source-storage-dir <isolated-source-store> --database-url <isolated-eval-url>
```

The network-free full-experiment preflight command shape is:

```powershell
backend_python\.venv_r1a\Scripts\python.exe scripts\run_real_provider_evaluation.py `
  --full-experiment-preflight --provider anthropic --repeats 3 `
  --generation-model claude-haiku-4-5-20251001 --embedding-provider openai `
  --embedding-model text-embedding-3-small
```

It reports the default S1-S6 plan as 42 queries, five modes, three repeats and
630 records, with an Anthropic request upper bound of 1008. Under the current
local character-count Haiku 4.5 estimate, that full plan is above the USD 2
Anthropic cap, so the preflight reports `anthropic_cost_cap_status=EXCEEDS_CAP`.
It also reports
`prepared_corpus_mode_available=false` and
`document_embeddings_reused_without_provider_calls=false`. Full execution
therefore remains disabled: `--confirm-full-experiment` refuses execution
until a prepared-corpus query-only reuse mode exists.

This document is readiness evidence only. It is not provider-run approval, a
dataset/config freeze, or final E1 evidence.

`DO_NOT_RUN_FINAL_E1_YET`
