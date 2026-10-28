# Original GaRAGe pilot

Start with REPORT.md for safe findings and local/REPORT_FULL.md for all ten exact questions, complete generated outputs and the 17-item review per case. The local companion is intentionally ignored.

The committed files contain adapter/provider/runner code, tests, hashes, aggregate metrics, exact selected IDs, safe metadata and a pending human-review template. Original data, full passages, reference answers, runtime inputs, unredacted gold, raw outputs and potentially sensitive traces are excluded by this directory's .gitignore. They remain available locally in datasets/, local/ and the explicitly ignored JSONL files.

The ten-case sample and tested implementation are frozen. Do not rerun download_source.py or adapter.py in this completed directory: download preparation is intended only for a fresh task, and the existing selection/results must remain immutable. runner.py refuses repeated freeze/pilot execution. A later authorized reproduction needs its own directory, persistent deadline and explicit call budget; never reset this task's clock or call ledger.

Offline verification from the repository uses the workspace venv Python:

```powershell
python -m pytest evaluation/cfaf_dataset3_garage_pilot_v1/test_adapter.py evaluation/cfaf_dataset3_garage_pilot_v1/test_scoring.py -q
```

The adapter tests require the ignored local runtime and gold files. Source-selection scorer unit tests use synthetic text. Historical regression ran in an exact-Git-blob scratch checkout with API credentials removed. The one known original-suite failure is documented, not repaired in this task.

Artifact map: source_audit.json / GARAGE_SOURCE_AUDIT.md (provenance and vocabulary); dataset3_selection_manifest.json plus selection_annotation_supplement.json (sample and metadata); experiment_manifest.json (pre-run freeze); grounding_metrics.json / mode_comparison.json / api_usage.json (safe results); security_audit.json / regression_audit.json (checks); HUMAN_REVIEW_TEMPLATE.csv (no fabricated human judgements); CHANGED_FILES.txt / checksums.sha256 (safe commit inventory).

Ignored root files runtime_inputs.jsonl, gold_annotations.jsonl, selected_records.jsonl, results.jsonl, per_case_diagnostics.jsonl, api_requests.jsonl and api_events.jsonl retain the original data boundary. Do not git add -f them. No push or merge was performed.
