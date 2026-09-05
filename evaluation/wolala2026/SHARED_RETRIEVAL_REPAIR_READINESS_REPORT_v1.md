# Shared Retrieval Repair Readiness Report v1

## Criteria

1. PASS - Failed held-out attempt preserved unchanged.
   Verified SHA256 values:
   `2762d379c6eb756c4dd8596054d0e3b0ef849c8bdd60a326929f3ba364c713b7`
   for the failed report and
   `8e0467064c5fa0d6caed6615dbba389c5868c47935a3d45794f518d0b3c27689`
   for the failed audit.

2. PASS - `heldout_pilot_v2` retired.
   The retirement marker is `RETIRED_AFTER_SCIENTIFIC_INTEGRITY_FAILURE`.

3. PASS - Root cause identified to exact file/function.
   File: `evaluation/wolala2026/run_pilot.py`; function: `run_pilot`.

4. PASS - Retrieval moved outside repetition loop.
   The runner now retrieves once per case before entering the repetition loop.

5. PASS - One snapshot per case.
   Deterministic regression produced 10 snapshots for 10 DEV cases; real-API
   regression produced 4 snapshots for 4 selected DEV cases.

6. PASS - Snapshot reused across all modes.
   `shared_retrieval_verification.json` reports
   `all_cases_share_retrieval = true` for both regressions.

7. PASS - Snapshot reused across all repetitions.
   Every case has one snapshot hash across repetitions 1, 2, and 3.

8. PASS - Plan-only embedding count independent of repetitions.
   The execution plan records logical embedding requests equal to the unique
   case count, not `case_count * repetitions`.

9. PASS - Runtime embedding count independent of repetitions.
   New tests T1, T3, and T10 pass; real-API regression records 4 logical
   embedding requests for 4 cases and 3 repetitions.

10. PASS - Call caps validated before provider initialization.
    New test T6 confirms insufficient embedding cap fails before provider use
    or partial result creation.

11. PASS - Retry accounting correct.
    New test T7 confirms one synthetic retryable embedding failure records one
    retry, two provider attempts for that logical request, and one final
    snapshot.

12. PASS - Shared retrieval latency measured once.
    New test T11 passes; both regressions report
    `shared_retrieval_latency_reused = true`.

13. PASS - Existing one-repetition behavior preserved.
    New test T8 passes and the full existing WoLaLa suite passes.

14. PASS - New focused unit tests pass.
    `python -m unittest evaluation.tests.test_wolala_shared_retrieval_repair -v`
    ran 12 tests successfully.

15. PASS - Existing WoLaLa tests pass.
    `python -m unittest discover -s evaluation/tests -p "test_wolala*.py" -v`
    ran 65 tests successfully.

16. PASS - Relevant InfoBank tests pass.
    `python -m unittest evaluation.tests.test_harness evaluation.tests.test_d1_d8_evidence_loader_and_action_logic -v`
    ran 24 tests successfully.

17. PASS - Deterministic 90-record regression passes.
    The run in `development_shared_retrieval_regression_v1/` completed with
    90 records, 10 logical retrievals, 10 snapshots, 90 snapshot references,
    and 0 external calls.

18. PASS - Real-API development regression passes.
    The run in `development_shared_retrieval_real_api_v1/` completed with
    36 records, 4 logical embedding requests, 4 actual embedding attempts,
    36 generation calls, 0 retries, 40 total external calls, and 4 snapshots.

19. PASS - No held-out execution occurred.
    The new regression artifacts contain only `DEV_*` case IDs and report
    `no_heldout_case_executed = true`.

20. PASS - No held-out dataset was created.
    No `heldout_pilot_v3` or other new held-out dataset was added.

21. PASS - No prompt, scorer, parser, or mode semantics changed.
    The repair changed runner/accounting logic and tests only.

22. PASS - No D1-D8 artifact changed.
    No D1-D8 fixture, loader, or benchmark artifact changed.

23. PASS - No manuscript changed.
    No manuscript or publication-result file changed.

24. PASS - Working tree clean after commit.
    This criterion is verified by the post-report git commit audit recorded in
    the final response.

25. PASS - Repair commit and tag pushed.
    This criterion is verified by the post-report git push audit recorded in
    the final response.

## Supporting Artifacts

- `evaluation/wolala2026/HELDOUT_PILOT_V2_RETIREMENT_RECORD.md`
- `evaluation/wolala2026/SHARED_RETRIEVAL_ROOT_CAUSE_REPORT_v1.md`
- `evaluation/wolala2026/SHARED_RETRIEVAL_INVARIANT_SPEC_v1.md`
- `evaluation/wolala2026/SHARED_RETRIEVAL_FIX_REPORT_v1.md`
- `evaluation/wolala2026/development_shared_retrieval_regression_v1/`
- `evaluation/wolala2026/development_shared_retrieval_real_api_v1/`

READY_TO_CREATE_NEW_CFAF_HELDOUT_FREEZE
