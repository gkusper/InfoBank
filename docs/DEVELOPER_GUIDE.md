# Developer guide

Status: `PRE_FREEZE`

## Architecture and module map

The browser frontend in `frontend/` calls FastAPI routers in
`backend_python/routers/`. SQLAlchemy models persist identities, policy,
provenance, evidence and audit rows in MariaDB. `document_processing.py`
performs page-aware PDF extraction/chunking; `source_storage.py` performs
UUID-namespaced atomic source writes and hash verification. `ai_service.py`
owns an embedding-provider/model/dimension-specific Chroma collection and
delegates embedding, keyword extraction and generation to `ai_provider.py`.

`policy_engine.py` resolves Owner/Reader/Aggregate/Metadata and scoped
Full/Aggregate/Metadata/Deny rules before routing. `routers/chat.py` applies the
query profile, routing, retrieval, evidence check and controlled-failure gate.
`controlled_failure.py` and `config/controlled_failure_v3.json` define the
versioned output/reason vocabulary. Evidence classification, action
reconstruction and aggregate execution are in `evidence_service.py`,
`action_closure.py` and `aggregate_executor.py`. Runtime action reconstruction
and the evaluation engine share the versioned `OPEN`, `CLOSED_COMPLETED`,
`CLOSED_CANCELLED`, and `SUPERSEDED` state resolver.

`gmail_connector.py` encrypts and expires OAuth state, binds it to an HttpOnly
SameSite callback cookie, and encrypts connector credentials before database
persistence. Plaintext legacy connector rows are not accepted. The optional
`OAUTH_STATE_SECRET` and `CONNECTOR_TOKEN_ENCRYPTION_KEY` settings provide key
separation; otherwise domain-separated keys are derived from `JWT_SECRET_KEY`.
This is locally contract-tested but is not evidence of a completed real Google
OAuth/provider run.

Evaluation packages live in `evaluation/`: A/C/D gates, owned-object and MailEx
candidate builders, actual-pipeline inputs/gold/runner/scorer, API workflows,
provider readiness, reconciliation, human QA and pre-freeze operations.
Generated outputs belong under ignored `artifacts/` paths.

## Endpoint map

- auth/profile: `/api/register`, `/api/login`, `/api/profile/me`;
- documents: `/api/upload`, `/api/documents/me`, keyword/metadata update, re-index/archive/restore/delete, processing report and authorized source page;
- assistant: `/api/ask`;
- policy: document permission grant/revoke, ownership transfer, `/api/policy/rules`, and effective resolution;
- evidence/connectors: import/classify/action-list and local self-test;
- diagnostics: `/api/test-db`, `/docs`, `/openapi.json`.

## Schema, migration and storage rules

`infobank_db.sql` is the clean schema. Existing MariaDB databases use the
explicit, rerunnable command
`backend_python/.venv_r1a/Scripts/python.exe scripts/apply_database_migrations.py
--expected-database infobank_db --yes` after a verified backup.
`scripts/check_database_schema.py` compares the active schema with the current
SQLAlchemy model and migration checksums. Startup does not migrate; it blocks
normal API operations on an incompatible schema while retaining safe schema
health and API documentation. A document UUID joins DB rows, Chroma
metadata, source namespace and citations. No distributed transaction spans
MariaDB, Chroma and the filesystem, so compensation, audit and orphan scanning
are required. Never remove a source/vector before the DB operation can be compensated.

Upload validation is bounded by `MAX_UPLOAD_BYTES` and checks sanitized PDF
extension, MIME and signature before persistence. Once accepted, the document
has durable processing state; a failed attempt retains its source and UUID for
the existing owner-only re-index endpoint. Processing remains synchronous in
the API worker rather than a distributed queue.

Relative Chroma and source-store paths are anchored to `backend_python/`, so
starting Uvicorn from the repository root or from `backend_python/` reaches the
same state. The collection identity contains the canonical embedding provider,
embedding model, expected dimension and a configuration hash. An embedding
provider/model/dimension change deliberately selects a new collection instead
of mixing incompatible vectors. Switching only `AI_PROVIDER` between OpenAI and
Anthropic does not reprocess documents because embeddings remain
`EMBEDDING_PROVIDER=openai`. `ai_service.vector_store_manifest()` exposes the
non-secret resolved path and identity for diagnostics.

## Provider and evaluation discipline

`AI_PROVIDER=deterministic-mock` is offline and used by tests/development.
`AI_PROVIDER=anthropic` selects Claude for query-time keyword selection and
answer generation only; OpenAI `text-embedding-3-small` remains the production
embedding path. Provider-backed evaluation is explicit, estimate-first and
separately sealed.
Runtime inputs are `QueryInput`; held-out expectations are `GoldAnnotation` and
must not be imported by the runner. Raw runs are sealed before scoring. Do not
tune on candidate holdout or the frozen D1-D8 benchmark.

## Development commands and branch workflow

```powershell
py -3.11 -m venv backend_python\.venv_r1a
backend_python\.venv_r1a\Scripts\python.exe -m pip install -r backend_python\requirements-dev-lock.txt
backend_python\.venv_r1a\Scripts\python.exe -m pytest backend_python\tests evaluation\tests -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1 -SkipDocker
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_normal_runtime_smoke.ps1
```

Work on focused feature commits, run targeted tests and `git diff --check`,
stage explicit paths, scan staged content, and push only the named feature
branch after authorization. Do not rewrite history or commit runtime artifacts,
credentials, local paths, raw MailEx, raw E1, databases, vectors or screenshots.
