# InfoBank S1-S6 Publication Protocol V2

Protocol locked: YES
Configurations: C0, C1, P1, C2, C3
Planned real-provider records: 630
Prompt-only governance prompt SHA-256: 982f197df7e1508cb978529f582cf405469abdc25fce84a6534d901a1b80bb4e

P1 is prompt-only governance: the prompt receives policy labels and descriptions, but no hard permission filtering, governed aggregate executor, controlled-failure gate, threshold/deduplication logic, CFAF, or post-generation correction is applied.

Balanced accuracy is the mean of per-class recall over FULL_ANSWER, AGGREGATE_RESULT, CONSTRAINED_ANSWER, REFUSE_INSUFFICIENT_EVIDENCE, REFUSE_AGGREGATION_THRESHOLD, and CLARIFICATION.

Persistent time-bounded grants and persistent purpose-bound grants are not implemented and are out of scope. Existing document-level PolicyRule purpose and valid_from/valid_until behavior is preserved.
