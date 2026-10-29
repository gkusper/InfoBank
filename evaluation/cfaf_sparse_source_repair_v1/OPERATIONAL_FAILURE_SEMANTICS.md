# Failure semantics v1

Internal states distinguish VERIFIED_FULFILMENT, VALIDATED_CFAF, OPERATIONAL_FAILURE and VALIDATED_RESTRICTED_NO_VIEW. VERIFIED_FULFILMENT means the existing gate accepted supplied model properties; it does not certify independent factual entailment.

Operational codes include SEMANTIC_ASSESSMENT_INVALID, SOURCE_ASSESSMENT_CONTRACT_INVALID, INVALID_EVIDENCE_REFERENCE, REFERENCE_RESOLUTION_FAILED and GENERATION_CONTRACT_INVALID. Evidence/request-limit codes include INSUFFICIENT_EVIDENCE, REQUIREMENT_NOT_SUPPORTED, UNRESOLVED_REFERENT and UNSUPPORTED_RELATION. Invalid contracts/references do not establish information absence.

Operational failures cannot serve FULL or be credited as successful evidential CFAF. Public fallback uses the existing six-field schema: CFAF, NONE, ABSTAIN, EPISTEMIC, empty next steps and neutral text: The answer could not be verified reliably for this request. Raw generation stays local with explicit fallback status; no silent repair is claimed.

P5/no-view retains the canonical public response and zero calls. Hidden/absent source worlds yield identical public traces. No operational wording reveals source IDs/counts, hidden existence, exceptions or policy state.

Public reason vocabulary is the existing ReasonClass enum, version existing-ReasonClass-v1-strict-validation. No new public category. Unknown reasons/realizations, nonnull FULL reasons and missing CFAF reason/realization are rejected. Primary model-visible prompts/schema stay unchanged; strict checks occur after generation. Control chooses its raw mode independently, then the same publication boundary withholds invalid/operational output. Raw and served modes must be reported separately.

Gate and per-generator status differ: valid T3 evidential/clarification can coexist with invalid control generation. Such control fallback is operational and cannot be credited as semantic refusal. Top-level CFAF alone cannot support an accuracy claim.
