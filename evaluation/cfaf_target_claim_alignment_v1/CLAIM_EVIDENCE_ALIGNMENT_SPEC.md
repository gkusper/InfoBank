# Claim-Evidence Alignment specification

Each essential RDA requirement receives a proposed claim with target/subject dependency, requested predicate and exact query span, candidate value, value type, qualifiers, temporal precision, authorized supporting span IDs, authority, relation status and unresolved issues. The complete RDA requirement and parent-evidence mapping remain available. Target association, candidate-value occurrence and semantic relation support are separate properties.

Authority states are represented separately for value extraction and relation support:

- TRUSTED_STRUCTURED_SOURCE: a whitelisted metadata field of a trusted resolved target, or an application-attested structured record whose exact fields, request signature and source hash validate.
- DETERMINISTIC_TYPED_EXTRACTION: a candidate token/value can be extracted and typed; this alone does not establish its relation to the subject.
- LLM_SEMANTIC_ASSESSMENT: the unchanged upstream model proposes relation support.
- UNRESOLVED: no independent relation association is established.

`StructuredFact` is a native application input, never created from model JSON. Its predicate, value, value type, subject-view IDs and operation must match an authorized structured source record, as well as the request/content bindings. A copied hash does not permit inventing a different value. A numeric count is distinct from an average or sum. Missing target or fragment remains uncertainty rather than a proven mismatch. These structured interfaces are exercised by new controlled examples; the live corpus uses the existing prose analyzer and trusted metadata only.

Metadata access is separated from the requested attribute, value type and precision. `file_type` has string/categorical value semantics; `created_at` has DATE_TIME semantics while retaining METADATA access. Dates are parsed for validity rather than trusted from an ISO-looking pattern. A trusted timestamp may yield its year when the user requests year precision. A date in free text never becomes authoritative metadata. Unknown or ambiguous target bindings cannot choose among multiple field values.

The pure `relevance.claim_relation_signals` subset from `main` supplies lexical relation anchors. Adapted question/answer support diagnostics compare scoped evidence anchors and numeric tokens, without a lexical-threshold veto. Numbers occurring only in the question do not count as source support. English numeric-token normalization includes simple compound forms, but it is not a general quantitative entailment engine. The actor/role and entity/quantity associations remain explicit uncertainties unless a trusted record supplies that relation.

Citation provenance uses the existing deterministic source/span catalogue and permitted content. Claim scope can identify support outside a resolved target. It never expands permissions. The minimal-span recommendation adapts the source-minimization design conservatively: bounded greedy anchor coverage is diagnostic only, preserves identified counterevidence and never removes actual model context. Private filenames, document URLs and source IDs from the production citation module are not copied into public outputs.

T1 adds target diagnostics; T2 adds claim diagnostics using the existing trusted binding; T3 combines both. A common metadata type correction is recorded separately. All remain shadow-only and retain B3's original sufficiency/access conditions. T4 is not executed, and no new semantic hard veto is selected after inspecting labels. The same upstream assessment, permitted views, prompts and response schema are used across live systems.

A warning is not an independently adjudicated error, and matching words/names/dates is not semantic proof. Coverage and warning counts must be reported alongside alerts on correct FULL answers. Diagnostic results and machine suggestions are not human annotations or independent validation.
