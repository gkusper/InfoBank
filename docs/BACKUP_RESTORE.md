# Backup and restore

Status: `ISOLATED_SMOKE_AUTOMATED`

Run only against task-owned `infobank_eval_` databases and new artifact
directories:

```powershell
$env:INFOBANK_SMOKE_DB_PASSWORD = '<local-compose-user-password>'
$env:INFOBANK_SMOKE_ADMIN_PASSWORD = '<local-compose-admin-password>'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pre_freeze_operations_smoke.ps1 `
  -OutputRoot .\artifacts\pre_freeze\operations-smoke
```

The command runs W1/W2/W3 to create a deterministic user, PDFs, chunks,
policies, queries and audit rows; uses the MariaDB container's `mariadb-dump`;
copies Chroma, durable sources and non-secret controlled-failure config; restores
into separately named DB/Chroma/source targets; and reruns the grounded W2 query.
The verification compares document UUID/SHA/page counts, chunk/vector IDs,
permissions and source hashes, validates document/page/chunk citations, and
requires a new audit ID.

The backup excludes `.env`, secret values, Gmail tokens and non-fixture user
data. `backup_manifest.json`, logical dumps, copied stores and verification
records are ignored runtime artifacts. Check their SHA-256 values before and
after transfer. Failure at any verification step invalidates the restore.

Rollback smoke takes a logical dump before applying forward migrations to an
isolated baseline, restores that dump into a second isolated database and reads
the fixture row. This is `BACKUP_BASED_NOT_REVERSE_MIGRATION`; it never
destructively downgrades an existing database and deletes no Docker volume.
