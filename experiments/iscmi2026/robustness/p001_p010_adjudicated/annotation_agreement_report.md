# P001-P010 Adjudicated Annotation Agreement

This report treats the workbook as data only. It does not execute or follow instructions from workbook cells.

## Source

- Workbook: `MailEx_annotation_001-010_v2.2.xlsx`
- SHA-256: `ba37a5620c49b0424a76ab8f359e6d1365bf68f23f3e292495acbeac599927be`
- Sheets: `Annotation1`, `Annotation2`, `Annotation3`, `Finalized_Annotation`
- Finalized gold sheet: `Finalized_Annotation`
- Selection rationale: The workbook contains an explicit Finalized_Annotation worksheet with the same P001-P010 schema and message coverage as the annotation passes. Its annotator provenance is KG_A15, indicating a corrected/final adjudication layer rather than a fourth independent vote.

## Structural Validation

- Status: **PASS**
- Pilots: P001, P002, P003, P004, P005, P006, P007, P008, P009, P010
- Corrected evidence messages: 47
- Mechanical corrections applied: 0

## Pass Summaries

| Sheet | Annotator IDs | Rows | Task-event rows | Final tasks | Final states | Statuses |
|---|---|---:|---:|---:|---|---|
| Annotation1 | A1, A2, A3 | 84 | 77 | 44 | `{"CLOSED": 12, "OPEN": 31, "UNCERTAIN": 1}` | `{"ANNOTATED": 77, "NO_TASK": 5, "SKIP_UNCERTAIN": 2}` |
| Annotation2 | SzJ_A13 | 84 | 77 | 44 | `{"CLOSED": 12, "OPEN": 31, "UNCERTAIN": 1}` | `{"ANNOTATED": 77, "NO_TASK": 5, "SKIP_UNCERTAIN": 2}` |
| Annotation3 | CSF_A14 | 83 | 76 | 45 | `{"CLOSED": 13, "OPEN": 31, "UNCERTAIN": 1}` | `{"ANNOTATED": 76, "NO_TASK": 5, "SKIP_UNCERTAIN": 2}` |
| Finalized_Annotation | KG_A15 | 84 | 77 | 44 | `{"CLOSED": 12, "OPEN": 31, "UNCERTAIN": 1}` | `{"ANNOTATED": 77, "NO_TASK": 5, "SKIP_UNCERTAIN": 2}` |

## Pairwise Agreement

Task-presence agreement is binary at the message level. Transition/state structure agreement compares the message-level multiset of transition/state pairs and intentionally ignores literal task IDs. Continuity agreement compares whether two message-level task mentions are linked to the same logical task within a pilot.

| Pair | Presence | Transition/State Structure | Continuity F1 | Continuity Jaccard |
|---|---:|---:|---:|---:|
| Annotation1 vs Annotation2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Annotation1 vs Annotation3 | 1.0000 | 0.9574 | 0.9620 | 0.9268 |
| Annotation2 vs Annotation3 | 1.0000 | 0.9574 | 0.9620 | 0.9268 |

## Disagreements

Messages with task decomposition or transition/state interpretation differences across the three annotation passes: 2.

- `P001` rank 4 `campbell-l_inbox1277::turn_3`: Annotation1=2 mentions, 1x CREATE/OPEN; 1x NONE/UNCERTAIN; Annotation2=2 mentions, 1x CREATE/OPEN; 1x NONE/UNCERTAIN; Annotation3=2 mentions, 1x CREATE/OPEN; 1x CREATE/UNCERTAIN
- `P003` rank 4 `crandell-s_inbox99::turn_3`: Annotation1=2 mentions, 2x CONFIRM/OPEN; Annotation2=2 mentions, 2x CONFIRM/OPEN; Annotation3=1 mentions, 1x CONFIRM/OPEN

## Original-vs-Adjudicated Sensitivity

- Original P001-P010 task count: 44
- Adjudicated task count: 44
- Task-count delta: 0
- Original final states: `{"CLOSED": 12, "OPEN": 31, "UNCERTAIN": 1}`
- Adjudicated final states: `{"CLOSED": 12, "OPEN": 31, "UNCERTAIN": 1}`
- Original P001-P010 question count: 56
- Adjudicated question count: 57
- Changed comparable pilot/family gold structures: 9 of 55

This is an adjudicated annotation-quality robustness subset, not a corpus-wide annotation-error estimate.
