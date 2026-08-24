# ISCMI 2026 Oracle Task-State RAG Experiment

Run mode: `real_api`. Questions: 271. Conditions: 3. Evaluations: 813.

The three conditions use the same generator and output schema. STANDARD_RAG uses semantic email-message retrieval; THREAD_AWARE_RAG expands to the complete chronological email thread; ORACLE_TASK_STATE_RAG additionally receives the human-derived task representation.

## Frozen Configuration

Generator: `gpt-4.1-2025-04-14`; embedding: `text-embedding-3-small`; temperature: `0.0`; maximum output tokens: `2000`.

## Primary Summary

| Condition | Exact | Structured | Controlled failure | Evidence F1 | Calls | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| STANDARD_RAG | 0.1211 | 0.3737 | 0.9077 | 0.7125 | 271 | 412262 |
| THREAD_AWARE_RAG | 0.1300 | 0.3927 | 0.9041 | 0.7342 | 271 | 421299 |
| ORACLE_TASK_STATE_RAG | 0.8296 | 0.9227 | 0.9520 | 0.8338 | 271 | 688921 |

## Family Results

| Condition | Family | N | Exact | Structured | Evidence F1 |
|---|---|---:|---:|---:|---:|
| STANDARD_RAG | ACTOR_RESPONSIBILITY | 45 | 0.0222 | 0.1554 | 0.6219 |
| STANDARD_RAG | BLOCKED_BY | 4 | 0.0000 | 0.0000 | 0.8333 |
| STANDARD_RAG | CLOSED_TASKS | 50 | 0.2000 | 0.4266 | 0.7345 |
| STANDARD_RAG | DEADLINE | 6 | 0.6667 | 0.7500 | 0.7222 |
| STANDARD_RAG | NO_TASK_CONTROL | 19 | 0.7368 | 0.7368 | 0.8772 |
| STANDARD_RAG | OPEN_TASKS | 50 | 0.1800 | 0.5673 | 0.7671 |
| STANDARD_RAG | REQUESTER | 36 | 0.0833 | 0.1436 | 0.5575 |
| STANDARD_RAG | TASK_HISTORY | 42 | 0.0952 | 0.5113 | 0.8511 |
| STANDARD_RAG | WAITING_FOR | 19 | 0.0000 | 0.0211 | 0.7504 |
| THREAD_AWARE_RAG | ACTOR_RESPONSIBILITY | 45 | 0.0667 | 0.1725 | 0.6485 |
| THREAD_AWARE_RAG | BLOCKED_BY | 4 | 0.0000 | 0.0000 | 0.7667 |
| THREAD_AWARE_RAG | CLOSED_TASKS | 50 | 0.2000 | 0.4764 | 0.7905 |
| THREAD_AWARE_RAG | DEADLINE | 6 | 0.5000 | 0.7247 | 0.8056 |
| THREAD_AWARE_RAG | NO_TASK_CONTROL | 19 | 0.7368 | 0.7368 | 1.0000 |
| THREAD_AWARE_RAG | OPEN_TASKS | 50 | 0.1800 | 0.5671 | 0.7716 |
| THREAD_AWARE_RAG | REQUESTER | 36 | 0.0556 | 0.1552 | 0.5398 |
| THREAD_AWARE_RAG | TASK_HISTORY | 42 | 0.1190 | 0.5249 | 0.8813 |
| THREAD_AWARE_RAG | WAITING_FOR | 19 | 0.0000 | 0.0211 | 0.8065 |
| ORACLE_TASK_STATE_RAG | ACTOR_RESPONSIBILITY | 45 | 0.9556 | 0.9951 | 0.8355 |
| ORACLE_TASK_STATE_RAG | BLOCKED_BY | 4 | 0.7500 | 0.8750 | 0.6417 |
| ORACLE_TASK_STATE_RAG | CLOSED_TASKS | 50 | 0.8400 | 0.8400 | 0.8156 |
| ORACLE_TASK_STATE_RAG | DEADLINE | 6 | 1.0000 | 1.0000 | 0.6389 |
| ORACLE_TASK_STATE_RAG | NO_TASK_CONTROL | 19 | 0.8421 | 0.8421 | 0.8684 |
| ORACLE_TASK_STATE_RAG | OPEN_TASKS | 50 | 0.9400 | 0.9560 | 0.8893 |
| ORACLE_TASK_STATE_RAG | REQUESTER | 36 | 0.6667 | 0.9067 | 0.6725 |
| ORACLE_TASK_STATE_RAG | TASK_HISTORY | 42 | 0.6905 | 0.9174 | 0.9257 |
| ORACLE_TASK_STATE_RAG | WAITING_FOR | 19 | 0.7895 | 0.8684 | 0.8261 |

## History

The dedicated 42-question HISTORY result compares exact transition/state sequences and ordered-subsequence LCS F1.

| Condition | Exact sequence | Ordered structured score | Evidence F1 |
|---|---:|---:|---:|
| STANDARD_RAG | 0.0952 | 0.5113 | 0.8511 |
| THREAD_AWARE_RAG | 0.1190 | 0.5249 | 0.8813 |
| ORACLE_TASK_STATE_RAG | 0.6905 | 0.9174 | 0.9257 |

## Evidence, Failure Control, And Usage

| Condition | Controlled failure | Evidence precision | Evidence recall | Evidence F1 | Input tokens | Output tokens | Total tokens | Tokens/question | Latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STANDARD_RAG | 0.9077 | 0.8097 | 0.7308 | 0.7287 | 315594 | 96668 | 412262 | 1521.26 | 15.587 |
| THREAD_AWARE_RAG | 0.9041 | 0.8312 | 0.7621 | 0.7600 | 320004 | 101295 | 421299 | 1554.61 | 15.557 |
| ORACLE_TASK_STATE_RAG | 0.9520 | 0.7723 | 0.9656 | 0.8285 | 540262 | 148659 | 688921 | 2542.14 | 63.129 |

## Paired Comparisons

Primary-family p-values use paired McNemar and Wilcoxon signed-rank tests with Holm correction. Negative differences favor the right-hand condition.

| Left | Right | Scope | Exact difference | Structured difference | Exact wins L/R | Holm McNemar | Holm Wilcoxon |
|---|---|---|---:|---:|---:|---:|---:|
| STANDARD_RAG | THREAD_AWARE_RAG | PRIMARY_OVERALL | -0.0090 | -0.0190 | 5/7 | 1.0 | 1.0 |
| STANDARD_RAG | THREAD_AWARE_RAG | TASK_HISTORY | -0.0238 | -0.0137 | 1/2 | 1.0 | 1.0 |
| THREAD_AWARE_RAG | ORACLE_TASK_STATE_RAG | PRIMARY_OVERALL | -0.6996 | -0.5300 | 2/158 | 2.9966028693599167e-43 | 6.775154478117258e-31 |
| THREAD_AWARE_RAG | ORACLE_TASK_STATE_RAG | TASK_HISTORY | -0.5714 | -0.3925 | 2/26 | 2.1226704120635986e-05 | 1.0799641223104385e-06 |
| STANDARD_RAG | ORACLE_TASK_STATE_RAG | PRIMARY_OVERALL | -0.7085 | -0.5490 | 1/159 | 3.9657841304817577e-45 | 1.8890493867436166e-31 |
| STANDARD_RAG | ORACLE_TASK_STATE_RAG | TASK_HISTORY | -0.5952 | -0.4062 | 1/26 | 4.172325134277344e-06 | 1.0616945089081154e-06 |

## Output Completeness

Recorded output statuses: `{"complete": 812, "truncated_by_output_limit": 1}`. Deterministic parser recoveries: 1.

## Limitations

The fixed 2000-token output ceiling produced 1 explicitly truncated responses. When malformed output occurs, the deterministic parser retains only complete emitted JSON values and discards incomplete suffixes; no value is inferred. Remaining evaluation errors: 0.

Raw email content remains external. Task alignment without an oracle task ID relies on source-message overlap. Secondary families have limited sample sizes and are exploratory.

## Interpretation Boundary

This is an oracle representation experiment. A positive result supports the usefulness of explicit task state, but does not establish that task state can be reconstructed automatically at the same quality.

Primary families are OPEN_TASKS, CLOSED_TASKS, ACTOR_RESPONSIBILITY, REQUESTER, and TASK_HISTORY. DEADLINE, WAITING_FOR, BLOCKED_BY, and rare REJECT observations are exploratory because of limited sample sizes.

## Generator Robustness Comparison

Primary structured Oracle-minus-Thread uplift: GPT-4o-mini 0.5538; GPT-4.1 0.5300.

Robustness pattern: **A**. Explicit Oracle Task-State advantage remains substantial: **YES**.

See `comparison_gpt4omini_vs_gpt41.md` and `.json` for the complete cross-model analysis.
