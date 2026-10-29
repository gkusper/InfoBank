# Contract-driven two-hour comparative study

Start with REPORT.md, PREREGISTRATION.md and the frozen experiment_manifest.json. MAKE_OR_REUSE.md/CONTRACTS.md describe prepared boundaries and existing components; WOLALA2026_FREEZE.md records historical SHA/tag and manual future publication commands.

A is standard selective RAG using policy-safe shared evidence and a self-reported mode schema. B postprocesses the exact same A generation; it is not an independent model sample. C is existing sparse-source CFAF, with only the unused fourth control-generation removed. The compact architecture/one-call/library replacements are not presented as newly evaluated frameworks.

Cohorts: 40 exposed InfoBank development cases, 40 fixed exposed RefusalBench-NQ fallback records (reserved 30 and other18 groups untouched), 80 new frozen GaRAGe rows excluding the ten pilot IDs. All80 were charged as exposed before requests. Remaining2276 records stay unused. The new independent InfoBank holdout is not opened.

Safe outputs: dataset1_results.jsonl, dataset2_results.jsonl, dataset3_results.jsonl; comparison_summary.csv/json; paired_mode_confusions.json; grounding_metrics.json; operational_failures.json and the finer breakdown; actual api_usage.json; security/regression audits; source/prompt/runtime hashes; RESULTS_FOR_PAPER.tex and integration notes. Failure denominators and cohort qualification are explicit.

Ignored local files retain runtime inputs, scorer-only original answers, actual API requests/events, *_results_raw.jsonl, blinded packets and the detailed case report. Do not force-add them. No original benchmark text/reference answer or fresh private trace is committed.

Do not rerun this completed study in place. Model commands refuse repeated cohorts and use a persistent deadline/attempt ledger; resetting either is not authorized. A later task needs separate outputs and a new predeclared protocol. Do not tune on the just-exposed80. The ordinary offline synthetic test entry point is:

```powershell
python -m pytest evaluation/cfaf_contract_driven_2h_v1/test_study.py -q
```

The annotated tag is local only, and does not enforce GitHub protection. No push/merge/deletion was executed. The user performs any later pushes manually using the commands in the report/freeze document.
