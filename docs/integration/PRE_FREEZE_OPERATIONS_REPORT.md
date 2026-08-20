# Pre-freeze operations report

Status: `PASS`

The automated smoke is implemented in
`scripts/run_pre_freeze_operations_smoke.ps1`. It creates only explicitly named
`infobank_eval_prefreeze_ops_*` databases and new ignored artifact directories.
Backup-manifest names are relativized against a resolved backup root, so a
repository path containing a `.` segment cannot truncate a filename.
It runs the actual W1/W2/W3 API workflow, creates a MariaDB logical dump, copies
Chroma/source/config backup scope, restores every store separately, reruns the
grounded W2 query, validates citations/audit and compares identities/hashes.

It also demonstrates backup-before-migration and restore-to-second-database
rollback, then runs dry-run and controlled/idempotent repair only on
`TASK_OWNED_FIXTURE` objects. It never deletes a Docker volume, contacts a
provider, reads a real `.env`, or mutates a production/user database. Runtime
results and backup payloads remain ignored.

The successful local run produced a 14-file backup manifest, six durable source
files, six documents/chunks/vectors and six permission relations. Source and
restored cross-store scans both found zero issues. The final source and restored
query both returned `CONSTRAINED_ANSWER` because the completed W2 state contains
the conflict source; output class was unchanged, both runtimes returned two
valid citations and fresh audit IDs, and `/api/test-db`, `/docs` and
`/openapi.json` returned 200. Backup-based rollback restored and read the
baseline fixture. Fixture repair applied three bounded repairs; its second apply
made zero changes. Non-blocking Chroma telemetry compatibility warnings were
observed; no telemetry/provider network call occurred.
