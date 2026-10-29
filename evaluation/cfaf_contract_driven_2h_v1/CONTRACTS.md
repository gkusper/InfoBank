# Four minimal component contracts

The executable standard-library dataclasses in contracts.py have no new framework dependency. They reuse existing policy and inventory validators.

- RequestContract: query plus exact authorized projection signature, constructed only after existing bound-payload validation.
- PermittedEvidenceContract: request signature, stable source inventory hash, immutable tuple of neutral view/access/hash entries; inventory comes from the existing authorized request and deterministic spans.
- FulfilmentDecision: existing FULL/CFAF value, explicit verification status and reason; rejects FULL on OPERATIONAL_FAILURE. It does not infer evidence sufficiency or entailment.
- PublicResponseContract: canonical six-field response serialized only after the existing strict public vocabulary/mode/status validator succeeds.

These are small executable boundary checks in the study harness. They do not reimplement profiling, retrieval, policy, labelling, RDA/RECV, mode selection, generation or citation proof. The measured C pipeline remains existing sparse-source code with only the unmeasured fourth generation removed. Proposed library substitutions and one-call realization remain future ablations.
