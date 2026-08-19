# Provider portability

## Contract

`backend_python/ai_provider.py` defines `AIProvider` with three operations:

- `extract_keywords` for ingestion keyword extraction and permitted-tag routing;
- `embed` for document and query embeddings;
- `generate` for grounded answers and optional classifier refinement.

`backend_python/ai_service.py` selects the adapter with `AI_PROVIDER` and keeps the public API contract independent of the adapter. `AI_GENERATION_MODEL`, `AI_KEYWORD_MODEL`, and `AI_EMBEDDING_MODEL` select model identifiers. Unsupported provider names fail with an explicit configuration error.

## Implementations

| `AI_PROVIDER` | Adapter | Network | Intended use |
|---|---|---:|---|
| `openai` | `OpenAIProvider` | yes | Existing production-compatible runtime behavior |
| `deterministic-mock` | `DeterministicMockProvider` | no | Automated tests and reproducible development evaluation |
| `local-compatible` | `LocalCompatibleProvider` | no | Provider-neutral/OpenAI-style local contract smoke |

Provider and model manifests include a versioned config hash. Document processing reports record separate keyword and embedding manifests. Evaluation runs record the deterministic provider/model identifiers.

## Governance invariant

Provider selection occurs after policy resolution. The provider interface accepts text or permitted keyword lists but has no method that can expand `Full`, `Aggregate`, `Metadata`, or `Deny`. `backend_python/tests/test_ai_provider.py` confirms switching between both network-free adapters does not alter the governance decision map, and scans domain modules for direct OpenAI-client use.

Aggregate individual content is not sent through the provider interface. `backend_python/aggregate_executor.py` creates only a thresholded aggregate generator context.

## Migration and smoke commands

Direct OpenAI calls were moved out of `routers/chat.py`, `routers/documents.py`, and `citds_classifier.py`. The compatibility-only `get_openai_client` remains in `ai_service.py` so the OpenAI adapter preserves lazy initialization and the existing missing-key error contract.

```powershell
$env:AI_PROVIDER='deterministic-mock'
backend_python\.venv_r1a\Scripts\python.exe -m pytest -q backend_python\tests\test_ai_provider.py

$env:AI_PROVIDER='local-compatible'
backend_python\.venv_r1a\Scripts\python.exe -c "import sys; sys.path.insert(0,'backend_python'); import ai_service; print(ai_service.provider_manifest(operation='smoke', model='local-smoke'))"
```

Neither smoke command makes an external request.

## Limitations

The local-compatible adapter validates portability and determinism but is not a quality claim for a local inference server. Chroma remains the only vector-store implementation. Provider cost accounting and retries are D-GATE work.
