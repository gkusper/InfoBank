# C-GATE report

Status: `PASS_WITH_LIMITATIONS`

Final E1 has not run. All results in this report are deterministic synthetic development evidence.

## Version and scope

- Starting A2 commit: `993be5f6a1fbb2fd5aee0104ff305f8adecb64fb`.
- Branch: `feature/infocom-cd-gates`.
- Provider config: `infocom-provider-v1`.
- Aggregate config: `infocom-aggregate-v1`, default k=3.
- C runner: `infocom-c-gate-v1`.
- Candidate: `reviewer-v2-candidate-v1`, 54 cases (27 development, 27 candidate holdout), non-final and non-frozen.

## Implemented and tested

- Persistent Reader/Aggregate/Metadata grant/update/revoke and stable-ID ownership transfer.
- Immediate policy re-resolution after revoke/transfer; archived sources and active Deny remain hard exclusions even if stale vector IDs exist.
- Numeric aggregate executor with contributor deduplication, Full/Aggregate inclusion, Metadata/Deny exclusion, configurable k, safe below-threshold refusal, no individual generator/debug/citation exposure.
- Provider-neutral keywords, embeddings, and generation; OpenAI behavior remains lazy, with two deterministic network-free adapters for tests and smoke.
- W3 permission lifecycle, candidate-v2 split audit, and 50/250/1000 scale stress.
- `IMPLEMENTATION_SCOPE.csv` uses only the approved status vocabulary and distinguishes persistent relation, query-time decision, graph, routing, development evaluation, and future final evaluation.

## W3 and safety

W3 status: `PASS`.

| Metric | Count |
|---|---:|
| Prohibited disclosure | 0 |
| Generator exposure | 0 |
| Aggregate individual leakage | 0 |
| Source-existence leakage | 0 |

Happy path: Reader grant → Full decision → three-source Aggregate decision/result → revoke → immediate Deny → ownership transfer with stable document ID → old Owner Deny/new Owner Full. Error path includes safe below-threshold refusal. Trace: `artifacts/c_gate/w3/w3_permission_lifecycle.json` (ignored).

## Scale result

All six size/mode combinations had Recall@3 1.0, false exclusions 0, answer correctness 1.0, unsupported-answer rate 0, and citation coverage 1.0. Keyword routing reduced the mean candidate set to one third of `ROUTING_OFF`; its hard-negative candidate-inclusion rate was 0.233333 versus 1.0. Exact latency and citation-correctness values are in `docs/integration/CORPUS_SCALE_STRESS.md` and ignored `artifacts/c_gate/scale/summary.json`.

## Candidate QA

- 54 generated synthetic cases across direct, multi-document, no-answer, conflict, citation, Aggregate threshold, purpose/expiry, stale-index, and hard-negative classes.
- Development and candidate holdout are disjoint by object family, template family, and document package.
- Exact normalized near-duplicate matches: 0.
- Automated no-health hits: 0.
- Redistribution: generated synthetic / redistributable.
- Manifest hashes: config `158abdb4ff4b70bfa2df7e98d276932b89a29322c25d4100cb9d97da16dc8879`; source `982062f10046d88b4238f92f5ce9e7d8d88ebef2d0d2d5bc3c7a8e85199f07a1`.

## Limitations

- Scale retrieval is an isolated deterministic lexical/vector-proxy development runner, not a concurrent production load test.
- Citation correctness was 0.916667 at 50/250 and 0.958333 at 1000 because some correct multi-page target documents returned a non-gold page; document coverage remained 1.0. D-GATE adds a formal citation scorer.
- Candidate holdout is neither final nor frozen and was not used for tuning.
- Human annotation, manual citation audit, licence adjudication, and final no-health sign-off remain pending.

## Validation

- Inherited tests at A2: 103.
- Final C-GATE repository tests: 124 passed, 0 failed, 0 skipped, 50 dependency/deprecation warnings.
- New net tests: 21.
- `pip check`: PASS.
- `compileall`: PASS.
- import smoke without a real provider key: PASS.
- final SkipDocker gate: `PASS_WITH_PENDING_DOCKER_SMOKE` (the expected SkipDocker status).
- final Docker/MariaDB/API gate: PASS; MariaDB healthy, `/api/test-db` success, `/docs` and `/openapi.json` HTTP 200, `volume_deleted=false`.
- The first full-gate attempt exposed an OpenAPI generated-model name collision in the new permission routes. The route operation names were made unique and `test_openapi_schema_builds_with_unique_operation_models` was added before the final passing runs.
- Deterministic-mock provider smoke: PASS, network required false.
- Local-compatible provider smoke: PASS, network required false.

The C-GATE change set contains 23 source/test/documentation files:

- `.gitignore`;
- `backend_python/aggregate_executor.py`;
- `backend_python/ai_provider.py`;
- `backend_python/ai_service.py`;
- `backend_python/citds_classifier.py`;
- `backend_python/document_processing.py`;
- `backend_python/policy_engine.py`;
- `backend_python/routers/chat.py`;
- `backend_python/routers/documents.py`;
- `backend_python/routers/policy.py`;
- `backend_python/tests/test_aggregate_executor.py`;
- `backend_python/tests/test_ai_provider.py`;
- `backend_python/tests/test_policy_invariants.py`;
- `backend_python/tests/test_runtime_and_chunking.py`;
- `evaluation/c_gate.py`;
- `evaluation/tests/test_c_gate.py`;
- `scripts/run_c_gate.py`;
- `docs/integration/ANNOTATION_GUIDELINE.md`;
- `docs/integration/CORPUS_SCALE_STRESS.md`;
- `docs/integration/C_GATE_REPORT.md`;
- `docs/integration/FACTS_FOR_AUTHORS.md`;
- `docs/integration/IMPLEMENTATION_SCOPE.csv`;
- `docs/integration/PROVIDER_PORTABILITY.md`.

Generated raw results, manifests, W3 traces, and quality-gate output are under ignored `artifacts/c_gate/` and `artifacts/local_quality_gate/`; none is staged. The commit SHA is the commit containing this report and is recorded in Git history after commit creation.
