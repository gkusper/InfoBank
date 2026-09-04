# Provider portability

## Contract

`backend_python/ai_provider.py` defines `AIProvider` with three operations:

- `extract_keywords` for ingestion keyword extraction and permitted-tag routing;
- `embed` for document and query embeddings;
- `generate` for grounded answers and optional classifier refinement.

`backend_python/ai_service.py` selects the chat/text-generation adapter with
`AI_PROVIDER` and selects the vector adapter with `EMBEDDING_PROVIDER`.
`OPENAI_CHAT_MODEL` selects the OpenAI chat model, `ANTHROPIC_MODEL` selects the
Claude model, and `OPENAI_EMBEDDING_MODEL` selects the OpenAI embedding model.
Legacy `AI_GENERATION_MODEL`, `AI_KEYWORD_MODEL`, and `AI_EMBEDDING_MODEL`
remain as OpenAI-compatible local overrides, but Anthropic mode uses
`ANTHROPIC_MODEL` for query-time keyword selection and answer generation.
Unsupported provider names fail with an explicit configuration error.

## Implementations

| `AI_PROVIDER` | Adapter | Network | Intended use |
|---|---|---:|---|
| `openai` | `OpenAIProvider` | yes | Existing production-compatible runtime behavior |
| `anthropic` | `AnthropicProvider` | yes | Claude chat/text generation with OpenAI embeddings |
| `deterministic-mock` | `DeterministicMockProvider` | no | Automated tests and reproducible development evaluation |
| `local-compatible` | `LocalCompatibleProvider` | no | Provider-neutral/OpenAI-style local contract smoke |

Provider and model manifests include a versioned config hash. Document
processing reports record separate keyword and embedding manifests. Evaluation
runs record LLM provider/model and embedding provider/model identifiers.

The supported production hybrid for Claude is:

```text
LLM provider: anthropic
LLM model: claude-haiku-4-5-20251001
Embedding provider: openai
Embedding model: text-embedding-3-small
```

Do not set `EMBEDDING_PROVIDER=anthropic`. Anthropic is generation-only in this
branch. Existing Chroma vectors and query embeddings remain OpenAI
`text-embedding-3-small`; therefore Claude mode normally still requires
`OPENAI_API_KEY` for query embeddings and `ANTHROPIC_API_KEY` for Claude
generation. Switching only `AI_PROVIDER` does not require re-uploading
documents, PDF extraction, chunking, reindexing, or embedding regeneration.

## Anthropic request mapping

OpenAI-style chat messages are transformed only as required by the Anthropic
Messages API:

- all `system` message text is combined in original order with blank-line
  separators and sent as Anthropic's top-level `system` parameter;
- `user` and `assistant` turns are sent as Anthropic messages in their original
  order;
- OpenAI-style `{"role":"system"}` entries are never forwarded as normal
  Anthropic messages;
- text response blocks are concatenated and empty/non-text responses are
  rejected explicitly;
- OpenAI-only parameters such as `temperature`, `top_p`, `top_k`, and response
  format objects are not sent to Claude by default.

For `claude-haiku-4-5-20251001`, sampling parameters are omitted by default:
no temperature, top-p, top-k, tools, batch API, extended thinking, or structured
response-format parameter is sent. This differs from the OpenAI call path,
which preserves the existing call-site temperature behavior.

## Configuration

```text
AI_PROVIDER=openai|anthropic
OPENAI_CHAT_MODEL=gpt-4o-mini
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY is required in the process environment.
ANTHROPIC_MAX_TOKENS=512
ANTHROPIC_TIMEOUT_SECONDS=60
ANTHROPIC_MAX_RETRIES=1
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`anthropic==1.3.0` is pinned in the backend requirements. Install with:

```powershell
backend_python\.venv_r1a\Scripts\python.exe -m pip install -r backend_python\requirements-dev-lock.txt
```

## Governance invariant

Provider selection occurs after policy resolution. The provider interface accepts text or permitted keyword lists but has no method that can expand `Full`, `Aggregate`, `Metadata`, or `Deny`. `backend_python/tests/test_ai_provider.py` confirms switching between both network-free adapters does not alter the governance decision map, and scans domain modules for direct OpenAI-client use.

Aggregate individual content is not sent through the provider interface. `backend_python/aggregate_executor.py` creates only a thresholded aggregate generator context.

## Migration and smoke commands

Direct OpenAI calls were moved out of `routers/chat.py`, `routers/documents.py`, and `citds_classifier.py`. The compatibility-only `get_openai_client` remains in `ai_service.py` so the OpenAI adapter preserves lazy initialization and the existing missing-key error contract.

```powershell
$env:AI_PROVIDER='deterministic-mock'
$env:EMBEDDING_PROVIDER='deterministic-mock'
backend_python\.venv_r1a\Scripts\python.exe -m pytest -q backend_python\tests\test_ai_provider.py

$env:AI_PROVIDER='local-compatible'
$env:EMBEDDING_PROVIDER='local-compatible'
backend_python\.venv_r1a\Scripts\python.exe -c "import sys; sys.path.insert(0,'backend_python'); import ai_service; print(ai_service.provider_manifest(operation='smoke', model='local-smoke'))"
```

Neither smoke command makes an external request.

Claude runtime smoke uses the existing stored corpus and OpenAI embeddings:

```powershell
$env:AI_PROVIDER='anthropic'
$env:ANTHROPIC_MODEL='claude-haiku-4-5-20251001'
$env:EMBEDDING_PROVIDER='openai'
$env:OPENAI_EMBEDDING_MODEL='text-embedding-3-small'
# Set ANTHROPIC_API_KEY and OPENAI_API_KEY in the process environment before running.
backend_python\.venv_r1a\Scripts\python.exe -m uvicorn main:app --app-dir backend_python --host 127.0.0.1 --port 8000
```

Guarded one-case actual-pipeline smoke:

```powershell
backend_python\.venv_r1a\Scripts\python.exe scripts\run_real_provider_evaluation.py `
  --provider anthropic --allow-network-provider --max-cases 1 `
  --generation-model claude-haiku-4-5-20251001 --embedding-provider openai `
  --embedding-model text-embedding-3-small `
  --max-provider-request-attempts 70 --max-anthropic-estimated-cost 6.0 `
  --max-provider-output-tokens 1024 --max-provider-retries 1 `
  --query-input <query_inputs.jsonl> --corpus-fixture <corpus_fixture.json> `
  --gold-annotations <gold_annotations.jsonl> `
  --database-url <isolated-eval-database-url> `
  --output <task-owned-output-dir> --cache-dir <task-owned-cache-dir> `
  --chroma-dir <task-owned-chroma-dir> --source-storage-dir <task-owned-source-dir>
```

The script only runs a C3 smoke path. Full experiment execution is currently
disabled even when `--confirm-full-experiment` is supplied, because the current
actual-pipeline runner seeds a fresh corpus and Chroma collection. Use
`--full-experiment-preflight` for a network-free 42-case, five-mode,
three-repeat plan and add a prepared-corpus query-only reuse mode before any
full provider run.

## Limitations

The local-compatible adapter validates portability and determinism but is not a
quality claim for a local inference server. Chroma remains the only vector-store
implementation. Anthropic support is cross-generator rather than complete
provider independence because embeddings remain OpenAI. Claude sampling behavior
may differ from the OpenAI temperature-zero setup. Only mocked tests and small
smoke runs are appropriate here; no scientific comparison follows until a
separately authorized cross-generator experiment is run.
