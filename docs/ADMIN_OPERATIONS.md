# Administrator operations

Status: `PRE_FREEZE`

## Secrets and environment

Set `DATABASE_URL`, `JWT_SECRET_KEY`, `AI_PROVIDER`, `CHROMA_PERSIST_DIR`,
`SOURCE_STORAGE_DIR`, `AGGREGATE_K_THRESHOLD` and optional model/provider names
outside Git. Restrict `.env` permissions, rotate exposed values and never put
secrets in backups or logs. `OPENAI_API_KEY` is required only for an explicitly
authorized provider run. Gmail OAuth tokens are currently stored by the local
connector without an implemented application-level encryption guarantee; do
not use it for production credentials until a human security decision and
encrypted token store exist.

The isolated operations smoke reads `INFOBANK_SMOKE_DB_PASSWORD` and
`INFOBANK_SMOKE_ADMIN_PASSWORD` from the process environment; values are never
written to tracked documentation or its backup manifest.

## Database, Chroma, source store and audit

MariaDB is authoritative for document identity, chunks, permissions, policy,
evidence and audit metadata. Chroma is a derived vector index. The durable PDF
store is authoritative for retrievable source bytes and must remain
UUID-namespaced. Monitor `/api/test-db`, MariaDB health, document processing
state, source SHA verification, vector/chunk counts and `audit_logs`. Never
repair by manually deleting one store in isolation.

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
