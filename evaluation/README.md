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

Fixture schema parsing supports future YAML or JSON synthetic benchmark
definitions. The benchmark dataset is intentionally not included yet. Future
synthetic fixtures should be tracked in Git; measured outputs should remain
local by default.

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
