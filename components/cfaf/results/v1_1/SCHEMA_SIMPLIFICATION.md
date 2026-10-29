# Proposal schema simplification audit

The public Request, Governed Evidence, Decision and Public Response responsibilities remain. CompactProposal is an internal wire adapter; the existing internal LLMProposal is derived locally for the tested gate/renderer. The model no longer copies authoritative application state. This is a complete v1.1 configuration comparison, not an isolated schema-only accuracy experiment.

| v1 field/group | Gate/security use | Renderer/audit use | v1.1 treatment |
|---|---|---|---|
| requirements[].requirement_id | Obligation membership | Trace | Stable IDs supplied by application; retained locally |
| query_start/query_end | Exact query anchor validation | Trace | Supplied once; not regenerated |
| required | Prevent silent obligation removal | Trace | Authoritative local value, not regenerated |
| value_type | Typed output check | Claim rendering | Request type stays local; claim value_type retained |
| qualifiers/exhaustive | Request scope constraints | Trace | Raw query/local contract retained; exhaustive flag supplied; no repeated model list |
| depends_on | DAG/subject binding | Trace | Local dependencies supplied; per-claim parent links retained |
| source_assessments.source_id/role | Explicit PRIMARY support | Inventory trace | Sparse evidence rows retain source and explicit role |
| relation SUPPORTS | Support-role gate | Trace | Evidence row used as support proposes SUPPORTS for PRIMARY, otherwise NONE; derived, still model-origin |
| grounding_span_ids | Reference existence | Trace | Replaced by exact source quotation; offsets generated/validated locally |
| note | Not consumed by gate | Verbose audit | Removed from wire; local note empty |
| claims.claim_id | Link integrity | Public claim association | Short local id retained |
| requirement_ids | Fulfilment coverage | Trace | Retained as claims.requirements |
| text | Candidate answer | Deterministic public text | Retained, no compulsory second generation |
| value_type/value | Type and identity/count checks | Trace | Retained |
| subject_key/dependencies | Person/count association | Trace | Retained as subject/parents |
| evidence source/span repeated per claim | Mechanical references | Citations | Deduplicated evidence rows; claims reference evidence IDs |
| requirement_support.requirement_id/claim_ids | Obligation coverage | Trace | Derived from claim mappings and missing list |
| requirement_support.status/missing rationale | Complete versus missing | Trace | Missing requirement IDs retained; no rationale string; SUFFICIENT means model asserted complete through the wire contract, never independent truth |
| interpretation_limit | Truthiness withholds FULL | Trace | Replaced by unresolved Boolean and derived internal marker |
| final mode/permission/trusted provenance | Must never be model authority | Public decision | Still absent from model schema |

Input also removes duplicate query text inside the full early profile, global inventory copies, per-window offset/hash catalogues and public-metadata wrappers. The complete authorized text, question and as-of context remain identical across systems; authoritative inventory/hashes stay local. Sparse omissions still mean NOT_ASSESSED.

The installed development-only o200k_base tokenizer measured schema+prompt at 1558 tokens for frozen v1 versus 847 for v1.1. Synthetic one/three/six-claim compact proposals contain 126/340/661 tokens. Both 1024 and 1536 fit those examples; 1536 was chosen before live output to preserve margin for longer quotations and dependencies. These are preflight counts, not actual API usage or evidence of real speedup. Live output tokens, truncation, latency and lost FULL decisions are measured separately. There is no JSON repair or unvalidated fallback.

## Observed paired-development limitation

The compact convention derives SUFFICIENT when a requirement has mapped claims and is absent from missing. Actual saved outputs show that limitation-shaped non-answers can satisfy that syntactic convention (one-based InfoBank cases 2/8), and accepted public text can omit the required name even when a private typed value/citation identifies it (case18). This is a semantic regression, not resolved by strict schema or quote validity. Case4 also supplied free text rather than an ID in missing and was safely withheld as application failure. No post-outcome change was made to the frozen convention. The combined compact configuration remains experimental despite lower measured output tokens and latency.
