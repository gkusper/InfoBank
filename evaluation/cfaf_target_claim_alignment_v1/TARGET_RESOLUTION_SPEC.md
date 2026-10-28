# Trusted Target Resolution specification

The resolver adapts the inspected `main` owned-object design to a generic, authorized catalogue. It does not infer general ownership from purchase wording or trust an entity merely because an LLM named it.

`Entry` records bind a permitted neutral view to an application entity key, target type, declared aliases/identifiers, optional edition, ownership attestation and explicit previous-version status. Entry provenance must be an authorized ingestion/retrieval origin. `Catalogue` binds these entries to the request signature, permitted-view content hashes and catalogue digest. Catalogue construction rejects unauthorized view IDs. A document-body string or LLM JSON dictionary cannot become a native authority object.

Resolution first checks explicit authorized identifiers, then contiguous declared aliases, then a permitted query-target anchor. The allowed-keyword matcher from `main` proposes only values from the authorized vocabulary. A cluster can contain several related views of one entity. Ownership-type selection requires a trusted ownership attestation. Edition selection uses declared edition/previous-version information rather than retrieval order. A sole retrieved candidate without a query/catalogue association remains unresolved.

States are RESOLVED, AMBIGUOUS, UNRESOLVED and NOT_APPLICABLE. Results record query target, neutral target ID, target type, permitted view IDs, resolution method, authoritative anchor, request/catalogue bindings and privileged candidate counts. They establish a permitted catalogue association, not that the requested relation is true. Scope is the authorized permitted catalogue, not every entity in the world.

Native `Resolution`/`LegacyResolution` objects retain the proof context. Consumers validate them before accepting a RESOLVED association; model-generated dictionaries cannot self-assert trusted resolution. Revalidation detects altered target data, query/projection or content hashes. The legacy proof uses the existing guarded metadata target binding, allowing the T2 claim-only ablation without attributing its old bindings to the new resolver.

Callers must supply a fresh policy-projected request. The pipeline's original access checks and mandatory pre-model policy/binding revalidation remain authoritative; the resolver does not replace the permission engine. Only included permitted catalogue entries are inspected. DENY/hidden sources never supply anchors, counts or ownership evidence. Metadata and aggregate views can have an internal target association without disclosing their restricted body or individual records.

Private titles, entity keys, identifiers, candidate counts and anchors remain privileged. No new target trace is sent to any model in this trial. The optional public summary contains no identifiers, titles, view list or counts. P5 hidden/absent requests remain publicly indistinguishable and make zero calls.

Controlled tests cover unique/ambiguous aliases, related-document clusters, two owned objects, explicit identifiers, editions, an unresolved pronoun, narrative mentions without catalogue authority, restricted views and forged/stale native bindings. The real development subset contains no owned-object multi-document stress sample; synthetic success is not independent production validation.
