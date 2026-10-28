# Semantic CFAF: 42-case RefusalBench development experiment

Read `REPORT.md` for measured outcomes, failures and the readiness decision.
This is development data, not independent final benchmark validation.

## Implementation

The reusable implementation is `evaluation/wolala2026/semantic_evidence.py`.
It accepts query text and a mapping of neutral source identifiers to permitted
context strings. The benchmark-specific runtime projection is the thin
`semantic_adapter.py` in this directory. No original CFAF source file is edited.
The original internal-fixture entry point remains unchanged.

The analyzer returns structured query interpretation, premise/support status,
requested/available granularity, possible interpretations, a proposed answer,
exact supporting/counterevidence spans, uncertainty causes and confidence. It
has no FULL/CFAF output field and never receives benchmark labels or old answers.
Quoted text must occur literally in the indicated runtime context; offsets are
computed locally. Fabricated quotes, malformed schemas and unsupported
counterevidence assertions become explicit invalid analyses.

The new eight-stage entry point reuses the original retrieval stage, permission
stage, label/claim/contract types and `TopLevelModeSelectionStage`. Semantic
stages infer roles and perform request-relative fulfilment checks. PRIMARY is
assigned only with verified spans, a sufficient semantic assessment, a specified
question, adequate detail, established premises, no unresolved counterevidence,
a candidate answer and confidence at least 0.70. Permission remains distinct
from semantic role.

The final model receives the actual question, the selected response contract,
the runtime-derived proposed answer and only verified permitted spans. It must
copy the answer candidate for FULL and the cause-specific public explanation
for CFAF. Local validation rejects changed modes or answers. Selected mode,
proposed answer, raw generation and final text remain separate. A fallback is
logged as failure, never credited as a successful refusal. Quote occurrence and
answer-copy agreement are mechanical checks, not independent entailment proof.

## Sampling and heldout boundary

`sample_development_cases.py` is a trusted preparation process. It loads the
pinned official dataset revision `b3684f805563e6ce465e7e9b055b840a48f519c2`.
It groups by original NQ `source_id`, excludes all ten previous-pilot sources,
and shuffles eligible source groups with Python `random.Random(20261028)`.
It reserves the first 30 groups before selecting development records. The
holdout manifest contains only source IDs, record indices, counts and a
metadata checksum; it contains no heldout query/context/answer/explanation.
The report-authoring process does not read heldout record text.

A seeded bipartite augmenting-path assignment fills six slots in each of the
seven original categories using 42 distinct source groups. Record choice and
final order are also seeded. If that exact design is infeasible, sampling stops
without silently reusing groups or changing quotas. In this run it is feasible.
`selection_manifest.json` records original IDs, source groups, dataset indices,
quotas, algorithm and selected/runtime checksums for trusted scoring only.

`development_cases.jsonl` retains the original records and annotations. The
worker NEVER reads it. `runtime_inputs.jsonl` contains only `perturbed_query`
and `perturbed_context`, with neutral row indices assigned at execution. Extra
fields are rejected. Original IDs encode perturbation information and never
reach a model, the semantic adapter or the mode selector. This is an explicit
application data-flow boundary, not a claim of OS filesystem isolation.

## Reproduction

Use Python 3.12 and install `requirements.lock.txt` into an isolated environment.
The actual run uses Python 3.12.14 and the existing urllib-based OpenAI provider;
no OpenAI SDK is needed. Set `OPENAI_API_KEY` in the environment without logging
it. On Windows use short writable Hugging Face cache paths and writable TEMP/TMP
paths to avoid long-path and sandbox temporary-directory errors.

Copy these additions onto base commit
`5f377de38312fb39c088551f9c74f8b6d4bd5080` on a separate branch. Keep the prior
pilot artifacts available because their source groups must be excluded.
From the repository root, use separate processes:

```powershell
python evaluation/refusalbench_semantic_dev/sample_development_cases.py --output-dir work/new-semantic-run
python -m pytest evaluation/refusalbench_semantic_dev/test_semantic.py evaluation/refusalbench_semantic_dev/test_experiment.py -q -p no:cacheprovider --basetemp work/acceptance-tmp --junitxml work/new-semantic-run/acceptance_tests.xml
python evaluation/refusalbench_semantic_dev/verify_regressions.py --work-dir work/new-regression-copies
```

The regression utility writes its XML/comparison files beside its source.
For a fresh alternate output directory, copy `regression_tests.xml`,
`baseline_regression_tests.xml` and `regression_comparison.json` there after the
utility finishes. The full historical suite has one pre-existing failure on
the verified base: a plan-only guard asserts that an already committed
`HELDOUT_RUN_AUTHORIZATION.json` does not exist. The run does not remove or
modify that artifact. Exact Git blob bytes are used in disposable copies to
avoid LF/CRLF checksum artifacts. The extension has the identical baseline
failure set. Strict acceptance condition 5 is therefore not fully satisfied;
this run remains diagnostic development work.

Then freeze and execute only in the NEW output directory:

```powershell
python evaluation/refusalbench_semantic_dev/run_experiment.py freeze --output-dir work/new-semantic-run
python evaluation/refusalbench_semantic_dev/run_experiment.py generate --output-dir work/new-semantic-run
python evaluation/refusalbench_semantic_dev/run_experiment.py score --output-dir work/new-semantic-run
```

Existing selection, freeze and live-result files are protected against
overwrite. A new directory is a new experiment with a separate budget, not a
retry of this delivered run. Do not regenerate the delivered artifacts.
Temperature 0 does not guarantee identical future outputs.

## Frozen design and API accounting

`prerun_protocol.json` and `frozen_prompts.json` freeze source hashes, prompts,
semantic JSON schema, runtime projection, settings and scoring before the
first real call. `experiment_manifest.json` records actual environment,
provider versions, timings and counts.

The complete planned experiment is 42 analyses plus 168 generations: Standard
RAG, existing prompt-only, semantic CFAF, and the optional shared-assessment
prompt control each generate once per case. There are 210 planned attempts,
a durable hard cap of 225, zero retries, zero embeddings and zero extra model
judges/validators. An analysis is shared between CFAF and the optional control;
it is not called again for the same case. The generator output limit is 160
tokens; structured analysis has a separately frozen 1,500-token limit. Both
use `gpt-4o-mini`, temperature 0.

`api_requests.jsonl` stores actual outbound JSON payloads without authorization
headers. `api_events.jsonl` stores returned model IDs, raw content, usage,
finish reasons, measured latency and errors. API attempts are journaled before
network I/O. `semantic_assessments.jsonl` retains the structured analysis and
quote/schema validation outcomes. `pipeline_traces.jsonl` preserves all eight
stages and selected modes. `generation_results.jsonl` is worker output without
labels; `results.jsonl` is the trusted post-generation join plus clearly marked
zero-cost Always FULL / Always CFAF prediction references.

## Scoring and interpretation limits

All generated systems use the same strict raw-JSON interpretation: a recognized
FULL/CFAF mode and nonempty string answer are required. Failed analyses,
malformed outputs, validation failures and missing executions are ERROR, not
successful safe fallback classifications. All 42 scheduled cases remain in
accuracy/recall denominators; confusion matrices include an ERROR column.
Selected gate mode and raw declared mode remain available as diagnostics.
Reference baselines generate no fictional text and incur no API calls.

Original expected labels are unchanged: ANSWER_CORRECTLY maps to FULL, each
REFUSE category to CFAF. Specific refusal-category recognition uses the same
frozen lexical procedure for all systems. It is not proof of a justified
reason. Exact answer substring matches, verified evidence quotes and candidate
copy checks are distinct from complete fulfilment and independent answer
correctness. Behavior labels alone provide no perturbed-answer gold standard.
Unmeasurable support and unreviewed responses remain null; no answer-support
scores are inferred from the analyzer's own claims.

If post-generation report-author reviews are supplied, their provenance and
non-independence must be disclosed. Do not describe them as blinded human
annotations or extra API-judge results. The report explains every incorrect
system decision and the limits of the optional component comparison, without
changing labels or repairing outputs after the freeze.

## Preservation

`predevelopment_file_hashes.json` protects the 381 original tracked files plus
the 24 prior-pilot deliverables. All original D1–D8 data, publication results,
previous CFAF outputs and the previous pilot are preserved. Regression test
side effects occur only in disposable copies. No branch is pushed or merged.
