# Sparse-source repair research version

REPORT.md is the safe committed report. local/REPORT_FULL.md contains exact original ten questions, complete raw/served responses and 19-item reviews; it is ignored. No original dataset, unredacted gold or raw trace is committed.

Core modules: source_inventory.py (application inventory), sparse_source_assessment.py (dense/sparse contract), reference_validation.py (exact reference checks), operational_failure_codes.py (internal states and strict existing public vocabulary), gate_controls.py/integration.py (existing substantive gate with new boundary), public_grounding_trace.py (experimental; no verified citations rendered).

Phase A: cached.py replays only the original ten exposed raw analyses. Phase B: runner.py freezes and runs one shared-analysis paired regression. Phase C: runner.py citations computes sidecars only after B completes. reference_alias_ablation.py is a separately labelled post-B numeric-format diagnostic, not frozen primary runtime.

The ten records remain exposed development data; the other 2356 were not opened. Dataset1's independent holdout and new Dataset2 records remain untouched. Earlier files/branches are preserved; no push/merge.

Offline synthetic checks from the repository:

```powershell
python -m pytest evaluation/cfaf_sparse_source_repair_v1/test_sparse.py evaluation/cfaf_sparse_source_repair_v1/test_reference_alias.py -q
```

Primary manifest excludes post-run scorer/report/audit files. R1 has separate tests and artifact hashes. Do not rerun cached/live preparation in this completed directory: results are immutable, commands refuse duplicate execution and persistent deadlines must not reset. A future run needs a fresh research directory/clock/budget and remains exposed development if it uses these ten records.

Artifacts: cached_ablation_results.json and cached_final_source_verification.json (zero-call comparison); case_metrics.jsonl / evaluation_summary.json / mode_transition_matrix.csv (safe live summaries); source_coverage_diagnostics.jsonl / reason_audit.jsonl / citation_diagnostics.jsonl; reference_alias_ablation.json (R1); api_usage.json; security_audit.json / regression_audit.json; CHANGED_FILES.txt / checksums.sha256.

Ignored: runtime_inputs.jsonl, live_paired_results.jsonl, api_requests.jsonl, api_events.jsonl, *_raw.jsonl and local/. Original scorer-only annotations stay in the previous ignored gold file. Do not force-add them. Exact questions, original answers and full passages remain ignored.
