# Requirement Decomposition and Alignment, version 1.0

RDA enriches the existing query-profile representation with explicit output obligations. It does not create a second FULL/CFAF selector or a second LLM reasoning pipeline. The original query and the legacy semantic assessment remain unchanged. Internal RDA data are not inserted into model payloads.

## Query provenance and requirements

Each requirement retains the familiar `requirement_id`, `request_type`, `answer_kind`, `metadata_fields` and `request_text` fields, with stable sequential IDs `request-1`, `request-2`, etc. Additional fields record the exact original query span and offsets, answer type, operation, explicit qualifiers, proposed antecedent dependencies, cardinality, requested precision, resolution status and legacy parent requirement IDs. The full original query and its SHA-256 are retained. Validation rejects invented spans, changed queries, unstable IDs and forward/missing dependencies.

The query-only grammar splits explicit output clauses such as WHO + HOW MANY, WHO + WHEN, COUNT + AVERAGE and a three-part interrogative. Parallel explicit attributes such as height and color become two obligations. A subject such as a university does not become an extra answer requirement merely because resolving it is an internal dependency. Ordinary WHEN questions acquire no exact-day constraint; explicit year/decade/range/day wording is recorded separately.

First/last/earliest/latest/only/unique and maximum/minimum wording is traced to query tokens. Capitalized proper-name uses and `not only` contexts are retained as unresolved, non-required qualifier interpretations. A detected qualifier is not proof of its semantic scope. Pronouns link to a sole preceding identity requirement as a proposed dependency; otherwise the referent remains unresolved. Complete-list requests record their required cardinality without asserting that a candidate list is exhaustive.

This is a finite grammar, not general natural-language understanding. Relation/operation fields and exact clause text preserve what needs interpretation; lexical patterns do not prove arbitrary predicates or antecedents. Decomposition completeness on natural benchmark questions has no independent requirement annotation.

## Alignment

`requirement_alignment.py` aligns each requirement with candidate-fragment proposals and exact offsets. It uses frozen analyzer entity proposals for names, lexical numeric/temporal/Boolean token shapes, conservative attribute patterns and the full candidate where isolation is unresolved. Every proposed fragment is validated against the unchanged candidate text. Multiple candidates remain visible rather than being silently resolved.

Numbers are narrowed by the requested unit when available, allowing a year elsewhere in an answer to coexist with a goal count. A mixed person/count answer is not compared with one global numeric answer form. The generic scorer-plus-count question therefore produces a named fragment and a numeric fragment, linked by a proposed dependency. Source clauses may produce a proposed same-entity match or potential mismatch warning. Both remain semantic diagnostics, not an entailment proof based on co-occurrence.

Supporting references are inherited from the explicitly recorded legacy parent requirements and deterministically resolved in permitted views. The trace distinguishes EXACT_TYPED_REQUIREMENT mapping from COARSE_INHERITED_ASSESSMENT. A newly separated child does not gain independent semantic evidence just because its parent claimed complete support. Original global/per-requirement semantic properties, candidate, roles and references are not rewritten.

A native requirement-keyed application candidate can expose a demonstrably omitted component or incompatible native value type. Model-generated prose does not have that authoritative structure: failure to extract a fragment becomes soft uncertainty. The live pilot uses the existing prose candidate schema, so these native-structure hard rules are exercised by development tests rather than live model outputs.

## Metadata value-type limitation

Metadata requirements preserve the exact requested field, for example `created_at`, and keep separate field obligations. The current profile uses answer kind METADATA for both file type and creation date. Thus the date field is represented, but its value answer kind is not refined to DATE_TIME. A separately authored 17-case audit achieved 17/17 expected requirement counts and 16/17 expected type sequences; the mismatch and original expectation are retained. This is a reason to keep semantic alignment diagnostic rather than claim a complete value-type system.

## Pipeline and model boundary

RDA is computed in the internal Query Profiling trace and consumed/recomputed by Stage 5. Stage 5 aligns fragments, resolves authorized spans, applies the unchanged source registry per requirement, classifies hard failures versus soft uncertainty and produces request fulfilment. The original eight named stages and `TopLevelModeSelectionStage` are unchanged.

The existing semantic analyzer still sees the same legacy profile and schema. This preserves controlled ablation but leaves some child support semantically coarse. A future version can evaluate an explicitly scoped analyzer interface separately; this study does not disguise such an upstream change as a deterministic gate effect.
