# CFAF Request-Evidence Verification development experiment

This directory contains the Stage-5b RECV implementation, source-capability registry, strict tests, frozen ablations, raw API observations and report. It starts from committed iterative CFAF v02, commit `f33e99218702338afca0dae03e8fea2ea92282fa`, on the new branch `experiment/cfaf-request-evidence-verification-v1`.

Read [REPORT.md](REPORT.md) for results and limitations, [RECV_SPEC.md](RECV_SPEC.md) for the verifier contract, and [SOURCE_CAPABILITY_RULES.md](SOURCE_CAPABILITY_RULES.md) for source rules and trust boundaries.

The primary results are **negative for unconditional default deployment**: the cached analysis trades one false FULL prevention for one correct FULL loss; the live pilot loses one correct FULL without preventing an additional false FULL. Source rules change no live decision. The optional trigger scan finds no eligible second-pass case. These are exposed development observations, not independent validation.

## Files and workflow

- `request_evidence_coverage.py`, `source_capability_rules.py`, `decision.py`, `integration.py`: runtime implementation. The original mode selector is imported unchanged.
- `focused_verification.py`: optional targeted opinion with bound attestations and frozen trigger conditions; no live verifier call was triggered.
- `prepare.py`, `selection_manifest.json`, `pilot_runtime.jsonl`: already-exposed inputs and selection provenance. `pilot_scorer_only.jsonl` is evaluator-only and is never imported by runtime execution.
- `experiment_manifest.json`: frozen prompts, schemas, code/input hashes, model settings and trigger policy.
- `cached_ablation_final.jsonl`: primary zero-API comparison on forty frozen v02 semantic assessments. `cached_ablation.jsonl` retains the initial API-free dry run before a trace-only missing-span/source distinction and requirement-relation annotation were refined; its gate decisions are unchanged.
- `pilot_observations.jsonl`, `api_requests.jsonl`, `api_events.jsonl`: all raw live observations and network attempts. Pipeline completion does not imply valid semantic acceptance; scoring rejects two incomplete source-role assessments.
- `optional_observations.jsonl`: actual trigger-scan/reuse records. Every row explicitly reuses B; there are no fabricated focused model outputs.
- `ablation_results.json`, `ablation_summary.csv`, `changed_decisions.jsonl`, `coverage_diagnostics.jsonl`: scorer-only comparison and diagnostics. A1/A2 have no separately generated public answer.
- `api_usage.json`, `security_validation.json`, `source_role_diagnostics.json`, `regression_audit.json`: measured resource use and mechanical audits.
- `qualitative_review.jsonl`: scoped, non-independent evidence review; it does not alter labels or primary metrics.
- `unit_tests.xml`, `final_regression_tests.xml`, `current_worktree_hash_tests.xml`, `historical_cfaf_tests.xml`: test evidence. Earlier unadjusted outputs are retained to explain environment-dependent failures.
- `CHANGED_FILES.txt`, `checksums.sha256`: committed deliverable inventory and byte checksums. `.gitattributes` preserves exact new artifact bytes.

## API-free checks

From the repository root, using an installed Python environment with the existing project test dependencies:

```powershell
python -m pytest evaluation/cfaf_request_evidence_verification_v1/test_verification.py -q
python -m evaluation.cfaf_request_evidence_verification_v1.scoring
python -m evaluation.cfaf_request_evidence_verification_v1.audit
```

Scoring and audit read the frozen observations and write only this experiment's derived audit files. They make no model calls. The historical suites use a disposable exact-Git-blob checkout through `regression.py`; `regression_environment.py` reanchors only the archived task clock inside the test process and runs two working-byte hash checks on the unchanged original files. This avoids both expired-clock false failures and LF/CRLF snapshot artifacts. No historical source or result is rewritten.

A single known original CFAF test remains red because it expects an already committed `HELDOUT_RUN_AUTHORIZATION.json` to be absent. The report separates it from new regressions.

## Live execution safeguards

The committed trial is immutable: preparation, freeze, pilot and optional execution refuse to overwrite existing observations. A new trial requires a separate experiment namespace, a new explicit start/deadline, frozen inputs and a fresh attempt ledger. Do not reset this trial's clock or remove its observations to rerun it. Model calls require an externally configured `OPENAI_API_KEY`; the key is never serialized.

The provider fixes gpt-4o-mini, temperature 0, one repetition, 1500 semantic-analysis output tokens, 160 generation tokens and at most 500 query-profile/focused-verifier tokens. Every network attempt is durably recorded before the request, including failures. The hard cap is 170 attempts; no new request starts after 55 minutes and the task stops by 60 minutes. Embeddings and stronger models are disabled.

No new RefusalBench record was exposed. The inherited ledger remains 130 eligible exposed out of 1234, with 1104 unseen; thirty reserved and eighteen further untouched source groups remain protected. The original forty synthetic InfoBank cases are development material. Student-created independent cases were not opened.
