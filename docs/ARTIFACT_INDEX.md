# Artifact index

Status: `PRE_FREEZE`

## Tracked technical artifacts

- source/runtime: `backend_python/`, `frontend/`, `infobank_db.sql`;
- configuration and schema: controlled-failure config, MySQL migrations,
  evaluation JSON schemas, requirements locks;
- evaluation: `evaluation/` runners, scorers, candidate/reconciliation,
  provider readiness, human-QA and operations modules;
- tests: `backend_python/tests/`, `evaluation/tests/`;
- commands: `scripts/` and `docs/REPRODUCTION.md`;
- reports: `docs/integration/` plus manuals in `docs/`.

Stable current evidence hashes include MailEx source ZIP
`dda3ce5da5ffc3452dd9e5a58cd69e19e68bd655eafe1deec48e87204f6c37b4`
and corrected API workflow trace
`999e95abf6db55594339c11bf195ef911a35e008660b7402a386f92b366ef4d4`.
The screenshot manifest records its own exact commit and PNG hashes.

## Ignored generated locations

- `artifacts/api_workflows/`: runtime W1/W2/W3 traces;
- `artifacts/reviewer_screenshots/`: seed, four PNGs and screenshot manifest;
- `artifacts/pre_freeze/`: operation dumps, copied stores, restore/repair reports;
- `artifacts/human_qa/`: pending assignment/annotation packages;
- `artifacts/actual_pipeline/`, `evaluation/results/`: development/provider raw and scored runs;
- `artifacts/local_quality_gate/`: JUnit and gate summaries;
- external sibling artifact root: MailEx candidate and reconciliation runs.

The paths above are repository-relative logical locations; generated content is
not tracked. Pending freeze artifacts are human-corrected gold, accepted MailEx
annotations/agreement/adjudication, complete citation/no-health reviews,
approved screenshot set, frozen manifests and final E1 raw-run seal/results.
