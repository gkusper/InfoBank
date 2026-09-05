# Document RAG Fixture Set

This directory contains tracked synthetic fixture definitions for the InfoBank
document-RAG ablation benchmark. Generated PDFs, manifests, and measured outputs
are intentionally kept outside Git.

## Benchmark Purpose

`document_rag_v1` defines the original 40 synthetic cases for comparing:

- Standard RAG
- Governance-only RAG
- Role-Aware RAG

`document_rag_v2` keeps the D1-D4 cases identical to `document_rag_v1` and
repairs D5 by removing explicit evidential-role hints from generator-visible
document text. Use v2 for development-pilot regression work.

`document_rag_v3` is the 400-case frozen large-scale D1-D5 benchmark for the
D1-D8 final-evaluation protocol. It is generated deterministically by
`evaluation/build_document_rag_v3.py` with seed `20260817`.

The benchmark uses shared retrieval. Each case declares an explicit
`document_scope`, and retrieval should be filtered to only those documents.

## Scenario Families

`document_rag_v1` and `document_rag_v2` contain 40 development cases:

- Full-access direct QA: 8 cases
- Metadata-only: 8 cases
- Deny/private-no-permission: 8 cases
- Aggregate-only: 8 cases
- Mixed or insufficient primary evidence: 8 cases

`document_rag_v3` contains 400 large-scale cases:

- D1 Full: 80 cases
- D2 Metadata: 80 cases
- D3 Aggregate: 80 cases
- D4 Deny: 80 cases
- D5 Mixed/contextual: 80 cases

The Full, Metadata, and Deny cases form eight matched counterfactual triplets.
Within each triplet, the document text, question, canonical answer, markers, and
retrieval scope are identical. Only the case-level access decision changes.

## Synthetic Data Policy

All facts are harmless and synthetic. User emails use `.example.test` domains.
Protected markers are distinctive strings that should not be answerable from
general model knowledge.

## Validation

Validate the fixture:

```powershell
python -m evaluation.validate_fixtures evaluation/fixtures/document_rag_v1.yaml
python -m evaluation.validate_fixtures evaluation/fixtures/document_rag_v2.yaml
python -m evaluation.validate_fixtures evaluation/fixtures/document_rag_v3.yaml
```

Regenerate v3 deterministically:

```powershell
python -m evaluation.build_document_rag_v3
```

Generate deterministic PDFs twice and compare hashes via tests:

```powershell
python -m unittest discover -s evaluation\tests -v
```

## Loader

The fixture loader is evaluation-only. It validates fixtures, invokes the
clean-state guard, uses deterministic IDs, supports mocked embeddings for tests,
and writes ID/hash/count manifests. Real OpenAI indexing is intentionally not
used in this fixture-construction task.

Example mock-embedding load command for a future isolated pilot:

```powershell
python -m evaluation.load_fixtures evaluation/fixtures/document_rag_v1.yaml --mock-embeddings --manifest evaluation/generated_fixtures/document_rag_v1_load_manifest.json
```

## Ground Truth

Ground truth describes factual, policy, and evidential conditions. It does not
contain measured model outputs and does not hard-code Standard RAG answers.
