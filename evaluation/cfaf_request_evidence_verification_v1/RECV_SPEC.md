# RECV specification, version 1.0

RECV is an explicit component of `SUFFICIENCY_AND_PERMITTED_OUTPUT`, after the existing semantic assessment and before the unchanged `TopLevelModeSelectionStage`. The eight named stages, model, upstream prompts, response schema and selection principle are preserved. RECV can narrow a FULL decision; it does not grant access, invent evidence, repair an invalid assessment or turn a failed analysis into a successful refusal.

## Inputs and boundaries

Inputs are the existing policy-bound request, query-only profile, validated semantic assessment, deterministic span catalogue and optional bound focused-verifier attestations. Original case IDs, gold behavior, fixture roles and evaluator answers are absent. Requirement IDs remain those of the existing profile. The query and policy views are revalidated by the inherited guards before every model call.

The existing profile distinguishes aggregate count/sum/average, individual record, metadata, document content, action and generic fact lookup. Its answer kinds distinguish named identity, location, temporal answer, count/quantity, duration, instance, Boolean, explanation, process and description. RECV enriches these requirements with request text, a conservative relation family, explicit first/earliest/last/latest/only/unique qualifiers, complete-list wording and explicitly requested day/range precision. Ordinary WHEN questions acquire no exact-day requirement. A year or decade can remain sufficient according to the analyzer. No requirements are derived from which sources happen to be accessible.

This reuse inherits profile errors: deterministic enrichment does not establish complete natural-language decomposition. Requirement counts measure identified elements, not recall against independently annotated requirement gold. A complete-list expression outside the conservative grammar can be missed.

## Checks and meaning

For every requirement RECV checks:

- Valid assessment and one-to-one requirement mapping.
- Nonempty candidate, excluding literal null/none/unknown placeholders.
- Existing authorized span IDs, current text hashes and deterministic offsets.
- A cited, grounded PRIMARY source with SUPPORTS relation.
- Preserved explicitly identified counterevidence; known conflicts always block fulfilment.
- Requirement support state, answer form and named-identity flag where applicable.
- Complete-answer, referent and relation/qualifier properties from the analyzer.
- Scope compatibility of aggregate/metadata views.
- Consistency between requirement-level support and global semantic fields.
- Explicit aggregation operation or requested precision where the ordinary scalar type cannot distinguish them.

Typed date, location and numeric answer forms constrain the result; token occurrence is never an entailment test. A numeric candidate does not prove an average. An exact typed `available_granularity` value COUNT/SUM/AVERAGE can attest the operation; arbitrary prose remains unresolved for average/sum requirements. This is a deliberately conservative interface limitation, not a proof of numerical correctness.

The v02 combined relation-and-qualifiers Boolean does not independently attest a first/only/last qualification or list exhaustiveness. Those become UNKNOWN unless a bound focused opinion resolves the specific uncertainty. This can unnecessarily block a correct answer and is measured explicitly. Neither a supported name/date nor a second model opinion constitutes formal proof.

A relation marked supported retains provenance `existing_analyzer_attestation`. Focused opinions retain `focused_model_attestation`. Every result explicitly states `deterministic_entailment_proof: false`.

## Output contract

Each requirement has `coverage_status` in COVERED, PARTIALLY_COVERED, NOT_COVERED or UNKNOWN, Boolean-or-null checks, supporting span IDs, reason codes and the original requirement description. Any false check blocks coverage. With no false checks, a null check yields UNKNOWN. A known partial requirement produces PARTIALLY_COVERED. UNKNOWN is never translated into a claim that a fact does not exist.

The request assessment includes the request signature, assessment SHA-256, requirement count and `all_essential_covered`. Validation rejects duplicate requirement IDs, inconsistent COVERED results, invalid states and nonserializable values. FULL requires both the old sufficiency/policy conditions and the enabled new checks. A0 switches both new checks off, A1 enables RECV, A2 enables source capabilities, and B enables both.

## Reasons and traces

Existing policy/evidence reasons retain precedence when the old pipeline already blocks fulfilment. New reasons identify the unsatisfied requirement and exact RECV/source rule internally. Public reasons distinguish unverified answer type, unresolved qualifier/list scope, internally inconsistent assessment and source limitations. Internal coverage records, provenance and rule diagnostics are excluded from the six-field public trace. P5 no-view cases use the inherited identical deterministic public response and make no model call.

## Optional C

Trigger conditions were frozen before live execution. Only B UNKNOWN requirements qualify when A0 was fully supportable, no source veto applies, all mechanical conditions pass, and every uncertainty belongs to the declared relation/qualifier/list/field-consistency set. No confidence-only trigger is used. A maximum of one focused gpt-4o-mini call per triggered requirement uses 500 output tokens.

The focused output is strict structured JSON with SUPPORTED/NOT_SUPPORTED/UNCERTAIN, requirement ID, cited support IDs, typed relation/qualifier/completeness properties and rationale. SUPPORTED requires existing authorized references and internally consistent properties. Attestations bind the exact request signature and assessment hash, which includes the candidate and spans. They resolve only previously null semantic checks. They cannot override a false mechanical check, existing policy/sufficiency failure or known counterevidence. Changed C decisions receive a new public generation; unchanged C results reuse B's response explicitly.

## Scientific limits

This is application-level consistency and coverage verification, not general contradiction detection, independent entailment verification or a stronger model. False positive semantic flags can still pass every deterministic check. False negative or coarse answer-form fields can produce unnecessary refusal. Measured behavior on exposed development data must not be presented as independent validation.
