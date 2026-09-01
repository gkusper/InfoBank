# S1-S6 C0-C3 Detailed Experiment Report

Status: READY_FOR_MANUSCRIPT_RESULTS_UPDATE

## 1. Evaluation goal and relation to Q3
The experiment measures whether the current InfoBank pipeline supports governed retrieval, citation, Aggregate behavior, and controlled failures across six frozen synthetic scenarios. It is evidence for Q3-style end-to-end behavior, not a production deployment claim.

## 2. Six scenarios and 42-case composition
The combined overlay contains S1, S2, S3, S4B, S5B, and S6 in canonical order with 42 cases and 41 unique source PDFs.

| Scenario | Cases |
|---|---|
| S1 | 6 |
| S2 | 6 |
| S3 | 10 |
| S4B | 8 |
| S5B | 6 |
| S6 | 6 |

## 3. Output-class distribution
{"AGGREGATE_RESULT":5,"CLARIFICATION":1,"CONSTRAINED_ANSWER":3,"FULL_ANSWER":29,"REFUSE_AGGREGATION_THRESHOLD":1,"REFUSE_INSUFFICIENT_EVIDENCE":3}

Combined validation status: PASS. Runtime/reference separation: PASS. Document-ID collisions: 0.

## 4. Human review and freeze status
S1-S2 and S3-S6 packages were verified by hash and their recorded human review/freeze statuses were preserved. S1-S2 historical citation-completeness limitations remain visible in provenance.

| Package | SHA-256 | Scenarios | Questions | PDFs | Annotations | Status |
| --- | --- | --- | --- | --- | --- | --- |
| S1-S2 | 83a9bb2394946b378af4efe2445be1e6e7095a60f5c14f6206ea1405f275bcd1 | 2 | 12 | 10 | 12 | PASS |
| S3-S6 | 3a5db23fddf55a007d013e09fd11ade74fcdf692847d01b0135346bdd3ddc50c | 4 | 30 | 31 | 30 | PASS |

## 5. Two-package read-only integration
The overlay remaps document identifiers for combined execution while retaining case IDs, source PDFs, questions, policy fixtures, and reference annotations as frozen inputs.

Overlay files: `artifacts/s1_s6_publication_experiment/combined_input/combined_query_inputs.jsonl`, `artifacts/s1_s6_publication_experiment/combined_input/combined_corpus_fixture.json`, `artifacts/s1_s6_publication_experiment/combined_input/combined_reference_annotations.jsonl`.

## 6. C0-C3 semantics
| Configuration | Retrieval | Routing | Permission filtering | Evidence roles | Controlled failure | Aggregate | Citation |
|---|---|---|---|---|---|---|---|
| C0_VECTOR_ONLY | active documents ranked by vector/page-aware retrieval | disabled | disabled; active documents treated as usable | not enforced | disabled; baseline generation except exact runtime errors | not governed as aggregate-only; baseline answer generation | answer citation selector after generation; refusals withhold citations |
| C1_VECTOR_ROUTING | keyword-routed candidate documents ranked by vector/page-aware retrieval | enabled except aggregate-only governance path | disabled; routed candidates treated as usable | not enforced | disabled; baseline generation except exact runtime errors | not governed as aggregate-only; baseline answer generation | answer citation selector after generation; refusals withhold citations |
| C2_PERMISSION_FILTERED | permitted documents ranked by vector/page-aware retrieval | disabled | enabled through policy fixture use decisions | aggregate/content/metadata/deny roles used for governance | post-retrieval permission, no-match, insufficient-evidence, and aggregate-threshold gates | aggregate executor used when aggregate evidence is available | citations withheld for refusals and aggregate outputs; selected for answers |
| C3_FULL_ROLE_AWARE | routed permitted documents ranked by vector/page-aware retrieval | enabled for non-aggregate-only requests | enabled through policy fixture use decisions | query-sensitive primary/contextual/aggregate/governance roles | pre-generation and post-retrieval controlled-failure and clarification gates | aggregate executor plus threshold and contributor-deduplication governance | citations withheld for refusals and aggregate outputs; selected with role-aware support for answers |

## 7. Deterministic protocol and results
DETERMINISTIC DEVELOPMENT AND REPRODUCIBILITY EVALUATION — NOT FINAL REAL-PROVIDER PERFORMANCE
Deterministic executed records: 168. Output accuracy: 0.702381. Safety findings: 6.

| Configuration | Cases | Output accuracy | Permitted-answer accuracy | Controlled-failure correctness | Citation coverage | Safety findings | Tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 42 | 0.690476 | 0.324324 | 0.0 | 0.357143 | 3 | 30653 |
| C1 | 42 | 0.690476 | 0.324324 | 0.0 | 0.345238 | 3 | 30035 |
| C2 | 42 | 0.738095 | 0.459459 | 0.538462 | 0.357143 | 0 | 20141 |
| C3 | 42 | 0.690476 | 0.459459 | 0.538462 | 0.345238 | 0 | 23006 |

## 8. OpenAI preregistration and real-provider protocol
The OpenAI run was preregistered before measured records with gpt-4o-mini for generation/keywording, text-embedding-3-small for embeddings, temperature 0.0, three repetitions, and 504 planned measured records.

Preregistration SHA-256: 600398961dc90641d7070d1f9b6e6f9558470ce53f8b55a98b994c167a12d870. The locked file was not modified during continuation.

## 9. Interruption and continuation provenance
The original run stopped after R3-C1 when OpenAI returned insufficient-quota errors. After the user reported the billing top-up, the continuation ran only R3-C2 and R3-C3. The 22 R3-C1 provider/runtime failed records were retained and were not rerun.

| Stage | Executed records | Complete groups | Provider/runtime failed records retained | Notes |
| --- | --- | --- | --- | --- |
| Before interruption | 420 | 10 | 22 | Stopped after R3-C1 due OpenAI quota exhaustion. |
| After continuation | 504 | 12 | 22 | R3-C2 and R3-C3 were added; R3-C1 failed records were not rerun. |

## 10. Repetition-level results
| Repetition | Configuration | Cases | Output accuracy | Permitted-answer accuracy | Controlled-failure correctness | Citation coverage | Safety findings | Tokens | Runtime/parser/provider errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | C0 | 42 | 0.690476 | 0.324324 | 0.0 | 0.369048 | 3 | 45513 | 0 |
| 1 | C1 | 42 | 0.690476 | 0.324324 | 0.0 | 0.357143 | 3 | 44223 | 0 |
| 1 | C2 | 42 | 0.738095 | 0.459459 | 0.538462 | 0.369048 | 0 | 29964 | 0 |
| 1 | C3 | 42 | 0.690476 | 0.459459 | 0.538462 | 0.369048 | 0 | 44447 | 0 |
| 2 | C0 | 42 | 0.690476 | 0.324324 | 0.0 | 0.369048 | 3 | 45576 | 0 |
| 2 | C1 | 42 | 0.690476 | 0.324324 | 0.0 | 0.369048 | 3 | 44252 | 0 |
| 2 | C2 | 42 | 0.738095 | 0.459459 | 0.538462 | 0.369048 | 0 | 29930 | 0 |
| 2 | C3 | 42 | 0.690476 | 0.459459 | 0.538462 | 0.369048 | 0 | 44418 | 0 |
| 3 | C0 | 42 | 0.690476 | 0.324324 | 0.0 | 0.369048 | 3 | 45492 | 0 |
| 3 | C1 | 42 | 0.333333 | 0.297297 | 0.0 | 0.214286 | 1 | 20345 | 22 |
| 3 | C2 | 42 | 0.738095 | 0.459459 | 0.538462 | 0.369048 | 0 | 29951 | 0 |
| 3 | C3 | 42 | 0.690476 | 0.459459 | 0.538462 | 0.369048 | 0 | 44394 | 0 |

## 11. Overall configuration comparison
- C0: n=126, output=0.690476, permitted=0.324324, controlled=0.0, citation=0.369048, safety=9, tokens=136581, errors=0
- C1: n=126, output=0.571429, permitted=0.315315, controlled=0.0, citation=0.313492, safety=7, tokens=108820, errors=22
- C2: n=126, output=0.738095, permitted=0.459459, controlled=0.538462, citation=0.369048, safety=0, tokens=89845, errors=0
- C3: n=126, output=0.690476, permitted=0.459459, controlled=0.538462, citation=0.369048, safety=0, tokens=133259, errors=0

| Configuration | Cases | Output accuracy | Permitted-answer accuracy | Controlled-failure correctness | Citation coverage | Support precision | Page correctness | Safety findings | Tokens | Runtime/parser/provider errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 126 | 0.690476 | 0.324324 | 0.0 | 0.369048 | 0.409639 | 0.277108 | 9 | 136581 | 0 |
| C1 | 126 | 0.571429 | 0.315315 | 0.0 | 0.313492 | 0.432584 | 0.314607 | 7 | 108820 | 22 |
| C2 | 126 | 0.738095 | 0.459459 | 0.538462 | 0.369048 | 0.578947 | 0.403509 | 0 | 89845 | 0 |
| C3 | 126 | 0.690476 | 0.459459 | 0.538462 | 0.369048 | 0.697674 | 0.534884 | 0 | 133259 | 0 |

## 12. Scenario-level comparison
| Configuration | Scenario | Cases | Output accuracy | Citation coverage | Safety findings |
| --- | --- | --- | --- | --- | --- |
| C0 | S1 | 18 | 0.833333 | 0.75 | 0 |
| C0 | S2 | 18 | 1.0 | 0.75 | 0 |
| C0 | S3 | 30 | 0.5 | 0.1 | 3 |
| C0 | S4B | 24 | 0.5 | 0.041667 | 6 |
| C0 | S5B | 18 | 0.666667 | 0.333333 | 0 |
| C0 | S6 | 18 | 0.833333 | 0.527778 | 0 |
| C1 | S1 | 18 | 0.833333 | 0.75 | 0 |
| C1 | S2 | 18 | 1.0 | 0.777778 | 0 |
| C1 | S3 | 30 | 0.433333 | 0.066667 | 2 |
| C1 | S4B | 24 | 0.333333 | 0.027778 | 5 |
| C1 | S5B | 18 | 0.444444 | 0.222222 | 0 |
| C1 | S6 | 18 | 0.555556 | 0.296296 | 0 |
| C2 | S1 | 18 | 1.0 | 0.75 | 0 |
| C2 | S2 | 18 | 1.0 | 0.75 | 0 |
| C2 | S3 | 30 | 0.6 | 0.1 | 0 |
| C2 | S4B | 24 | 0.625 | 0.041667 | 0 |
| C2 | S5B | 18 | 0.5 | 0.333333 | 0 |
| C2 | S6 | 18 | 0.833333 | 0.527778 | 0 |
| C3 | S1 | 18 | 1.0 | 0.75 | 0 |
| C3 | S2 | 18 | 1.0 | 0.833333 | 0 |
| C3 | S3 | 30 | 0.4 | 0.1 | 0 |
| C3 | S4B | 24 | 0.625 | 0.041667 | 0 |
| C3 | S5B | 18 | 0.5 | 0.333333 | 0 |
| C3 | S6 | 18 | 0.833333 | 0.444444 | 0 |

## 13. Output-class-level comparison
| Configuration | Expected output class | Cases | Output accuracy | Permitted-answer accuracy | Controlled-failure correctness |
| --- | --- | --- | --- | --- | --- |
| C0 | AGGREGATE_RESULT | 15 | 0.0 | 0.0 | 0.0 |
| C0 | CLARIFICATION | 3 | 0.0 |  | 0.0 |
| C0 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 |
| C0 | FULL_ANSWER | 87 | 1.0 | 0.413793 |  |
| C0 | REFUSE_AGGREGATION_THRESHOLD | 3 | 0.0 |  | 0.0 |
| C0 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.0 |  | 0.0 |
| C1 | AGGREGATE_RESULT | 15 | 0.0 | 0.0 | 0.0 |
| C1 | CLARIFICATION | 3 | 0.0 |  | 0.0 |
| C1 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 |
| C1 | FULL_ANSWER | 87 | 0.827586 | 0.402299 |  |
| C1 | REFUSE_AGGREGATION_THRESHOLD | 3 | 0.0 |  | 0.0 |
| C1 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.0 |  | 0.0 |
| C2 | AGGREGATE_RESULT | 15 | 1.0 | 1.0 | 1.0 |
| C2 | CLARIFICATION | 3 | 0.0 |  | 0.0 |
| C2 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 |
| C2 | FULL_ANSWER | 87 | 0.827586 | 0.413793 |  |
| C2 | REFUSE_AGGREGATION_THRESHOLD | 3 | 1.0 |  | 1.0 |
| C2 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.333333 |  | 0.333333 |
| C3 | AGGREGATE_RESULT | 15 | 1.0 | 1.0 | 1.0 |
| C3 | CLARIFICATION | 3 | 0.0 |  | 0.0 |
| C3 | CONSTRAINED_ANSWER | 9 | 0.0 | 0.0 | 0.0 |
| C3 | FULL_ANSWER | 87 | 0.758621 | 0.413793 |  |
| C3 | REFUSE_AGGREGATION_THRESHOLD | 3 | 1.0 |  | 1.0 |
| C3 | REFUSE_INSUFFICIENT_EVIDENCE | 9 | 0.333333 |  | 0.333333 |

## 14. Owner/Full versus Aggregate-only comparison
| Configuration | Permission group | Cases | Output accuracy | Permitted-answer accuracy | Controlled-failure correctness | Citation coverage | Safety findings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | Aggregate-only | 18 | 0.0 | 0.0 | 0.0 | 0.0 | 9 |
| C0 | Owner/Full | 108 | 0.805556 | 0.375 | 0.0 | 0.430556 | 0 |
| C1 | Aggregate-only | 18 | 0.0 | 0.0 | 0.0 | 0.0 | 7 |
| C1 | Owner/Full | 108 | 0.666667 | 0.364583 | 0.0 | 0.365741 | 0 |
| C2 | Aggregate-only | 18 | 1.0 | 1.0 | 1.0 | 0.0 | 0 |
| C2 | Owner/Full | 108 | 0.694444 | 0.375 | 0.142857 | 0.430556 | 0 |
| C3 | Aggregate-only | 18 | 1.0 | 1.0 | 1.0 | 0.0 | 0 |
| C3 | Owner/Full | 108 | 0.638889 | 0.375 | 0.142857 | 0.430556 | 0 |

## 15. Aggregate privacy and threshold behavior
| Repetition | Configuration | Aggregate-only cases | Aggregate numerical correctness | Output-class correctness | Threshold correctness | Duplicate/reissue handling S3-Q9 | Individual-value exposure | Withheld-value exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | C0 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 1 | C1 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 1 | C2 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 1 | C3 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 2 | C0 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 2 | C1 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 2 | C2 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 2 | C3 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 3 | C0 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 3 |
| 3 | C1 | 6 | 0.0 | 0.0 | 0 | 0 | 0 | 1 |
| 3 | C2 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |
| 3 | C3 | 6 | 1.0 | 1.0 | 1 | 1 | 0 | 0 |

## 16. Citation behavior
| Configuration | Cases | Citation document coverage | Citation support precision | Page-level citation correctness | Citation coverage | Unsupported citation count | Wrong-document citation count | Wrong-page citation count | Missing-required-document count | Citation-free intentionally withheld |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 126 | 0.566667 | 0.409639 | 0.277108 | 0.369048 | 147 | 147 | 33 | 78 | 0 |
| C1 | 126 | 0.427778 | 0.432584 | 0.314607 | 0.313492 | 101 | 101 | 21 | 103 | 0 |
| C2 | 126 | 0.55 | 0.578947 | 0.403509 | 0.369048 | 72 | 72 | 30 | 81 | 39 |
| C3 | 126 | 0.5 | 0.697674 | 0.534884 | 0.369048 | 39 | 39 | 21 | 90 | 45 |

## 17. Controlled-failure behavior
Controlled-failure correctness is reported for expected non-full outputs. Baseline configurations intentionally lack these gates and therefore show high false-answer counts on governed cases.

## 18. Safety behavior
| Configuration | Total safety findings | prohibited_document_id_exposure | prohibited_text_fragment_exposure | source_existence_disclosure | denied_filename_hash_page_disclosure | aggregate_individual_value_exposure | generator_visible_restricted_text | archived_source_usage | wrong_permission_citation | local_path_exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C1 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| C3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## 19. Stability analysis
{"answer_text_variable":66,"case_configuration_rows":168,"citation_variable":23,"complete_3_repetition_rows":168,"incomplete_rows":0,"one_off_failures":22,"output_class_stable_yes":146,"output_class_variable":22,"repeated_failures_3_of_3":0}

## 20. Retrieval and efficiency
| Configuration | Cases | Mean latency | Median latency | P95 latency | Prompt/input tokens | Completion/output tokens | Total tokens | Recorded generation calls | Retry count | Failed call count | Recorded cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 126 | 3198.564717 | 2344.90465 | 5099.0997 | 128610 | 7971 | 136581 | 126 | 0 | 0 | NOT_RECORDED_BY_PROVIDER_ADAPTER |
| C1 | 126 | 8030.413585 | 2190.19045 | 5358.02105 | 102782 | 6038 | 108820 | 104 | 3 | 22 | NOT_RECORDED_BY_PROVIDER_ADAPTER |
| C2 | 126 | 2677.139003 | 2469.62085 | 5478.818725 | 83304 | 6541 | 89845 | 87 | 0 | 0 | NOT_RECORDED_BY_PROVIDER_ADAPTER |
| C3 | 126 | 5456.281132 | 2546.7198 | 5345.16695 | 127596 | 5663 | 133259 | 81 | 0 | 0 | NOT_RECORDED_BY_PROVIDER_ADAPTER |

Retrieval metrics not exposed by the current evaluator remain marked as NOT_AVAILABLE_IN_CURRENT_EVALUATOR in the machine-readable tables.

## 21. Paired configuration comparison
| Repetition | Comparison | Metric | C0 wins | C1 wins | C2 wins | Ties | C0 losses | C1 losses | C2 losses | Compared cases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | C0 vs C1 | Output class | 0 |  |  | 42 | 0 |  |  | 42 |
| 1 | C0 vs C1 | Reason code | 0 |  |  | 42 | 0 |  |  | 42 |
| 1 | C0 vs C1 | Factual atoms | 0 |  |  | 42 | 0 |  |  | 42 |
| 1 | C0 vs C1 | Citation document coverage | 2 |  |  | 32 | 0 |  |  | 34 |
| 1 | C0 vs C1 | Safety clean | 0 |  |  | 42 | 0 |  |  | 42 |
| 1 | C0 vs C2 | Output class | 5 |  |  | 30 | 7 |  |  | 42 |
| 1 | C0 vs C2 | Reason code | 5 |  |  | 30 | 7 |  |  | 42 |
| 1 | C0 vs C2 | Factual atoms | 0 |  |  | 37 | 5 |  |  | 42 |
| 1 | C0 vs C2 | Citation document coverage | 1 |  |  | 33 | 0 |  |  | 34 |
| 1 | C0 vs C2 | Safety clean | 0 |  |  | 39 | 3 |  |  | 42 |
| 1 | C0 vs C3 | Output class | 7 |  |  | 28 | 7 |  |  | 42 |
| 1 | C0 vs C3 | Reason code | 7 |  |  | 28 | 7 |  |  | 42 |
| 1 | C0 vs C3 | Factual atoms | 0 |  |  | 37 | 5 |  |  | 42 |
| 1 | C0 vs C3 | Citation document coverage | 4 |  |  | 30 | 0 |  |  | 34 |
| 1 | C0 vs C3 | Safety clean | 0 |  |  | 39 | 3 |  |  | 42 |
| 1 | C1 vs C3 | Output class |  | 7 |  | 28 |  | 7 |  | 42 |
| 1 | C1 vs C3 | Reason code |  | 7 |  | 28 |  | 7 |  | 42 |
| 1 | C1 vs C3 | Factual atoms |  | 0 |  | 37 |  | 5 |  | 42 |
| 1 | C1 vs C3 | Citation document coverage |  | 3 |  | 30 |  | 1 |  | 34 |
| 1 | C1 vs C3 | Safety clean |  | 0 |  | 39 |  | 3 |  | 42 |
| 1 | C2 vs C3 | Output class |  |  | 2 | 40 |  |  | 0 | 42 |
| 1 | C2 vs C3 | Reason code |  |  | 2 | 40 |  |  | 0 | 42 |
| 1 | C2 vs C3 | Factual atoms |  |  | 0 | 42 |  |  | 0 | 42 |
| 1 | C2 vs C3 | Citation document coverage |  |  | 3 | 31 |  |  | 0 | 34 |
| 1 | C2 vs C3 | Safety clean |  |  | 0 | 42 |  |  | 0 | 42 |
| 2 | C0 vs C1 | Output class | 0 |  |  | 42 | 0 |  |  | 42 |
| 2 | C0 vs C1 | Reason code | 0 |  |  | 42 | 0 |  |  | 42 |
| 2 | C0 vs C1 | Factual atoms | 0 |  |  | 42 | 0 |  |  | 42 |
| 2 | C0 vs C1 | Citation document coverage | 1 |  |  | 33 | 0 |  |  | 34 |
| 2 | C0 vs C1 | Safety clean | 0 |  |  | 42 | 0 |  |  | 42 |

Additional rows omitted here: 45. See the CSV artifact for the full table.

## 22. Confidence intervals
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
| 3 | C0 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C0 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C0 | permitted_answer_accuracy | 12 | 37 | 0.324324 | 0.196333 | 0.485363 |
| 3 | C0 | controlled_failure_correctness | 0 | 13 | 0.0 | 0.0 | 0.228095 |
| 3 | C1 | output_class_accuracy | 14 | 42 | 0.333333 | 0.210125 | 0.484475 |
| 3 | C1 | reason_code_accuracy | 14 | 42 | 0.333333 | 0.210125 | 0.484475 |
| 3 | C1 | permitted_answer_accuracy | 11 | 37 | 0.297297 | 0.174895 | 0.457831 |
| 3 | C1 | controlled_failure_correctness | 0 | 13 | 0.0 | 0.0 | 0.228095 |
| 3 | C2 | output_class_accuracy | 31 | 42 | 0.738095 | 0.589313 | 0.846974 |
| 3 | C2 | reason_code_accuracy | 31 | 42 | 0.738095 | 0.589313 | 0.846974 |
| 3 | C2 | permitted_answer_accuracy | 17 | 37 | 0.459459 | 0.310386 | 0.61616 |
| 3 | C2 | controlled_failure_correctness | 7 | 13 | 0.538462 | 0.291438 | 0.767939 |
| 3 | C3 | output_class_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C3 | reason_code_accuracy | 29 | 42 | 0.690476 | 0.53974 | 0.809289 |
| 3 | C3 | permitted_answer_accuracy | 17 | 37 | 0.459459 | 0.310386 | 0.61616 |
| 3 | C3 | controlled_failure_correctness | 7 | 13 | 0.538462 | 0.291438 | 0.767939 |

Confidence intervals are repetition-specific and use the 42 unique cases within a repetition where applicable. The repeated responses are not treated as independent new cases.

## 23. Deterministic versus OpenAI comparison
| Configuration | Deterministic records | OpenAI records | Deterministic output accuracy | OpenAI output accuracy | Deterministic controlled failure | OpenAI controlled failure | Deterministic citation coverage | OpenAI citation coverage | Deterministic safety findings | OpenAI safety findings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 42 | 126 | 0.690476 | 0.690476 | 0.0 | 0.0 | 0.357143 | 0.369048 | 3 | 9 |
| C1 | 42 | 126 | 0.690476 | 0.571429 | 0.0 | 0.0 | 0.345238 | 0.313492 | 3 | 7 |
| C2 | 42 | 126 | 0.738095 | 0.738095 | 0.538462 | 0.538462 | 0.357143 | 0.369048 | 0 | 0 |
| C3 | 42 | 126 | 0.690476 | 0.690476 | 0.538462 | 0.538462 | 0.345238 | 0.369048 | 0 | 0 |

## 24. Error analysis
Failure inventory rows: 500.

| Category | Count |
| --- | --- |
| aggregation-threshold mismatch | 8 |
| citation document miss | 308 |
| contributor-deduplication failure | 8 |
| factual-atom omission | 361 |
| false answer | 53 |
| false refusal | 48 |
| output-class mismatch | 215 |
| prohibited disclosure | 22 |
| provider/runtime failure | 22 |
| unsupported citation | 252 |
| wrong page | 126 |

Failures are classified in case_failure_inventory.csv and openai/error_analysis.md by case, scenario, configuration, repetition, category, expected behavior, observed behavior, and likely pipeline stage.

## 25. Limitations and conclusions
The evaluation contains 42 unique controlled cases. Three repetitions assess provider stability but do not create 126 independent cases per configuration. The evidence supports proof-of-concept conclusions only.

The continuation makes the artifact set complete with 504 measured records, while preserving the original quota-interruption evidence. The 22 R3-C1 provider/runtime failures remain part of the measured results.
