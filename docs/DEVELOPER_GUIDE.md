# Developer guide

Status: `PRE_FREEZE`

## Architecture and module map

The browser frontend in `frontend/` calls FastAPI routers in
`backend_python/routers/`. SQLAlchemy models persist identities, policy,
provenance, evidence and audit rows in MariaDB. `document_processing.py`
performs page-aware PDF extraction/chunking; `source_storage.py` performs
UUID-namespaced atomic source writes and hash verification. `ai_service.py`
owns the Chroma `infobank_vectors` collection and delegates embedding,
keyword extraction and generation to `ai_provider.py`.

`policy_engine.py` resolves Owner/Reader/Aggregate/Metadata and scoped
Full/Aggregate/Metadata/Deny rules before routing. `routers/chat.py` applies the
query profile, routing, retrieval, evidence check and controlled-failure gate.
`controlled_failure.py` and `config/controlled_failure_v3.json` define the
versioned output/reason vocabulary. Evidence classification, action
reconstruction and aggregate execution are in `evidence_service.py`,
`action_closure.py` and `aggregate_executor.py`.

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

`infobank_db.sql` is the clean schema. Existing MariaDB databases use
`backend_python/migrations/citds_11_mysql.sql` and
`infocom_a_gate_phase1_mysql.sql`; migrations are forward/idempotent helpers,
not automatic reverse migrations. A document UUID joins DB rows, Chroma
metadata, source namespace and citations. No distributed transaction spans
MariaDB, Chroma and the filesystem, so compensation, audit and orphan scanning
are required. Never remove a source/vector before the DB operation can be compensated.

## Provider and evaluation discipline

`AI_PROVIDER=deterministic-mock` is offline and used by tests/development.
Provider-backed evaluation is explicit, estimate-first and separately sealed.
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
```

Work on focused feature commits, run targeted tests and `git diff --check`,
stage explicit paths, scan staged content, and push only the named feature
branch after authorization. Do not rewrite history or commit runtime artifacts,
credentials, local paths, raw MailEx, raw E1, databases, vectors or screenshots.
