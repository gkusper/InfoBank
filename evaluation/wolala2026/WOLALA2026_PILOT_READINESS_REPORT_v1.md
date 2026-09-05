# WoLaLa 2026 Pilot Readiness Report v1

## 1. Starting Branch And Commit

- Branch: `wolala2026`
- Starting commit: `1f7c7adbd91a539cd6eb0c05513cec85c11c6875`
- Previous tag present locally: `wolala2026-readiness-v0.1`

## 2. Ending Commit

The ending commit is recorded in the final response after this report and all
generated artifacts are committed. A commit cannot contain its own SHA without
changing that SHA.

## 3. Previous Readiness Status

Previous WoLaLa readiness classification:

`PARTIAL - MISSING_DATA_OR_COMPONENTS`

Phase 1 had an explicit eight-stage CFAF pipeline, serializable state,
structured labels, smoke tests, traces, latency fields, and a readiness report,
but not yet a frozen small pilot protocol, held-out pilot dataset, real adapter
envelopes, run manifest, or scorer.

## 4. Current Architecture Status

The original eight-stage pipeline remains explicit in `pipeline.py`:

1. `QUERY_PROFILING`
2. `CANDIDATE_RETRIEVAL`
3. `ACCESS_AND_SAFETY_RESOLUTION`
4. `EVIDENCE_LABELLING`
5. `SUFFICIENCY_AND_PERMITTED_OUTPUT`
6. `TOP_LEVEL_MODE_SELECTION`
7. `RESPONSE_REALIZATION`
8. `VALIDATION_TRACE_AND_FEEDBACK`

Phase 2 adds shared retrieval snapshots, three functional adapters, a capped
runner, deterministic scorer, frozen prompts, frozen development and held-out
datasets, run manifests, and development-run artifacts. Production API code and
frozen D1-D8 artifacts were not changed.

## 5. Protocol Version And Checksum

- Protocol: `WOLALA2026_PILOT_PROTOCOL_v1.md`
- SHA-256: `91c6e3279821abdd0c5b92006a4ce572293fc5ed29a77e7edbf5d1b47147f93e`

The protocol was written before any held-out model execution. No held-out model
outputs were viewed or generated.

## 6. Development Dataset

- Path: `evaluation/wolala2026/data/development_integration_v1/`
- Cases: 10
- Pairs: 5
- Families: P1-P5, one pair per family
- Dataset checksum: `df847ef72fa28e55277f153989add2cf94b06471f1ff068cae4bbf15cc95f0f4`
- Files: `cases.jsonl`, `gold.jsonl`, `manifest.json`, `provenance.csv`,
  `checksums.sha256`, `README.md`

All cases are deterministic synthetic records with no personal, health,
credential, or private e-mail data.

## 7. Held-Out Dataset

- Path: `evaluation/wolala2026/data/heldout_pilot_v1/`
- Cases: 40
- Pairs: 20
- Families: P1-P5, four pairs per family
- Dataset checksum: `b86ddfa2a3db79a5d9e3e31b57000f1619f790040a6d9d814970ea2d1f54031b`
- Files: `cases.jsonl`, `gold.jsonl`, `manifest.json`, `provenance.csv`,
  `checksums.sha256`, `README.md`

Held-out cases were schema/checksum/provenance validated only. They were not
executed through Standard RAG, prompt-only control, or the CFAF generator.

## 8. No-Overlap Proof

Recorded in `readiness_baseline_manifest.json`:

- `case_id_overlap`: `[]`
- `pair_id_overlap`: `[]`
- `protected_marker_overlap`: `[]`

The held-out set uses `HELD_*` IDs, held-out source text, held-out query wording,
held-out titles, held-out evidence-unit IDs, held-out thread IDs, and held-out
canary markers distinct from both the 13 smoke cases and the 10 development
cases.

## 9. Adapter Implementation Summary

`standard_rag` receives only the user query and raw synthetic retrieved
candidates.

`prompt_only_control` receives the same raw retrieved candidates plus
`prompts/prompt_only_v1.txt`; it does not receive external CFAF gate labels,
gold mode, gold reason, response contracts, or internal traces.

`cfaf_pipeline` calls the explicit eight-stage pipeline and passes only the
response contract plus permitted evidence views to realization.

All adapters return the common result envelope required by the protocol.

## 10. Shared Retrieval Proof

Each case is retrieved once by `retrieval.py`, producing a snapshot with query,
candidate IDs, candidate order, raw experimental text, metadata, retrieval
scores, retriever version, and snapshot hash.

The Phase 2 tests assert that all three mode results for a case have exactly one
shared `retrieval_snapshot_hash`.

## 11. Scorer Implementation Summary

`score_pilot.py` is deterministic and uses no LLM judge. It produces:

- per-case scores;
- per-pair scores;
- per-family summaries;
- per-mode summaries;
- diagnostic confusion matrix;
- latency summaries;
- model-call counts;
- machine-readable JSON;
- `summary.csv`;
- `summary_table.tex`.

It scores top-level mode accuracy, false-CFAF, request fulfilment, CFAF
realization, protected leakage, generator exposure, source-existence leakage,
safe next steps, public reason class, fallback correctness, latency, and model
calls.

## 12. Run Manifest And Call Caps

`run_manifest_schema.json` defines the required manifest fields. The runner
refuses execution if requested mode executions or estimated external calls exceed
configured caps. It also refuses held-out execution unless an explicit held-out
approval flag is supplied.

Development integration caps used:

- `max_mode_executions = 30`
- `max_embedding_calls = 10`
- `max_generation_calls = 30`
- `max_total_external_calls = 40`
- `temperature = 0`
- `max_output_tokens = 160`

## 13. Deterministic Integration Results

Command:

```powershell
python -m evaluation.wolala2026.run_pilot --dataset development_integration_v1 --modes standard_rag,prompt_only_control,cfaf_pipeline --repetitions 1 --max-mode-executions 30 --max-embedding-calls 10 --max-generation-calls 30 --max-total-external-calls 40
```

Result:

```json
{"completion_status": "COMPLETED", "mode_execution_count": 30}
```

Artifacts are in `evaluation/wolala2026/development_run/`.

Mode summaries are diagnostic development-integration values only:

| Mode | Mode accuracy | Fulfilment accuracy | Protected leakage | Generator exposure |
| --- | ---: | ---: | ---: | ---: |
| `cfaf_pipeline` | 1.0 | 1.0 | 0.0 | 0.0 |
| `prompt_only_control` | 0.9 | 0.8 | 0.2 | 0.5 |
| `standard_rag` | 0.7 | 0.6 | 0.3 | 0.5 |

These are not publication-ready empirical results.

## 14. Real-API Development Integration

Not executed. `OPENAI_API_KEY` was visible in the environment, but the explicit
`--allow-real-api` flag was not supplied. The protocol and runner require that
flag before any real external calls.

Real-API development integration remains a blocker before claiming full pilot
readiness.

## 15. Execution And External-Call Counts

- Mode executions: 30
- Actual embedding calls: 0
- Actual generation calls: 0
- Actual total external calls: 0
- Held-out mode execution count: 0

## 16. Held-Out Non-Execution Proof

`development_run/raw_results.jsonl` contains only `DEV_*` case IDs.

`heldout_mode_execution_count = 0` is recorded in:

- `readiness_baseline_manifest.json`
- `data/heldout_pilot_v1/manifest.json`
- `development_run/run_manifest.json`

The runner was tested to raise an error for held-out execution without explicit
held-out approval.

## 17. D1-D8 Non-Execution Proof

No full D1-D8 command was run. No frozen D1-D8 publication result,
preregistration, manifest, or tag was modified. The only existing InfoBank tests
run were fast unit tests:

- `evaluation.tests.test_harness`
- `evaluation.tests.test_d1_d8_evidence_loader_and_action_logic`

## 18. Protected-Content And Generator-Exposure Checks

The scorer measures protected-content leakage in public responses and protected
marker exposure in generator-visible context. For `cfaf_pipeline`, the
development run produced:

- protected-content leakage rate: 0.0
- generator-exposure rate: 0.0

Baseline modes intentionally show diagnostic failures on some governance cases,
which confirms the scorer is measuring these risks.

## 19. Source-Existence Pair Checks

P5 pairs require equal normalized public responses for no-source and
internal-only-inaccessible-source variants. The Phase 2 tests assert for
`cfaf_pipeline`:

- public response equality;
- no hidden source title, ID, type, or marker in public response;
- no source-existence leakage flag.

Internal traces differ by construction.

## 20. Latency Instrumentation

All result envelopes include:

- eight top-level stage timings;
- `embedding_api_ms`;
- `generation_api_ms`;
- `external_api_ms`;
- `end_to_end_ms`;
- token usage;
- model-call counts.

All durations are non-negative. Development P50/P95 latency summaries are
diagnostic only and marked not publication-ready.

## 21. Test Commands And Results

WoLaLa tests:

```powershell
python -m unittest discover -s evaluation\tests -p "test_wolala*.py" -v
```

Result: 28 tests passed.

Relevant fast InfoBank tests:

```powershell
$env:PYTHONPATH = '..\pydeps'
python -m unittest evaluation.tests.test_harness evaluation.tests.test_d1_d8_evidence_loader_and_action_logic -v
```

Result: 24 tests passed. The `pydeps` directory is outside the repository and
was used only to supply missing local test dependencies/stubs in this bare
runtime.

## 22. Remaining Work Before Held-Out Pilot

1. Run the strictly capped real-API development integration with explicit
   `--allow-real-api`.
2. Review the real-API dev run errors and leakage diagnostics without touching
   held-out data.
3. If prompts or parser rules change after real dev diagnostics, freeze a new
   protocol version and checksum before any held-out run.
4. Execute held-out only with explicit held-out approval and protocol-compliant
   call caps.
5. Keep held-out outputs separate from development artifacts.

## 23. Known Limitations

The development run is deterministic and synthetic. It is an integration
diagnostic, not a paper result. The optional real-API path is guarded but was
not executed. The protocol prepares a small held-out pilot; it does not claim
production safety, universal CFAF validation, or D1-D8 reproduction.

## 24. Changed Files

Major additions:

- `WOLALA2026_PILOT_PROTOCOL_v1.md`
- `WOLALA2026_PILOT_READINESS_REPORT_v1.md`
- `readiness_baseline_manifest.json`
- `run_manifest_schema.json`
- `prompts/prompt_only_v1.txt`
- `prompts/cfaf_generator_v1.txt`
- `data/development_integration_v1/`
- `data/heldout_pilot_v1/`
- `development_run/`
- `common.py`
- `pilot_data.py`
- `retrieval.py`
- `run_manifest.py`
- `run_pilot.py`
- `score_pilot.py`
- `tests/test_wolala_pilot_phase2.py`

Updated:

- `adapters.py`
- smoke output artifacts regenerated by the smoke test path.

## 25. Git Diff Summary

Phase 2 adds frozen pilot assets, adapters, scorer, runner, manifest schema,
development-run artifacts, and tests. It does not modify production endpoints or
frozen D1-D8 artifacts.

## 26. Final Readiness Classification

The deterministic pilot machinery, datasets, scorer, run manifests, call-cap
guards, and tests are ready. Full small-pilot readiness is blocked until an
explicitly approved, strictly capped real-API development integration run is
completed or a new protocol version explicitly permits proceeding without it.

PARTIAL - REAL_API_OR_COMPONENT_BLOCKER
