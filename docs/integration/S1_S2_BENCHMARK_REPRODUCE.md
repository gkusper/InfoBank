# S1/S2 Benchmark v2 Reproduction

Package identity: S1_S2_JOURNAL_BENCHMARK_V2

Freeze date: 2026-08-25

Expected branch: `feature/scenario-workflows`

Expected HEAD: `70a8852fc5cb7b4dea5abb856b4893fbd4ff5b0c`

Code-state manifest: `docs/integration/S1_S2_FREEZE_CODE_STATE.json`

Frozen package: `artifacts/s1s2_freeze/S1_S2_journal_benchmark_v2.zip`

Frozen package SHA-256: `83a9bb2394946b378af4efe2445be1e6e7095a60f5c14f6206ea1405f275bcd1`

No secrets are required in benchmark artifacts. Do not write API keys, database passwords, or local absolute paths into reproduced package contents.

## Python Environment

Use the repository Python environment:

```powershell
backend_python\.venv_r1a\Scripts\python.exe -m pip check
```

For pytest on Windows, isolate temp files:

```powershell
$env:TMP='C:\Users\EKKE\Documents\Codex\2026-08-24\files-pasted-by-the-user-you\work\pytest_tmp'
$env:TEMP=$env:TMP
$env:PYTEST_DEBUG_TEMPROOT=$env:TMP
$env:PYTEST_ADDOPTS='-p no:cacheprovider'
```

## MariaDB Isolation

Use a fresh evaluation database whose name starts with `infobank_eval_`. The actual-pipeline runner refuses other MySQL database names for evaluation bootstrapping. Keep runtime MariaDB data outside the benchmark package.

## Verify Package Checksums

After extracting `S1_S2_journal_benchmark_v2.zip`:

```powershell
backend_python\.venv_r1a\Scripts\python.exe -c "from pathlib import Path; import json; from evaluation.external_scenario_corpus import verify_package_checksums, verify_external_scenario_package; root=Path('artifacts/s1s2_freeze/S1_S2_JOURNAL_BENCHMARK_V2'); print(json.dumps(verify_package_checksums(root), sort_keys=True, indent=2)); print(json.dumps(verify_external_scenario_package(root, source_filename_map=json.loads((root/'source_filename_map.json').read_text(encoding='utf-8'))), sort_keys=True, indent=2))"
```

Expected: both checks pass, with 12 total questions and 10 PDF sources.

## Bind Frozen Package

Use the included source filename map because several S2 logical source IDs intentionally differ from PDF filenames:

```powershell
backend_python\.venv_r1a\Scripts\python.exe scripts\bind_external_scenario_package.py --package-root artifacts\s1s2_freeze\S1_S2_JOURNAL_BENCHMARK_V2 --output artifacts\s1s2_freeze_rebound --scenario-id S1_SOFA_01 --scenario-id S2_TV_WARRANTY_01 --source-filename-map artifacts\s1s2_freeze\S1_S2_JOURNAL_BENCHMARK_V2\source_filename_map.json --package-sha256 83a9bb2394946b378af4efe2445be1e6e7095a60f5c14f6206ea1405f275bcd1
```

The rebound runtime must remain gold-blind: `query_inputs.jsonl` must not contain `required_sources`, `reference_answer`, `reference_citations`, `gold_document_ids`, `gold_page_or_message_ranges`, `reason_code`, or `manual_validation_state`.

For exact reproduction of the frozen reference B3 hash, use the sealed bound inputs included in `artifacts/s1s2_freeze/S1_S2_JOURNAL_BENCHMARK_V2/actual_pipeline_inputs/`. Fresh binding is still required as a package-integrity/loadability check, but it may use a different document-ID namespace from the historical sealed reference.

## Run B3 Deterministic Smoke

Use the deterministic provider path only. The frozen reference result is a deterministic development/reproducibility result, not final real-LLM journal performance.

Run `evaluation.actual_pipeline_runner.run_actual_pipeline` with:

- `query_input_path`: frozen `actual_pipeline_inputs/query_inputs.jsonl`
- `corpus_fixture_path`: frozen `actual_pipeline_inputs/corpus_fixture.json`
- `modes`: `B3_FULL_ROLE_AWARE`
- isolated MariaDB evaluation database
- fresh Chroma directory
- fresh source storage directory
- deterministic/mock provider configuration

Then score the sealed run:

```powershell
backend_python\.venv_r1a\Scripts\python.exe -c "from pathlib import Path; from evaluation.actual_pipeline_scorer import score_sealed_run; score_sealed_run(raw_run_path=Path('<run>')/'raw'/'raw_records.jsonl', seal_path=Path('<run>')/'raw'/'run_seal.json', gold_annotation_path=Path('artifacts/s1s2_freeze/S1_S2_JOURNAL_BENCHMARK_V2/actual_pipeline_inputs')/'gold_annotations.jsonl', output_dir=Path('<run>')/'scores')"
```

## Expected B3 Reference

Expected deterministic content hash:

`24afef714fe8bfc4715b41720cff8d44d7fd20b83b6a9786b308ecedb9023c5a`

Expected combined metrics:

- output-class accuracy: 1.0
- reason-code accuracy: 1.0
- permitted-answer accuracy: 1.0
- false-answer rate/count: 0.0 / 0
- citation document coverage: 0.785714
- citation support precision: 1.0
- page-level citation correctness: 1.0
- citation coverage: 0.785714
- controlled-failure correctness: 1.0
- safety error total: 0

Known non-passing citation-completeness cases: S1-Q6, S2-Q2, S2-Q5.
