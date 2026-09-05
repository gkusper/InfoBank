# WoLaLa 2026 Pipeline Label Spec

## State Model

`PipelineState` is the shared object passed through every stage. It is
serializable after every stage and contains appended `LabelRecord` entries,
candidates, claim assessments, a top-level CFAF decision object, response
contract, generator context, internal trace, public trace, timings, model-call
counts, and token usage when known.

`LabelRecord` preserves:

- `value`
- `producer`
- `method`
- `confidence`
- `rule_id`
- `model_version`
- `timestamp`
- scoped subject fields such as `query_id`, `claim_id`, and `source_id`

Labels are append-only in this preparation harness. Later stages may derive new
labels, but they do not overwrite earlier access, retrieval, or evidence labels.

## Stage Order

1. `QUERY_PROFILING`: appends task, purpose, requested content, requested
   granularity, requested action, time horizon, required evidence strength, and
   source scope.
2. `CANDIDATE_RETRIEVAL`: appends candidate ID, source ID, source type,
   retrieval rank, retrieval score, retriever name, and retrieval reason.
3. `ACCESS_AND_SAFETY_RESOLUTION`: appends authoritative access mode,
   existence visibility, policy rule, policy version, purpose compatibility, and
   security status.
4. `EVIDENCE_LABELLING`: appends claim-scoped evidential role, evidence state,
   and relation labels. Denied content is not inspected by an LLM classifier.
5. `SUFFICIENCY_AND_PERMITTED_OUTPUT`: derives disposition and claim
   assessments without replacing the underlying dimensions.
6. `TOP_LEVEL_MODE_SELECTION`: selects `FULL` or `CFAF` outside generation with
   the rule `permitted_output meets requested_output -> FULL`, otherwise CFAF.
7. `RESPONSE_REALIZATION`: builds a response contract and passes only permitted
   evidence views into generator context.
8. `VALIDATION_TRACE_AND_FEEDBACK`: checks leakage markers, records validation,
   separates public/internal traces, and uses a safe fallback on failure.

## Label Dimensions

- Query profile: `task`, `purpose`, `requested_content`,
  `requested_granularity`, `requested_action`, `time_horizon`,
  `required_evidence_strength`, `source_scope`.
- Retrieval: `candidate_id`, `source_id`, `source_type`, `retrieval_rank`,
  `retrieval_score`, `retriever_name`, `retrieval_reason`.
- Access and visibility: `AccessMode` = `FULL`, `AGGREGATE`, `METADATA`,
  `DENY`; `ExistenceVisibility` = `PUBLIC`, `OWNER_OR_AUDITOR`,
  `INTERNAL_ONLY`.
- Evidence: `EvidentialRole` = `PRIMARY`, `CONTEXTUAL`, `CONTRASTIVE`,
  `IRRELEVANT`, `UNKNOWN`; `EvidenceState` = `CURRENT`, `STALE`, `DEFEATED`,
  `SUPERSEDED`; relation = `SUPPORTS`, `REFUTES`, `CLOSES`, `QUALIFIES`,
  `NONE`.
- Disposition: `DIRECT_USE`, `AGGREGATE_ONLY`, `METADATA_ONLY`, `EXCLUDED`.
- Top-level mode: `FULL` or `CFAF`.
- CFAF realization: `RESTRICT_CONTENT`, `RESTRICT_GRANULARITY`, `ABSTAIN`,
  `REFUSE`, `CLARIFY`, `ESCALATE`.
- Reason class: `EPISTEMIC`, `EVIDENTIAL`, `GOVERNANCE_PRIVACY`, `SAFETY`,
  `TEMPORAL_CONFLICT`, `OPERATIONAL_SECURITY`.
- Validation: `PASS` or `FAIL`.

## Propagation Rules

Policy dominates semantic relevance. A denied source is dispositioned as
`EXCLUDED` even when it would otherwise be relevant. Metadata-only content and
aggregate-only raw individual content never enter ordinary answer generation.

Contextual evidence may qualify an answer but cannot establish a factual claim
or open action alone. Contrastive evidence may close or qualify a claim; an
unambiguous later cancellation can support a `FULL` closed-status answer rather
than forcing CFAF.

Public traces are filtered by existence visibility and the response contract.
`INTERNAL_ONLY` source IDs, titles, and existence are retained only in the
internal trace.
