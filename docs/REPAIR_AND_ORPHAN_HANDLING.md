# Repair and orphan handling

Status: `DRY_RUN_DEFAULT`

`evaluation/orphan_repair.py` scans DB documents with missing source, source
directories without DB documents, chunks without documents, vectors without
documents/chunks, DB chunks without vectors, archived documents with active
vectors, deleted documents with staged source pending purge, source SHA
mismatch, and cross-document citation/chunk mismatch.

Scanning never changes a store. The apply API rejects external/unknown scope
and operates only on objects explicitly marked `TASK_OWNED_FIXTURE`. Supported
fixture repairs deactivate/quarantine orphan vectors, quarantine source/chunk
records, recreate a missing derived vector, deactivate archived vectors and
invalidate a mismatched citation link. Source loss/SHA mismatch requires manual
verified-backup restoration; staged-source purge remains explicit. Nothing is
silently deleted. Every proposed/applied action is UUID/object scoped and logged.

```powershell
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_orphan_fixture_smoke.py `
  --output .\artifacts\pre_freeze\orphan-fixture-report.json
```

The fixture smoke asserts dry-run zero mutation, controlled repair,
idempotence and `production_data_touched=false`. For a real incident: preserve
all stores, take a backup, run dry-run, review identifiers/hashes, approve a
bounded repair, retain the compensation record, then repeat the integrity and
API query checks.
