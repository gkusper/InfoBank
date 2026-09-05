# InfoBank Evaluation Harness

This package is an evaluation-only harness for the document-RAG ablation study.
It does not add a production endpoint and does not change the normal `/api/ask`
behavior.

## Modes

- `standard_rag`: uses the shared raw retrieved passages as a conventional RAG baseline. It bypasses InfoBank governance, source-role labeling, evidence checks, controlled failure, and role-aware redaction.
- `governance_only_rag`: uses the same retrieved passages, then applies only Full, Aggregate, Metadata, and Deny access decisions before generation.
- `role_aware_rag`: uses the same retrieved passages, then applies the existing production governance, source-role profiling, evidence checks, controlled-failure gates, and role-aware context blocks.

## Shared Retrieval

The main ablation retrieves once per case and reuses the exact same candidate
set across all modes. Candidate chunk IDs, document IDs, rank, raw text,
metadata, distance, score, and ordering are persisted in every raw result.

## Isolated Environment

Runs must use the isolated evaluation environment:

```text
DATABASE_URL -> infobank_eval
CHROMA_PERSIST_DIR -> backend_python/chroma_eval
```

The clean-state guard refuses to proceed if scientific tables or Chroma vectors
are already present before fixture loading.

## CLI

Clean-state check only:

```powershell
python -m evaluation.run_suite --check-clean-only
```

Mocked no-fixture dry run:

```powershell
python -m evaluation.run_suite --mock-generation
```

Useful options:

```text
--fixture <path>
--results-dir <path>
--top-k <int>
--repetitions <int>
--modes standard,governance,role-aware
--mock-generation
```

Default `top_k` is 4. Default repetitions is 1. Evaluation generation
temperature is 0.0.

## Results

Raw measured outputs are written as JSONL under `evaluation/results/`, which is
ignored by Git. Each record contains prompts, retrieved candidates, generated
answer, mode-specific decisions, model configuration, and API usage fields.

Each run also writes a `run_manifest.json` with Git, Python, package, DB,
Chroma, model, top-k, temperature, and fixture metadata.

## Fixture Workflow

Fixture schema parsing supports YAML or JSON synthetic benchmark definitions.
`evaluation/fixtures/document_rag_v1.yaml` is the original 40-case D1-D5
document-RAG fixture. `evaluation/fixtures/document_rag_v2.yaml` preserves
D1-D4 and repairs D5 by removing explicit evidential-role hints from
generator-visible source prose. `evaluation/fixtures/document_rag_v3.yaml` is
the frozen 400-case large-scale D1-D5 benchmark for the final D1-D8 protocol.

Synthetic fixtures should be tracked in Git; measured outputs should remain
local by default.

## EvidenceUnit D6-D8 Benchmark

The D6-D8 action-list pilot is stored separately under
`data/benchmarks/evidence_unit_v1/`. It uses selected, modified MailEx e-mail
excerpts for D6 and natural D8, plus deterministic synthetic browser/search
counterfactuals for D7. Runtime inputs are in `cases.jsonl`; hidden scoring
labels are in `gold.jsonl`.

Validate it with:

```powershell
python scripts/mailex/validate_evidence_benchmark.py --benchmark data/benchmarks/evidence_unit_v1
```

The large-scale held-out EvidenceUnit benchmark is
`data/benchmarks/evidence_unit_v2_holdout/`. It contains 340 runtime cases and
keeps scorer-only labels in `gold.jsonl`. Raw MailEx downloads remain ignored
under `data/external/`; the tracked benchmark contains only pseudonymized
excerpts and controlled synthetic counterfactual/control records.

Validate the v2 holdout with:

```powershell
python scripts/mailex/validate_evidence_benchmark.py --benchmark data/benchmarks/evidence_unit_v2_holdout
```

## Combined D1-D8 Development Pilot

Use the combined runner for the frozen development pilot that joins D1-D5
document-RAG with D6-D8 EvidenceUnit action reconstruction:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -ResetEvaluationState -SkipPackageInstall -RunPilotCheck
.\evaluation\run_d1_d8_pilot.ps1 -CheckOnly
.\evaluation\run_d1_d8_pilot.ps1 -MockGeneration
.\evaluation\run_d1_d8_pilot.ps1
```

The isolated runtime is mandatory:

```text
database: infobank_eval at 127.0.0.1:3307
Chroma: backend_python/chroma_eval
env file: backend_python/.env.eval
Python: backend_python/.venv_eval
```

The real run uses `OPENAI_API_KEY` only from the current process environment;
do not put it in `.env.eval`. If the key is absent, the combined runner skips
real D1-D5 generation, runs the deterministic EvidenceUnit phase when selected,
and prints the exact command for completing the real document phase later.

The combined pilot writes one ignored directory:

```text
evaluation/results/d1_d8_pilot_<UTC timestamp>/
```

Expected root artifacts include:

```text
run_manifest.json
document_results.jsonl
document_scores.jsonl
evidence_results.jsonl
evidence_scores.jsonl
combined_case_summary.jsonl
metrics.json
api_usage.json
baseline_evidence_diagnostic.json
final_evidence_diagnostic.json
pilot_report.md
```

`document_results.jsonl` contains 21 records: seven D1-D5 cases across
`standard_rag`, `governance_only_rag`, and `role_aware_rag`. `evidence_results.jsonl`
contains 32 records from the production `evidence_service.reconstruct_action_list`
path in the single `role_aware_action_reconstruction` mode. D6-D8 uses no
external LLM calls unless the production service is changed later.

Current D6-D8 values are development-pilot results after observing and fixing
baseline failures on this same frozen set. Treat them as reproducibility and
implementation diagnostics, not as held-out benchmark performance.

## Frozen Large-Scale D1-D8 Evaluation

The large-scale protocol is preregistered in:

```text
evaluation/preregistration/d1_d8_large_scale_v1.md
```

Build and validate frozen benchmarks:

```powershell
.\evaluation\run_d1_d8_large_scale.ps1 -BuildBenchmarks
.\evaluation\run_d1_d8_large_scale.ps1 -ValidateBenchmarks
```

Preflight the isolated runtime:

```powershell
.\evaluation\run_d1_d8_large_scale.ps1 -CheckOnly
```

Run the complete real-API evaluation:

```powershell
$env:OPENAI_API_KEY = "<set outside the repository>"
.\evaluation\run_d1_d8_large_scale.ps1 -RealApi -Resume
```

Expected measured records:

```text
D1-D5: 400 cases x 3 modes x 5 repetitions = 6000
D6-D8: 340 cases x 3 clean repetitions = 1020
Total: 7020
```

The runner supports `-CheckOnly`, `-BuildBenchmarks`, `-ValidateBenchmarks`,
`-DocumentOnly`, `-EvidenceOnly`, `-RealApi`, `-Resume`, `-ScoreOnly`,
`-ReportOnly`, and `-ResultsDir`. A complete run writes a local ignored result
directory `evaluation/results/d1_d8_large_scale_<UTC>/` and a sanitized
publication package under `evaluation/publication_results/d1_d8_large_scale_v1/`.

Corrected D1-D5 metric denominators are frozen in
`evaluation/score_document_results.py`: permitted-answer accuracy is computed
only over permitted cases; prohibited disclosure, safe withholding, and
generator exposure are computed only over restricted cases; exact output-class
conformance is separate from safe withholding; source-role conformance is
reported independently.

## Manual Real-API Pilot Run

The manual pilot runner is for the seven-case, 21-record real-API pilot only.
It does not run the full benchmark and does not calculate final metrics.

Before running it from a normal Windows PowerShell window:

1. MariaDB must already be running at `127.0.0.1:3307`.
2. `backend_python/.env.eval` must exist and point `DATABASE_URL` to `infobank_eval`.
3. `CHROMA_PERSIST_DIR` in `backend_python/.env.eval` must resolve to `backend_python/chroma_eval`; the recommended value is `./chroma_eval`.
4. The evaluation DB and the `backend_python/chroma_eval` Chroma store must be empty.
5. `OPENAI_API_KEY` must be visible in the PowerShell process. If it was set with `setx`, open a new PowerShell window.

For a reproducibility-oriented setup helper, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -PrepareEvalDatabase -RunUnitTests -RunPilotCheck
```

The helper uses `backend_python/.venv_eval`, installs dependencies with a
repository-local `.pip-cache`, creates missing local `.env` files, checks the
MariaDB port, and can prepare `infobank_eval` even when Docker CLI is not
available but the database is already running.

Run the preflight check:

```powershell
Set-Location "<repository root>"
.\evaluation\run_document_rag_pilot.ps1 -CheckOnly
```

Run the real pilot:

```powershell
Set-Location "<repository root>"
.\evaluation\run_document_rag_pilot.ps1
```

The runner uses exactly:

- cases: `FULL_01`, `METADATA_01`, `DENY_01`, `AGG_SAFE_01`, `AGG_INDIVIDUAL_01`, `MIXED_PRIMARY_01`, `CONTEXT_ONLY_01`
- modes: `standard_rag`, `governance_only_rag`, `role_aware_rag`
- repetitions: `1`
- retrieval top-k: `4`
- embedding model: `text-embedding-3-small`
- generator model: `gpt-4o-mini`
- generation temperature: `0.0`

For a concise methods-paper version of the reproduction procedure, see
`docs/evaluation/PAPER_REPRODUCTION_SECTION.md`.

A successful run writes 21 raw result records under a unique ignored directory:

```text
evaluation/results/pilot_<UTC timestamp>/
```

The expected artifacts are:

```text
results.jsonl
run_manifest.json
fixture_subset_manifest.json
shared_retrieval.jsonl
pilot_inspection.json
```

If a failure occurs, the runner also writes `pilot_failure.json` with sanitized
stage, case, mode, and error information. Credentials are never printed or
serialized.

Pilot data remains loaded in `infobank_eval` and `backend_python/chroma_eval`
after a successful real run so the raw state can be inspected. Reset the
evaluation database and Chroma store before another pilot or before the full
experiment.
