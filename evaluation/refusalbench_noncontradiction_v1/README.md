# RefusalBench-NQ filtered development pilot

This directory evaluates the finalized, unchanged InfoBank `semantic-integration-v2.1` on twenty newly selected RefusalBench records. It is a contradiction-filtered development experiment within already exposed source-question groups, not full-benchmark performance or independent holdout validation. REPORT.md and case_level_analysis.md contain the critical results.

Source: https://huggingface.co/datasets/aashiqmuhamed/RefusalBench-NQ at revision b3684f805563e6ce465e7e9b055b840a48f519c2, original test split of 1,600 records. Preparation uses the pinned official cached JSONL, records its SHA-256, parses only explicit annotation columns globally, and decodes question/context text only for the twenty selected records. It never writes to the source dataset. Reserved and untouched passage/answer text is not materialized or sent to the worker.

Filter A is exactly case-insensitive whole-word `contradiction` in implementation_reasoning. Filter B is the exact official contradictory-context label OR P-Contradiction class. Related words are counted separately and do not broaden A. The sampler uses seed 20261028, exact 10 FULL plus 2 each of five refusal-category quotas, twenty distinct previously exposed development source groups, and zero previously executed record IDs. The union of earlier pilot/development groups is 52; thirty reserved and eighteen untouched groups remain excluded. Selection and runtime hashes are frozen before live calls.

The worker reads only runtime_inputs.jsonl (exactly perturbed_query and perturbed_context per row) and its label-free hash authorization. public_adapter.py supplies the unchanged passage as FULL-authorized public content with neutral local IDs. It fabricates neither metadata nor target binding, and never overrides the latest query profiler. Query profiles, neutral span catalogues, permitted views and model-inferred assessments are derived inputs, not additional benchmark annotations. Both generators share these inputs. Only CFAF receives its response contract. Existing eight stages, selector, strict schema and evidence references are imported from the latest implementation.

Reproduce only in a NEW experiment directory/version; existing selection and live output files refuse overwrite:

1. `python -m evaluation.refusalbench_noncontradiction_v1.prepare_dataset --source <official-pinned-jsonl>`
2. Run test_pilot.py and earlier semantic/span/InfoBank suites with a writable workspace TEMP/TMP; historical tests use an isolated exact-Git-blob checkout.
3. `python -m evaluation.refusalbench_noncontradiction_v1.verify_preflight --initialize` saves trusted preparation hashes after passed test artifacts in a new directory; without --initialize it checks without rewriting.
4. `python -m evaluation.refusalbench_noncontradiction_v1.execute freeze`
5. `python -m evaluation.refusalbench_noncontradiction_v1.execute generate`
6. `python -m evaluation.refusalbench_noncontradiction_v1.score`

OPENAI_API_KEY is supplied only through the environment. The provider journals requests before HTTP, logs raw responses, tokens and latency, caps attempts at 75, uses no automatic retries/embeddings, and fixes gpt-4o-mini at temperature zero, analysis max 1500 and generation max 160. Invalid execution remains ERROR in all twenty-case denominators, never a fabricated correct refusal. Constant FULL/CFAF references generate no text and cost no API calls.

Preparation, worker and scoring execute as separate processes. selected_cases.jsonl retains official annotations for trusted scoring, and is never read by execution. score.py checks preparation-file hashes before joining labels to worker outputs. The frozen scorer reuses the earlier strict parser, error-inclusive metrics and lexical refusal-category recognizer. Generic explanations are not automatically specific-category matches. Original answers are not gold answers for changed contexts. Candidate copying, exact span references and answer substrings do not prove complete support. Report-author contextual reviews are non-independent agent judgments and incur no model-judge calls; they never change labels or primary predictions.

All earlier files are protected by protected_files.json. Previous results, original annotations and the wolala2026 branch are preserved. No classifier or contradiction-detection tuning is performed using these twenty labels. No push or merge is performed.

