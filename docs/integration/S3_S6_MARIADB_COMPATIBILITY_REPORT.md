# S3-S6 MariaDB Compatibility Report

## 1. Preserved starting state

- Branch: `infocom2026`
- HEAD: `0b72faf194f202f4d5631344978003c17d084096`
- origin SHA: `0b72faf194f202f4d5631344978003c17d084096`
- Ahead/behind: `0/0`
- Tracked working-tree diff hash: `ddea9de6df43a02144f08faccf220c1fa0116279b27002157e7067ccdccdbfca`
- Preflight patch: `artifacts/s3_s6_candidate_integration/mariadb_preflight_working_tree.patch`
- Preflight patch SHA-256: `ddea9de6df43a02144f08faccf220c1fa0116279b27002157e7067ccdccdbfca`
- Pre-existing untracked runtime/temp directories: see `MARIADB_PREFLIGHT_CODE_STATE.json`; failed MariaDB smoke attempts were preserved separately.

## 2. MariaDB environment

- Compose service: `db`
- Container: `infobank-mariadb`
- Health: `healthy`
- MariaDB version: `11.4.12-MariaDB-ubu2404`
- Host: `127.0.0.1`
- Port: `3307`
- Administrative access status: `OK`
- Password exposure: `NO`
- Docker CLI note: health inspect was blocked by the Codex sandbox; direct MariaDB TCP/admin validation passed.

## 3. Isolated evaluation databases

| Purpose | Configuration | Database | Schema status |
| --- | --- | --- | --- |
| focused | C2 | infobank_eval_s3s6_mariadb_focus_c2_20260831173131 | COMPATIBLE |
| focused | C3 | infobank_eval_s3s6_mariadb_focus_c3_20260831173131 | COMPATIBLE |
| full | C0 | infobank_eval_s3s6_mariadb_full_c0_20260831173131 | COMPATIBLE |
| full | C1 | infobank_eval_s3s6_mariadb_full_c1_20260831173131 | COMPATIBLE |
| full | C2 | infobank_eval_s3s6_mariadb_full_c2_20260831173131 | COMPATIBLE |
| full | C3 | infobank_eval_s3s6_mariadb_full_c3_20260831173131 | COMPATIBLE |

Every database name starts with `infobank_eval_`: `TRUE`.

## 4. Schema validation

- Migration mechanism: `backend_python.database_schema.apply_database_migrations`
- Migration identifiers: `001_citds_11, 002_infocom_a_gate_phase1`
- Table count: `13` per isolated DB
- Schema compatibility: `COMPATIBLE`
- Failures: none

MARIADB_SCHEMA_STATUS: COMPATIBLE

## 5. Focused MariaDB Aggregate validation

12-row artifact: `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/focused_mariadb_assessment.json`

FOCUSED_MARIADB_RECORD_COUNT: 12
AGGREGATE_ONLY_CLASS_MISMATCH_COUNT: 0
AGGREGATE_PUBLIC_CITATION_COUNT: 0
AGGREGATE_PROHIBITED_EXPOSURE_COUNT: 0
FOCUSED_MARIADB_RUNTIME_ERROR_COUNT: 0

## 6. S4B-Q6 threshold verification

- `C2_PERMISSION_FILTERED`: k=`3`, contributor count=`2`, class=`REFUSE_AGGREGATION_THRESHOLD`, reason=`aggregation_threshold_not_met`, total withheld=`YES`, contributor count withheld=`YES`, citations withheld=`YES`
- `C3_FULL_ROLE_AWARE`: k=`3`, contributor count=`2`, class=`REFUSE_AGGREGATION_THRESHOLD`, reason=`aggregation_threshold_not_met`, total withheld=`YES`, contributor count withheld=`YES`, citations withheld=`YES`

C2 = REFUSE_AGGREGATION_THRESHOLD
C3 = REFUSE_AGGREGATION_THRESHOLD

## 7. S3-Q9 reissue verification

- `C2_PERMISSION_FILTERED`: raw representations=`3`, unique contributors=`2`, deduplication key=`relation_key/object_id contributor key`, k=`2`, class=`AGGREGATE_RESULT`, duplicate contribution status=`NO`
- `C3_FULL_ROLE_AWARE`: raw representations=`3`, unique contributors=`2`, deduplication key=`relation_key/object_id contributor key`, k=`2`, class=`AGGREGATE_RESULT`, duplicate contribution status=`NO`

DUPLICATE_REISSUE_CONTRIBUTION: NO

## 8. Focused SQLite--MariaDB equivalence

- Compared records: `12`
- Ignored metadata fields: database identity, timestamps, run_id, audit_id, timing values, local paths, seal hashes.
- Substantive difference count: `0`

FOCUSED_BACKEND_SEMANTIC_DIFFERENCE_COUNT: 0

## 9. Full MariaDB C0--C3 compatibility run

DETERMINISTIC DEVELOPMENT COMPATIBILITY EVALUATION — MARIA DB BACKEND — NOT FINAL REAL-PROVIDER PERFORMANCE

- Planned/executed records: `120/120`
- Records per configuration: `{'C0': 30, 'C1': 30, 'C2': 30, 'C3': 30}`
- PDF ingest: `31/31` per isolated corpus load (`all_pdf_ingest_31_of_31=True`)
- Ingestion failures: `0`
- Runtime errors: `0`
- Parser errors: `0`
- Provider errors: `0`
- Aggregate diagnostics: class mismatches `0`, public citations `0`, prohibited exposure `0`
- Safety diagnostics: `{'C0': 3, 'C1': 3, 'C2': 0, 'C3': 0}`
- Citation diagnostics: substantively equivalent to SQLite after canonicalization.
- Full artifact: `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/full_mariadb_public_summary.json`

## 10. Full SQLite--MariaDB equivalence

FULL_BACKEND_COMPARED_RECORD_COUNT: 120
FULL_BACKEND_SEMANTIC_DIFFERENCE_COUNT: 0
FULL_BACKEND_MISSING_RECORD_COUNT: 0
FULL_BACKEND_EXTRA_RECORD_COUNT: 0

Ignored metadata fields: database identity, timestamps, run IDs, audit IDs, timing values, local paths, raw/seal hashes.

## 11. Isolation validation

NORMAL_DATABASE_CHANGED: NO
CROSS_CONFIGURATION_DATABASE_CONTAMINATION: NO
NORMAL_CHROMA_CHANGED: NO
NORMAL_SOURCE_STORAGE_CHANGED: NO

## 12. S1--S2 preservation

S1_S2_CHANGED: NO

Pre-existing checksum warning: not repaired in this task.

## 13. Validation

- Focused tests: `16 passed, 6 warnings in 9.08s`
- Full tests: `337 passed, 75 warnings in 70.29s (0:01:10)`
- Failures: `0`
- Skips: `0`
- Diff check: `PASS_WITH_CRLF_WARNINGS_ONLY`
- Quality gate: `PASS_WITH_PENDING_DOCKER_SMOKE`
- Docker/MariaDB smoke result: `PASS_WITH_DIRECT_MARIADB_CONNECTION; DOCKER_CLI_HEALTH_INSPECT_BLOCKED_BY_CODEX_SANDBOX`

## 14. Mutation and provider check

SOURCE_CODE_CHANGED_IN_THIS_TASK: NO
TEST_CODE_CHANGED_IN_THIS_TASK: NO
AUTHOR_DECISIONS_CHANGED: NO
REFERENCE_OUTPUT_CLASSES_CHANGED: NO
REFERENCE_ANSWERS_CHANGED: NO
REFERENCE_ANNOTATIONS_CHANGED: NO
S1_S2_CHANGED: NO
EXTERNAL_PROVIDER_CALLS: 0
FINAL_BENCHMARK_FREEZE_PERFORMED: NO
MANUSCRIPT_CHANGED: NO
COMMIT_CREATED: NO
PUSH_PERFORMED: NO

## 15. Generated artifacts

- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/database_row_counts.json`: `919562442af306038a9360945a6ddf9d406b36e143070574b678593f9bf2a359`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/focused/raw_records_mariadb_combined.jsonl`: `14e4dce53e2b9bf059b3eb7c5dd930aad03de9f416622689bdc5047566dfc301`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/focused_mariadb_assessment.json`: `16ff7e0a03e01a6a216586c322bdf1103845bb29b68d8ea7540b0f40603e61f8`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/focused_sqlite_vs_mariadb.json`: `0e696eb447f07fa760152d0e2d0f05ececafaf051b4e94ce7a73eeca2dd393b8`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/focused_tests.log`: `f48abde3c56d55e9689e51c20467a0547519e82799e6bd7bb144a690aa065e82`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/full/raw_records_mariadb_combined.jsonl`: `54198282d9133b77dcbcff43933b1996f9dcc0b4b1987bc15b0166ee719560f5`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/full_mariadb_public_summary.json`: `af119fbc0b978c28bdab628a75ea75d3a9595279b15e2ed152f6c7f6293d6465`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/full_sqlite_vs_mariadb.csv`: `1fb02b1037ce5e394db3376bd4213d8972babd3bf234c467ebacea95616d3d86`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/full_sqlite_vs_mariadb.json`: `663c854e139665b8f0e8c81e19ddd9548b708bdee32b473f3fc988880c4958f8`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/full_tests.log`: `5d17d2949cbdffa61bbf5e54ef1e6ead396579e9a55571a7eade0e5f1f53a5e4`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/git_diff_check.log`: `b88433463a2bcd38ac7a75f7b073bc1e4b904dbb9ad744b168dce438fcde5cbf`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/isolation_validation.json`: `e6641af0424ab74c76661833c46f9b00ef3b5a0f470070bb37001bd1de7f78aa`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/mariadb_environment.json`: `2354b6521174b15ac63f763b9d3ccd721f9adaaaaf7366c371ce118912ca4804`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/normal_runtime_baseline.json`: `70b72cd36634519cadab31a0afcc88d9b2e2ff559dae30522c2f76d8eb75d76b`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/quality_gate_non_docker.log`: `75894b6582a22930b67208c767594bbb92401301e4ac662d4a96a3a1b4885ee4`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/S1_S2_PRESERVATION_MARIADB_CHECK.json`: `bd7b9e6bf9d362ed9b857d7b83a7087462a143d3101c5218f75ba0ea6b94e03d`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/schema_validation.json`: `053495498be27565e1834c57d095270161dffc25aefb0bf58a7ea41e8b1914f9`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/source_mutation_check.json`: `ed3a49088a193bc6d59c85dacad06139e64f12e4004fee5cc6b1c8067de8d8db`
- `artifacts/s3_s6_candidate_integration/MARIADB_PREFLIGHT_CODE_STATE.json`: `5e10cdda388a01704549f396f212d90233905b3e684ef3c075fa56dc24ee92e1`
- `artifacts/s3_s6_candidate_integration/mariadb_preflight_working_tree.patch`: `ddea9de6df43a02144f08faccf220c1fa0116279b27002157e7067ccdccdbfca`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/MARIADB_COMPATIBILITY_MANIFEST.json`: `8b56f8e591fc0a43701c733bca56dd378036fc31efdc81d0dee35871eda4c6bf`
- `artifacts/s3_s6_candidate_integration/mariadb_compatibility_smoke/SHA256SUMS.txt`: final checksum-file hash is external to the self-referential list
- `docs/integration/S3_S6_MARIADB_COMPATIBILITY_REPORT.md`: final report hash is recorded in `SHA256SUMS.txt`

## 16. Status

READY_FOR_S3_S6_CANDIDATE_FREEZE_REVIEW
