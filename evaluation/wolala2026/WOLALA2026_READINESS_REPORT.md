# WoLaLa 2026 Readiness Report

## 1. Base Branch And Commit

- Base branch: `origin/d1-d8-large-scale-final-evaluation`
- Base commit: `5bb2cc742e105cc3238b022130126947c04bcd35`
- New branch: `wolala2026`
- Final commit: recorded in the final response after commit creation. A Git
  commit cannot contain its own SHA without changing that SHA.

## 2. Architecture Audit

The original code already contains controlled-failure helpers in
`backend_python/controlled_failure.py`, role-aware retrieval/evidence checks in
`backend_python/evidence_service.py`, and D1-D8 evaluation modes in
`evaluation/modes.py`. It was not organized as the requested explicit
eight-stage WoLaLa pipeline with serializable stage-by-stage state.

The production endpoint was left untouched. The WoLaLa path is a dedicated
evaluation runner under `evaluation/wolala2026/`, preserving existing D1-D8
source, frozen results, and production APIs.

## 3. Refactoring Performed

Added a conservative evaluation-only pipeline:

- `labels.py`: dataclass/enum label model and serializable `PipelineState`.
- `pipeline.py`: eight top-level stages, request-relative mode selection,
  response contract, trace separation, validation fallback, and latency timing.
- `adapters.py`: stubs for `standard_rag`, `prompt_only_control`, and
  `cfaf_pipeline`.
- `smoke_config.yaml`: deterministic synthetic WoLaLa smoke fixtures.
- `run_smoke.py`: smoke runner that writes result, trace, public response, and
  inventory artifacts.
- `data_readiness.py`: data inventory/audit helper.

## 4. Stage Inputs And Outputs

| Stage | Main Input | Main Output |
| --- | --- | --- |
| `QUERY_PROFILING` | query and fixture-declared request fields | query-profile labels |
| `CANDIDATE_RETRIEVAL` | fixture sources | retrieval candidate labels |
| `ACCESS_AND_SAFETY_RESOLUTION` | candidates and policy fields | authoritative access/visibility labels |
| `EVIDENCE_LABELLING` | accessible candidates and trusted metadata | claim-scoped role/state/relation labels |
| `SUFFICIENCY_AND_PERMITTED_OUTPUT` | labels and requested output | dispositions and claim assessments |
| `TOP_LEVEL_MODE_SELECTION` | claim assessments | `FULL` or `CFAF` decision object |
| `RESPONSE_REALIZATION` | response contract and permitted views | draft response and generator context |
| `VALIDATION_TRACE_AND_FEEDBACK` | draft and forbidden marker set | final response, fallback status, traces |

## 5. Label Catalogue

The label catalogue is documented in `PIPELINE_LABEL_SPEC.md`. Access mode,
existence visibility, evidential role, evidence state, disposition, claim
assessment, top-level mode, CFAF realization, reason class, response contract,
validation status, internal trace, and public trace are separate dimensions.

Policy labels are authoritative. DENY, METADATA, and AGGREGATE restrictions are
enforced before response realization. The top-level mode is selected outside the
free-form generator.

## 6. Data Inventory

Detailed inventory is in `data_inventory.json`.

| Corpus Or Fixture | Cases | Status | Key Finding |
| --- | ---: | --- | --- |
| `evaluation/fixtures/document_rag_v3.yaml` | 400 | PARTIAL | D1-D5 fixture is frozen and useful, but it lacks WoLaLa-specific structured CFAF labels and public/internal reason labels. |
| `data/benchmarks/evidence_unit_v2_holdout/cases.jsonl` | 340 | PARTIAL | D6-D8 runtime/gold separation is documented, but runtime cases lack WoLaLa access/mode/reason schema fields. |
| `evaluation/wolala2026/smoke_config.yaml` | 13 | READY | Covers required smoke cases with synthetic data and structured expected labels. |

The repository now contains smoke-level positive metadata lookup, paired
source-existence leakage cases, prompt-only adapter configuration, structured
CFAF gold labels, public/internal reason labels, and latency-ready smoke
records. It does not yet contain enough WoLaLa-specific held-out data for a
publication-scale experiment.

## 7. Smoke Test Results

Command:

```powershell
python -m evaluation.wolala2026.run_smoke
```

Observed result:

```json
{"case_count": 13, "passed": true}
```

The smoke suite covers:

- S1 full-access primary evidence -> `FULL`
- S2 contextual-only evidence -> `CFAF` / `EVIDENTIAL`
- S3a aggregate request with aggregate permission -> `FULL`
- S3b individual request with aggregate permission -> `CFAF` / `RESTRICT_GRANULARITY`
- S4a metadata lookup with metadata permission -> `FULL`
- S4b content request with metadata permission -> `CFAF` / `RESTRICT_CONTENT`
- S5 denied source excluded from generator context
- S6 e-mail primary plus browser contextual -> open action
- S7 browser-only action candidate -> no obligation, evidential CFAF
- S8 later cancellation -> `FULL` closed-status answer
- S9a/S9b public reason normalization for hidden source existence
- S10 invalid generated marker -> validation failure and safe fallback

## 8. Internal And Public Trace Example

Full internal trace: `example_internal_trace.json`.

Filtered public response: `example_public_response.json`.

The example case is `S4B_CONTENT_WITH_METADATA_ACCESS`. The internal trace
contains the policy and source details needed for audit. The public response
contains only the safe public reason and public trace fields.

## 9. Generator Exposure Proof

Tests assert that:

- `DENIED_SECRET_S5` is absent from generator context.
- `S4_PRIVATE_CONTENT` is absent from generator context while allowed metadata
  remains visible.
- `S3_INDIVIDUAL_CANARY` is absent from aggregate-only generator context.
- `FORBIDDEN_S10_CANARY` is not sent to generator context and is removed from
  the final response by fallback validation.

## 10. Latency Instrumentation

`smoke_results.json` contains timing records for every top-level stage and
`end_to_end_ms` for all 13 smoke cases. All durations are non-negative.

The smoke summary computes P50/P95 to verify aggregation logic, but these values
are not reported as statistically meaningful. The later latency design is in
`latency_plan.md`.

## 11. Test Commands And Results

New WoLaLa tests:

```powershell
python -m unittest discover -s evaluation\tests -p "test_wolala*.py" -v
```

Result: 15 tests passed.

Existing relevant fast tests:

```powershell
$env:PYTHONPATH = '..\pydeps'
python -m unittest evaluation.tests.test_harness evaluation.tests.test_d1_d8_evidence_loader_and_action_logic -v
```

Result: 24 tests passed. The temporary `pydeps` directory was outside the repo
tree and supplied missing local runtime dependencies/stubs only for test
execution.

## 12. Missing Work Before Small WoLaLa Pilot

1. Decide whether the 13 smoke cases are enough for the first pilot or expand to
   a small held-out pilot fixture with the same schema.
2. Implement real generator adapters for `standard_rag` and
   `prompt_only_control` with a strict call cap.
3. Add a run manifest for pilot executions with model, seed, case subset, and
   environment metadata.
4. Add repeated cold/warm latency collection for a tiny fixed subset.
5. Document exact statistical questions for the pilot before collecting real
   outputs.

## 13. Missing Work Before Publication-Scale Benchmark

1. Build a larger WoLaLa-specific held-out case set with all required structured
   fields.
2. Document train/development/test separation for WoLaLa data.
3. Add prompt-only baseline measured outputs and scoring.
4. Add repeated latency runs separated by `FULL`/`CFAF` and generation-used/
   generation-skipped cases.
5. Add per-case licence/provenance records for all new evidence.

## 14. Known Limitations And Risks

This branch demonstrates the evidential and governance instantiation of CFAF,
not production safety, identity, cryptography, tool execution, or prompt
injection benchmarks. The smoke suite is deterministic and synthetic. The
adapters are prepared interfaces, not a complete comparative experiment.

## 15. Later Full Experiment Commands

Do not execute these from this preparation task. They are placeholders for a
future explicitly approved experiment:

```powershell
$env:OPENAI_API_KEY = "<set outside repository>"
python -m evaluation.wolala2026.run_smoke --config evaluation/wolala2026/smoke_config.yaml
```

A future measured experiment should add explicit arguments such as
`--modes standard_rag,prompt_only_control,cfaf_pipeline`, `--max-cases`, and
`--max-generation-calls` before any real API use.

## 16. Git Diff Summary

Added `evaluation/wolala2026/` and six WoLaLa-focused test files under
`evaluation/tests/`. No D1-D8 frozen result, preregistration, manifest, or
publication artifact was modified.

## 17. Readiness Classification

PARTIAL - MISSING_DATA_OR_COMPONENTS

The branch is ready for deterministic smoke testing and architecture review, but
publication-scale WoLaLa data, real adapter execution, and repeated latency
records are still missing.
