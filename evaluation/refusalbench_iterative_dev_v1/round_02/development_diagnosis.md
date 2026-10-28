# Diagnosis after round 02

Observed round results: CFAF 70% accuracy, FULL recall 60%, CFAF recall 80%; control 75%, FULL recall 70%, CFAF recall 80%. Four query profiles remain unresolved, and primary output-validation errors are zero. The sample differs from round 01, so these figures alone do not establish a causal effect.

Two official ambiguous-query cases receive FULL from both systems: an identical song title shared by original/adaptation and a deictic film query with two titles. Choosing the first referent or listing both alternatives does not necessarily fulfil a singular unresolved request. v02 adds an explicit per-requirement referent-resolution check and ambiguity cause rather than general contradiction detection.

A telegraphic person query, a factual yes/no query and fronted question context expose remaining deterministic-typing gaps. v02 recognizes common yes/no/why/prefaced forms. When deterministic typing still cannot resolve a query, a constrained fallback sees ONLY the query, returns typed requirements with copied query spans, and has no FULL/CFAF or answer field. It is separately budgeted and logged. It never runs on zero permitted evidence.

v02 also requires explicit per-requirement identity identification, relation/critical-qualifier support, answer form and completeness. A named identity cannot be replaced by an unnamed role; an associated entity cannot substitute for a supported role relation; a category definition cannot substitute for a requested concrete instance. These checks address conceptual defects documented in the earlier bounded development runs, not ID-specific expected labels. A structured semantic refusal cause is distinct from the final gate and public wording. Fictional subjects and unsupported year qualifiers are explicitly separated from nonfactual/subjective requests.

All old versions and round outputs remain unchanged. The v02 controller/provider are new files solely to support the query-only stage while preserving the earlier frozen framework and the identical external primary scorer.
