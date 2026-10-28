# Hard and soft verification policy

A Boolean returned by an LLM is not authoritative merely because it is typed. The revised Stage-5 component distinguishes the origin and enforcement authority of each check.

| Category | Examples | Basis | Policy |
|---|---|---|---|
| Hard | No authorized view; aggregate/metadata scope violation | Authoritative policy projection and requested scope | Blocks FULL |
| Hard | Unknown/unauthorized span, rejected assessment contract | Deterministic schema/reference validation | Blocks FULL; invalid upstream assessment remains ERROR in scoring |
| Hard | Explicitly absent candidate output | Actual output structure | Blocks FULL; does not prove fact absence |
| Hard | Missing component or wrong native value type in a requirement-keyed application candidate | Demonstrable structured output contract | Blocks FULL |
| Hard | Trusted source registry explicitly FORBIDDEN for an asserted use | Authenticated/test-attested provenance plus application rule | Blocks FULL |
| Soft | Prose answer type inferred from entity or token proposals | Model/heuristic interpretation | Shadow diagnostic |
| Soft | First/last/unique priority, list exhaustiveness, referent resolution | Semantic interpretation | Shadow diagnostic |
| Soft | Entity/quantity association or same-name roles | Proposed clause matching/model evidence | Shadow diagnostic |
| Soft | Negative or unknown analyzer completeness/relation properties | LLM semantic assessment | Never relabeled as deterministic proof |
| Soft | Default capability requiring additional evidence | Claim-relative source rule needing semantic support | Shadow diagnostic; FORBIDDEN remains hard |

Existing v02 access and independent semantic sufficiency requirements remain mandatory in every revised configuration. B2/B3 cannot promote an A0 refusal. Shadow mode preserves an otherwise valid original FULL decision while recording new uncertainty; it does not convert UNKNOWN into proof of support or fact nonexistence.

Coverage keeps COVERED, PARTIALLY_COVERED, NOT_COVERED and UNKNOWN. Its justification identifies deterministic/application facts, LLM assessment or unresolved interpretation. `deterministic_entailment_proof` is false throughout. Coverage can be UNKNOWN while B3 retains an original FULL decision: the support basis remains the independently validated legacy assessment, and the new semantic diagnostic has no blocking authority. This is an explicit policy tradeoff, not a claim that every new requirement was independently proven.

A0 retains v02 decisions. B1 uses the previous strict RECV and source enforcement. B2 uses RDA and hard constraints; B3 adds visible soft diagnostics. Their modes are identical by design. For controlled diagnostics B2 also retains internal shadow rows, but it exposes no new top-level soft-warning enforcement. B4 and the optional second-pass verifier are disabled. No post-result choice of soft vetoes was made.

The source registry itself is imported unchanged. RDA changes the granularity of its application from coarse parent requirements to separate children. Default ADDITIONAL_EVIDENCE_REQUIRED uses are soft, while explicitly FORBIDDEN uses stay hard. Any difference caused by that authority classification must be reported separately from source-rule expansion; no registry expansion occurred.

Hard policy reasons take priority over soft ambiguity for B2/B3. Other existing semantic refusal reasons remain intact. New genuine output omissions receive specific internal component codes. P5 no-view cases always use the identical canonical public response and make zero model calls; internal reasoning does not reveal source existence.

The World Cup restoration cannot be uniquely attributed to decomposition alone: removing veto authority from an inferred global answer type can independently restore the original mode. RDA additionally repairs representation and identifies distinct fragments. The historical-priority case exposes the reverse cost: shadow policy retains A0's incorrect FULL where strict B1 refused. Both changes must remain visible in paired results.
