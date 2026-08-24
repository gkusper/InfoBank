# ISCMI 2026 Oracle Task-State RAG Experiment

Run mode: `real_api`. Questions: 271. Conditions: 3. Evaluations: 813.

The three conditions use the same generator and output schema. STANDARD_RAG uses semantic email-message retrieval; THREAD_AWARE_RAG expands to the complete chronological email thread; ORACLE_TASK_STATE_RAG additionally receives the human-derived task representation.

## Frozen Configuration

Generator: `gpt-4o-mini`; embedding: `text-embedding-3-small`; temperature: `0.0`; maximum output tokens: `2000`.

## Primary Summary

| Condition | Exact | Structured | Controlled failure | Evidence F1 | Calls | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| STANDARD_RAG | 0.1256 | 0.3612 | 0.8487 | 0.7727 | 271 | 392548 |
| THREAD_AWARE_RAG | 0.1031 | 0.3402 | 0.8524 | 0.7618 | 271 | 396926 |
| ORACLE_TASK_STATE_RAG | 0.6592 | 0.8940 | 0.9668 | 0.8799 | 271 | 695900 |

## Family Results

| Condition | Family | N | Exact | Structured | Evidence F1 |
|---|---|---:|---:|---:|---:|
| STANDARD_RAG | ACTOR_RESPONSIBILITY | 45 | 0.0000 | 0.0922 | 0.7277 |
| STANDARD_RAG | BLOCKED_BY | 4 | 0.0000 | 0.0000 | 0.4750 |
| STANDARD_RAG | CLOSED_TASKS | 50 | 0.3000 | 0.4747 | 0.8176 |
| STANDARD_RAG | DEADLINE | 6 | 0.5000 | 0.5667 | 0.5865 |
| STANDARD_RAG | NO_TASK_CONTROL | 19 | 0.9474 | 0.9474 | 0.6887 |
| STANDARD_RAG | OPEN_TASKS | 50 | 0.1400 | 0.4961 | 0.7574 |
| STANDARD_RAG | REQUESTER | 36 | 0.0278 | 0.2139 | 0.6939 |
| STANDARD_RAG | TASK_HISTORY | 42 | 0.1190 | 0.4800 | 0.8531 |
| STANDARD_RAG | WAITING_FOR | 19 | 0.0000 | 0.0421 | 0.6728 |
| THREAD_AWARE_RAG | ACTOR_RESPONSIBILITY | 45 | 0.0000 | 0.0622 | 0.7237 |
| THREAD_AWARE_RAG | BLOCKED_BY | 4 | 0.0000 | 0.0000 | 0.4750 |
| THREAD_AWARE_RAG | CLOSED_TASKS | 50 | 0.3200 | 0.4804 | 0.7849 |
| THREAD_AWARE_RAG | DEADLINE | 6 | 0.5000 | 0.5667 | 0.5806 |
| THREAD_AWARE_RAG | NO_TASK_CONTROL | 19 | 0.9474 | 0.9474 | 0.9123 |
| THREAD_AWARE_RAG | OPEN_TASKS | 50 | 0.0800 | 0.4623 | 0.7649 |
| THREAD_AWARE_RAG | REQUESTER | 36 | 0.0000 | 0.1468 | 0.6510 |
| THREAD_AWARE_RAG | TASK_HISTORY | 42 | 0.0714 | 0.4913 | 0.8665 |
| THREAD_AWARE_RAG | WAITING_FOR | 19 | 0.0000 | 0.0421 | 0.6248 |
| ORACLE_TASK_STATE_RAG | ACTOR_RESPONSIBILITY | 45 | 0.7556 | 0.9524 | 0.9514 |
| ORACLE_TASK_STATE_RAG | BLOCKED_BY | 4 | 0.5000 | 0.8333 | 0.8500 |
| ORACLE_TASK_STATE_RAG | CLOSED_TASKS | 50 | 0.8400 | 0.9258 | 0.8608 |
| ORACLE_TASK_STATE_RAG | DEADLINE | 6 | 1.0000 | 1.0000 | 0.8444 |
| ORACLE_TASK_STATE_RAG | NO_TASK_CONTROL | 19 | 0.6316 | 0.6316 | 0.5789 |
| ORACLE_TASK_STATE_RAG | OPEN_TASKS | 50 | 0.9800 | 0.9960 | 0.9093 |
| ORACLE_TASK_STATE_RAG | REQUESTER | 36 | 0.3056 | 0.7631 | 0.7494 |
| ORACLE_TASK_STATE_RAG | TASK_HISTORY | 42 | 0.2619 | 0.7841 | 0.9030 |
| ORACLE_TASK_STATE_RAG | WAITING_FOR | 19 | 0.5789 | 0.7421 | 0.8538 |

## History

The dedicated 42-question HISTORY result compares exact transition/state sequences and ordered-subsequence LCS F1.

| Condition | Exact sequence | Ordered structured score | Evidence F1 |
|---|---:|---:|---:|
| STANDARD_RAG | 0.1190 | 0.4800 | 0.8531 |
| THREAD_AWARE_RAG | 0.0714 | 0.4913 | 0.8665 |
| ORACLE_TASK_STATE_RAG | 0.2619 | 0.7841 | 0.9030 |

## Evidence, Failure Control, And Usage

| Condition | Controlled failure | Evidence precision | Evidence recall | Evidence F1 | Input tokens | Output tokens | Total tokens | Tokens/question | Latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STANDARD_RAG | 0.8487 | 0.7042 | 0.9150 | 0.7513 | 315582 | 76966 | 392548 | 1448.52 | 3.540 |
| THREAD_AWARE_RAG | 0.8524 | 0.7020 | 0.9097 | 0.7545 | 320004 | 76922 | 396926 | 1464.67 | 3.550 |
| ORACLE_TASK_STATE_RAG | 0.9668 | 0.8114 | 0.9560 | 0.8558 | 540262 | 155638 | 695900 | 2567.90 | 6.570 |

## Paired Comparisons

Primary-family p-values use paired McNemar and Wilcoxon signed-rank tests with Holm correction. Negative differences favor the right-hand condition.

| Left | Right | Scope | Exact difference | Structured difference | Exact wins L/R | Holm McNemar | Holm Wilcoxon |
|---|---|---|---:|---:|---:|---:|---:|
| STANDARD_RAG | THREAD_AWARE_RAG | PRIMARY_OVERALL | 0.0224 | 0.0210 | 9/4 | 1.0 | 1.0 |
| STANDARD_RAG | THREAD_AWARE_RAG | TASK_HISTORY | 0.0476 | -0.0113 | 2/0 | 1.0 | 1.0 |
| THREAD_AWARE_RAG | ORACLE_TASK_STATE_RAG | PRIMARY_OVERALL | -0.5561 | -0.5538 | 3/127 | 9.149301587887914e-33 | 2.548442177937961e-31 |
| THREAD_AWARE_RAG | ORACLE_TASK_STATE_RAG | TASK_HISTORY | -0.1905 | -0.2928 | 2/10 | 0.27001953125 | 7.751720379833023e-05 |
| STANDARD_RAG | ORACLE_TASK_STATE_RAG | PRIMARY_OVERALL | -0.5336 | -0.5328 | 5/124 | 1.3475945572770243e-29 | 7.770559164141396e-31 |
| STANDARD_RAG | ORACLE_TASK_STATE_RAG | TASK_HISTORY | -0.1429 | -0.3042 | 4/10 | 1.0 | 7.751720379833023e-05 |

## Output Completeness

Recorded output statuses: `{"complete": 812, "truncated_by_output_limit": 1}`. Deterministic parser recoveries: 1.

## Limitations

The fixed 2000-token output ceiling produced 1 explicitly truncated responses. When malformed output occurs, the deterministic parser retains only complete emitted JSON values and discards incomplete suffixes; no value is inferred. Remaining evaluation errors: 0.

Raw email content remains external. Task alignment without an oracle task ID relies on source-message overlap. Secondary families have limited sample sizes and are exploratory.

## Interpretation Boundary

This is an oracle representation experiment. A positive result supports the usefulness of explicit task state, but does not establish that task state can be reconstructed automatically at the same quality.

Primary families are OPEN_TASKS, CLOSED_TASKS, ACTOR_RESPONSIBILITY, REQUESTER, and TASK_HISTORY. DEADLINE, WAITING_FOR, BLOCKED_BY, and rare REJECT observations are exploratory because of limited sample sizes.

## Comparison With The 800-Token Run

| Condition | Exact 800 -> 2000 | Structured 800 -> 2000 | Truncated 800 -> 2000 | Total tokens 800 -> 2000 |
|---|---:|---:|---:|---:|
| STANDARD_RAG | 0.1734 -> 0.1808 | 0.3734 -> 0.3791 | 1 -> 0 | 393024 -> 392548 |
| THREAD_AWARE_RAG | 0.1587 -> 0.1624 | 0.3577 -> 0.3618 | 1 -> 0 | 396358 -> 396926 |
| ORACLE_TASK_STATE_RAG | 0.6089 -> 0.6568 | 0.8470 -> 0.8664 | 62 -> 1 | 676336 -> 695900 |

Parsed answers changed in 374 of 813 pairs. Exact correctness improved in 26, worsened in 10, and was unchanged in 777.

The 64 previously truncated cases produced 63 complete new outputs. See `comparison_max800_vs_max2000.md` and `.json` for pair-level details.

Main oracle-superiority conclusion retained: **YES**.
