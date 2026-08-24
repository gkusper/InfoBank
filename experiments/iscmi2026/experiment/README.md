# ISCMI 2026 Oracle Task-State RAG Experiment

This directory implements the first ISCMI 2026 RAG experiment over the fixed
271-question MailEx task benchmark. It tests whether a reliable persistent task
representation improves todo-oriented question answering. It does **not** test
automatic task-state extraction.

## Conditions

All conditions use `gpt-4o-mini`, temperature `0.0`, the same 800-token output
limit, system prompt, question text, and JSON response schema. Email semantic
retrieval uses `text-embedding-3-small`, cosine similarity, and fixed top-k 6.
The benchmark conversation boundary is a non-semantic scope supplied equally to
all conditions; no condition is allowed to search by task ID or target answer.

- `STANDARD_RAG`: top-k corrected original email messages. One message is one
  retrieval unit. No MailEx event annotation or ISCMI task field is indexed.
- `THREAD_AWARE_RAG`: the same semantic seed retrieval, followed by deterministic
  expansion to every original email in that conversation, ordered by the
  corrected chronological rank.
- `ORACLE_TASK_STATE_RAG`: the same chronological email context plus compact
  human-derived task histories and final snapshots with source-message IDs.
  Question-specific `gold_answer` and `gold_structured` remain unavailable.

The B-to-C comparison isolates the value of explicit persistent task state beyond
a strong email-thread baseline. A positive result cannot establish that an
automatic extractor can reproduce the oracle representation.

## Corpus Separation

Raw MailEx bodies remain in the corrected external `P001.md`-`P050.md` packet and
are never written into this directory. The loader stops each message at
`### Original MailEx annotations`, so the baseline corpus contains only original
email metadata and body text. Supply the packet with `--packet-dir` or
`MAILEX_PILOT_PACKET`. Its 50 committed manifest hashes are verified by the
leakage validator.

Inference records are gold-free. `evaluate_results.py` joins
`gold_structured` only after generation. Generated results are ignored by Git;
the tracked `results/.gitignore` only reserves the output location.

## Stage A: Structural Dry-Run

The default run uses deterministic local mock embeddings and a controlled-failure
mock generator over one question from OPEN, HISTORY, NO_TASK, and DEADLINE. It
checks all three paths without making an API call or claiming experimental
performance.

```powershell
python experiments/iscmi2026/experiment/validate_no_leakage.py
python experiments/iscmi2026/experiment/run_experiment.py `
  --output-dir C:\path\outside\the\repository\iscmi_dry_run
python experiments/iscmi2026/experiment/validate_no_leakage.py `
  --results C:\path\outside\the\repository\iscmi_dry_run\inference_results.jsonl
python experiments/iscmi2026/experiment/evaluate_results.py `
  --inference-results C:\path\outside\the\repository\iscmi_dry_run\inference_results.jsonl
```

Mock output is only a pipeline test and must never be reported as a real model
result.

## Stage B: Frozen Full Run

Set `OPENAI_API_KEY` in the process environment, choose an empty output directory,
and invoke `--real-api`. The script then runs all 271 questions in all three
conditions, producing 813 generation records. It does not read `.env` files or
store the key. Use `--resume` only with the same frozen code/configuration and
partially written result file.

```powershell
python experiments/iscmi2026/experiment/run_experiment.py `
  --real-api `
  --output-dir experiments/iscmi2026/experiment/results
python experiments/iscmi2026/experiment/validate_no_leakage.py `
  --results experiments/iscmi2026/experiment/results/inference_results.jsonl
python experiments/iscmi2026/experiment/evaluate_results.py `
  --inference-results experiments/iscmi2026/experiment/results/inference_results.jsonl
```

The run manifest records Git/config hashes, models, generation settings,
retrieval policy, benchmark manifest hash, package versions, question count,
packet provenance, and API usage. `actual_generator_model` records the model name
returned by the API for each generation.

## Deterministic Evaluation

No LLM judge is used. Baseline predictions may omit internal task IDs; predicted
tasks are aligned first by exact ID when available and otherwise by deterministic
source-message Jaccard overlap.

- OPEN/CLOSED: task precision, recall, F1, and exact set match.
- ACTOR/REQUESTER: normalized exact value matching after task alignment.
- HISTORY: exact transition/state sequence, ordered-subsequence LCS F1, and
  transition-multiset F1. Truncated JSON is deterministically closed at the last
  complete token boundary; incomplete suffix values are discarded, never guessed.
- DEADLINE: exact normalized ISO date.
- WAITING_FOR/BLOCKED_BY: deterministic normalized text matching.
- NO_TASK and negative controls: explicit no-task/controlled-failure accuracy.
- Evidence: precision, recall, F1, exact match, ID validity, and presence in the
  retrieved email context, reported separately from answer correctness.

OPEN, CLOSED, ACTOR, REQUESTER, and HISTORY are primary families. DEADLINE,
WAITING_FOR, BLOCKED_BY, and rare REJECT observations are exploratory. Complete
runs include paired wins/losses/ties, exact McNemar tests, Wilcoxon signed-rank
comparisons for structured scores, absolute effects, and Holm correction across
primary tests. Tests are suppressed for family samples below 20.

The evaluator writes `per_question_results.jsonl`, `aggregate_results.json`,
`family_results.csv`, `pairwise_comparisons.csv`, `error_summary.json`, and
`experiment_report.md` beside the inference file.

## Validation

```powershell
python -m py_compile experiments/iscmi2026/experiment/run_experiment.py
python -m py_compile experiments/iscmi2026/experiment/evaluate_results.py
python experiments/iscmi2026/experiment/validate_no_leakage.py
python experiments/iscmi2026/experiment/test_experiment.py
git diff --check
git status
git diff --stat
```

The leakage test verifies corpus schemas, corrected packet hashes, resolvable
evidence, common generator parameters, and all 271 question paths. It replaces
every benchmark target with sentinels and proves that the inference projection
and model prompt remain byte-identical.
