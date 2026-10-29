# Exact quotation reference resolution

The compact model output contains sparse evidence rows: local evidence ID, permitted neutral source ID, a short exact quotation and explicit source role. Claims refer to those local evidence IDs. They do not generate catalogue span IDs or source offsets.

Application resolution verifies unique source membership in the authorized supplied view, matching source/inventory SHA-256, nonempty exact substring, exactly one occurrence, valid source offsets and current request/policy binding. There is no whitespace/fuzzy/nearest-neighbor matching. Repeated identical substrings are ambiguous; this version has no trusted repeated-quote locator and therefore rejects them. Unknown sources and absent quotes remain operational reference failures. A model is never called to repair its own citation.

Successful quote offsets receive an application-generated source:quote-start-end locator. The renderer/public guard resolves the original quote again and checks source/hash/offset and accepted claim association. Claims/requirements/evidence IDs must exist. Trusted structured metadata cites the exact JSON field-value pairs; a verified aggregate cites its permitted structured snapshot.

Legacy source:span-N decimal aliases remain valid only when the index resolves to exactly one real authorized catalogue entry, with matching inventory/hash/offset. Invented indexes remain invalid. This path supports the frozen v1 models/tests and is not the v1.1 model output format.

Source IDs remain strict strings with membership checks rather than per-case dynamic enums. This keeps one stable schema and avoids catalogue/schema duplication; the local permitted inventory remains authoritative. Model evidence IDs are local links, not proof of source existence.

REFERENCE_VALID proves mechanical existence/integrity, MODEL_ATTRIBUTED records the model's association, SUPPORT_NOT_INDEPENDENTLY_VERIFIED preserves the absence of entailment proof. APPLICATION_STRUCTURED applies only to application-verified structured output. A valid quotation alone cannot set FULL, grant permission or establish truth. Missing obligations, non-primary roles, unresolved dependencies/scope and operational failures still prevent FULL.

## Observed limits

The above obligation checks validate explicit proposal links/types/statuses, not independent natural-language completeness. Four C2 proposals fail exact-quote validation in the actual paired run; one more fails the missing-ID contract. All released links resolve mechanically, but several FULL answers remain incomplete or semantically unsupported. Removing the span-ID output field did not improve overall reference/application reliability. See REPORT.md and reference_error_analysis.json. No fuzzy tolerance or citation substitution was introduced after observing these failures.
