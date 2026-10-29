# Migration and provenance

Base commit: `bfd80bbfe2ccbb251da46bdc22b791dad5b9341f`, the last completed committed `experiment/cfaf-contract-driven-v1` study. New isolated branch: **ComponentBasaedCFAF** (intentional spelling). It does not include later QASPER repair or final-replacement commits. The two pre-existing worktrees, all prior refs/freeze tags, legacy requirements and manuscript remain protected.

The old study is unchanged and remains reproducible. The new package does not rename or replace historical experiment directories. The old measured C still has its two-call analysis/realization protocol. The new C1 has a new internal proposal schema and deterministic publication, so it is a different configuration and has its own freeze/results. Historical study percentages are not transplanted as C1 accuracy.

## Reused code

- `adapters/legacy_projection.py` is an exact working-byte copy of the base checkout's `evaluation/infobank_semantic_regression_v1/policy_projection.py`. The thin LegacyGovernance adapter authenticates the application policy input, excludes denied/nonpublic records before projection/search, converts safe projected documents to typed views, and retains private records separately.
- `adapters/aggregate_core.py` is an exact working-byte copy of the existing vendored `evaluation/cfaf_target_claim_alignment_v1/vendor/aggregate_core.py`. Its original header records main `8079f29dc3a97273f51b55b2a22f9ff896a2e758`. That existing pure executor handles policy filtering, contributor deduplication and k thresholds. The current repository's license applies to this reuse; no independent upstream-main license verification is claimed.
- `adapters/legacy_selector.py` extracts the small first-failing-assessment principle from `evaluation/wolala2026/pipeline.py` at the base SHA. Differential tests compare mode, fulfilment, reason, realization and permitted-output fields on 300 nonempty synthetic states (1–4 assessments, every support bit pattern, five permitted-content classes, two reason classes). Empty requests and execution/policy validity are new caller preconditions. This is not a claim that the entire old and new semantic pipelines are equivalent.

Exact working/blob SHA values and line counts are in component_manifest.json/code_size_report.json. Imported runtime is counted separately from new code, including adapters. A short wrapper is not counted as eliminating its dependencies.

## Deployment boundary

Install the new Pydantic-2 package only in its own environment. The legacy backend pins Pydantic 1.10.24, FastAPI 0.103.2, ChromaDB 0.4.24 and OpenAI 1.59.9 in the inspected base. None is upgraded in place. Existing backend integration should exchange simple JSON/dicts at the boundary rather than embedding V1 models in V2 models. The package runs without a database server or web service.

No general backend migration, production policy-service replacement, ingestion replacement or durable quota store is delivered. The resolver/current callbacks are trusted application boundaries that production must authenticate. Supplied-context and SQLite retrieval require no embedding index. Missing optional spaCy/NLI integrations are explicit NOT_IMPLEMENTED_OPTIONAL, rather than hidden fallback models.

## Separate evaluations

Renderer ablation reuses saved old valid proposals and response contracts. Its compatibility renderer copies that contract deterministically with zero new analysis or generation. Raw old generations remain in ignored local storage. This measures contract realization, not the new semantic schema or factual answer accuracy.

The new one-call smoke uses 10 previously exposed InfoBank P1–P5 cases, 10 fixed exposed RefusalBench cases and the original 10 GaRAGe pilot cases. It does not sample new records or open reserved groups. The raw questions, gold, responses and private traces are ignored. QASPER is registered only as a separate adapter boundary; no QASPER question, annotation, source or intermediate/final output is used for development here.

The legacy dataset keys remain: Dataset1/InfoBank; Dataset2/RefusalBench-NQ; Dataset3-v1/GaRAGe; Dataset3-QASPER-v2-candidate as the requested historical registry key. QASPER's separately completed replacement study is not relabelled or modified by this package. No GaRAGe native binary accuracy is manufactured and no cross-cohort pooled accuracy is reported.
