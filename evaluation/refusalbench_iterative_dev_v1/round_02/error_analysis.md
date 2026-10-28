# Round error analysis

All official labels are unchanged. Error attributions below are provisional mechanistic flags, not independent human adjudication.

## Case 0 / semantic_cfaf

Dataset index 274; record hash `d5d0d89bcc3870bdc48fedd7295bd3fda5807b106173d5da2593c8be9ad08942`. Expected FULL; observed CFAF.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP. Validation: none.

## Case 0 / shared_control

Dataset index 274; record hash `d5d0d89bcc3870bdc48fedd7295bd3fda5807b106173d5da2593c8be9ad08942`. Expected FULL; observed CFAF.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP. Validation: none.

## Case 1 / semantic_cfaf

Dataset index 1200; record hash `10c460df8fb823cfb23f1eb31340d7b7fe16aa6863dc95be9ba6eedc65959b80`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 1 / shared_control

Dataset index 1200; record hash `10c460df8fb823cfb23f1eb31340d7b7fe16aa6863dc95be9ba6eedc65959b80`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 6 / semantic_cfaf

Dataset index 1089; record hash `984330b6e80d7acfe4ab84c4c56c64668be7b976ca43893a850b284a8cfb120d`. Expected FULL; observed CFAF.

Attribution: Query profiling. Issues: AMBIGUOUS_REFERENCE, REQUEST_SCOPE_UNRESOLVED. Validation: none.

## Case 7 / semantic_cfaf

Dataset index 60; record hash `c8460616efd34eda5b929e0ea62c7f9e31765b88a54eb3436b931b23e68090ce`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 7 / shared_control

Dataset index 60; record hash `c8460616efd34eda5b929e0ea62c7f9e31765b88a54eb3436b931b23e68090ce`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 14 / semantic_cfaf

Dataset index 1007; record hash `da6af9021602ed450790858bc9a36e4048a9a361ef15af2c9342088207857052`. Expected FULL; observed CFAF.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: ESSENTIAL_INFORMATION_MISSING, NONFACTUAL_REQUEST, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP. Validation: none.

## Case 14 / shared_control

Dataset index 1007; record hash `da6af9021602ed450790858bc9a36e4048a9a361ef15af2c9342088207857052`. Expected FULL; observed CFAF.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: ESSENTIAL_INFORMATION_MISSING, NONFACTUAL_REQUEST, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP. Validation: none.

## Case 15 / semantic_cfaf

Dataset index 1078; record hash `41761274a52e4da39f8a79223b393b7cee2549679cd53886036580b25d25341c`. Expected FULL; observed CFAF.

Attribution: Query profiling. Issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NONFACTUAL_REQUEST, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED. Validation: none.

## Case 15 / shared_control

Dataset index 1078; record hash `41761274a52e4da39f8a79223b393b7cee2549679cd53886036580b25d25341c`. Expected FULL; observed CFAF.

Attribution: Query profiling. Issues: ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NONFACTUAL_REQUEST, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_SCOPE_UNRESOLVED, REQUIREMENT_UNSUPPORTED:UNRESOLVED. Validation: none.


## Contextual report-author review

These notes are post-run, unblinded agent judgments, not independent human gold or score corrections. Only already-selected, exposure-charged records were reviewed.

- Case 0: A truncated passage names an electricity authority and plants but does not specify actual energy sources. Both systems refuse against an official FULL label; the label and required source/agency interpretation are questionable, not corrected.

- Case 1: The passage contains an original work and adaptation with the same title. Both systems select the original author without resolving the intended work. This is a query-reference/answer-relation error rather than an internal contradiction problem.

- Case 6: A telegraphic bowler-identity query receives an otherwise grounded candidate but remains UNRESOLVED. The later query-only fallback is designed for this class of nominal fragments, without seeing context or gold.

- Case 7: Two film titles have different filming locations. Listing locations for both does not resolve a singular this-film referent. Both systems return official false FULLs; the final version adds a referent-resolution property and uncertainty requirement.

- Case 14: A query uses an unsupported edition year for a role. The model incorrectly labels this NONFACTUAL rather than distinguish a factual core from an unsupported qualifier. The official FULL label remains unchanged.

- Case 15: A yes/no question about a fictional cultural figure can be factual historical-influence inquiry. UNRESOLVED profiling and NONFACTUAL labeling conflate subject matter with epistemic request type.
