# Sparse Source Assessment Contract v1

Complete source inventory is an application fact, constructed from the policy-authorized request before the model call. It records neutral view ID, access/view kind, source hash, exact span IDs/offsets/hashes, source date, private original marker mapping, request signature and stable inventory hash. Private mappings must refer only to authorized views and be unambiguous. Revalidation reconstructs inventory from the bound request; stale content/policy/hash fails.

Model source_assessments can be dense, sparse or empty. Explicit roles need known views, unique/conflict-free declarations and valid same-source grounding references. Omission creates NOT_ASSESSED bookkeeping, without inventing role, relevance, permission, absence or support. The legacy pipeline enum may retain UNKNOWN for an unlabeled candidate; assessed coverage comes from the explicit audit, not that enum default.

Every selected global/requirement support source needs an explicit assessment. Missing selected-source assessment fails the contract; CONTEXTUAL/non-SUPPORTS roles cannot establish sufficiency. Requirement IDs remain covered and completeness/relation/referent/granularity/confidence/premise conditions remain in the substantive gate. DENY, metadata, aggregate and trusted-target controls are preserved. Original selector/eight stages are unchanged.

Original prompts/schemas remain identical. Optional view_id spelling can be normalized exactly to source_id with a logged representation change; conflicting spellings fail. Normalization does not fill in model claims or relabel sources. Model data stays unchanged except logged exact representation normalization.

Reference v1 accepts existing catalogue IDs, unique exact whole-catalogue-span quotations, exact catalogue offsets, or verified original-marker/equivalent-span mapping. Partial-quote-to-larger-window guessing, absent/nonunique text, stale hashes, arbitrary/nearest spans and gold/LLM repairs are rejected. Overlapping duplicate quotations are ambiguous. The original nonexistent span remains invalid.

R1 is a separate post-B ablation: decimal index padding is canonicalized only if that exact source/span ID exists. It changes representation, not source choice, offsets or claims. Every repair logs original/normalized value/method. Primary frozen outputs are not rewritten.
