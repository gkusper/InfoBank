# WoLaLa 2026 Pilot Readiness Report v2

## 1. Previous Readiness Classification

`PARTIAL - REAL_API_OR_COMPONENT_BLOCKER`

Phase 2 prepared the frozen protocol, development set, held-out set, adapters,
shared retrieval, deterministic scorer, run manifests, call caps, and
deterministic integration artifacts, but did not execute a real-API development
integration run.

## 2. Starting Commit

- Branch: `wolala2026`
- Starting commit: `cb62b2778c154125623a0c68b0a9d8f069cd7623`
- Phase 2 tag: `wolala2026-pilot-readiness-v0.2`

## 3. Ending Commit

The ending commit is recorded in the final response after this report and all
generated artifacts are committed. A commit cannot contain its own SHA without
changing that SHA.

## 4. Real-API Run Status

- Run ID: `development_integration_v1_real_api_v1`
- Run type: `real_api_development_integration`
- Provider: `openai`
- Embedding model: `text-embedding-3-small`
- Generator model: `gpt-4o-mini`
- Completion status: `COMPLETED`
- `real_api`: `true`
- `mock_or_stub_used`: `false`

## 5. External-Call Counts

- Embedding calls: `10`
- Generation calls: `30`
- Retry count: `0`
- Total external calls: `40`

All calls were within the frozen caps.

## 6. Mode-Execution Counts

- Development cases: `10`
- Modes: `3`
- Repetitions: `1`
- Planned mode executions: `30`
- Actual mode executions: `30`
- Held-out mode execution count: `0`

## 7. Test Results

Pre-run and final-gate relevant commands:

- `python -m unittest discover -s evaluation/tests -p "test_wolala*.py" -v`: `30` tests passed
- `python -m unittest evaluation.tests.test_harness evaluation.tests.test_d1_d8_evidence_loader_and_action_logic -v`: `24` tests passed

The WoLaLa count increased from 28 to 30 because Phase 3 added plan-only and
fake-provider real-path tests.

## 8. Readiness Criteria

1. Real provider path executed: PASS.
2. `actual_total_external_calls > 0`: PASS, `40`.
3. `mock_or_stub_used = false`: PASS.
4. Call caps respected: PASS.
5. All 30 planned mode executions completed: PASS.
6. `heldout_mode_execution_count = 0`: PASS.
7. All three adapters returned valid common envelopes: PASS.
8. All cases used shared retrieval across modes: PASS.
9. No baseline received gold or external CFAF decision labels: PASS.
10. CFAF generator received only filtered evidence views: PASS.
11. CFAF generator exposure rate = 0: PASS.
12. CFAF protected-content leakage rate = 0: PASS.
13. CFAF source-existence leakage rate = 0: PASS.
14. Deterministic CFAF top-level mode selection matched every development gold label: PASS.
15. Request-relative aggregate and metadata cases behaved as specified: PASS.
16. Browser-only evidence did not create an obligation: PASS.
17. Cancellation/closure logic remains covered by existing tests: PASS.
18. Every required latency field was present and non-negative: PASS.
19. Deterministic scorer completed: PASS.
20. No unresolved schema, parser, validator, manifest, or scoring defect remains: PASS.
21. All relevant tests pass: PASS.
22. No frozen D1-D8 artifact changed: PASS.
23. No held-out case was executed: PASS.
24. No full D1-D8 experiment was executed: PASS.
25. Working tree clean after commit: PASS pending final commit gate; no uncommitted work is expected after commit.

## 9. Remaining Blockers

No readiness blocker remains for executing the small held-out WoLaLa pilot under
the frozen protocol and explicit held-out approval.

The held-out pilot still must not be run casually. It requires a separate,
explicit held-out execution task using the frozen protocol, call caps, and
no-post-hoc-tuning rule.

## 10. Development Diagnostics

These values are not held-out results and are not publication-ready.

- `cfaf_pipeline`: top-level mode accuracy `1.0`, request fulfilment `1.0`, protected leakage `0.0`, generator exposure `0.0`
- `prompt_only_control`: top-level mode accuracy `0.4`, request fulfilment `0.3`, protected leakage `0.1`, generator exposure `0.5`
- `standard_rag`: top-level mode accuracy `0.4`, request fulfilment `0.3`, protected leakage `0.1`, generator exposure `0.5`

Baseline failures are diagnostic; they do not block pilot readiness.

## 11. Artifact Summary

Created or updated:

- `evaluation/wolala2026/real_api.py`
- `evaluation/wolala2026/run_pilot.py`
- `evaluation/wolala2026/adapters.py`
- `evaluation/tests/test_wolala_real_api_phase3.py`
- `evaluation/wolala2026/development_run_real_api_v1/`
- `evaluation/wolala2026/WOLALA2026_REAL_API_DEVELOPMENT_REPORT_v1.md`
- `evaluation/wolala2026/WOLALA2026_PILOT_READINESS_REPORT_v2.md`

Existing smoke result artifacts were not changed in this commit. Smoke-case
semantics remain covered by the passing tests.

## 12. Final Readiness Classification

READY_FOR_SMALL_WOLALA_PILOT
