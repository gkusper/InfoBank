# Actual-pipeline development output-class coverage

Status: `DEVELOPMENT_ONLY_NOT_FROZEN`

Dataset: `actual-pipeline-development-v1`. The builder creates 15 deterministic synthetic PDFs in three device families and 20 QueryInput rows. QueryInput and GoldAnnotation are separate files; execution never opens the gold file. Candidate holdout data was not read.

| Retained output class | Positive development cases | Neighbor/contrast | Runtime decision source | Reason coverage |
|---|---:|---|---|---|
| `FULL_ANSWER` | 2 | insufficient evidence | provider over permitted context | `supported` |
| `CONSTRAINED_ANSWER` | 2 | authority-required conflict refusal | role-aware conflict gate | `conflict_defeat` |
| `AGGREGATE_RESULT` | 2 | below-k refusal | aggregate executor | `aggregate_threshold_satisfied` |
| `METADATA_ONLY` | 2 | Full and Deny | policy engine plus content withholding | `governance` |
| `CLARIFICATION` | 2 | specific object query | pre-generation query gate | `epistemic` |
| `REFUSE_PERMISSION` | 2 | permitted Reader query | policy engine | `governance` |
| `REFUSE_INSUFFICIENT_EVIDENCE` | 2 | supported object fact | measured support gate | `evidential` |
| `REFUSE_NO_MATCH` | 2 | known object ID | exact object resolver plus no-match gate | `epistemic` |
| `REFUSE_AGGREGATION_THRESHOLD` | 2 | k-satisfied aggregate | aggregate executor | `aggregation_threshold_not_met` |
| `REFUSE_CONFLICT` | 2 | bounded conflict summary | authority-sensitive conflict gate | `conflict_defeat` |

`ESCALATE_TO_HUMAN` is marked `FUTURE`: mutation requests are outside the paper's evaluation scope and are not represented by an artificial positive evaluation case.

Automated coverage tests verify two positives per retained class, neighboring contrast pairs, scorer support, separation of runtime inputs from annotations, and absence of B0/B1 switches from production routes. All labels remain pending human QA.
