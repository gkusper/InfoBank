# Round error analysis

All official labels are unchanged. Error attributions below are provisional mechanistic flags, not independent human adjudication.

## Case 0 / semantic_cfaf

Dataset index 631; record hash `a01105f5f919e2e72826e52fc9c5add71e70aa09ba8bff56a417bc55763a7c5e`. Expected FULL; observed CFAF.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: GRANULARITY_NOT_SUPPORTED. Validation: none.

## Case 5 / semantic_cfaf

Dataset index 1236; record hash `5796a2ee0d676df8818dbd6638c88bea0bcc7657d095f6de80237aee2afac026`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 5 / shared_control

Dataset index 1236; record hash `5796a2ee0d676df8818dbd6638c88bea0bcc7657d095f6de80237aee2afac026`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 8 / semantic_cfaf

Dataset index 1112; record hash `20a0dd6385fb803c9bac883a30e7770aee14562781d40a553bd5ae82fb3d5fab`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 8 / shared_control

Dataset index 1112; record hash `20a0dd6385fb803c9bac883a30e7770aee14562781d40a553bd5ae82fb3d5fab`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 12 / semantic_cfaf

Dataset index 828; record hash `103b67edf036f79a9a24bae7638fa486e76383a2d32373537c78c4e39f280867`. Expected FULL; observed CFAF.

Attribution: Requested-identity completeness. Issues: AMBIGUOUS_REFERENCE, ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, REQUEST_INCOMPLETE, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP. Validation: none.

## Case 12 / shared_control

Dataset index 828; record hash `103b67edf036f79a9a24bae7638fa486e76383a2d32373537c78c4e39f280867`. Expected FULL; observed CFAF.

Attribution: Requested-identity completeness. Issues: AMBIGUOUS_REFERENCE, ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NO_GROUNDED_ANSWER_CANDIDATE, REQUEST_INCOMPLETE, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP. Validation: none.

## Case 16 / semantic_cfaf

Dataset index 621; record hash `ea60c4a27c0aeb79cc34eab4af0f35de9069165f9b6bfa9467ecce54d0ccfd41`. Expected FULL; observed CFAF.

Attribution: Requested-identity completeness. Issues: AMBIGUOUS_REFERENCE, ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NONFACTUAL_REQUEST, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_INCOMPLETE, REQUEST_RELATION_UNSUPPORTED, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP, SEMANTIC_UNCERTAIN. Validation: none.

## Case 16 / shared_control

Dataset index 621; record hash `ea60c4a27c0aeb79cc34eab4af0f35de9069165f9b6bfa9467ecce54d0ccfd41`. Expected FULL; observed CFAF.

Attribution: Requested-identity completeness. Issues: AMBIGUOUS_REFERENCE, ESSENTIAL_INFORMATION_MISSING, GRANULARITY_NOT_SUPPORTED, NONFACTUAL_REQUEST, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_INCOMPLETE, REQUEST_RELATION_UNSUPPORTED, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP, SEMANTIC_UNCERTAIN. Validation: none.


## Contextual report-author review

These notes are post-run, unblinded agent judgments, not independent human gold or score corrections. Only already-selected, exposure-charged records were reviewed.

- Case 0: The final profile recognizes the definition question, but another granularity flag still blocks CFAF FULL while the control answers. The per-requirement complete flag and broader granularity flag are inconsistent. This shows that typing alone does not settle evidence assessment.

- Case 5: The final version returns the two named periodic-table composers. The official label requests refusal for ambiguity; the same ambiguity-versus-list interpretation issue remains. All labels and primary outcomes stay unchanged.

- Case 6: A qualified final answer names the actor and the series year supported by the passage, rather than repeating the unsupported query year. Correct official mode alone still does not prove every presupposition or detail has been resolved.

- Case 8: The model extrapolates a century-long national trend from a limited collection of states and events. A valid quotation does not establish representative historical coverage; this is an official granularity failure-to-restrict case.

- Case 12: The final assessor still requires an exact date where the question can accept decade-level availability. It then labels missing precision as an unresolved referent. This exposes semantic reason inconsistency despite the improved profile.

- Case 16: The purported discovery date is absent from the permitted text. Official FULL remains unchanged. Missing evidence and unsupported qualifiers are conflated with ambiguity/nonfactual status; a faithful restricted answer can disagree with the benchmark label.
