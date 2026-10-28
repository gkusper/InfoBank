# CFAF span-reference / public-response contract fix

This is a separate targeted development pilot. Previous experiments are frozen
and are neither rewritten nor rescored. Read REPORT.md for actual outcomes and
null_response_root_cause.md for the evidence-based diagnosis.

## Changes

`span_references.py` deterministically catalogues unchanged runtime documents
using 430-character windows with 70-character overlap. IDs use neutral source
IDs plus stable span indices. Offsets are zero-based, half-open Python Unicode
character offsets. Source SHA-256 digests and the deterministic catalogue are
checked when resolving references. The model selects existing supporting and
contradicting IDs; code slices the original string to obtain exact text. No
quotation normalization, fuzzy matching, replacement span or generated quote
repair is used. Both evidence sides remain available to the existing semantic
fulfilment gate. A valid reference is not entailment or semantic sufficiency.

`contracts.py` defines one strict six-field output schema for all four generated
systems. `answer` must be a string for FULL and CFAF; common instructions require
nonempty public explanation text and distinguish it from nullable semantic
answer_candidate. Empty/invalid raw output remains an explicit failure. The
shared-assessment prompt still selects its own FULL/CFAF mode.

`api_budget.py` applies the reference schema to analysis and the same public
schema to every generation, journals actual payloads/results, and enforces a
persistent 60-attempt cap. No retries or embeddings are used. The original
CFAF selector, semantic decision conditions and prior source files are unchanged.

## Sampling and runtime boundary

`sample_cases.py` uses pinned dataset revision
b3684f805563e6ce465e7e9b055b840a48f519c2 and seed 20261028. Only source groups
already assigned to the 42-case development experiment are eligible. Previously
executed records are excluded; the chosen 10 records are new, from 10 distinct
already exposed groups. Five ANSWER_CORRECTLY records and five distinct refusal
categories are selected before new model outputs exist. No reserved holdout or
extra 18 untouched group text is selected or exposed.

Original records and annotations are kept in cases.jsonl for trusted scoring.
The model worker reads only runtime_inputs.jsonl with exactly perturbed_query
and perturbed_context. Original IDs, labels, original answers, perturbation
metadata and explanations never reach an evaluated component. Neutral runtime
IDs are used. This is application-level data separation, not OS isolation.

## Reproduce

Start from local development commit
f8aaf117764c919993fd076143793c8f8fbe0bb8, copy this new directory, and use Python
3.12 with the previous requirements.lock.txt. Set OPENAI_API_KEY only in the
environment. On Windows, short writable HF_HOME/HF_DATASETS_CACHE and TEMP/TMP
paths may be needed. Never regenerate into this delivered directory.

The delivered frozen files can be inspected/scored without new API use. A NEW
run needs a fresh copy/output directory and new test/protocol artifacts:

```powershell
python evaluation/refusalbench_span_fix_v1/sample_cases.py
python -m pytest evaluation/refusalbench_semantic_dev/test_semantic.py evaluation/refusalbench_semantic_dev/test_experiment.py evaluation/refusalbench_span_fix_v1/test_span_fix.py -q -p no:cacheprovider --junitxml evaluation/refusalbench_span_fix_v1/test_results.xml
python evaluation/refusalbench_span_fix_v1/run_experiment.py freeze
python evaluation/refusalbench_span_fix_v1/run_experiment.py generate
python evaluation/refusalbench_span_fix_v1/run_experiment.py score
```

Before freeze, run all original test_wolala regression modules in a disposable
copy using exact Git blob bytes and save regression_test_results.xml here. The
only permitted historical failure is the already documented authorization-file
presence test; no historical artifact is removed. The previous
verify_regressions.py illustrates exact-blob extraction but writes old artifact
paths, so do not run it directly against the frozen previous experiment.

The complete new/previous experimental suites have 70 passing tests. Original
regressions have 77 passing test functions plus 13 passing subtests and the same
single historical guard failure. Tests are synthetic and incur no real API use.

## Protocol and evidence

The source, prompts, both schemas, runtime projection, model settings and common
scoring rules are frozen before the first new live call. Generator settings:
gpt-4o-mini, temperature 0, maximum 160 output tokens, one repetition. Analysis
uses the same model/temperature with a 1,500-token limit. One analysis per case
is shared by CFAF and prompt control: 10 analysis + 40 generation calls, normal
50 attempts, hard cap 60. Raw outputs, parsed responses, tokens, latency,
reference catalogues and exact extracted text are retained.

The scoring procedure reuses the previous strict raw-JSON binary interpretation
and error-inclusive metrics; invalid outputs/fallbacks are never silently
credited as successful CFAF. Always FULL/CFAF references generate no fake text
and incur no calls. Specific refusal reasons are evaluated separately. Gold
behavior labels alone cannot establish complete answer support. Optional
post-generation report-author contextual reviews are unblinded, not independent
human annotations, and never modify primary predictions or gold labels.

The historical 35 null public answers were already present in raw API JSON;
the old JSON-object-only contract did not prohibit null and did not explicitly
distinguish missing factual candidates from user-facing refusal text. The new
schema and prompt fix that source defect, rather than filling null after output.

Read summary.json and span_reference_validation.json for measured outcomes.
checksums.sha256 covers all new deliverables. protected_files.json and final
validation preserve all earlier tracked files. No push or merge is performed.
