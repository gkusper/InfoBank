# D-GATE development report

Controlled-failure specification: `PASS`

Scorer and run-record infrastructure: `PASS`

Deterministic contract simulation: `PASS`

Actual gold-blind B0–B3 development evaluation: `PASS`

Final frozen E1: `NOT_STARTED`

This is development evaluation on a generated, non-frozen candidate. No final dataset/scorer/config/code freeze occurred, no final E1 claim is made, and the 40-response manual citation audit remains pending human work.

The corrected actual-pipeline results are reported separately in `ACTUAL_PIPELINE_DEVELOPMENT_RESULTS.md`. They use 20 synthetic development inputs, actual isolated MariaDB/Chroma/source storage, production domain stages, a context-only deterministic provider, raw-run sealing, and post-run scoring. They do not supersede the need for human QA, candidate holdout, an approved provider run, or final E1.

## Versions and isolation

- Starting C-GATE commit: `510142c42908e2cfc7e736cda2edae3d8611a34e`.
- D runner: `infocom-d-gate-v1`.
- Controlled failure: `controlled-failure-v3`.
- Scorer: `infocom-controlled-failure-scorer-v1`.
- Citation scorer: `infocom-citation-scorer-v1`.
- Candidate: `reviewer-v2-candidate-v1`, non-final/non-frozen.
- Provider/model: `deterministic-mock` / `infobank-deterministic-v1`.
- B0/B1 database/vector paths are isolated evaluation identifiers. Production exposes only the B3 governed behavior; no B0/B1 switch exists in the production API.

## Deprecated contract-simulation calibration

Six configurations (support thresholds 0.4/0.5/0.6 crossed with minimum primary sources 1/2) were recorded by the pre-hardening simulator. Selection used exact-output conformance, then false-answer rate, reason accuracy, and config hash. Only the 27-case development split was used; candidate holdout and frozen D1–D8 v1 were not used. The helper constructed some predictions from gold output classes and reason codes, so this is contract-test evidence, not empirical calibration.

Selected config: minimum support 0.5, minimum primary sources 1, hash `3eb526bebe2f9cc879e51273df65689cc1c7313b0cc6b6fe2be143575ff136f7`. Development calibration scores: exact output conformance 1.0, reason accuracy 1.0, abstention precision/recall/F1 1.0/1.0/1.0, false-answer rate 0.0. These perfect values reflect deterministic generated templates and are not a final generalization claim.

## Deprecated B0–B3 deterministic contract simulation (54 cases per mode)

The following table is retained for provenance only. The simulator used gold output classes, reason codes, document IDs, or page ranges to construct parts of predictions, retrieval traces, or citations. Safety counters and latency/token values were also partly assigned or simulated. These numbers must not be used as system-performance estimates.

| Mode | Output conformance | Reason accuracy | Abstention F1 | Permitted accuracy | False answer | Skip rate | Citation precision | Citation coverage | P50/P95 ms | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0_VECTOR_ONLY | 0.333333 | 0.000000 | 0.000000 | 1.000000 | 0.666667 | 0.000000 | 0.333333 | 1.000000 | 0.402 / 0.402 | 4860 |
| B1_VECTOR_ROUTING | 0.333333 | 0.000000 | 0.000000 | 1.000000 | 0.666667 | 0.000000 | 0.333333 | 1.000000 | 0.436 / 0.436 | 4860 |
| B2_PERMISSION_FILTERED | 0.777778 | 0.444444 | 0.909091 | 1.000000 | 0.111111 | 0.555556 | 0.750000 | 1.000000 | 0.247 / 0.457 | 2400 |
| B3_FULL_ROLE_AWARE | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.666667 | 1.000000 | 1.000000 | 0.359 / 0.569 | 1908 |

Latencies in this table are simulated deterministic instrumentation values, not measured actual-pipeline or provider latency. Cost is 0 and retries are 0 by construction.

## Deprecated simulated citation metrics

| Mode | Support precision | Coverage | Wrong page | Unsupported claim | Invalid association | Inaccessible citation |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 0.333333 | 1.000000 | 0.555556 | 0.666667 | 0 | 0.333333 |
| B1 | 0.333333 | 1.000000 | 0.555556 | 0.666667 | 0 | 0.333333 |
| B2 | 0.750000 | 1.000000 | 0.000000 | 0.111111 | 0 | 0.000000 |
| B3 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 0 | 0.000000 |

## Deprecated simulated safety and utility

B3 counters were zero in the contract simulation, but some counters were assigned by construction rather than calculated by scanning actual produced traces. They validate expected schema/invariant behavior only.

B0/B1 intentionally disable governance in an isolated synthetic evaluation and therefore record 18 generator/source-existence/wrong-permission exposures, 6 Aggregate leaks, and 6 archived-source uses per mode. These baseline violations are the measured ablation effect; they are not reachable from production and are not represented as safe. No real protected or personal data is present.

The former B3 permitted-answer accuracy, false-answer rate, and generation-skip values are deprecated as performance claims. An actual gold-blind pipeline run must produce raw answers and traces before post-run scoring. Failure taxonomy remains: retrieval, routing, role classification, evidence threshold, output class, generation skip, generation content, citation, and scorer/parsing.

## Action/closure development

The new engine defines `ActionCandidate`, normalized action keys, request, acceptance, completion, cancellation, rejection, postponement, reminder, acknowledgement, status-update and supersession events. Linking uses relation/thread/reply first, then participant + temporal + semantic evidence; semantic similarity is secondary. States are `OPEN`, `CLOSED_COMPLETED`, `CLOSED_CANCELLED`, and `SUPERSEDED`.

The generated set contains 120 threads / 240 email messages and 60 browser-only cases. Its perfect scores are deterministic template contract results, not action-system performance estimates. A separate actual-format local MailEx transformation now produces an untracked 120-thread candidate with 120 primary and 24 second-annotation assignments; all human annotation and adjudication remain pending. The browser-only false-action invariant is covered by deterministic tests.

## Artifacts and limitations

Ignored output under `artifacts/d_gate/` includes raw JSONL, summary CSV/JSON/Markdown/LaTeX, calibration records, safety/utility/citation fields, action records, and the pending 40-row manual audit sheet. Tracked code/config/docs reproduce them.

Limitations: the historical B0–B3 runner is a gold-informed deterministic contract simulator and remains deprecated as performance evidence. A separate actual-pipeline development evaluator now exists, but its synthetic deterministic results are not final or frozen. Manual citation review, local MailEx licence approval and human action annotation, approved real-provider evaluation, and final frozen E1 remain pending.

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
