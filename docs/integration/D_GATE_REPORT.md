# D-GATE development report

Status: `PASS_WITH_LIMITATIONS`

This is development evaluation on a generated, non-frozen candidate. No final dataset/scorer/config/code freeze occurred, no final E1 claim is made, and the 40-response manual citation audit remains pending human work.

## Versions and isolation

- Starting C-GATE commit: `510142c42908e2cfc7e736cda2edae3d8611a34e`.
- D runner: `infocom-d-gate-v1`.
- Controlled failure: `controlled-failure-v3`.
- Scorer: `infocom-controlled-failure-scorer-v1`.
- Citation scorer: `infocom-citation-scorer-v1`.
- Candidate: `reviewer-v2-candidate-v1`, non-final/non-frozen.
- Provider/model: `deterministic-mock` / `infobank-deterministic-v1`.
- B0/B1 database/vector paths are isolated evaluation identifiers. Production exposes only the B3 governed behavior; no B0/B1 switch exists in the production API.

## Development calibration

Six configurations (support thresholds 0.4/0.5/0.6 crossed with minimum primary sources 1/2) were all recorded. Selection used exact-output conformance, then false-answer rate, reason accuracy, and config hash. Only the 27-case development split was used; candidate holdout and frozen D1–D8 v1 were not used.

Selected config: minimum support 0.5, minimum primary sources 1, hash `3eb526bebe2f9cc879e51273df65689cc1c7313b0cc6b6fe2be143575ff136f7`. Development calibration scores: exact output conformance 1.0, reason accuracy 1.0, abstention precision/recall/F1 1.0/1.0/1.0, false-answer rate 0.0. These perfect values reflect deterministic generated templates and are not a final generalization claim.

## B0–B3 development results (54 cases per mode)

| Mode | Output conformance | Reason accuracy | Abstention F1 | Permitted accuracy | False answer | Skip rate | Citation precision | Citation coverage | P50/P95 ms | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0_VECTOR_ONLY | 0.333333 | 0.000000 | 0.000000 | 1.000000 | 0.666667 | 0.000000 | 0.333333 | 1.000000 | 0.402 / 0.402 | 4860 |
| B1_VECTOR_ROUTING | 0.333333 | 0.000000 | 0.000000 | 1.000000 | 0.666667 | 0.000000 | 0.333333 | 1.000000 | 0.436 / 0.436 | 4860 |
| B2_PERMISSION_FILTERED | 0.777778 | 0.444444 | 0.909091 | 1.000000 | 0.111111 | 0.555556 | 0.750000 | 1.000000 | 0.247 / 0.457 | 2400 |
| B3_FULL_ROLE_AWARE | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.666667 | 1.000000 | 1.000000 | 0.359 / 0.569 | 1908 |

Latencies are deterministic stage-instrumentation values for the local mocked pipeline, not external-provider or production-load timings. Cost is 0 and retries are 0 in every mode.

## Citation metrics

| Mode | Support precision | Coverage | Wrong page | Unsupported claim | Invalid association | Inaccessible citation |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 0.333333 | 1.000000 | 0.555556 | 0.666667 | 0 | 0.333333 |
| B1 | 0.333333 | 1.000000 | 0.555556 | 0.666667 | 0 | 0.333333 |
| B2 | 0.750000 | 1.000000 | 0.000000 | 0.111111 | 0 | 0.000000 |
| B3 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 0 | 0.000000 |

## Safety and utility

B3 counts are zero for prohibited disclosure, generator exposure, Aggregate individual leakage, source-existence leakage, protected local paths, wrong-permission citations, and archived-source use. B2 is also zero on those counters.

B0/B1 intentionally disable governance in an isolated synthetic evaluation and therefore record 18 generator/source-existence/wrong-permission exposures, 6 Aggregate leaks, and 6 archived-source uses per mode. These baseline violations are the measured ablation effect; they are not reachable from production and are not represented as safe. No real protected or personal data is present.

B3 permitted-answer accuracy is 1.0 (development target >=0.80 met), false/unsupported-answer rate 0, and generation-skip rate 0.666667. Failure taxonomy is: retrieval, routing, role classification, evidence threshold, output class, generation skip, generation content, citation, and scorer/parsing.

## Action/closure development

The new engine defines `ActionCandidate`, normalized action keys, request, acceptance, completion, cancellation, rejection, postponement, reminder, acknowledgement, status-update and supersession events. Linking uses relation/thread/reply first, then participant + temporal + semantic evidence; semantic similarity is secondary. States are `OPEN`, `CLOSED_COMPLETED`, `CLOSED_CANCELLED`, and `SUPERSEDED`.

The generated set contains 120 threads / 240 email messages and 60 browser-only cases. Results: open-action accuracy 1.0, closure/linking accuracy 1.0, overall status accuracy 1.0, action precision/recall/F1 1.0/1.0/1.0, browser-only false actions 0. MailEx was not available/used in this development run; data is marked generated synthetic and redistributable. Perfect scores reflect the controlled templates and are not frozen-benchmark claims.

## Artifacts and limitations

Ignored output under `artifacts/d_gate/` includes raw JSONL, summary CSV/JSON/Markdown/LaTeX, calibration records, safety/utility/citation fields, action records, and the pending 40-row manual audit sheet. Tracked code/config/docs reproduce them.

Limitations: generated templates are simpler than natural provider output and real email; latency/cost are mocked local measurements; manual citation review is incomplete; MailEx licensing/source selection and human action annotation remain pre-freeze tasks; candidate holdout is non-frozen. Scale stress remains the C-GATE 50/250/1000 run and is not rerun inside each B mode.

## Validation

- Inherited C-GATE tests: 124.
- Final D-GATE repository tests: 135 passed, 0 failed, 0 skipped, 50 dependency/deprecation warnings.
- New net tests: 11.
- Standalone controlled-failure self-test: PASS.
- Final SkipDocker gate: `PASS_WITH_PENDING_DOCKER_SMOKE` (expected SkipDocker status).
- Final Docker/MariaDB/API gate: PASS; MariaDB healthy, database smoke success, `/docs` and `/openapi.json` HTTP 200, `volume_deleted=false`.
- `pip check`, `compileall`, and keyless import smoke: PASS.
- 50/250/1000 C scale stress rerun: PASS, zero false exclusions, no final-E1 claim.
- No-health scan of generated D artifacts: 0 hits.
- Local-path scan of generated D artifacts: 0 hits.
- Production-module scan for `B0_VECTOR_ONLY`/`B1_VECTOR_ROUTING`: 0 hits.
- Generated D output and quality-gate output are ignored; frozen D1–D8/CogInfoCom/MailEx/WoLaLa artifacts were not modified.

The D-GATE commit contains 14 source/config/test/documentation files:

- `.gitignore`;
- `backend_python/action_closure.py`;
- `backend_python/config/controlled_failure_v3.json`;
- `backend_python/controlled_failure.py`;
- `backend_python/controlled_failure_config.py`;
- `backend_python/tests/test_action_closure.py`;
- `docs/CONTROLLED_FAILURE_IMPLEMENTATION.md`;
- `docs/integration/CITATION_AUDIT_GUIDE.md`;
- `docs/integration/CONTROLLED_FAILURE_SPEC.md`;
- `docs/integration/D_GATE_REPORT.md`;
- `docs/integration/IMPLEMENTATION_SCOPE.csv`;
- `evaluation/d_gate.py`;
- `evaluation/tests/test_d_gate.py`;
- `scripts/run_d_gate.py`.

The commit SHA is the commit containing this report and is recorded in Git history after commit creation.
