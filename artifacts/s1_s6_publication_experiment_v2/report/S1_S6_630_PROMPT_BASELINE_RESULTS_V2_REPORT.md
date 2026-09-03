# S1-S6 630 Prompt Baseline Results V2 Report

## 1. Scope And Status
Final status: READY_FOR_MANUSCRIPT_RESULTS_UPDATE. The v2 experiment evaluates 42 frozen cases across C0, C1, P1, C2, and C3 for three real-provider repetitions, yielding a planned 630 measured records.

No scientific manuscript files are edited by this task.

## 2. Frozen Inputs
Combined validation status: PASS. Runtime/reference separation: PASS. Document-ID collisions: 0.

| Package | SHA-256 | Scenarios | Questions | PDFs | Annotations | Status |
| --- | --- | --- | --- | --- | --- | --- |
| S1-S2 | 83a9bb2394946b378af4efe2445be1e6e7095a60f5c14f6206ea1405f275bcd1 | 2 | 12 | 10 | 12 | PASS |
| S3-S6 | 3a5db23fddf55a007d013e09fd11ade74fcdf692847d01b0135346bdd3ddc50c | 4 | 30 | 31 | 30 | PASS |

## 3. Permission Model
| Layer | Status | Notes |
| --- | --- | --- |
| Persistent permissions | Implemented | Owner, Reader/Full, Aggregate, Metadata, query-limited grants, explainability-required grants, and Audit grants are stored on user-document relations. |
| Query-time effective decisions | Implemented | Runtime policy resolution maps grants and document rules to full, aggregate, metadata, or deny use decisions. |
| Document-level PolicyRule conditions | Preserved | PolicyRule purpose, valid_from, and valid_until remain document-level conditions and are not extended to persistent user-specific grants. |
| Document inventory caveat | Known limitation | Document inventory follows direct account permissions rather than the full document PolicyRule path. |
| Persistent time/purpose-bound grants | Not implemented / out of scope | The v2 scope deliberately excludes user-specific persistent purpose-bound and time-bounded grant constraints. |

## 4. New Governance Mechanisms
| Mechanism | Runtime enforcement | Persistent extension |
| --- | --- | --- |
| Query-limited access | Consumed and denied after grant capacity is exhausted. | max_queries and queries_used on the grant relation. |
| Explainability-required access | Answer paths must carry traceable source/page/chunk evidence when required. | requires_explainability on the grant relation. |
| Audit-only access | Audit grants do not provide content access and redact inventory metadata. | Audit grant type. |

## 5. Configuration Semantics
| Configuration | Retrieval | Routing | Permission filtering | Controlled-failure logic | Aggregate handling | Citation handling |
| --- | --- | --- | --- | --- | --- | --- |
| C0_VECTOR_ONLY | active documents ranked by vector/page-aware retrieval | disabled | disabled; active documents treated as usable | disabled; baseline generation except exact runtime errors | not governed as aggregate-only; baseline answer generation | answer citation selector after generation; refusals withhold citations |
| C1_VECTOR_ROUTING | keyword-routed candidate documents ranked by vector/page-aware retrieval | enabled except aggregate-only governance path | disabled; routed candidates treated as usable | disabled; baseline generation except exact runtime errors | not governed as aggregate-only; baseline answer generation | answer citation selector after generation; refusals withhold citations |
| P1_PROMPT_ONLY_GOVERNANCE | keyword-routed candidate documents ranked by vector/page-aware retrieval | enabled except aggregate-only prompt availability path | disabled; policy labels are provided only in the prompt | disabled; output class is selected by the provider response | no governed aggregate executor, threshold gate, or contributor deduplication | answer citation selector after generation; refusals withhold citations |
| C2_PERMISSION_FILTERED | permitted documents ranked by vector/page-aware retrieval | disabled | enabled through policy fixture use decisions | post-retrieval permission, no-match, insufficient-evidence, and aggregate-threshold gates | aggregate executor used when aggregate evidence is available | citations withheld for refusals and aggregate outputs; selected for answers |
| C3_FULL_ROLE_AWARE | routed permitted documents ranked by vector/page-aware retrieval | enabled for non-aggregate-only requests | enabled through policy fixture use decisions | pre-generation and post-retrieval controlled-failure and clarification gates | aggregate executor plus threshold and contributor-deduplication governance | citations withheld for refusals and aggregate outputs; selected with role-aware support for answers |

## 6. P1 Prompt-Only Governance
P1 prompt version: prompt-only-governance-v1. Prompt SHA-256: 982f197df7e1508cb978529f582cf405469abdc25fce84a6534d901a1b80bb4e.

P1 receives policy labels and descriptions next to retrieved sources. It does not use hard permission filtering, the governed aggregate executor, threshold/deduplication logic, CFAF, deterministic correction, or reference annotations at raw runtime.

## 7. AF_ALWAYS_FULL Baseline
AF_ALWAYS_FULL is offline label-only. Provider calls: 0. Accuracy: 0.690476. Balanced accuracy: 0.166667.

| Baseline | Cases | Output accuracy | Balanced accuracy | Macro recall | Provider calls | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AF_ALWAYS_FULL | 42 | 0.690476 | 0.166667 | 0.166667 | 0 | PASS |

## 8. Metrics
Utility metrics and safety counters are reported separately. Balanced accuracy is macro recall over the six frozen output classes.

Reference output-class distribution: `{"AGGREGATE_RESULT":5,"CLARIFICATION":1,"CONSTRAINED_ANSWER":3,"FULL_ANSWER":29,"REFUSE_AGGREGATION_THRESHOLD":1,"REFUSE_INSUFFICIENT_EVIDENCE":3}`.

## 9. Deterministic Run
DETERMINISTIC DEVELOPMENT AND REPRODUCIBILITY EVALUATION — NOT FINAL REAL-PROVIDER PERFORMANCE
Deterministic records: 210. Output accuracy: 0.7. Balanced accuracy: 0.308429. Safety findings: 50.

| Configuration | Cases | Output accuracy | Balanced accuracy | Permitted-answer accuracy | Controlled-failure correctness | Citation coverage | Safety findings | Tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 42 | 0.690476 | 0.166667 | 0.324324 | 0.0 | 0.357143 | 3 | 30653 |
| C1 | 42 | 0.690476 | 0.166667 | 0.324324 | 0.0 | 0.345238 | 3 | 30035 |
| C2 | 42 | 0.738095 | 0.52682 | 0.459459 | 0.538462 | 0.357143 | 0 | 20141 |
| C3 | 42 | 0.690476 | 0.515326 | 0.459459 | 0.538462 | 0.345238 | 0 | 23006 |
| P1 | 42 | 0.690476 | 0.166667 | 0.324324 | 0.0 | 0.345238 | 44 | 38445 |

## 10. Real-Provider Protocol
Protocol HEAD: 691bcef3bbcd015c62d7175facef966b9ac5d4d1. Preregistration SHA-256: b6cc5e10d2955f8111cff0bc154060e20406217f1dcc6324d15cf13d824b8477. Planned measured records: 630.

The run order is C0, C1, P1, C2, C3 for each of three repetitions. The no-tuning and no result-dependent rerun rules are locked in the protocol.

## 11. Overall Results
- C0: n=126, output=0.690476, balanced=0.166667, permitted=0.324324, controlled=0.0, citation=0.369048, safety=9, tokens=136527, errors=0
- C1: n=126, output=0.690476, balanced=0.166667, permitted=0.324324, controlled=0.0, citation=0.357143, safety=9, tokens=132763, errors=0
- C2: n=126, output=0.738095, balanced=0.52682, permitted=0.459459, controlled=0.538462, citation=0.369048, safety=0, tokens=89666, errors=0
- C3: n=126, output=0.690476, balanced=0.515326, permitted=0.459459, controlled=0.538462, citation=0.357143, safety=0, tokens=133254, errors=0
- P1: n=126, output=0.706349, balanced=0.308429, permitted=0.405405, controlled=0.384615, citation=0.353175, safety=132, tokens=194749, errors=0

| Configuration | Cases | Output accuracy | Balanced accuracy | Permitted-answer accuracy | Controlled-failure correctness | Citation coverage | Support precision | Page correctness | Safety findings | Tokens | Runtime/parser/provider errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 126 | 0.690476 | 0.166667 | 0.324324 | 0.0 | 0.369048 | 0.409639 | 0.277108 | 9 | 136527 | 0 |
| C1 | 126 | 0.690476 | 0.166667 | 0.324324 | 0.0 | 0.357143 | 0.432432 | 0.297297 | 9 | 132763 | 0 |
| C2 | 126 | 0.738095 | 0.52682 | 0.459459 | 0.538462 | 0.369048 | 0.578947 | 0.403509 | 0 | 89666 | 0 |
| C3 | 126 | 0.690476 | 0.515326 | 0.459459 | 0.538462 | 0.357143 | 0.690476 | 0.52381 | 0 | 133254 | 0 |
| P1 | 126 | 0.706349 | 0.308429 | 0.405405 | 0.384615 | 0.353175 | 0.445 | 0.325 | 132 | 194749 | 0 |

## 12. Scenario Results
| Configuration | Scenario | Cases | Output accuracy | Balanced accuracy | Citation coverage | Safety findings |
| --- | --- | --- | --- | --- | --- | --- |
| C0 | S1 | 18 | 0.833333 | 0.5 | 0.75 | 0 |
| C0 | S2 | 18 | 1.0 | 1.0 | 0.75 | 0 |
| C0 | S3 | 30 | 0.5 | 0.333333 | 0.1 | 3 |
| C0 | S4B | 24 | 0.5 | 0.2 | 0.041667 | 6 |
| C0 | S5B | 18 | 0.666667 | 0.5 | 0.333333 | 0 |
| C0 | S6 | 18 | 0.833333 | 0.5 | 0.527778 | 0 |
| C1 | S1 | 18 | 0.833333 | 0.5 | 0.75 | 0 |
| C1 | S2 | 18 | 1.0 | 1.0 | 0.75 | 0 |
| C1 | S3 | 30 | 0.5 | 0.333333 | 0.1 | 3 |
| C1 | S4B | 24 | 0.5 | 0.2 | 0.041667 | 6 |
| C1 | S5B | 18 | 0.666667 | 0.5 | 0.333333 | 0 |
| C1 | S6 | 18 | 0.833333 | 0.5 | 0.444444 | 0 |
| C2 | S1 | 18 | 1.0 | 1.0 | 0.75 | 0 |
| C2 | S2 | 18 | 1.0 | 1.0 | 0.75 | 0 |
| C2 | S3 | 30 | 0.6 | 0.466667 | 0.1 | 0 |
| C2 | S4B | 24 | 0.625 | 0.55 | 0.041667 | 0 |
| C2 | S5B | 18 | 0.5 | 0.375 | 0.333333 | 0 |
| C2 | S6 | 18 | 0.833333 | 0.5 | 0.527778 | 0 |
| C3 | S1 | 18 | 1.0 | 1.0 | 0.75 | 0 |
| C3 | S2 | 18 | 1.0 | 1.0 | 0.75 | 0 |
| C3 | S3 | 30 | 0.4 | 0.333333 | 0.1 | 0 |
| C3 | S4B | 24 | 0.625 | 0.55 | 0.041667 | 0 |
| C3 | S5B | 18 | 0.5 | 0.375 | 0.333333 | 0 |
| C3 | S6 | 18 | 0.833333 | 0.5 | 0.444444 | 0 |
| P1 | S1 | 18 | 0.833333 | 0.5 | 0.75 | 0 |
| P1 | S2 | 18 | 1.0 | 1.0 | 0.75 | 0 |
| P1 | S3 | 30 | 0.8 | 0.6 | 0.1 | 60 |
| P1 | S4B | 24 | 0.25 | 0.25 | 0.041667 | 51 |
| P1 | S5B | 18 | 0.666667 | 0.5 | 0.333333 | 0 |
| P1 | S6 | 18 | 0.777778 | 0.466666 | 0.416667 | 21 |

## 13. Class Balance And Confusion
| Configuration | Expected output class | Cases | Output accuracy | Balanced accuracy | Permitted-answer accuracy | Controlled-failure correctness |
| --- | --- | --- | --- | --- | --- | --- |
| C0 | AGGREGATE_RESULT | 15 | 0.0 | 0.0 | 0.0 | 0.0 |
| C0 | CLARIFICATION | 3 | 0.0 | 0.0 |  | 0.0 |
| C0 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 | 0.0 |
| C0 | FULL_ANSWER | 87 | 1.0 | 1.0 | 0.413793 |  |
| C0 | REFUSE_AGGREGATION_THRESHOLD | 3 | 0.0 | 0.0 |  | 0.0 |
| C0 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.0 | 0.0 |  | 0.0 |
| C1 | AGGREGATE_RESULT | 15 | 0.0 | 0.0 | 0.0 | 0.0 |
| C1 | CLARIFICATION | 3 | 0.0 | 0.0 |  | 0.0 |
| C1 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 | 0.0 |
| C1 | FULL_ANSWER | 87 | 1.0 | 1.0 | 0.413793 |  |
| C1 | REFUSE_AGGREGATION_THRESHOLD | 3 | 0.0 | 0.0 |  | 0.0 |
| C1 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.0 | 0.0 |  | 0.0 |
| C2 | AGGREGATE_RESULT | 15 | 1.0 | 1.0 | 1.0 | 1.0 |
| C2 | CLARIFICATION | 3 | 0.0 | 0.0 |  | 0.0 |
| C2 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 | 0.0 |
| C2 | FULL_ANSWER | 87 | 0.827586 | 0.827586 | 0.413793 |  |
| C2 | REFUSE_AGGREGATION_THRESHOLD | 3 | 1.0 | 1.0 |  | 1.0 |
| C2 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.333333 | 0.333333 |  | 0.333333 |
| C3 | AGGREGATE_RESULT | 15 | 1.0 | 1.0 | 1.0 | 1.0 |
| C3 | CLARIFICATION | 3 | 0.0 | 0.0 |  | 0.0 |
| C3 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 | 0.0 |
| C3 | FULL_ANSWER | 87 | 0.758621 | 0.758621 | 0.413793 |  |
| C3 | REFUSE_AGGREGATION_THRESHOLD | 3 | 1.0 | 1.0 |  | 1.0 |
| C3 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.333333 | 0.333333 |  | 0.333333 |
| P1 | AGGREGATE_RESULT | 15 | 1.0 | 1.0 | 0.6 | 1.0 |
| P1 | CLARIFICATION | 3 | 0.0 | 0.0 |  | 0.0 |
| P1 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 | 0.0 |
| P1 | FULL_ANSWER | 87 | 0.850575 | 0.850575 | 0.413793 |  |
| P1 | REFUSE_AGGREGATION_THRESHOLD | 3 | 0.0 | 0.0 |  | 0.0 |
| P1 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.0 | 0.0 |  | 0.0 |

Complete confusion matrices are exported in `openai/output_class_confusion_matrix.csv` and `openai/output_class_confusion_matrix.json`, including zero-count cells.

## 14. Safety Results
| Configuration | Total safety findings | prohibited_document_id_exposure | prohibited_text_fragment_exposure | source_existence_disclosure | denied_filename_hash_page_disclosure | aggregate_individual_value_exposure | generator_visible_restricted_text | archived_source_usage | wrong_permission_citation | local_path_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C1 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| P1 | 132 | 48 | 18 | 0 | 18 | 0 | 30 | 0 | 18 | 0 |

## 15. Utility Results
| Configuration | Permission group | Cases | Output accuracy | Balanced accuracy | Permitted-answer accuracy | Controlled-failure correctness | Citation coverage | Safety findings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | Aggregate-only | 18 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 9 |
| C0 | Owner/Full | 108 | 0.805556 | 0.25 | 0.375 | 0.0 | 0.430556 | 0 |
| C1 | Aggregate-only | 18 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 9 |
| C1 | Owner/Full | 108 | 0.805556 | 0.25 | 0.375 | 0.0 | 0.416667 | 0 |
| C2 | Aggregate-only | 18 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0 |
| C2 | Owner/Full | 108 | 0.694444 | 0.29023 | 0.375 | 0.142857 | 0.430556 | 0 |
| C3 | Aggregate-only | 18 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0 |
| C3 | Owner/Full | 108 | 0.638889 | 0.272988 | 0.375 | 0.142857 | 0.416667 | 0 |
| P1 | Aggregate-only | 18 | 0.833333 | 0.5 | 0.6 | 0.833333 | 0.0 | 90 |
| P1 | Owner/Full | 108 | 0.685185 | 0.212644 | 0.375 | 0.0 | 0.412037 | 42 |

| Configuration | Cases | Citation document coverage | Citation support precision | Page-level citation correctness | Citation coverage | Unsupported citation count | Wrong-document citation count | Wrong-page citation count | Missing-required-document count | Citation-free intentionally withheld |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 126 | 0.566667 | 0.409639 | 0.277108 | 0.369048 | 147 | 147 | 33 | 78 | 0 |
| C1 | 126 | 0.533333 | 0.432432 | 0.297297 | 0.357143 | 126 | 126 | 30 | 84 | 0 |
| C2 | 126 | 0.55 | 0.578947 | 0.403509 | 0.369048 | 72 | 72 | 30 | 81 | 39 |
| C3 | 126 | 0.483333 | 0.690476 | 0.52381 | 0.357143 | 39 | 39 | 21 | 93 | 45 |
| P1 | 126 | 0.494444 | 0.445 | 0.325 | 0.353175 | 111 | 111 | 24 | 91 | 13 |

| Repetition | Configuration | Aggregate-only cases | Aggregate numerical correctness | Output-class correctness | Threshold correctness | Duplicate/reissue handling S3-Q9 | Individual-value exposure | Withheld-value exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | C0 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 1 | C1 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 1 | C2 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 1 | C3 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 1 | P1 | 6 | 0.6 | 0.833333 | 0 | 1 | 0 | 6 |
| 2 | C0 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 2 | C1 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 2 | C2 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 2 | C3 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 2 | P1 | 6 | 0.6 | 0.833333 | 0 | 1 | 0 | 6 |
| 3 | C0 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 3 | C1 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 3 | C2 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 3 | C3 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 3 | P1 | 6 | 0.6 | 0.833333 | 0 | 1 | 0 | 6 |

## 16. Stability And Efficiency
{"case_configuration_rows":210,"complete_3_repetition_rows":210,"incomplete_rows":0,"one_off_failures":0,"output_class_stable_yes":209,"output_class_variable":1,"repeated_failures_3_of_3":0}

| Configuration | Cases | Mean latency | Median latency | P95 latency | Prompt/input tokens | Completion/output tokens | Total tokens | Recorded generation calls | Retry count | Failed call count | Recorded cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 126 | 3012.469875 | 2646.54135 | 6452.27385 | 128610 | 7917 | 136527 | 126 | 0 | 0 | NOT_RECORDED_BY_PROVIDER_ADAPTER |
| C1 | 126 | 2624.235148 | 2306.3567 | 5905.270825 | 125241 | 7522 | 132763 | 126 | 0 | 0 | NOT_RECORDED_BY_PROVIDER_ADAPTER |
| C2 | 126 | 3448.093007 | 3096.7848 | 6863.90795 | 83304 | 6362 | 89666 | 87 | 0 | 0 | NOT_RECORDED_BY_PROVIDER_ADAPTER |
| C3 | 126 | 3300.304078 | 2949.7695 | 7173.650525 | 127596 | 5658 | 133254 | 81 | 0 | 0 | NOT_RECORDED_BY_PROVIDER_ADAPTER |
| P1 | 126 | 3030.933139 | 2483.80495 | 5752.9851 | 186390 | 8359 | 194749 | 126 | 0 | 0 | NOT_RECORDED_BY_PROVIDER_ADAPTER |

| Repetition | Comparison | Metric | C0 wins | C1 wins | P1 wins | C2 wins | Ties | C0 losses | C1 losses | P1 losses | C2 losses | Compared cases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | C0 vs C1 | Output class | 0 |  |  |  | 42 | 0 |  |  |  | 42 |
| 1 | C0 vs C1 | Reason code | 0 |  |  |  | 42 | 0 |  |  |  | 42 |
| 1 | C0 vs C1 | Factual atoms | 0 |  |  |  | 42 | 0 |  |  |  | 42 |
| 1 | C0 vs C1 | Citation document coverage | 2 |  |  |  | 32 | 0 |  |  |  | 34 |
| 1 | C0 vs C1 | Safety clean | 0 |  |  |  | 42 | 0 |  |  |  | 42 |
| 1 | C1 vs P1 | Output class |  | 4 |  |  | 33 |  | 5 |  |  | 42 |
| 1 | C1 vs P1 | Reason code |  | 29 |  |  | 13 |  | 0 |  |  | 42 |
| 1 | C1 vs P1 | Factual atoms |  | 1 |  |  | 37 |  | 4 |  |  | 42 |
| 1 | C1 vs P1 | Citation document coverage |  | 2 |  |  | 32 |  | 0 |  |  | 34 |
| 1 | C1 vs P1 | Safety clean |  | 13 |  |  | 29 |  | 0 |  |  | 42 |
| 1 | P1 vs C2 | Output class |  |  | 3 |  | 35 |  |  | 4 |  | 42 |
| 1 | P1 vs C2 | Reason code |  |  | 0 |  | 11 |  |  | 31 |  | 42 |
| 1 | P1 vs C2 | Factual atoms |  |  | 1 |  | 38 |  |  | 3 |  | 42 |
| 1 | P1 vs C2 | Citation document coverage |  |  | 0 |  | 31 |  |  | 3 |  | 34 |
| 1 | P1 vs C2 | Safety clean |  |  | 0 |  | 26 |  |  | 16 |  | 42 |
| 1 | P1 vs C3 | Output class |  |  | 5 |  | 33 |  |  | 4 |  | 42 |
| 1 | P1 vs C3 | Reason code |  |  | 0 |  | 13 |  |  | 29 |  | 42 |
| 1 | P1 vs C3 | Factual atoms |  |  | 1 |  | 38 |  |  | 3 |  | 42 |
| 1 | P1 vs C3 | Citation document coverage |  |  | 2 |  | 31 |  |  | 1 |  | 34 |
| 1 | P1 vs C3 | Safety clean |  |  | 0 |  | 26 |  |  | 16 |  | 42 |
| 1 | C2 vs C3 | Output class |  |  |  | 2 | 40 |  |  |  | 0 | 42 |
| 1 | C2 vs C3 | Reason code |  |  |  | 2 | 40 |  |  |  | 0 | 42 |
| 1 | C2 vs C3 | Factual atoms |  |  |  | 0 | 42 |  |  |  | 0 | 42 |
| 1 | C2 vs C3 | Citation document coverage |  |  |  | 4 | 30 |  |  |  | 0 | 34 |
| 1 | C2 vs C3 | Safety clean |  |  |  | 0 | 42 |  |  |  | 0 | 42 |
| 2 | C0 vs C1 | Output class | 0 |  |  |  | 42 | 0 |  |  |  | 42 |
| 2 | C0 vs C1 | Reason code | 0 |  |  |  | 42 | 0 |  |  |  | 42 |
| 2 | C0 vs C1 | Factual atoms | 0 |  |  |  | 42 | 0 |  |  |  | 42 |
| 2 | C0 vs C1 | Citation document coverage | 2 |  |  |  | 32 | 0 |  |  |  | 34 |
| 2 | C0 vs C1 | Safety clean | 0 |  |  |  | 42 | 0 |  |  |  | 42 |

Additional rows omitted here: 45. See the CSV artifact for the full table.

| Repetition | Configuration | Metric | Numerator | Denominator | Value | Wilson 95% lower | Wilson 95% upper |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | C0 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 1 | C0 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 1 | C0 | permitted_answer_accuracy | 12 | 37 | 0.324324 | 0.196333 | 0.485363 |
| 1 | C0 | controlled_failure_correctness | 0 | 13 | 0.0 | 0.0 | 0.228095 |
| 1 | C1 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 1 | C1 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 1 | C1 | permitted_answer_accuracy | 12 | 37 | 0.324324 | 0.196333 | 0.485363 |
| 1 | C1 | controlled_failure_correctness | 0 | 13 | 0.0 | 0.0 | 0.228095 |
| 1 | C2 | output_class_accuracy | 31 | 42 | 0.738095 | 0.589313 | 0.846974 |
| 1 | C2 | reason_code_accuracy | 31 | 42 | 0.738095 | 0.589313 | 0.846974 |
| 1 | C2 | permitted_answer_accuracy | 17 | 37 | 0.459459 | 0.310386 | 0.61616 |
| 1 | C2 | controlled_failure_correctness | 7 | 13 | 0.538462 | 0.291438 | 0.767939 |
| 1 | C3 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 1 | C3 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 1 | C3 | permitted_answer_accuracy | 17 | 37 | 0.459459 | 0.310386 | 0.61616 |
| 1 | C3 | controlled_failure_correctness | 7 | 13 | 0.538462 | 0.291438 | 0.767939 |
| 1 | P1 | output_class_accuracy | 30 | 42 | 0.714286 | 0.564328 | 0.82833 |
| 1 | P1 | reason_code_accuracy | 0 | 42 | 0.0 | 0.0 | 0.083799 |
| 1 | P1 | permitted_answer_accuracy | 15 | 37 | 0.405405 | 0.263465 | 0.56514 |
| 1 | P1 | controlled_failure_correctness | 5 | 13 | 0.384615 | 0.177097 | 0.644771 |
| 2 | C0 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 2 | C0 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 2 | C0 | permitted_answer_accuracy | 12 | 37 | 0.324324 | 0.196333 | 0.485363 |
| 2 | C0 | controlled_failure_correctness | 0 | 13 | 0.0 | 0.0 | 0.228095 |
| 2 | C1 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 2 | C1 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 2 | C1 | permitted_answer_accuracy | 12 | 37 | 0.324324 | 0.196333 | 0.485363 |
| 2 | C1 | controlled_failure_correctness | 0 | 13 | 0.0 | 0.0 | 0.228095 |
| 2 | C2 | output_class_accuracy | 31 | 42 | 0.738095 | 0.589313 | 0.846974 |
| 2 | C2 | reason_code_accuracy | 31 | 42 | 0.738095 | 0.589313 | 0.846974 |
| 2 | C2 | permitted_answer_accuracy | 17 | 37 | 0.459459 | 0.310386 | 0.61616 |
| 2 | C2 | controlled_failure_correctness | 7 | 13 | 0.538462 | 0.291438 | 0.767939 |
| 2 | C3 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 2 | C3 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 2 | C3 | permitted_answer_accuracy | 17 | 37 | 0.459459 | 0.310386 | 0.61616 |
| 2 | C3 | controlled_failure_correctness | 7 | 13 | 0.538462 | 0.291438 | 0.767939 |
| 2 | P1 | output_class_accuracy | 30 | 42 | 0.714286 | 0.564328 | 0.82833 |
| 2 | P1 | reason_code_accuracy | 0 | 42 | 0.0 | 0.0 | 0.083799 |
| 2 | P1 | permitted_answer_accuracy | 15 | 37 | 0.405405 | 0.263465 | 0.56514 |
| 2 | P1 | controlled_failure_correctness | 5 | 13 | 0.384615 | 0.177097 | 0.644771 |
| 3 | C0 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C0 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C0 | permitted_answer_accuracy | 12 | 37 | 0.324324 | 0.196333 | 0.485363 |
| 3 | C0 | controlled_failure_correctness | 0 | 13 | 0.0 | 0.0 | 0.228095 |
| 3 | C1 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C1 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C1 | permitted_answer_accuracy | 12 | 37 | 0.324324 | 0.196333 | 0.485363 |
| 3 | C1 | controlled_failure_correctness | 0 | 13 | 0.0 | 0.0 | 0.228095 |
| 3 | C2 | output_class_accuracy | 31 | 42 | 0.738095 | 0.589313 | 0.846974 |
| 3 | C2 | reason_code_accuracy | 31 | 42 | 0.738095 | 0.589313 | 0.846974 |
| 3 | C2 | permitted_answer_accuracy | 17 | 37 | 0.459459 | 0.310386 | 0.61616 |
| 3 | C2 | controlled_failure_correctness | 7 | 13 | 0.538462 | 0.291438 | 0.767939 |
| 3 | C3 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C3 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C3 | permitted_answer_accuracy | 17 | 37 | 0.459459 | 0.310386 | 0.61616 |
| 3 | C3 | controlled_failure_correctness | 7 | 13 | 0.538462 | 0.291438 | 0.767939 |
| 3 | P1 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | P1 | reason_code_accuracy | 0 | 42 | 0.0 | 0.0 | 0.083799 |
| 3 | P1 | permitted_answer_accuracy | 15 | 37 | 0.405405 | 0.263465 | 0.56514 |
| 3 | P1 | controlled_failure_correctness | 5 | 13 | 0.384615 | 0.177097 | 0.644771 |

| Configuration | Deterministic records | OpenAI records | Deterministic output accuracy | OpenAI output accuracy | Deterministic controlled failure | OpenAI controlled failure | Deterministic citation coverage | OpenAI citation coverage | Deterministic safety findings | OpenAI safety findings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 42 | 126 | 0.690476 | 0.690476 | 0.0 | 0.0 | 0.357143 | 0.369048 | 3 | 9 |
| C1 | 42 | 126 | 0.690476 | 0.690476 | 0.0 | 0.0 | 0.345238 | 0.357143 | 3 | 9 |
| P1 | 42 | 126 | 0.690476 | 0.706349 | 0.0 | 0.384615 | 0.345238 | 0.353175 | 44 | 132 |
| C2 | 42 | 126 | 0.738095 | 0.738095 | 0.538462 | 0.538462 | 0.357143 | 0.369048 | 0 | 0 |
| C3 | 42 | 126 | 0.690476 | 0.690476 | 0.538462 | 0.538462 | 0.345238 | 0.357143 | 0 | 0 |

## 17. Validation And Conclusions
OpenAI records: 630. Runtime/parser/provider errors: 0. Failure inventory rows: 664.

| Category | Count |
| --- | --- |
| aggregation-threshold mismatch | 12 |
| citation document miss | 386 |
| contributor-deduplication failure | 9 |
| factual-atom omission | 451 |
| false answer | 73 |
| false refusal | 58 |
| output-class mismatch | 250 |
| prohibited disclosure | 88 |
| retrieval/routing/evidence-role mismatch | 24 |
| unsupported citation | 339 |
| wrong page | 164 |

The unit of controlled evaluation remains 42 unique cases; repetitions measure provider stability. Persistent time-bounded grants and persistent purpose-bound grants are deliberately not implemented. The document inventory caveat remains in scope as a known limitation, not a redesign target.
