# InfoBank

InfoBank is a governed, citation-bearing document assistant and evidence/action
prototype. This branch is a pre-freeze technical workstream, not a release.

## Local quick start

Supported runtime: Python 3.11 or 3.12. The canonical local environment is
`backend_python\.venv_r1a`. Docker Desktop with Docker Compose and MariaDB is
required for the integrated Docker runtime.

```powershell
docker compose up -d db
py -3.11 -m venv backend_python\.venv_r1a
backend_python\.venv_r1a\Scripts\python.exe -m pip install -r backend_python\requirements-dev-lock.txt
Copy-Item backend_python\.env.example backend_python\.env
backend_python\.venv_r1a\Scripts\python.exe scripts\check_database_schema.py
backend_python\.venv_r1a\Scripts\python.exe scripts\apply_database_migrations.py --expected-database infobank_db --yes
backend_python\.venv_r1a\Scripts\python.exe -m uvicorn main:app --app-dir backend_python --host 127.0.0.1 --port 8000
```

In another terminal, serve the frontend with `python -m http.server 8765` and
open `http://127.0.0.1:8765/frontend/`. Required environment-variable names are
`DATABASE_URL`, `JWT_SECRET_KEY`, `AI_PROVIDER`, `EMBEDDING_PROVIDER`,
`CHROMA_PERSIST_DIR`, `SOURCE_STORAGE_DIR`, and `AGGREGATE_K_THRESHOLD`.
Provider-backed operation also needs provider-specific model names and API
keys; never commit values or a real `.env`. The deterministic provider needs no
network key.

OpenAI remains the default LLM provider:

```powershell
$env:AI_PROVIDER='openai'
$env:OPENAI_CHAT_MODEL='gpt-4o-mini'
$env:EMBEDDING_PROVIDER='openai'
$env:OPENAI_EMBEDDING_MODEL='text-embedding-3-small'
backend_python\.venv_r1a\Scripts\python.exe -m uvicorn main:app --app-dir backend_python --host 127.0.0.1 --port 8000
```

Claude can be selected for chat/text generation only:

```powershell
$env:AI_PROVIDER='anthropic'
$env:ANTHROPIC_API_KEY='<secret>'
$env:ANTHROPIC_MODEL='claude-sonnet-5'
$env:EMBEDDING_PROVIDER='openai'
$env:OPENAI_EMBEDDING_MODEL='text-embedding-3-small'
backend_python\.venv_r1a\Scripts\python.exe -m uvicorn main:app --app-dir backend_python --host 127.0.0.1 --port 8000
```

Anthropic mode is a hybrid configuration: query routing keyword selection and
final answer generation use Claude, while document and query embeddings remain
OpenAI `text-embedding-3-small` for compatibility with the existing Chroma
vectors. Switching only `AI_PROVIDER` does not require PDF extraction,
chunking, re-upload, reindexing, or embedding regeneration. Switch back by
setting `AI_PROVIDER=openai`.

For Gmail OAuth, set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and the redirect
URI. Dedicated `OAUTH_STATE_SECRET` and `CONNECTOR_TOKEN_ENCRYPTION_KEY` values
are recommended; changing the effective token-encryption key requires Gmail
reconnection, and legacy plaintext token rows are intentionally rejected.

Relative `CHROMA_PERSIST_DIR` and `SOURCE_STORAGE_DIR` values are resolved from
`backend_python/`, not from the shell's current directory. Chroma collections
are isolated by embedding provider, embedding model and vector dimension.
Changing any embedding setting selects a separate derived index; re-upload or
re-index documents from their durable source before expecting them in the new
index.

Back up an existing development database before the explicit migration
command. Startup never upgrades a database automatically. If the schema is
outdated, normal API operations return a generic
`DATABASE_MIGRATION_REQUIRED` response while `/docs`, `/openapi.json`, and
`/api/health/schema` remain available.

## Deterministic demos and quality gates

```powershell
# One-command start after the one-time venv/.env setup:
powershell -NoProfile -Command "docker compose up -d db; & backend_python\.venv_r1a\Scripts\python.exe -m uvicorn main:app --app-dir backend_python --host 127.0.0.1 --port 8000"
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_api_end_to_end_workflows.py --help
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1 -SkipDocker
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_normal_runtime_smoke.ps1
```

The API workflow command requires an isolated database whose name starts with
`infobank_eval_`, plus task-owned Chroma, source-store, and output directories;
the exact reproducible command is in `docs/REPRODUCTION.md`.

For a guarded one-case Claude actual-pipeline smoke, use
`scripts\run_real_provider_evaluation.py` with `--provider anthropic`,
`--allow-network-provider`, `--max-cases 1`, and explicit task-owned output,
cache, Chroma, source-storage, query, corpus, and gold paths. The full
cross-generator S1-S6 experiment has intentionally not been run by this branch.

`main` is the protected integration/release baseline. The current
`feature/infocom-cd-gates` branch contains reviewer and evaluation hardening and
must be reviewed before integration. Final E1, dataset/code/config freeze,
release branch, merge, tag, pull request, and release are **not authorized**.

See `docs/USER_MANUAL.md`, `docs/DEVELOPER_GUIDE.md`,
`docs/ADMIN_OPERATIONS.md`, and `docs/DATASET_AND_EVALUATION.md`. Project code
is under the repository `LICENSE`; the local MailEx source has the separate
state `LICENCE_PENDING_HUMAN_CONFIRMATION` and is not authorized for
redistribution.
