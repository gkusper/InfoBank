# InfoBank Evaluation Status

## Current State

InfoBank has two evaluation layers:

- Development diagnostics: `document_rag_v1`, `document_rag_v2`,
  `evidence_unit_v1`, and the 53-record D1-D8 pilot runner.
- Frozen large-scale protocol: `document_rag_v3`,
  `evidence_unit_v2_holdout`, corrected deterministic scorers,
  preregistration, statistical analysis, and the `run_d1_d8_large_scale`
  runner.

The development diagnostics are useful for reproducibility checks and
regression testing. They must not be reported as held-out final benchmark
performance.

## Large-Scale Evaluation Protocol

The large-scale protocol is preregistered in:

```text
evaluation/preregistration/d1_d8_large_scale_v1.md
```

The intended freeze sequence is:

```text
1. code freeze: d1-d8-large-scale-code-freeze-v1
2. benchmark freeze: d1-d8-large-scale-benchmark-freeze-v1
3. final result tag: coginfocom-2026-d1-d8-final-eval-v1
```

After benchmark freeze, result-affecting production behavior, prompts, scorer
definitions, gold labels, and benchmark text must not be tuned based on final
outcomes.

## Benchmarks

`evaluation/fixtures/document_rag_v3.yaml` contains 400 synthetic D1-D5 cases:

- D1 Full: 80
- D2 Metadata: 80
- D3 Aggregate: 80
- D4 Deny: 80
- D5 Mixed/contextual: 80

`data/benchmarks/evidence_unit_v2_holdout/` contains 340 D6-D8 cases:

- D6 open action: 100
- D7 browser-only counterfactual: 100
- D8 closure: 100
- D8 non-closing control: 40

The EvidenceUnit holdout excludes source threads used in `evidence_unit_v1`,
separates runtime cases from scorer-only gold labels, and records natural versus
synthetic strata.

## Required Runtime

The evaluation runtime is isolated from the normal prototype database:

```text
database: infobank_eval at 127.0.0.1:3307
Chroma: backend_python/chroma_eval
Python: backend_python/.venv_eval
```

The OpenAI API key is required only for real D1-D5 generation and must be set as
a local process environment variable. It must not be written to `.env`,
`.env.eval`, result manifests, or Git.

## Canonical Commands

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -PrepareEvalDatabase -RunUnitTests -RunPilotCheck
.\evaluation\run_d1_d8_large_scale.ps1 -BuildBenchmarks
.\evaluation\run_d1_d8_large_scale.ps1 -ValidateBenchmarks
.\evaluation\run_d1_d8_large_scale.ps1 -CheckOnly
$env:OPENAI_API_KEY = "<set outside the repository>"
.\evaluation\run_d1_d8_large_scale.ps1 -RealApi -Resume
```

Expected measured records for a complete final run:

```text
D1-D5: 400 x 3 x 5 = 6000
D6-D8: 340 x 3 = 1020
Total: 7020
```

## Corrected D1-D5 Metrics

The frozen scorer reports numerator, denominator, and rate for primary metrics.
Permitted-answer accuracy is computed only over answer-permitted cases.
Prohibited-disclosure, safe-withholding, and generator-exposure rates are
computed only over restricted cases. Literal protected-marker occurrence is a
diagnostic, not a disclosure violation. Exact output-class conformance is
reported separately from safe withholding, and source-role conformance is
reported independently.

## Current Verification

The codebase includes unit and regression tests for the development harness, the
corrected document scorer, benchmark validation, EvidenceUnit source/gold
separation, D6-D8 production action logic, and large-scale statistical
aggregation. A valid real final evaluation should start only after these tests
and benchmark validators pass.
