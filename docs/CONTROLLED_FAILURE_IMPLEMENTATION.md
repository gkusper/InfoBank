# Controlled Failure Implementation Map

This branch implements the PDF concept of controlled failure as an explicit output mode in the InfoBank RAG pipeline.

## Backend contract

The backend now returns a `controlled_failure` object when the system must avoid the full requested answer:

```json
{
  "status": "abstain",
  "reason": "evidential",
  "evidenceState": {},
  "policyState": {},
  "safeOutput": "The answer cannot be found in the document.",
  "nextSteps": [],
  "trace": {}
}
```

Implemented statuses:

- `full_answer`
- `abstain`
- `refuse`
- `restricted_answer`
- `aggregate_answer`
- `metadata_only_answer`
- `ask_clarification`
- `escalate_to_human`

Implemented reason classes:

- `epistemic`
- `evidential`
- `governance`
- `safety`
- `conflict_defeat`
- `temporal_status`
- `operational_security`

## Gate mapping

| PDF stage | Repository implementation |
| --- | --- |
| Query profiling | `relevance.build_query_profile` |
| Candidate retrieval | `routers/chat.py` keyword routing + permitted corpus fallback |
| Policy and safety filtering | `policy_engine.resolve_document_access_bulk` |
| Source-role labelling | `relevance.classify_chunk_profile` and `citds_classifier.py` |
| Evidence sufficiency checking | `evidence_service.check_rag_evidence` + `controlled_failure.select_rag_output_mode` |
| Output-mode selection | `controlled_failure.py` |
| Trace and feedback | `AuditLog.details.controlled_failure`, `/api/admin/citds-traces` |

## Runtime behavior

- Metadata-only sources return `metadata_only_answer` and never expose raw content.
- Aggregate-only sources can answer aggregate/statistical questions but not specific content claims.
- Contextual/activity sources cannot create obligations by themselves.
- Missing support after generation is converted into an `abstain` controlled-failure object.
- Browser-history action-list rule questions return a `restricted_answer` instead of inventing an obligation.
