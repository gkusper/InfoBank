# ISCMI 2026 Oracle Task-State RAG Experiment

Run mode: `real_api`. Questions: 57. Conditions: 3. Evaluations: 171.

The three conditions use the same generator and output schema. STANDARD_RAG uses semantic email-message retrieval; THREAD_AWARE_RAG expands to the complete chronological email thread; ORACLE_TASK_STATE_RAG additionally receives the human-derived task representation.

## Frozen Configuration

Generator: `gpt-4.1-2025-04-14`; embedding: `text-embedding-3-small`; temperature: `0.0`; maximum output tokens: `2000`.

## Primary Summary

| Condition | Exact | Structured | Controlled failure | Evidence F1 | Calls | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| STANDARD_RAG | 0.1111 | 0.3639 | 0.8947 | 0.6550 | 57 | 94572 |
| THREAD_AWARE_RAG | 0.1556 | 0.3713 | 0.8947 | 0.6714 | 57 | 96239 |
| ORACLE_TASK_STATE_RAG | 0.7333 | 0.8492 | 0.9298 | 0.8976 | 57 | 151729 |

## Family Results

| Condition | Family | N | Exact | Structured | Evidence F1 |
|---|---|---:|---:|---:|---:|
| STANDARD_RAG | ACTOR_RESPONSIBILITY | 9 | 0.1111 | 0.2614 | 0.7138 |
| STANDARD_RAG | BLOCKED_BY | 2 | 0.0000 | 0.0000 | 0.5833 |
| STANDARD_RAG | CLOSED_TASKS | 10 | 0.1000 | 0.3500 | 0.6290 |
| STANDARD_RAG | DEADLINE | 1 | 0.0000 | 0.5000 | 0.6667 |
| STANDARD_RAG | NO_TASK_CONTROL | 5 | 0.8000 | 0.8000 | 0.8000 |
| STANDARD_RAG | OPEN_TASKS | 10 | 0.2000 | 0.4900 | 0.7474 |
| STANDARD_RAG | REQUESTER | 6 | 0.1667 | 0.1667 | 0.1667 |
| STANDARD_RAG | TASK_HISTORY | 10 | 0.0000 | 0.4624 | 0.8287 |
| STANDARD_RAG | WAITING_FOR | 4 | 0.0000 | 0.1000 | 0.7667 |
| THREAD_AWARE_RAG | ACTOR_RESPONSIBILITY | 9 | 0.1111 | 0.2354 | 0.6966 |
| THREAD_AWARE_RAG | BLOCKED_BY | 2 | 0.0000 | 0.0000 | 0.5833 |
| THREAD_AWARE_RAG | CLOSED_TASKS | 10 | 0.2000 | 0.3833 | 0.6367 |
| THREAD_AWARE_RAG | DEADLINE | 1 | 0.0000 | 0.4000 | 0.6667 |
| THREAD_AWARE_RAG | NO_TASK_CONTROL | 5 | 0.8000 | 0.8000 | 1.0000 |
| THREAD_AWARE_RAG | OPEN_TASKS | 10 | 0.2000 | 0.4900 | 0.7720 |
| THREAD_AWARE_RAG | REQUESTER | 6 | 0.1667 | 0.1667 | 0.2333 |
| THREAD_AWARE_RAG | TASK_HISTORY | 10 | 0.1000 | 0.4857 | 0.8455 |
| THREAD_AWARE_RAG | WAITING_FOR | 4 | 0.0000 | 0.1000 | 0.8333 |
| ORACLE_TASK_STATE_RAG | ACTOR_RESPONSIBILITY | 9 | 0.8889 | 0.9444 | 0.9630 |
| ORACLE_TASK_STATE_RAG | BLOCKED_BY | 2 | 0.5000 | 0.8333 | 0.5333 |
| ORACLE_TASK_STATE_RAG | CLOSED_TASKS | 10 | 0.7000 | 0.7000 | 0.9146 |
| ORACLE_TASK_STATE_RAG | DEADLINE | 1 | 1.0000 | 1.0000 | 1.0000 |
| ORACLE_TASK_STATE_RAG | NO_TASK_CONTROL | 5 | 1.0000 | 1.0000 | 1.0000 |
| ORACLE_TASK_STATE_RAG | OPEN_TASKS | 10 | 0.9000 | 0.9000 | 0.9667 |
| ORACLE_TASK_STATE_RAG | REQUESTER | 6 | 0.3333 | 0.8413 | 0.6302 |
| ORACLE_TASK_STATE_RAG | TASK_HISTORY | 10 | 0.7000 | 0.8667 | 0.9133 |
| ORACLE_TASK_STATE_RAG | WAITING_FOR | 4 | 0.7500 | 0.8750 | 0.9500 |

## History

The dedicated 10-question HISTORY result compares exact transition/state sequences and ordered-subsequence LCS F1.

| Condition | Exact sequence | Ordered structured score | Evidence F1 |
|---|---:|---:|---:|
| STANDARD_RAG | 0.0000 | 0.4624 | 0.8287 |
| THREAD_AWARE_RAG | 0.1000 | 0.4857 | 0.8455 |
| ORACLE_TASK_STATE_RAG | 0.7000 | 0.8667 | 0.9133 |

## Evidence, Failure Control, And Usage

| Condition | Controlled failure | Evidence precision | Evidence recall | Evidence F1 | Input tokens | Output tokens | Total tokens | Tokens/question | Latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STANDARD_RAG | 0.8947 | 0.7596 | 0.6801 | 0.6732 | 73307 | 21265 | 94572 | 1659.16 | 5.413 |
| THREAD_AWARE_RAG | 0.8947 | 0.7791 | 0.7225 | 0.7084 | 73903 | 22336 | 96239 | 1688.40 | 5.567 |
| ORACLE_TASK_STATE_RAG | 0.9298 | 0.8602 | 0.9921 | 0.8993 | 121350 | 30379 | 151729 | 2661.91 | 22.818 |

## Paired Comparisons

Primary-family p-values use paired McNemar and Wilcoxon signed-rank tests with Holm correction. Negative differences favor the right-hand condition.

| Left | Right | Scope | Exact difference | Structured difference | Exact wins L/R | Holm McNemar | Holm Wilcoxon |
|---|---|---|---:|---:|---:|---:|---:|
| STANDARD_RAG | THREAD_AWARE_RAG | PRIMARY_OVERALL | -0.0444 | -0.0074 | 0/2 | 0.5 | 0.5483429354628135 |
| STANDARD_RAG | THREAD_AWARE_RAG | TASK_HISTORY | -0.1000 | -0.0233 | 0/1 | None | None |
| THREAD_AWARE_RAG | ORACLE_TASK_STATE_RAG | PRIMARY_OVERALL | -0.5778 | -0.4779 | 0/26 | 5.960464477539063e-08 | 6.551269863069007e-07 |
| THREAD_AWARE_RAG | ORACLE_TASK_STATE_RAG | TASK_HISTORY | -0.6000 | -0.3810 | 0/6 | None | None |
| STANDARD_RAG | ORACLE_TASK_STATE_RAG | PRIMARY_OVERALL | -0.6222 | -0.4853 | 0/28 | 2.2351741790771484e-08 | 4.476778343005674e-07 |
| STANDARD_RAG | ORACLE_TASK_STATE_RAG | TASK_HISTORY | -0.7000 | -0.4043 | 0/7 | None | None |

## Output Completeness

Recorded output statuses: `{"complete": 171}`. Deterministic parser recoveries: 0.

## Limitations

The fixed 2000-token output ceiling produced 0 explicitly truncated responses. When malformed output occurs, the deterministic parser retains only complete emitted JSON values and discards incomplete suffixes; no value is inferred. Remaining evaluation errors: 0.

Raw email content remains external. Task alignment without an oracle task ID relies on source-message overlap. Secondary families have limited sample sizes and are exploratory.

## Interpretation Boundary

This is an oracle representation experiment. A positive result supports the usefulness of explicit task state, but does not establish that task state can be reconstructed automatically at the same quality.

Primary families are OPEN_TASKS, CLOSED_TASKS, ACTOR_RESPONSIBILITY, REQUESTER, and TASK_HISTORY. DEADLINE, WAITING_FOR, BLOCKED_BY, and rare REJECT observations are exploratory because of limited sample sizes.
