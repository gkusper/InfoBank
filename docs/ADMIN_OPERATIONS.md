# Administrator operations

Status: `PRE_FREEZE`

## Secrets and environment

Set `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_TTL_SECONDS`, exact
`CORS_ALLOWED_ORIGINS`, `AI_PROVIDER`, `CHROMA_PERSIST_DIR`,
`SOURCE_STORAGE_DIR`, `MAX_UPLOAD_BYTES`, `AGGREGATE_K_THRESHOLD` and optional model/provider names
outside Git. Restrict `.env` permissions, rotate exposed values and never put
secrets in backups or logs. `OPENAI_API_KEY` is required only for an explicitly
authorized provider run. Gmail OAuth state is encrypted, browser-bound and
short-lived. Connector tokens are stored in a versioned Fernet envelope using
`CONNECTOR_TOKEN_ENCRYPTION_KEY`, or a domain-separated key derived from
`JWT_SECRET_KEY` when no dedicated key is configured. Prefer dedicated
`OAUTH_STATE_SECRET` and `CONNECTOR_TOKEN_ENCRYPTION_KEY` values outside local
development. Rotating the effective connector-token key requires Gmail
reconnection; legacy plaintext rows are deliberately refused rather than read.

The isolated operations smoke reads `INFOBANK_SMOKE_DB_PASSWORD` and
`INFOBANK_SMOKE_ADMIN_PASSWORD` from the process environment; values are never
written to tracked documentation or its backup manifest.

## Database, Chroma, source store and audit

MariaDB is authoritative for document identity, chunks, permissions, policy,
evidence and audit metadata. Chroma is a derived vector index. The durable PDF
store is authoritative for retrievable source bytes and must remain
UUID-namespaced. Monitor `/api/test-db`, MariaDB health, document processing
state, source SHA verification, vector/chunk counts, `audit_logs`, and
`/api/health/schema`. Never
repair by manually deleting one store in isolation.

PDF upload accepts only a sanitized `.pdf` filename, a PDF MIME type, a valid
PDF signature and at most `MAX_UPLOAD_BYTES` bytes (25 MiB by default). An
accepted source is committed with `PENDING`, then `PROCESSING`, then `COMPLETE`.
If extraction, embedding or indexing fails after source acceptance, the UUID,
durable source and an owner-visible `FAILED` report/audit record are preserved;
retry through `POST /api/documents/{id}/reindex`. A
`FAILED_REPAIR_REQUIRED` state means automatic vector compensation also failed:
run the documented dry-run consistency scanner before retrying.

Relative `CHROMA_PERSIST_DIR` and `SOURCE_STORAGE_DIR` values are resolved from
the `backend_python/` directory. Each provider/model/dimension combination has
its own deterministic Chroma collection identity. After changing embedding
configuration, rebuild the selected derived index from verified durable source;
do not copy vectors between collections. `AI_EMBEDDING_DIMENSIONS` is optional
and valid only for OpenAI `text-embedding-3-*` models.

Before serving an existing database, run
`backend_python/.venv_r1a/Scripts/python.exe scripts/check_database_schema.py`.
After a verified logical backup, the only supported forward-upgrade command is
`backend_python/.venv_r1a/Scripts/python.exe scripts/apply_database_migrations.py
--expected-database infobank_db --yes`. The command prints only a redacted
target, records migration checksums in `schema_migrations`, preserves existing
row fingerprints, and is safe to rerun. Startup never performs this upgrade.

## Backup, restore, repair and rollback

Use `scripts/run_pre_freeze_operations_smoke.ps1` as the isolated reference. A
backup includes a MariaDB logical dump, Chroma directory, durable source store,
non-secret controlled-failure config, commit/config hashes and checksums. It
excludes `.env`, secrets, Gmail tokens and private data. Restore every component
to separately named targets, then verify UUID, source hash, pages/chunks,
vectors, permission decision, output class, citations and fresh audit logging.

The supported rollback concept is backup-based: back up before a migration,
apply it only to an isolated/test target first, and restore the pre-migration
dump into a second database if rollback is required. No reverse-migration claim
is made. Run the consistency scanner in `DRY_RUN`; apply behavior is allowed
only for fixtures explicitly marked `TASK_OWNED_FIXTURE`. Missing/corrupt source
bytes require a verified backup and are never synthesized or silently deleted.

Operational limitations are documented in `KNOWN_LIMITATIONS.md`; detailed
procedures are in `BACKUP_RESTORE.md` and `REPAIR_AND_ORPHAN_HANDLING.md`.
