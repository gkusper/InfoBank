# ISCMI 2026: GPT-4o-mini vs GPT-4.1

## Frozen Protocol

Validation: **PASS**. The fixed 271-question benchmark, ordered question IDs, three conditions, corrected packet, prompts, embeddings, retrieval, oracle records, parser, scoring, temperature 0.0, and 2000-token output limit match. Only the generator changes.

## Generator Difference

`gpt-4o-mini-2024-07-18` -> `gpt-4.1-2025-04-14`. Both runs use Chat Completions JSON mode. GPT-4.1 is a pinned non-reasoning snapshot, so no prompt, API, parser, or parameter adaptation was required.

## Primary Results

| Generator | Condition | Exact | Structured | Controlled failure | Evidence F1 |
|---|---|---:|---:|---:|---:|
| gpt-4o-mini-2024-07-18 | STANDARD_RAG | 0.1256 | 0.3612 | 0.8475 | 0.7727 |
| gpt-4o-mini-2024-07-18 | THREAD_AWARE_RAG | 0.1031 | 0.3402 | 0.8520 | 0.7618 |
| gpt-4o-mini-2024-07-18 | ORACLE_TASK_STATE_RAG | 0.6592 | 0.8940 | 0.9910 | 0.8799 |
| gpt-4.1-2025-04-14 | STANDARD_RAG | 0.1211 | 0.3737 | 0.9103 | 0.7125 |
| gpt-4.1-2025-04-14 | THREAD_AWARE_RAG | 0.1300 | 0.3927 | 0.9058 | 0.7342 |
| gpt-4.1-2025-04-14 | ORACLE_TASK_STATE_RAG | 0.8296 | 0.9227 | 0.9552 | 0.8338 |

## Task-State Uplift

Primary structured uplift is ORACLE_TASK_STATE_RAG minus the selected email-only baseline.

| Generator | Oracle - Thread-aware | Oracle - Standard |
|---|---:|---:|
| gpt-4o-mini-2024-07-18 | 0.5538 | 0.5328 |
| gpt-4.1-2025-04-14 | 0.5300 | 0.5490 |

## Family-Level Results

Values are exact/structured.

| Family | GPT-4o-mini Standard | GPT-4o-mini Thread | GPT-4o-mini Oracle | GPT-4.1 Standard | GPT-4.1 Thread | GPT-4.1 Oracle |
|---|---:|---:|---:|---:|---:|---:|
| OPEN_TASKS | 0.1400/0.4961 | 0.0800/0.4623 | 0.9800/0.9960 | 0.1800/0.5673 | 0.1800/0.5671 | 0.9400/0.9560 |
| CLOSED_TASKS | 0.3000/0.4747 | 0.3200/0.4804 | 0.8400/0.9258 | 0.2000/0.4266 | 0.2000/0.4764 | 0.8400/0.8400 |
| ACTOR_RESPONSIBILITY | 0.0000/0.0922 | 0.0000/0.0622 | 0.7556/0.9524 | 0.0222/0.1554 | 0.0667/0.1725 | 0.9556/0.9951 |
| REQUESTER | 0.0278/0.2139 | 0.0000/0.1468 | 0.3056/0.7631 | 0.0833/0.1436 | 0.0556/0.1552 | 0.6667/0.9067 |
| TASK_HISTORY | 0.1190/0.4800 | 0.0714/0.4913 | 0.2619/0.7841 | 0.0952/0.5113 | 0.1190/0.5249 | 0.6905/0.9174 |

## HISTORY Analysis

| Generator | Condition | Exact sequence | Ordered structured | Evidence F1 |
|---|---|---:|---:|---:|
| gpt-4o-mini-2024-07-18 | STANDARD_RAG | 0.1190 | 0.4800 | 0.8531 |
| gpt-4o-mini-2024-07-18 | THREAD_AWARE_RAG | 0.0714 | 0.4913 | 0.8665 |
| gpt-4o-mini-2024-07-18 | ORACLE_TASK_STATE_RAG | 0.2619 | 0.7841 | 0.9030 |
| gpt-4.1-2025-04-14 | STANDARD_RAG | 0.0952 | 0.5113 | 0.8511 |
| gpt-4.1-2025-04-14 | THREAD_AWARE_RAG | 0.1190 | 0.5249 | 0.8813 |
| gpt-4.1-2025-04-14 | ORACLE_TASK_STATE_RAG | 0.6905 | 0.9174 | 0.9257 |

## NO_TASK_CONTROL Analysis

| Generator | Condition | Exact | Structured | Controlled failure | Evidence F1 |
|---|---|---:|---:|---:|---:|
| gpt-4o-mini-2024-07-18 | STANDARD_RAG | 0.9474 | 0.9474 | 0.9474 | 0.6887 |
| gpt-4o-mini-2024-07-18 | THREAD_AWARE_RAG | 0.9474 | 0.9474 | 0.9474 | 0.9123 |
| gpt-4o-mini-2024-07-18 | ORACLE_TASK_STATE_RAG | 0.6316 | 0.6316 | 0.6316 | 0.5789 |
| gpt-4.1-2025-04-14 | STANDARD_RAG | 0.7368 | 0.7368 | 0.7368 | 0.8772 |
| gpt-4.1-2025-04-14 | THREAD_AWARE_RAG | 0.7368 | 0.7368 | 0.7368 | 1.0000 |
| gpt-4.1-2025-04-14 | ORACLE_TASK_STATE_RAG | 0.8421 | 0.8421 | 0.8421 | 0.8684 |

## Evidence Grounding

The overall evidence precision, recall, and F1 values are reported independently from answer correctness in the model-condition table below.

## Token, Latency, And Cost Comparison

| Generator | Condition | Overall exact | Overall structured | Controlled failure | Evidence F1 | Tokens/question | Mean latency | Median | P95 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gpt-4o-mini-2024-07-18 | STANDARD_RAG | 0.1808 | 0.3791 | 0.8487 | 0.7513 | 1448.52 | 3.540 | 3.460 | 6.240 |
| gpt-4o-mini-2024-07-18 | THREAD_AWARE_RAG | 0.1624 | 0.3618 | 0.8524 | 0.7545 | 1464.67 | 3.550 | 3.323 | 6.689 |
| gpt-4o-mini-2024-07-18 | ORACLE_TASK_STATE_RAG | 0.6568 | 0.8664 | 0.9668 | 0.8558 | 2567.90 | 6.570 | 5.889 | 13.862 |
| gpt-4.1-2025-04-14 | STANDARD_RAG | 0.1661 | 0.3772 | 0.9077 | 0.7287 | 1521.26 | 15.587 | 5.150 | 12.406 |
| gpt-4.1-2025-04-14 | THREAD_AWARE_RAG | 0.1697 | 0.3923 | 0.9041 | 0.7600 | 1554.61 | 15.557 | 4.509 | 13.324 |
| gpt-4.1-2025-04-14 | ORACLE_TASK_STATE_RAG | 0.8303 | 0.9142 | 0.9520 | 0.8285 | 2542.14 | 63.129 | 10.011 | 129.515 |

Estimated actual run costs use official prices accessed 2026-08-24 and include the shared embedding pass: GPT-4o-mini `$0.3629`; GPT-4.1 `$5.1255`.

## Statistical Interpretation

The GPT-4.1 run uses the same paired McNemar and Wilcoxon signed-rank tests with Holm correction as the GPT-4o-mini run. Full rows remain in `pairwise_comparisons.csv`; the selected primary and HISTORY rows are also preserved in the comparison JSON.

## Limitations

Temperature 0 does not guarantee bit-identical service output. Model tokenization, response length, and latency differ. The oracle records are human-derived and do not measure automatic task-state extraction. NO_TASK_CONTROL remains a separate test of task-existence gating.

## Model-Robustness Conclusion

Pattern: **A**. STANDARD and THREAD_AWARE remain similar and both remain well below ORACLE under both generators.

Explicit Oracle Task-State representation still provides a substantial advantage with GPT-4.1: **YES**.

This is a generator-model robustness experiment using the same fixed benchmark and oracle task representation as the GPT-4o-mini run. No automatic task-state extraction claim is evaluated.
