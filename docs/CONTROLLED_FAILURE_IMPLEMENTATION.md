# Controlled Failure Implementation Map

This branch implements the PDF concept of controlled failure as an explicit output mode in the InfoBank RAG pipeline.

## Backend contract

The backend returns a `controlled_failure` object whenever the system must avoid, restrict, escalate, or qualify the full requested answer:

```json
{
  "status": "REFUSE_INSUFFICIENT_EVIDENCE",
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
| `FULL_ANSWER` | Permitted, sufficiently supported answer mode. |
| `REFUSE_INSUFFICIENT_EVIDENCE` | Permitted candidate exists but lacks supporting evidence. |
| `REFUSE_NO_MATCH` | A permitted search scope exists but no relevant object/source match exists. |
| `REFUSE_PERMISSION` | Revoke/missing permission, Deny, archive, purpose/validity rejection, unsafe request, or prompt-injection request. |
| `CONSTRAINED_ANSWER` | Contextual-only, bounded conflict/defeat, browser-history-only, or qualified answer mode. |
| `AGGREGATE_RESULT` | K-thresholded aggregate result with individual content withheld. |
| `REFUSE_AGGREGATION_THRESHOLD` | Aggregate threshold not met; source count and existence withheld. |
| `METADATA_ONLY` | Metadata can be acknowledged, but source content is withheld. |
| `CLARIFICATION` | Underspecified or temporally unclear question. |
| `REFUSE_CONFLICT` | Authority-sensitive conflict blocks a safe answer. |
| `ESCALATE_TO_HUMAN` | State-changing or operationally unsafe action boundary. |

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

- Policy resolution runs over the internal document scope before routing. Denied identifiers stay in privileged audit data and are removed from the public failure payload.
- Revoke, explicit Deny, archive, purpose mismatch, expiry/future validity, and stale-index rejection return internal `REFUSE_PERMISSION`; a wrong object inside an otherwise permitted scope returns `REFUSE_NO_MATCH`.
- Both public failure shapes are non-enumerating, contain no denied filename/UUID/hash/page count, denied-source count, or citation, and expose only permitted operational summaries plus an identifier-free routing trace. Exact denied-source details remain in the privileged audit record.
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
