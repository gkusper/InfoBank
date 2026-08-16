# InfoBank Evaluation Status

## Project Goal

InfoBank is a research prototype for governed personal-data retrieval. The evaluation asks whether Role-Aware RAG over governed personal data improves policy compliance, evidence-grounded behavior, controlled failure, and protection against unsupported disclosure compared with simpler RAG variants.

The current state is pre-pilot. Startup reproducibility, the isolated evaluation environment, the three-mode harness, synthetic fixtures, and a manual real-API pilot runner are implemented, but the real 21-record OpenAI-backed pilot has not yet produced final results.

## Milestone History

| Milestone | Branch | Commit | Main achievement |
|---|---|---|---|
| Original prototype | `main` | `e9dc92b903b36de31e267993671d8f31d3a176ea` | Baseline InfoBank prototype with governed personal-data features. |
| Reproducibility repair | `reproducibility-repair` | `2d2874a` | Startup repair for local FastAPI/MariaDB execution. |
| Isolated evaluation environment | `reproducibility-repair` | `66efcfcb6fd5a5c2d0f06291067c0071627b6f01` | Clean Python 3.12 evaluation environment, `infobank_eval`, and isolated Chroma path. |
| Evaluation harness | `evaluation-harness` | `9a4626713000bc517bfb27321ef6ec9255d16b52` | Three-mode document-RAG harness with shared retrieval and JSONL result persistence. |
| Synthetic benchmark fixtures | `benchmark-fixtures` | `81778bb8e153ee300b5a819d280ede415fb0457d` | Deterministic `document_rag_v1` fixture set with 40 cases. |
| Manual pilot runner | `evaluation-pilot` | `9b7326b9d53741c3455cbdc61186a2f6412f5864` | Tracked PowerShell/Python runner for the seven-case, 21-record real-API pilot. |

## Verified Startup State

The prototype has been verified to start locally with MariaDB. The backend can expose `/docs` and `/api/test-db` without an OpenAI key for non-AI functionality. The static frontend can be served locally and pointed at the backend API.

The evaluation environment uses Python 3.12 with pinned dependencies and a passing dependency check. MariaDB is used for the application database, and the evaluation workflow isolates its database as `infobank_eval` with Chroma persisted under `backend_python/chroma_eval`.

The configured OpenAI models have been tested separately from a normal Windows process:

- chat generation: `gpt-4o-mini`
- embeddings: `text-embedding-3-small`

## Verified Functional Behavior

### Full-Access Test

A synthetic full-access document contained the protected fact marker `BLUE ORCHID`. With owner/full access, the system returned the fact in a normal answer. The observed output mode was `full_answer`, and the source role was `primary`.

### Metadata-Only Test

The same synthetic fact and question were used in a cross-user Metadata access condition. The protected marker was not disclosed. The observed output mode was `metadata_only_answer`, the source role was `contextual`, and governance/controlled-failure restriction behavior was observed.

These smoke tests exercised the governed retrieval and response pipeline without publishing local identifiers, credentials, or raw runtime artifacts.

## Evaluation Architecture

The evaluation harness compares three modes:

- `standard_rag`: conventional RAG over the shared retrieved passages.
- `governance_only_rag`: applies Full, Aggregate, Metadata, and Deny access decisions before generation.
- `role_aware_rag`: applies governance, source-role classification, evidence checks, and controlled-failure/output-mode logic.

All three modes receive the same shared retrieval result for each case. Raw outputs are persisted as JSONL, and manifests record run configuration. A clean-state guard refuses evaluation runs if the isolated DB or Chroma store already contains data before fixture loading.

Production `/api/ask` behavior is unchanged by the evaluation harness.

## Benchmark Fixture

The tracked fixture set is `document_rag_v1`.

It contains 40 synthetic cases:

- 8 Full-access direct QA cases
- 8 Metadata-only cases
- 8 Deny/private-no-permission cases
- 8 Aggregate-only cases
- 8 Mixed/contextual-only cases

The Full/Metadata/Deny cases are matched counterfactual triplets with identical document text, question, canonical answer, markers, and retrieval scope; only access configuration differs. Aggregate cases form safe aggregate versus individual-disclosure pairs. Mixed cases include both primary-support and contextual-only evidence conditions.

All fixture data is synthetic, deterministic, and intended only for evaluation.

## Manual Pilot Protocol

The manual pilot runner selects exactly:

- `FULL_01`
- `METADATA_01`
- `DENY_01`
- `AGG_SAFE_01`
- `AGG_INDIVIDUAL_01`
- `MIXED_PRIMARY_01`
- `CONTEXT_ONLY_01`

Protocol:

- modes: `standard_rag`, `governance_only_rag`, `role_aware_rag`
- repetitions: 1
- retrieval top-k: 4
- generation temperature: 0.0
- expected raw result records: 21

The runner writes raw result JSONL, shared retrieval records, run manifests, fixture subset manifests, and deterministic inspection output. It does not calculate final benchmark metrics.

## Current Limitation

The real 21-record OpenAI-backed pilot is the next step. It has not yet produced final results. No final metrics, statistical tests, or publication tables exist yet.

## Next Planned Steps

1. Independent reproduction by a second researcher.
2. Real seven-case pilot.
3. Review of the 21 raw records.
4. Deterministic scoring.
5. Full 40 x 3 x 3 experiment.
6. Update the paper's Evaluation section.
