# A-GATE Phase A1 Technical Report

## Identification

- Date: 2026-08-19
- Branch: `feature/infocom-a-gate`
- Starting HEAD: `077c85c44f570c6a6b3f15edcd584f834f335ea1`
- Phase: A1 — core ingestion, provenance, durable source, re-index, and citation
- Result: **PASS_WITH_LIMITATIONS**

No commit or push was performed. A-GATE Phase A2 is not complete.

All eight capability groups defined for A-GATE Phase A1 were implemented and tested. This wording refers to the Phase A1 capability groups in this work package, not to similarly numbered tasks elsewhere in the Review A roadmap.

## Exact changed files

Modified:

- `.gitignore`
- `backend_python/.env.example`
- `backend_python/models.py`
- `backend_python/policy_engine.py`
- `backend_python/routers/chat.py`
- `backend_python/routers/documents.py`
- `backend_python/tests/conftest.py`
- `docs/integration/IMPLEMENTATION_SCOPE.csv`
- `infobank_db.sql`

Created:

- `backend_python/document_processing.py`
- `backend_python/source_storage.py`
- `backend_python/migrations/infocom_a_gate_phase1_mysql.sql`
- `backend_python/tests/test_a_gate_schema_contract.py`
- `backend_python/tests/test_citations.py`
- `backend_python/tests/test_document_processing.py`
- `backend_python/tests/test_reindexing.py`
- `backend_python/tests/test_source_storage.py`
- `docs/integration/A_GATE_PHASE1_GAP_ANALYSIS.md`
- `docs/integration/METADATA_PIPELINE.md`
- `docs/integration/CHUNKING_CONFIG.md`
- `docs/integration/A_GATE_PHASE1_REPORT.md`
- `scripts/generate_a_gate_owned_object_demo.py`

## Architecture and compatibility

`document_processing.py` is a deterministic provider-neutral processing core for configuration hashing, PyMuPDF page extraction, within-page chunks, keyword normalization/fallback, hashes, and statistics. `source_storage.py` owns UUID path validation, atomic writes, integrity reads, and compensated deletion staging. Database/Chroma orchestration remains in the documents router.

Existing upload fields (`status`, `keywords`, `document_id`, `visibility`) and document-list fields remain. The legacy `Document.file_path` is retained as a compatibility filename field and is never used as a durable filesystem path. `ai_service.chunk_text` remains unchanged for non-ingestion callers.

## Schema and migration

Document rows now record the safe stored relative path, exact source SHA-256, MIME type, byte size, page count, lifecycle/processing status, config version/hash, optional URL/licence, PDF metadata, and archive/update timestamps. Document chunks now record page/block/offset, source/content hashes, and config identity. Keyword relations carry provenance and user-edit state. New tables persist field-level metadata provenance and processing reports.

Migration evidence:

- Existing `infobank_db`: migration run 1 PASS.
- Existing `infobank_db`: migration rerun PASS.
- Existing schema: 6 required document trace columns, 7 chunk trace columns, 2 A1 tables.
- Clean audit database: `infobank_a1_audit_clean_20260819`.
- Representative legacy audit database: `infobank_a1_audit_legacy_20260819`, containing a synthetic user, document, permission, keyword relation, and legacy chunk; all five records survived migration.
- Clean schema: 4/4 required tables, 6 document trace columns, 7 chunk trace columns.
- Migration rerun: PASS; both new document indexes exist on clean and upgraded schemas.
- No database or Docker volume was deleted.

## Endpoint changes

| Method and path | Authorization | Behavior |
|---|---|---|
| `POST /api/upload` | Authenticated | Atomic source save, extraction, provenance, deterministic fallback, indexing, report |
| `POST /api/documents/{id}/metadata` | Owner | Update editable metadata with USER provenance |
| `POST /api/documents/update-keywords` | Owner | Replace editable keyword set with USER provenance |
| `POST /api/documents/{id}/reindex` | Owner | Verify source hash and deterministically replace chunks/vectors |
| `POST /api/documents/{id}/archive` | Owner | Remove active chunks/vectors and retain source |
| `POST /api/documents/{id}/restore` | Owner | Verify source and idempotently re-index archived document |
| `GET /api/documents/{id}/source` | Policy-controlled | Owner/Reader raw source or page; Metadata metadata only; Aggregate denied; Deny hidden |
| `GET /api/documents/{id}/processing-report` | Owner | Latest processing report as JSON or CSV |

`POST /api/ask` sources retain existing fields and add a structured citation for Full sources. Citations contain no local path.

## Durable-source and lifecycle behavior

- Save: exact bytes are atomically moved from a temporary file into `<UUID>/source.pdf` under `SOURCE_STORAGE_DIR`.
- Integrity: source SHA-256 and byte count derive from exact bytes and are verified before re-index/restore/view.
- Archive: durable source remains; vectors and DB chunks are removed; policy denies retrieval.
- Restore: source integrity is verified and the deterministic index is rebuilt; repeated restore when active is a no-op success.
- Permanent delete: current vectors are snapshotted, vector cleanup succeeds before the source directory is staged, and database cleanup commits before staged source purge. Failure before commit restores both vectors and staged source. A post-commit purge failure returns explicit `PENDING` source-cleanup state; UUID-scoped staged cleanup is repairable without exposing a local path.
- Runtime source and demo directories are ignored and absent from the tracked file set.

## Processing and provenance

Defaults remain 1000 characters with 200 overlap, but chunks never cross pages. Every chunk has stable UUIDv5 identity, one-based page, page-relative offsets, content/source SHA-256, and config version/hash. Chroma metadata includes all citation identifiers.

Metadata provenance covers 16 stored document metadata fields. Derived report metrics, intrinsic IDs, permission relations, and policy decisions have explicit named system provenance rather than metadata-provenance rows. Keywords retain distinct AI/RULE/USER provenance entries. Missing provider configuration uses deterministic fallback without a call; a configured provider/API failure is caught after an attempted call; malformed output is also caught and falls back. Explicit user metadata and keywords survive re-index.

Processing reports record pages, empty pages, extracted characters, keyword counts by provenance, chunk count/length distribution, duplicate count, models/methods/config, duration, warnings, and failed stages.

## Tests and validation

| Check | Result | Evidence |
|---|---|---|
| Previous R1 tests | PASS | 35 retained tests |
| Original A1 tests | PASS | 32 focused tests |
| New pre-commit audit tests | PASS | 24 failure-injection/security/consistency cases |
| Total pytest | PASS | 91 passed, 0 failed, 0 skipped; 43 non-blocking warnings |
| Config/page/chunk/hash | PASS | Generated PDF and pure page tests |
| Durable source/path traversal | PASS | Atomic roundtrip, traversal, staged restore/purge |
| Keyword fallback/provenance | PASS | Provider failure and duplicate provenance tests |
| Re-index idempotence | PASS | Stable IDs/hashes/count; changed config replacement; mismatch stop |
| Archive/restore/delete | PASS | Source survival, idempotence, compensation, owner enforcement |
| Cross-store failure injection | PASS | Partial vector add, embedding/report/commit/staging/purge failures restore or expose tested repair state |
| Citation/source authorization | PASS | Page/chunk correctness and Owner/Reader/Metadata/Aggregate/Deny matrix |
| Schema contract | PASS | Clean schema and idempotent migration assertions |
| Synthetic owned-object workflow | PASS | Two runs produced identical manifest and SHA-256 values |
| SkipDocker quality gate | PASS | `PASS_WITH_PENDING_DOCKER_SMOKE`, 91/0/0 |
| Full quality gate | PASS | 20.225 s, 91/0/0, all steps exit 0 |
| MariaDB/API smoke | PASS | healthy, DB success with 0 users, docs/OpenAPI 200, volume retained |

Commands:

```powershell
backend_python\.venv_r1a\Scripts\python.exe -m pytest backend_python/tests evaluation/tests -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1 -SkipDocker
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1
backend_python\.venv_r1a\Scripts\python.exe scripts\generate_a_gate_owned_object_demo.py
```

## Warnings and limitations

- PyMuPDF SWIG and Starlette multipart dependency warnings are non-blocking.
- Existing naïve UTC defaults and policy time capture emit deprecation warnings.
- Chroma emits two known telemetry warnings during import.
- MariaDB and Chroma do not share a transaction; cross-store replacement uses deterministic IDs and ordered best-effort cleanup rather than distributed transactions.
- Vector snapshots and staged source moves compensate tested operation/commit failures, but there is no general cross-store orphan detector. The repair helper is limited to UUID-scoped staged-source cleanup.
- The existing SQL-only `UNIQUE(user_id, document_id)` constraint still has no matching SQLAlchemy `UniqueConstraint`; this inherited schema-hardening follow-up was not widened in A1.
- Durable storage is a configurable local filesystem backend; object-store deployment is future work.
- OCR, semantic chunk boundary optimization, and full PDF block mapping are not included.
- Citation API is implemented, but the current frontend does not yet render all citation fields.
- No full routing ablation, hard-negative retrieval study, final W1/W2 scripted demonstration, final reviewer dataset v2, provider adapter, or B0–B3 evaluation is included.

No research dataset, fixture, frozen result, publication artifact, personal data, real provider call, health-related scenario, or reviewer-response prose was added or modified.

## Phase A2 boundary

A-GATE Phase A2 must still cover graph/routing scope, hard-negative retrieval, the final W1/W2 scripted demonstration, and reviewer artifact polish. Phase A1 makes no scientific result claim.
