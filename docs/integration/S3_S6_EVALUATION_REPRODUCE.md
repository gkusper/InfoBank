# S3-S6 Evaluation Reproduction

Package identity: S3_S6_JOURNAL_EVALUATION_V1

Use the repository state recorded in `docs/integration/S3_S6_FREEZE_CODE_STATE.json`. HEAD alone is not sufficient because the evaluated implementation includes approved uncommitted source and test changes captured by `artifacts/s3_s6_freeze/s3_s6_freeze_working_tree.patch`.

Python environment: use the repository virtual environment and install the locked local dependencies already used by the project.

MariaDB: validated with MariaDB `11.4.12-MariaDB-ubu2404` in isolated evaluation databases. Runtime databases, Chroma stores, and durable source-storage copies must be isolated from normal application state.

Provider: use the deterministic mock provider only. Do not call an external provider.

Architectural configurations: C0, C1, C2, C3.

Candidate package binding command:

```powershell
.\.venv\Scripts\python.exe .\scripts\bind_external_scenario_package.py --package <scenario-pack-root> --output-dir artifacts/s3_s6_candidate_integration/actual_pipeline_inputs
```

Focused Aggregate-only validation command:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_python/tests/test_aggregate_executor.py evaluation/tests/test_actual_pipeline.py::test_aggregate_only_focus_after_fix
```

Full deterministic compatibility command:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Scoring command:

```powershell
.\.venv\Scripts\python.exe -m pytest evaluation/tests/test_actual_pipeline.py
```

Expected record counts: 12 focused C2/C3 Aggregate-only records and 120 full C0-C3 deterministic records.

Expected Aggregate confirmation invariants: 6 confirmed cases, C2 accepted 6/6, C3 accepted 6/6, no prohibited disclosure 6/6, contributor and threshold semantics confirmed 6/6.

Expected backend compatibility: zero SQLite-MariaDB substantive differences.

No external-provider requirement: all compatibility evidence is deterministic development compatibility evidence, not final real-provider performance.
