# ISCMI 2026 Oracle Task-State RAG Experiment

Run mode: `real_api`. Questions: 57. Conditions: 3. Evaluations: 171.

The three conditions use the same generator and output schema. STANDARD_RAG uses semantic email-message retrieval; THREAD_AWARE_RAG expands to the complete chronological email thread; ORACLE_TASK_STATE_RAG additionally receives the human-derived task representation.

## Frozen Configuration

Generator: `gpt-4o-mini-2024-07-18`; embedding: `text-embedding-3-small`; temperature: `0.0`; maximum output tokens: `2000`.

## Primary Summary

| Condition | Exact | Structured | Controlled failure | Evidence F1 | Calls | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| STANDARD_RAG | 0.0667 | 0.3290 | 0.8421 | 0.7269 | 57 | 92700 |
| THREAD_AWARE_RAG | 0.0667 | 0.2881 | 0.8596 | 0.6907 | 57 | 91435 |
| ORACLE_TASK_STATE_RAG | 0.6667 | 0.8186 | 0.9649 | 0.8831 | 57 | 155658 |

## Family Results

| Condition | Family | N | Exact | Structured | Evidence F1 |
|---|---|---:|---:|---:|---:|
| STANDARD_RAG | ACTOR_RESPONSIBILITY | 9 | 0.0000 | 0.0741 | 0.6829 |
| STANDARD_RAG | BLOCKED_BY | 2 | 0.0000 | 0.0000 | 0.3667 |
| STANDARD_RAG | CLOSED_TASKS | 10 | 0.1000 | 0.3000 | 0.7187 |
| STANDARD_RAG | DEADLINE | 1 | 0.0000 | 0.4000 | 0.6667 |
| STANDARD_RAG | NO_TASK_CONTROL | 5 | 1.0000 | 1.0000 | 0.8800 |
| STANDARD_RAG | OPEN_TASKS | 10 | 0.2000 | 0.5542 | 0.8143 |
| STANDARD_RAG | REQUESTER | 6 | 0.0000 | 0.2222 | 0.5500 |
| STANDARD_RAG | TASK_HISTORY | 10 | 0.0000 | 0.4261 | 0.7935 |
| STANDARD_RAG | WAITING_FOR | 4 | 0.0000 | 0.2000 | 0.8056 |
| THREAD_AWARE_RAG | ACTOR_RESPONSIBILITY | 9 | 0.0000 | 0.0000 | 0.6728 |
| THREAD_AWARE_RAG | BLOCKED_BY | 2 | 0.0000 | 0.0000 | 0.3667 |
| THREAD_AWARE_RAG | CLOSED_TASKS | 10 | 0.1000 | 0.2833 | 0.6964 |
| THREAD_AWARE_RAG | DEADLINE | 1 | 0.0000 | 0.4000 | 0.6667 |
| THREAD_AWARE_RAG | NO_TASK_CONTROL | 5 | 1.0000 | 1.0000 | 1.0000 |
| THREAD_AWARE_RAG | OPEN_TASKS | 10 | 0.2000 | 0.5542 | 0.7889 |
| THREAD_AWARE_RAG | REQUESTER | 6 | 0.0000 | 0.0000 | 0.3444 |
| THREAD_AWARE_RAG | TASK_HISTORY | 10 | 0.0000 | 0.4590 | 0.8107 |
| THREAD_AWARE_RAG | WAITING_FOR | 4 | 0.0000 | 0.2000 | 0.5804 |
| ORACLE_TASK_STATE_RAG | ACTOR_RESPONSIBILITY | 9 | 0.8889 | 0.9206 | 1.0000 |
| ORACLE_TASK_STATE_RAG | BLOCKED_BY | 2 | 0.5000 | 0.8333 | 0.7000 |
| ORACLE_TASK_STATE_RAG | CLOSED_TASKS | 10 | 0.8000 | 0.8000 | 0.8829 |
| ORACLE_TASK_STATE_RAG | DEADLINE | 1 | 1.0000 | 1.0000 | 1.0000 |
| ORACLE_TASK_STATE_RAG | NO_TASK_CONTROL | 5 | 1.0000 | 1.0000 | 0.6000 |
| ORACLE_TASK_STATE_RAG | OPEN_TASKS | 10 | 0.9000 | 0.9889 | 0.9889 |
| ORACLE_TASK_STATE_RAG | REQUESTER | 6 | 0.0000 | 0.4254 | 0.5500 |
| ORACLE_TASK_STATE_RAG | TASK_HISTORY | 10 | 0.5000 | 0.8108 | 0.8723 |
| ORACLE_TASK_STATE_RAG | WAITING_FOR | 4 | 0.2500 | 0.6500 | 0.9167 |

## History

The dedicated 10-question HISTORY result compares exact transition/state sequences and ordered-subsequence LCS F1.

| Condition | Exact sequence | Ordered structured score | Evidence F1 |
|---|---:|---:|---:|
| STANDARD_RAG | 0.0000 | 0.4261 | 0.7935 |
| THREAD_AWARE_RAG | 0.0000 | 0.4590 | 0.8107 |
| ORACLE_TASK_STATE_RAG | 0.5000 | 0.8108 | 0.8723 |

## Evidence, Failure Control, And Usage

| Condition | Controlled failure | Evidence precision | Evidence recall | Evidence F1 | Input tokens | Output tokens | Total tokens | Tokens/question | Latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STANDARD_RAG | 0.8421 | 0.7184 | 0.8766 | 0.7321 | 73307 | 19393 | 92700 | 1626.32 | 4.057 |
| THREAD_AWARE_RAG | 0.8596 | 0.6840 | 0.8173 | 0.6983 | 73903 | 17532 | 91435 | 1604.12 | 3.704 |
| ORACLE_TASK_STATE_RAG | 0.9649 | 0.8180 | 0.9570 | 0.8563 | 121350 | 34308 | 155658 | 2730.84 | 6.724 |

## Paired Comparisons

Primary-family p-values use paired McNemar and Wilcoxon signed-rank tests with Holm correction. Negative differences favor the right-hand condition.

| Left | Right | Scope | Exact difference | Structured difference | Exact wins L/R | Holm McNemar | Holm Wilcoxon |
|---|---|---|---:|---:|---:|---:|---:|
| STANDARD_RAG | THREAD_AWARE_RAG | PRIMARY_OVERALL | 0.0000 | 0.0408 | 1/1 | 1.0 | 0.1952308709703821 |
| STANDARD_RAG | THREAD_AWARE_RAG | TASK_HISTORY | 0.0000 | -0.0330 | 0/0 | None | None |
| THREAD_AWARE_RAG | ORACLE_TASK_STATE_RAG | PRIMARY_OVERALL | -0.6000 | -0.5304 | 0/27 | 4.470348358154297e-08 | 1.061138273489127e-07 |
| THREAD_AWARE_RAG | ORACLE_TASK_STATE_RAG | TASK_HISTORY | -0.5000 | -0.3518 | 0/5 | None | None |
| STANDARD_RAG | ORACLE_TASK_STATE_RAG | PRIMARY_OVERALL | -0.6000 | -0.4896 | 0/27 | 4.470348358154297e-08 | 1.061138273489127e-07 |
| STANDARD_RAG | ORACLE_TASK_STATE_RAG | TASK_HISTORY | -0.5000 | -0.3848 | 0/5 | None | None |

## Output Completeness

Recorded output statuses: `{"complete": 171}`. Deterministic parser recoveries: 0.

## Limitations

The fixed 2000-token output ceiling produced 0 explicitly truncated responses. When malformed output occurs, the deterministic parser retains only complete emitted JSON values and discards incomplete suffixes; no value is inferred. Remaining evaluation errors: 0.

Raw email content remains external. Task alignment without an oracle task ID relies on source-message overlap. Secondary families have limited sample sizes and are exploratory.

## Interpretation Boundary

This is an oracle representation experiment. A positive result supports the usefulness of explicit task state, but does not establish that task state can be reconstructed automatically at the same quality.

Primary families are OPEN_TASKS, CLOSED_TASKS, ACTOR_RESPONSIBILITY, REQUESTER, and TASK_HISTORY. DEADLINE, WAITING_FOR, BLOCKED_BY, and rare REJECT observations are exploratory because of limited sample sizes.
