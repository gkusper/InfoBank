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
