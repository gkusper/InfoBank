# Architecture: ComponentCFAF v1

This package implements the CFAF application boundary in a small runnable Python library. It is not a replacement retrieval framework or an independent entailment prover. Runtime imports no dataset scorer or versioned experiment chain.

## Four public responsibilities

1. **RequestContract** retains original question, as-of context, language, exact query offsets, required parts, value types, qualifiers and dependencies. The early profile is local and query-only. The untrusted proposal may refine UNKNOWN types or add anchored parts; it cannot silently remove/weaken explicit parts. Every dependency ID and acyclic graph is checked with `graphlib`.
2. **GovernedEvidenceContract** contains authenticated application authority, permitted views, exact content hashes/offset catalogues, complete authorized inventory and a view-processing key. Raw IDs, denied records and private metadata remain in a private trace. The policy resolver is supplied by the authenticated application, never by the model. A hash proves integrity rather than source authority.
3. **DecisionContract** separates `FULL|CFAF` from execution status. FULL requires nonempty required obligations accepted by the local gate; operational fallbacks are not valid evidential refusals. Accepted model support is labelled `GATE_ACCEPTED_FULL`, not independently verified truth.
4. **PublicResponseContract** contains deterministic text, controlled reason/realization, safe next step and explicit claim–source links. Private trace is returned separately and must be stored privately by the host application.

`LLMProposal` is an internal adapter output, not a fifth public CFAF responsibility. It proposes anchored requirements, sparse source roles, typed claims, claim-specific references, missing parts and unresolved interpretation limits. It has no final mode, permission or trusted-provenance field. Support origin is assigned by application code, not by the model.

## Eight logical stages and physical order

| Logical stage | Concrete component | Model calls |
|---|---|---:|
| 1 Profiling | LocalProfiler, conservative AND segmentation | 0 |
| 2 Candidate retrieval | ProvidedContextRetriever or in-memory SQLite FTS5/BM25 | 0 |
| 3 Access views | LegacyGovernance plus reused authoritative projection | 0 |
| 4 Evidence assessment | SDKProvider returns one strict LLMProposal | 1 |
| 5 Sufficiency | Anchors, references, role, type, dependency and scope checks | 0 |
| 6 Mode selection | Small extracted first-failing-assessment selector | 0 |
| 7 Realization | DeterministicRenderer | 0 |
| 8 Validation/audit | Policy-current checks, public reference validation, private trace | 0 |

Physical authorization and projection happen **before retrieval**. Only permitted text enters either retriever and the SDK. Neutral view IDs are assigned after filtering. The late semantic proposal did not guide the earlier retrieval. If it exposes unresolved interpretation or a need for another retrieval, FULL is withheld; no hidden agent loop runs.

The standard successful generative path makes one actual Chat Completions request to `gpt-4o-mini`, temperature 0, strict Structured Outputs, one repetition, shared output ceiling 2048. SDK retries are disabled. Timeout, refusal, truncation, interrupted completion, HTTP failure and application validation are distinct statuses. There is no repair call, answer-regeneration call, embedding service or online judge. The SDK adapter caps total persisted attempts at 100 in the one-process pilot and enforces its deadline. The task runner independently enforces 105-minute/new-call and 120-minute/full-task bounds.

No usable views, an empty request, or explicitly recognized structured syntax can use zero calls. The structured grammar is deliberately narrow: `metadata[created_at]`, `metadata[title]`, or `aggregate[count|sum|mean]` with the matching single authorized view. It does not infer a shortcut from a model claim. The aggregate helper reuses the existing contributor-deduplicating threshold executor. Arbitrary natural-language metadata/aggregate fulfilment is conservatively restricted in v1; it needs an explicit trusted target/scope integration before general use.

## Evidence and publication

The local catalogue uses consecutive 600-character, nonoverlapping windows with exact offsets and source SHA-256. Sparse omission means NOT_ASSESSED across the complete authorized inventory. A selected support source must have an explicit PRIMARY/SUPPORTS assessment with valid grounding. Unassessed sources cannot establish exhaustive lists or earliest/latest claims; such requirements need an application-provided complete-scope attestation.

Decimal reference aliases are allowed only for the same source and an existing unique catalogue index. Original and normalized spellings are logged. Unknown indexes are rejected; there is no nearest-span or content-based repair. A source hash, valid offset and explicit model attribution still do not prove semantic entailment.

FULL rendering concatenates accepted claim texts without adding facts. Citations use claim IDs and validated source/span IDs; they do not depend on matching the complete answer to a candidate string. Public provenance separates REFERENCE_VALID, MODEL_ATTRIBUTED and SUPPORT_NOT_INDEPENDENTLY_VERIFIED. Structured local shortcuts use APPLICATION_STRUCTURED for attribution, while retaining the support limitation. Merely examined sources are listed separately and are not supporting citations.

CFAF uses controlled templates. With no permitted view, hidden-present and absent cases have the same historical no-support text and public fields. Neutral execution-failure text does not masquerade as an evidential refusal. No partial factual claim is published in this minimal CFAF configuration. Private blocked markers do not influence the fixed no-view template. Quota is debited once in prepare; guard and renderer never debit it. Reusing a consumed query ID cannot trigger another generation. Authority is checked before projection and after inference before publication.

The view key includes principal, purpose, policy/revocation version, processing version, selected IDs and content hashes. It is an evidence-view key, not a question-independent answer-cache key. No application answer/model cache is enabled; a future proposal cache must also bind the complete RequestContract. The demo quota is memory-only; production must supply durable, atomic policy/quota state and current revocation checks.

## Replaceability and remaining semantic trust

Profiler, retriever, governance, proposal provider, optional local shadow support checker and renderer are constructor inputs via simple Protocols. Two concrete retrievers work through the same View/Evidence boundary and gate. A shadow checker must explicitly declare local-only execution and cannot change the primary decision. No spaCy, NLI, Chroma, Casbin or workflow engine is imported or downloaded at runtime.

The profiler is conservative query segmentation, not a general parser. OR is unresolved; dependency semantics and free-text entailment remain model/application assumptions. Mechanical person/count equality checks catch inconsistent explicit bindings but do not independently prove the source relation. The new configuration changes proposal schema, prompting and execution together; it cannot isolate the selector's accuracy effect.
