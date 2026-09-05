# WoLaLa 2026 CFAF Preparation

This directory contains a small deterministic preparation harness for the WoLaLa
2026 paper claim that Controlled Failure to Answer Fully (CFAF) is a first-class
application-level output mode.

It does not run the frozen D1-D8 benchmark, does not call paid APIs, and does
not modify the D1-D8 preregistration, manifests, publication results, or
archived reports.

## Pipeline

The CFAF smoke path is implemented in `pipeline.py` and exposes these eight
top-level stages:

1. `QUERY_PROFILING`
2. `CANDIDATE_RETRIEVAL`
3. `ACCESS_AND_SAFETY_RESOLUTION`
4. `EVIDENCE_LABELLING`
5. `SUFFICIENCY_AND_PERMITTED_OUTPUT`
6. `TOP_LEVEL_MODE_SELECTION`
7. `RESPONSE_REALIZATION`
8. `VALIDATION_TRACE_AND_FEEDBACK`

Labels are appended to a shared JSON-serializable `PipelineState`. Access mode,
existence visibility, evidential role, evidence state, disposition, permitted
output, and top-level mode remain separate dimensions.

## Smoke Command

```powershell
python -m evaluation.wolala2026.run_smoke
```

In a minimal runtime without the project dependencies installed, use any Python
3.12 interpreter from the repository root. The WoLaLa smoke path itself uses
only the standard library.

## Outputs

- `smoke_config.yaml`: deterministic 13-case smoke suite.
- `smoke_results.json`: observed mode, validation, and latency records.
- `example_internal_trace.json`: full internal trace for one CFAF case.
- `example_public_response.json`: corresponding filtered public response.
- `data_inventory.json`: data-readiness audit for D1-D8 and WoLaLa smoke data.
- `PIPELINE_LABEL_SPEC.md`: label catalogue and propagation rules.
- `latency_plan.md`: latency instrumentation and later experiment plan.
- `WOLALA2026_READINESS_REPORT.md`: branch preparation report.

## Later Opt-In Real API Smoke

Do not run this automatically. A later capped real-API smoke should use a tiny
case subset and an explicit cap, for example:

```powershell
$env:OPENAI_API_KEY = "<set outside the repository>"
python -m evaluation.wolala2026.run_smoke --config evaluation/wolala2026/smoke_config.yaml
```

The current implementation uses deterministic realization, so that command is a
placeholder for a future real generator adapter rather than a paid benchmark.
