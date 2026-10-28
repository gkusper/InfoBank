# Round error analysis

All official labels are unchanged. Error attributions below are provisional mechanistic flags, not independent human adjudication.

## Case 5 / semantic_cfaf

Dataset index 387; record hash `e23e39f8982845e3bf69f8661462d6e9846800cf6856b6abe391dfe313749c54`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 5 / shared_control

Dataset index 387; record hash `e23e39f8982845e3bf69f8661462d6e9846800cf6856b6abe391dfe313749c54`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 8 / semantic_cfaf

Dataset index 1023; record hash `5495f5a4101d13fedf6fcd61383364319d9ee27b31548c6798a0dda9a38d6da1`. Expected FULL; observed CFAF.

Attribution: Requested-identity completeness. Issues: AMBIGUOUS_REFERENCE, ESSENTIAL_INFORMATION_MISSING, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_INCOMPLETE, REQUEST_RELATION_UNSUPPORTED, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP, SEMANTIC_UNCERTAIN. Validation: none.

## Case 8 / shared_control

Dataset index 1023; record hash `5495f5a4101d13fedf6fcd61383364319d9ee27b31548c6798a0dda9a38d6da1`. Expected FULL; observed CFAF.

Attribution: Requested-identity completeness. Issues: AMBIGUOUS_REFERENCE, ESSENTIAL_INFORMATION_MISSING, NO_GROUNDED_ANSWER_CANDIDATE, NO_VERIFIED_SUPPORT_SPANS, REQUEST_INCOMPLETE, REQUEST_RELATION_UNSUPPORTED, REQUIREMENT_UNSUPPORTED:FACT_LOOKUP, SEMANTIC_UNCERTAIN. Validation: none.

## Case 9 / semantic_cfaf

Dataset index 1243; record hash `5dfaa94a619fd442ca623175d7fbe5aa8221af67f89d8507402eba2184eea3e2`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.

## Case 9 / shared_control

Dataset index 1243; record hash `5dfaa94a619fd442ca623175d7fbe5aa8221af67f89d8507402eba2184eea3e2`. Expected CFAF; observed FULL.

Attribution: Evidence sufficiency / answer generation; contextual review needed. Issues: none. Validation: none.


## Contextual report-author review

These notes are post-run, unblinded agent judgments, not independent human gold or score corrections. Only already-selected, exposure-charged records were reviewed.

- Case 5: Oregon has multiple reinstatement dates/events in the passage. The model selects 1984 and marks referent resolution/complete fulfilment true despite the deictic request. The selected fact is present, but complete disambiguation is not established; official CFAF is unchanged.

- Case 8: The question asks for band members while adding an unsupported award presupposition. The assessor rejects both membership and award evidence and even marks the referent unresolved. Core members appear across the narrative; unsupported incidental qualifiers and list coverage remain difficult. Official FULL is preserved, not repaired.

- Case 9: The passage supplies two roles in the same show; the model chooses one and incorrectly marks complete coverage true. A cited true role does not establish complete fulfilment or remove alternative-role ambiguity. This is an official failure to restrict.
