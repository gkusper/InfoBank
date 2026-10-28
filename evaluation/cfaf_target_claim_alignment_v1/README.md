# CFAF Trusted Target and Claim-Evidence Alignment

Starting commit: `d304d3e80a08c2d1c3b20dd96a5e2692c1baab22`; branch `experiment/cfaf-target-claim-alignment-v1`. Remote main was fetched as a read-only reference at `8079f29dc3a97273f51b55b2a22f9ff896a2e758`, without merge. All previous experiments and the original research branch are preserved.

Read [REPORT.md](REPORT.md), the pre-implementation [reuse assessment](CROSS_BRANCH_REUSE_REPORT.md), [target specification](TARGET_RESOLUTION_SPEC.md), [claim specification](CLAIM_EVIDENCE_ALIGNMENT_SPEC.md) and [aggregation feasibility report](AGGREGATION_REUSE_REPORT.md).

The metadata-date limitation is corrected: all seventeen original type expectations pass unchanged. Trusted catalogue resolution and claim/value provenance are more explicit. Binary accuracy does not improve over the same-input A0/B3 baseline: all configurations score 80% cached and 83.33% live. Keep T1-T3 in shadow mode. No optional T4 semantic veto or second verifier was enabled.

## Runtime and provenance

- `trusted_target_resolution.py`: authorized catalogue entries, identifier/alias/cluster resolution, native binding proofs and privileged counts.
- `claim_evidence_alignment.py`: target-scoped typed claims, structured field checks, adapted lexical/numeric diagnostics and non-pruning evidence recommendations.
- `metadata_value_typing.py`: access/attribute/value-type separation and trusted metadata binding.
- `integration_controls.py`, `integration.py`: Stage-5 shadow extensions to the unchanged eight-stage selector protocol.
- `vendor/`: selected pure source units, not full production backend imports. `remote_source_manifest.json` records all ten requested file hashes/blob IDs; `selected_reuse_manifest.json` records exact selected source-function hashes. A controlled test verifies these bodies match the inspected source.
- `aggregate_smoke_adapter.py`: isolated structured-input computation reuse; not part of RefusalBench mode scoring.

The resolver requires a fresh policy-projected request. Existing mandatory access/binding guards still run before every model call. A trusted catalogue match does not prove the user's requested relation. Free-text numbers, model confidence and LLM Boolean properties never acquire structured authority solely through matching.

## Frozen experiment

`cached_ablation_final.jsonl` contains the primary zero-call study on forty previously exposed frozen assessments. `cached_ablation.jsonl` retains the preparation replay. `pilot_runtime.jsonl` is the exact 24-case mixed subset from the preceding RDA study; `pilot_scorer_only.jsonl` is evaluator-only. No new RefusalBench record or independent student case is opened.

`experiment_manifest.json` freezes source hashes, prompts, schemas and inputs before live execution. A0/T3 and the independent shared-assessment control receive the same permitted views and one shared semantic assessment. No new target/claim diagnostics, private catalogue data, counts or gate result are sent to the control. B3/T1/T2 are gate-only ablations. Raw outputs, model requests and events are retained separately.

`ablation_results.json`, `ablation_summary.csv`, `changed_decisions.jsonl` and `target_claim_diagnostics.jsonl` record mode results and diagnostics. The empty changed-decision file means no gate changes occurred; it is an actual measured result. `metadata_type_audit.jsonl` preserves all old expected type sequences, and the new metadata-value checks extend them. `synthetic_tests_report.json`, `regression_audit.json`, `security_validation.json`, `source_role_diagnostics.json` and `api_usage.json` provide test/resource evidence.

## Reproduction and safeguards

API-free checks from repository root using the existing Python environment:

```powershell
python -m pytest evaluation/cfaf_target_claim_alignment_v1/test_target_claim.py -q
python -m evaluation.cfaf_target_claim_alignment_v1.scoring
python -m evaluation.cfaf_target_claim_alignment_v1.audit
```

Use a disposable copy to preserve committed byte checksums when recalculating derived audit/report files. Preparation, freeze and pilot refuse to overwrite existing immutable observations. A new trial requires a new namespace, explicit start/deadline, fixed exposure authorization and a fresh attempt ledger. Never reset this completed trial's clock to rerun calls.

The provider permits gpt-4o-mini only, temperature 0, one repetition, 1500 semantic-analysis output tokens and 160 generation output tokens. Existing query-only profiling can use 500 tokens if needed, but none was used in this run. The cap is 120 model API attempts; every attempt is persisted before network access. No new large implementation starts after 45 minutes, reporting takes priority at 50, no API request starts after 55, and the complete task is bounded by sixty minutes. API authentication remains external; its value is never serialized.

Historical tests run in a disposable exact-Git-blob checkout with the API key removed. Only the archived task clock is reanchored inside the test process; three byte-hash tests run against the unchanged real working files to handle CRLF/LF differences. One original CFAF test remains a known failure because it expects an already committed authorization file to be absent. The full fetched-main SQLAlchemy/router test suite was inspected where requested but not imported; selected pure mechanisms are tested locally.

`CHANGED_FILES.txt` lists the exact new files; `checksums.sha256` covers all deliverables except itself. The completion receipt outside the repository records the final commit SHA and inclusive end time. No push or merge occurs.
