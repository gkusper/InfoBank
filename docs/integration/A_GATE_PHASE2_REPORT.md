# A-GATE Phase A2 technical report

## Status

Phase A2 implementation is complete as an uncommitted pre-commit review set on `feature/infocom-a-gate`. The pre-commit audit added one minimal controlled-failure word-boundary fix and strengthened W1/W2 regression evidence. No commit, push, merge, pull request, or release branch was part of the validation run recorded below.

## Implemented artifacts

| Area | Implementation | Deterministic evidence |
|---|---|---|
| Explicit routing modes | `backend_python/routing.py` | `backend_python/tests/test_routing.py` |
| Governance-before-routing chat flow | `backend_python/routers/chat.py` | routing invariant tests plus full suite/API gate |
| Semantic Co-occurrence Graph | `backend_python/semantic_graph.py`, `backend_python/routers/analytics.py` | `backend_python/tests/test_semantic_graph.py` |
| 12-document/24-query hard-negative corpus | `evaluation/a_gate_phase2.py` | `evaluation/tests/test_a_gate_phase2.py` |
| Routing on/off runner | `scripts/run_a_gate_phase2.py` | ignored `artifacts/a_gate_phase2/` result bundle |
| W1 owned-object onboarding | `evaluation.a_gate_phase2.run_w1` | `w1_owned_object_trace.json` |
| W2 warranty/support | `evaluation.a_gate_phase2.run_w2` | `w2_warranty_support_trace.json` |
| Scope documentation | `ROUTING_SCOPE.md`, `A_GATE_PHASE2_CORPUS.md`, `DEMO_WORKFLOWS.md` | this report and scope matrix |

## Evaluation result

The runner executed 48 records: 24 queries in `ROUTING_OFF` and the same 24 in `KEYWORD_ROUTING`. At `k=3`, both modes achieved mean Recall@3 1.000000, found rate 1.000000, mean Precision@3 0.466667, and mean target rank 1.066667 on the 15 queries with gold sources. Keyword routing reduced mean candidate-set size from 12 to 4, reduced hard-negative candidate inclusion from 1.000000 to 0.233333, and produced zero false exclusions.

The evidence-based decision is therefore `retain_as_measured_candidate_narrowing`. This decision is intentionally narrow: it applies only to governance-preserving keyword narrowing with complete permitted-corpus fallback. It makes no claim about production distributions, scale, semantic routing, learned routing, ontology quality, or scientific effectiveness.

## Workflow result

- W1 owned-object onboarding: PASS.
- W2 multi-document warranty/support: PASS.
- W2 includes explicit insufficient-evidence, conflict, and wrong-object hard-negative behavior.

## Validation record

The final focused A2 test set passed 12/12 after implementation and audit fixes. The repository-wide gates then completed on the uncommitted A2 tree:

- SkipDocker gate: `PASS_WITH_PENDING_DOCKER_SMOKE` as designed; pip check PASS, compileall PASS, 103 passed, 0 failed, 0 skipped, import smoke PASS.
- Full gate: `PASS`; pip check PASS, compileall PASS, 103 passed, 0 failed, 0 skipped, import smoke PASS.
- Docker/API smoke: PASS; MariaDB healthy, `/api/test-db` success with zero users, `/docs` HTTP 200, `/openapi.json` HTTP 200, and `volume_deleted=false`.

Machine gate records are written only to ignored `artifacts/local_quality_gate/`. Known PyMuPDF/Chroma telemetry, `python_multipart`, SQLAlchemy datetime, and SWIG deprecation warnings are non-blocking; they did not skip or fail a test.

## Pre-commit audit

- Branch and refs: local branch remains `feature/infocom-a-gate`; local HEAD and `origin/feature/infocom-a-gate` remain the A1 commit `f827e2e3efa52ca6ec2b8c831ce631d3fed39663`; `origin/main` remains `077c85c44f570c6a6b3f15edcd584f834f335ea1`.
- Git operations: no A2 commit, staging, push, merge, pull request, release branch, tag operation, force push, or branch deletion occurred.
- Diff integrity: `git diff --check` passed; the A2 change set contains only runtime source, deterministic evaluation/generation code, tests, frontend labels, scope matrix updates, ignore rules, and technical documentation.
- Secret/path scan: no API key, private-key marker, GitHub token, or user/machine absolute path was found in the tracked diff.
- Privacy scan: no medical/health scenario, patient data, real person, real receipt, real device record, private email/browser data, or research fixture was introduced.
- Provider scan: the new A2 generator, evaluator, routing, and graph modules contain no HTTP client or OpenAI/Gmail call. The run used local deterministic logic only.
- Generated-artifact scan: corpus PDFs, JSONL/JSON/CSV/Markdown run products, and quality-gate records are ignored; `git ls-files` contains none of them. Machine-readable outputs contain no absolute path.
- Assistant-data scan: no prompt, conversation transcript, assistant memory, `AGENTS.md`, active-task file, or project-status database was created.
- Preserved evidence: the external pre-main evaluation and quality-gate quarantine directories were only listed read-only and were not modified.

## Deliberate exclusions and remaining limitations

- No real OpenAI, Gmail, browser-history, or other private service was called.
- No frozen D1–D8/MailEx/WoLaLa reviewer data or result was read, copied, or modified.
- No health scenario or health-data fixture was introduced.
- The generated corpus and results are ignored; only generators, schemas, tests, and technical documentation are tracked.
- The graph is a visualization-only keyword co-occurrence graph, not an ontology.
- The local lexical evaluator is deterministic and provider-free; it does not validate the live embedding model.
- Sub-millisecond latency measurements are machine-specific and are retained only in the generated run bundle.
- Final reviewer evaluation, production scale tests, and Review D B0–B3 ablations remain outside A-GATE Phase A2.
