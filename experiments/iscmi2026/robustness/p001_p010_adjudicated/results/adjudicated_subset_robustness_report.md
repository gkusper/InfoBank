# P001-P010 Adjudicated Subset Robustness Report

**This experiment tests annotation-quality robustness of the oracle task-state representation on the adjudicated P001–P010 subset. It does not evaluate automatic task-state extraction.**

## Source And Benchmark

- Workbook: `MailEx_annotation_001-010_v2.2.xlsx`
- Workbook SHA-256: `ba37a5620c49b0424a76ab8f359e6d1365bf68f23f3e292495acbeac599927be`
- Annotation sheets: `Annotation1`, `Annotation2`, `Annotation3`
- Finalized gold sheet: `Finalized_Annotation`
- Corrected evidence messages: 47
- Final tasks: 44 ({'CLOSED': 12, 'OPEN': 31, 'UNCERTAIN': 1})
- Questions: 57 ({'ACTOR_RESPONSIBILITY': 9, 'BLOCKED_BY': 2, 'CLOSED_TASKS': 10, 'DEADLINE': 1, 'NO_TASK_CONTROL': 5, 'OPEN_TASKS': 10, 'REQUESTER': 6, 'TASK_HISTORY': 10, 'WAITING_FOR': 4})
- Benchmark content hash: `b286aa64237a302a497cd41b2d27ca5a6e0240603caadc81357505f9aa767af2`

## Annotation Agreement

- Task-presence agreement: {'Annotation1_vs_Annotation2': 1.0, 'Annotation1_vs_Annotation3': 1.0, 'Annotation2_vs_Annotation3': 1.0}
- Transition/state structure agreement: {'Annotation1_vs_Annotation2': 1.0, 'Annotation1_vs_Annotation3': 0.95744681, 'Annotation2_vs_Annotation3': 0.95744681}
- Decomposition or structure disagreement messages: 2
- Mechanical corrections applied: 0

## Full Benchmark Reference

The cloned branch does not contain the frozen full-run aggregate result directories. The comparison therefore uses the full-benchmark structured uplift reference values supplied in the request; full primary Exact/Structured, family, HISTORY, NO_TASK_CONTROL, and evidence-grounding tables are not guessed from unavailable files.

## GPT-4o-mini

| Condition | Exact | Structured | Evidence F1 |
|---|---:|---:|---:|
| STANDARD_RAG | 0.0667 | 0.3290 | 0.7269 |
| THREAD_AWARE_RAG | 0.0667 | 0.2881 | 0.6907 |
| ORACLE_TASK_STATE_RAG | 0.6667 | 0.8186 | 0.8831 |

- Oracle-minus-Thread structured uplift: 0.5304 (full reference 0.5538)
- Oracle-minus-Standard structured uplift: 0.4896 (full reference 0.5328)
- Thread bootstrap Oracle-minus-Thread mean/95% interval: 0.5209 [0.4185, 0.6110]

### GPT-4o-mini History

| Condition | Exact Sequence | Ordered Structured | Evidence F1 |
|---|---:|---:|---:|
| STANDARD_RAG | 0.0000 | 0.4261 | 0.7935 |
| THREAD_AWARE_RAG | 0.0000 | 0.4590 | 0.8107 |
| ORACLE_TASK_STATE_RAG | 0.5000 | 0.8108 | 0.8723 |

### GPT-4o-mini NO_TASK_CONTROL

| Condition | N | Exact | Structured | Evidence F1 |
|---|---:|---:|---:|---:|
| STANDARD_RAG | 5 | 1.0000 | 1.0000 | 0.8800 |
| THREAD_AWARE_RAG | 5 | 1.0000 | 1.0000 | 1.0000 |
| ORACLE_TASK_STATE_RAG | 5 | 1.0000 | 1.0000 | 0.6000 |

## GPT-4.1

| Condition | Exact | Structured | Evidence F1 |
|---|---:|---:|---:|
| STANDARD_RAG | 0.1111 | 0.3639 | 0.6550 |
| THREAD_AWARE_RAG | 0.1556 | 0.3713 | 0.6714 |
| ORACLE_TASK_STATE_RAG | 0.7333 | 0.8492 | 0.8976 |

- Oracle-minus-Thread structured uplift: 0.4779 (full reference 0.5300)
- Oracle-minus-Standard structured uplift: 0.4853 (full reference 0.5490)
- Thread bootstrap Oracle-minus-Thread mean/95% interval: 0.4623 [0.3406, 0.5760]

### GPT-4.1 History

| Condition | Exact Sequence | Ordered Structured | Evidence F1 |
|---|---:|---:|---:|
| STANDARD_RAG | 0.0000 | 0.4624 | 0.8287 |
| THREAD_AWARE_RAG | 0.1000 | 0.4857 | 0.8455 |
| ORACLE_TASK_STATE_RAG | 0.7000 | 0.8667 | 0.9133 |

### GPT-4.1 NO_TASK_CONTROL

| Condition | N | Exact | Structured | Evidence F1 |
|---|---:|---:|---:|---:|
| STANDARD_RAG | 5 | 0.8000 | 0.8000 | 0.8000 |
| THREAD_AWARE_RAG | 5 | 0.8000 | 0.8000 | 1.0000 |
| ORACLE_TASK_STATE_RAG | 5 | 1.0000 | 1.0000 | 1.0000 |

## Robustness Conclusion

**Does the substantial Oracle Task-State advantage remain on the adjudicated P001-P010 subset? YES.**

Both generators retain large positive primary structured uplifts for ORACLE_TASK_STATE_RAG over THREAD_AWARE_RAG on the adjudicated subset. The subset uplifts are slightly smaller than the full 50-thread references, but remain of the same order of magnitude.

- GPT-4o-mini full vs adjudicated Oracle-minus-Thread: 0.5538 vs 0.5304
- GPT-4.1 full vs adjudicated Oracle-minus-Thread: 0.5300 vs 0.4779

**Classification: ROBUST TO ADJUDICATED ANNOTATION.**

The subset has only 10 threads and question outcomes are clustered by thread, so conventional question-level p-values should not be treated as independent-observation evidence. The thread-level bootstrap above is descriptive sensitivity analysis, not a corpus-wide uncertainty estimate.

## Integrity

- Leakage validation: PASS for both generator snapshots and final result files
- Raw emails committed: NO
- Secrets committed: NO
- Previous benchmark fixture hashes unchanged: PASS for committed fixture hashes
- Previous result files changed: NO tracked previous full-run result files are present in this checkout
- Operational note: The first GPT-4.1 attempt produced two rate-limit error records; those failed records were removed from the JSONL and rerun with one worker. Final result files contain 171 complete records, zero API errors, and zero parser recoveries for each model.
