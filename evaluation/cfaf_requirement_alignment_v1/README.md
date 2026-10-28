# CFAF Requirement Decomposition and Alignment development experiment

Starting commit: `c2ae2f5b8d5c210edbdf242c3d060efcbe8a798b`. New branch: `experiment/cfaf-requirement-alignment-v1`. The prior RECV study and all 848 earlier tracked files are preserved. The original `wolala2026` branch is unchanged.

Read [REPORT.md](REPORT.md), [RDA_SPEC.md](RDA_SPEC.md) and [HARD_SOFT_VERIFICATION_SPEC.md](HARD_SOFT_VERIFICATION_SPEC.md).

The experiment repairs the generic multipart person/count representation and prevents the previous strict type check from discarding that complete answer. B3 preserves A0's correct FULL decisions but does not improve A0's accuracy. It also retains A0's unsupported historical-priority FULL in shadow mode. B3 should remain experimental/shadow-only. A separate synthetic audit retains a metadata value-type limitation: 17/17 expected requirement counts, 16/17 expected type sequences.

## Implementation

- `requirement_decomposition.py`: existing-profile enrichment, exact query provenance, stable output obligations, dependencies and explicit/inferred qualifiers.
- `requirement_alignment.py`: per-requirement fragment proposals and exact candidate offsets, authorized evidence references, proposed entity/quantity relationships.
- `rec_v2.py`: four-valued coverage, hard versus soft authority, unchanged source registry applied per requirement, B1 comparator, B2/B3 and specific reasons.
- `integration.py`: internal Stage-1 enrichment and Stage-5 RDA/RECV subcomponents; original eight stages, selector, semantic analyzer prompt/schema and generation contracts retained.
- `provider.py`, `deadline.py`, `runner.py`: frozen shared-assessment execution, disabled second verifier/B4, 120-attempt ledger and 60-minute task bound.

A0 is v02 without RECV enforcement. B1 is the previous strict combined RECV. B2 uses RDA and hard constraints. B3 adds shadow semantic diagnostics and has the same mode policy as B2. B4 is not executed. Existing independent v02 sufficiency/permission requirements remain mandatory; B2/B3 cannot promote an A0 refusal.

## Evidence and results

`cached_ablation_final.jsonl` is the primary forty-case zero-API comparison. `pilot_observations.jsonl`, `api_requests.jsonl` and `api_events.jsonl` retain all raw live observations from the fixed 24-case pilot. Every compared system shares the same upstream semantic JSON. B2 is gate-only; A0/B1/B3 and the independent prompt control have live public generations.

`ablation_results.json`, `ablation_summary.csv`, `changed_decisions.jsonl`, `B3_vs_B1_changes.jsonl` and `requirement_diagnostics.jsonl` contain scorer-only results and attribution. `qualitative_review.jsonl` is a scoped, non-independent review. Original labels remain unchanged. Natural benchmark requirement completeness and alignment entailment do not have independent gold annotations.

`experiment_manifest.json` freezes final code, prompts, schemas and selection before the first live call. `pre_api_freeze_initial.json` and `pre_api_cached_initial.jsonl` retain an earlier zero-API preflight before the final reason-priority/numeric-name interpretation adjustments; they are not another live experiment. Final cached gate decisions did not change. Runtime source remains unchanged throughout the live trial.

`synthetic_decomposition_cases.jsonl` preserves seventeen additional authored structural cases and their original expectations. Its exact-type audit intentionally exits nonzero for the retained created_at/METADATA-versus-DATE_TIME mismatch after persisting results; this is a reported experimental limitation, not a silently repaired expected label. The two metadata fields are still separate and the created_at field is retained. Unit/regression tests and the separate synthetic audit are reported distinctly.

## API-free reproduction

From the repository root, use the existing Python/test environment:

```powershell
python -m pytest evaluation/cfaf_requirement_alignment_v1/test_rda.py -q
python -m evaluation.cfaf_requirement_alignment_v1.scoring
python -m evaluation.cfaf_requirement_alignment_v1.audit
```

Scoring/audit use frozen observations and make no model call; derived files may be rewritten, so use a disposable copy to retain original byte checksums. Historical tests run in an exact-Git-blob disposable checkout. `regression_environment.py` reanchors only the archived task clock in the test process and runs three byte-hash checks on the unchanged real working files. This handles expired-clock and CRLF/LF snapshot artifacts without changing historical code or results.

The original CFAF suite still has one known failure: a test expects an already committed `HELDOUT_RUN_AUTHORIZATION.json` to be absent. It is retained and identified separately from new regressions.

## Live safeguards

Preparation/freeze/pilot refuse to overwrite their existing immutable inputs or observations. A fresh trial requires a new namespace, explicit task start/deadline and a new durable attempt ledger. Do not reset this experiment's clock or delete its observations to rerun it. API authentication is supplied externally through `OPENAI_API_KEY`; its value is never serialized.

The provider permits only gpt-4o-mini, temperature 0, one repetition, 1500 analysis tokens and 160 generation tokens. Existing query-only profiling can use 500 tokens, but no such fallback was needed in this run. Focused second-pass verification and embeddings are disabled. Every external attempt is persisted before network access. The cap is 120 attempts; no request starts after 55 minutes, and the hard task bound is sixty minutes.

Only already-exposed RefusalBench cases and original synthetic InfoBank cases were used. The inherited exposure ledger remains unchanged at 130 eligible exposed and 1104 unseen. Thirty reserved and eighteen further untouched source groups and student-created independent cases were not inspected.

`CHANGED_FILES.txt` and `checksums.sha256` provide the committed inventory and exact artifact checksums. The final commit SHA and inclusive end time are recorded in the completion receipt outside the repository and returned to the user; no push or merge is performed.
