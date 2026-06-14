# Controlled Failure Implementation Map

This branch implements the PDF concept of controlled failure as an explicit output mode in the InfoBank RAG pipeline.

## Backend contract

The backend returns a `controlled_failure` object whenever the system must avoid, restrict, escalate, or qualify the full requested answer:

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

## Implemented statuses

| Status | Runtime behavior |
| --- | --- |
| `full_answer` | Permitted, sufficiently supported answer mode. |
| `abstain` | No source, no support, missing context, or unsupported post-generation answer. |
| `refuse` | Governance-denied, unsafe, or prompt-injection request. |
| `restricted_answer` | Contextual-only, conflict/defeat, browser-history-only, or qualified answer mode. |
| `aggregate_answer` | Aggregate/statistical answer over aggregate-only sources with raw content withheld. |
| `metadata_only_answer` | Metadata can be acknowledged, but source content is withheld. |
| `ask_clarification` | Underspecified or temporally unclear question. |
| `escalate_to_human` | State-changing or operationally unsafe action boundary. |

## Implemented reason classes

| Reason | Runtime trigger |
| --- | --- |
| `epistemic` | No relevant source, underspecified query, generated not-found answer. |
| `evidential` | Missing, weak, contextual-only, analogical-only, or non-primary evidence. |
| `governance` | Denied, metadata-only, aggregate-only, or purpose-limited evidence. |
| `safety` | Harmful or abusive operational request. |
| `conflict_defeat` | Contrastive evidence closes, cancels, contradicts, or weakens a candidate claim. |
| `temporal_status` | Current/status question without current/open/closed/recent/deadline evidence signal. |
| `operational_security` | Prompt injection, source instruction attack, unsafe action boundary, or protected-instruction request. |

## Gate mapping

| PDF stage | Repository implementation |
| --- | --- |
| Query profiling | `relevance.build_query_profile`, pre-generation clarification gate |
| Candidate retrieval | `routers/chat.py` keyword routing + permitted corpus fallback |
| Policy and safety filtering | `policy_engine.resolve_document_access_bulk`, `controlled_failure.select_pre_generation_output_mode` |
| Prompt-injection shielding | user-question risk gate + retrieved-source shield before context assembly |
| Source-role labelling | `relevance.classify_chunk_profile` and `citds_classifier.py` |
| Evidence sufficiency checking | `evidence_service.check_rag_evidence` + `controlled_failure.select_rag_output_mode` |
| Output-mode selection | `controlled_failure.py` |
| Trace and feedback | `AuditLog.details.controlled_failure`, `/api/admin/citds-traces`, `/api/controlled-failure/feedback` |

## Runtime behavior

- Metadata-only sources return `metadata_only_answer` and never expose raw content.
- Aggregate-only sources can answer aggregate/statistical questions but not specific content claims.
- Contextual/activity sources cannot create obligations by themselves.
- Analogical evidence cannot support a direct factual claim unless the task is comparison.
- Contrastive evidence forces a restricted/qualified answer mode.
- Current/status questions require current, open, closed, recent, or deadline evidence signals.
- Missing support after generation is converted into an `abstain` controlled-failure object.
- Browser-history action-list rule questions return a `restricted_answer` instead of inventing an obligation.
- Unsafe requests are refused before retrieval or generation.
- State-changing requests are escalated to explicit workflows instead of being executed through chat.
- Prompt-injection text in retrieved sources is withheld and never sent to the generator.

## Deterministic checks

`/api/citds/self-test` now checks the action-list scenario and the controlled-failure gates. A standalone script is also available:

```bash
python scripts/controlled_failure_selftest.py
```
