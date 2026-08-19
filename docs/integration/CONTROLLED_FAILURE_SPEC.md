# Controlled-failure specification

Version: `controlled-failure-v3`

Configuration: `backend_python/config/controlled_failure_v3.json`

Implementation: `backend_python/controlled_failure.py`, `backend_python/aggregate_executor.py`

Development scorer: `infocom-controlled-failure-scorer-v1` in `evaluation/d_gate.py`

## Output classes

| Output class | Meaning | Generator |
|---|---|---|
| `FULL_ANSWER` | Authorized evidence fully supports the requested claim. | Allowed with permitted, traceable context. |
| `CONSTRAINED_ANSWER` | A bounded qualified answer is safe, for example a stated disagreement. | Allowed only with the stated constraint. |
| `AGGREGATE_RESULT` | A k-thresholded numeric aggregate is available. | Skipped in the current executor; the deterministic aggregate is returned. |
| `METADATA_ONLY` | Only policy-approved metadata may be shown. | Skipped. |
| `CLARIFICATION` | Object, source, time window, or current status is underspecified. | Skipped. |
| `REFUSE_PERMISSION` | Hard authorization, archive, Deny, or security policy blocks use. | Skipped. |
| `REFUSE_INSUFFICIENT_EVIDENCE` | Permitted candidates exist but lack supporting evidence. | Skipped. |
| `REFUSE_NO_MATCH` | No permitted match exists. | Skipped. |
| `REFUSE_AGGREGATION_THRESHOLD` | Distinct permitted contributors do not satisfy k. | Skipped; no count or source existence is disclosed. |
| `REFUSE_CONFLICT` | An authority-sensitive conflict cannot be resolved safely. | Skipped. |
| `ESCALATE_TO_HUMAN` | A state-changing request must use an explicit audited action workflow. | Skipped. |

`REFUSE_CONFLICT` is used by evaluation cases that require authority resolution. Runtime conflicts that can be reported without choosing a winner use `CONSTRAINED_ANSWER`.

## Precedence and decision table

Precedence is evaluated top to bottom. A lower row cannot weaken an earlier hard result.

| Priority | Condition | Output | Reason code | Public behavior |
|---:|---|---|---|---|
| 1 | Archived source, active Deny, purpose mismatch, expired/future-only authorization, or no persistent permission | `REFUSE_PERMISSION` | `governance`, `inactive_policy`, or `stale_index_denied` | Do not reveal content, citation, generator context, or hidden source identity. |
| 2 | Unsafe request or user/source prompt injection | `REFUSE_PERMISSION` | `safety` or `operational_security` | Provide policy-safe wording only. |
| 3 | Aggregate-only request below configured distinct-contributor k | `REFUSE_AGGREGATION_THRESHOLD` | `aggregation_threshold_not_met` | Do not reveal k shortfall, source count, source ID, value, or citation. |
| 4 | Aggregate-only request at/above k | `AGGREGATE_RESULT` | `aggregate_threshold_satisfied` | Return mean/sum/count and distinct-contributor count; no individual value or identity. |
| 5 | Metadata-only usable evidence | `METADATA_ONLY` | `governance` | Return declared metadata only. |
| 6 | No permitted candidate match | `REFUSE_NO_MATCH` | `epistemic` or `wrong_object` | State that no supported match is available. |
| 7 | Permitted candidates but no traceable supporting chunk for each indispensable source | `REFUSE_INSUFFICIENT_EVIDENCE` | `evidential` or `insufficient_evidence` | Request better evidence without fabricating a claim. |
| 8 | Current/status question without a current/open/closed/recent/deadline signal | `CLARIFICATION` | `temporal_status` | Ask for time window or current source. |
| 9 | Primary and contrastive evidence with an authority-sensitive unresolved conflict | `REFUSE_CONFLICT` | `conflicting_evidence` or `conflict_defeat` | State that authority must be resolved. |
| 10 | Primary and contrastive evidence with a bounded reportable disagreement | `CONSTRAINED_ANSWER` | `conflict_defeat` | Report the disagreement without selecting an unsupported winner. |
| 11 | At least one authorized traceable primary source per indispensable claim | `FULL_ANSWER` | `supported` | Generate only from permitted context and cite exact document/page/chunk. |

## Hard and soft gates

The hard authorization gate runs before routing, retrieval context assembly, generation, logging, and citation output. Deny, archive, Metadata-content withholding, Aggregate individual withholding, purpose, and validity cannot be relaxed by calibration.

The soft evidence gate uses the versioned defaults:

- minimum primary sources: 1;
- minimum source diversity: 1;
- minimum support score: 0.5;
- aggregate k: 3.

Calibration may compare soft thresholds on the development split only. It may not modify authorization precedence or use the candidate holdout or frozen D1–D8 v1.

Supporting-chunk rule: every indispensable gold document must have at least one accessible, traceable chunk on an allowed page. A citation must match document ID, chunk-document association, and page range. Source-diversity greater than one is required only when a case definition marks multiple documents indispensable.

## Safe public wording

- Permission: “There is no permitted source that can be used for this question in the InfoBank.”
- Insufficient evidence: “The answer cannot be found in the document.”
- Aggregate threshold: “A governed aggregate result is unavailable for this request.”
- Conflict: identify that evidence conflicts, but not a winner unless authority is established.
- Clarification: request only the missing object, source, time period, or claim.

The aggregate-threshold response uses an empty public source list, sanitized governance state, no citation, and a trace without excluded/available source counts.

## Pseudocode

```text
profile(query)
if unsafe_or_mutating(query): return safe_refusal_or_escalation

permitted = resolve_policy_before_routing(user, purpose, all_candidates)
if no permitted candidate: return REFUSE_PERMISSION or REFUSE_NO_MATCH

routed = route(permitted)                 # routing cannot expand permitted
resolved = resolve_policy_again(routed)   # stale index defense
retrieved = retrieve(resolved.content_ids)
withhold Deny, Metadata content, Aggregate individual content, attacked sources

if aggregate_request:
    aggregate = execute_after_policy_and_dedup(retrieved.numeric_contributions, k)
    if below_k: return REFUSE_AGGREGATION_THRESHOLD without source disclosure
    return AGGREGATE_RESULT without calling the generator

if metadata_only: return METADATA_ONLY
if no match: return REFUSE_NO_MATCH
if missing indispensable supporting chunk: return REFUSE_INSUFFICIENT_EVIDENCE
if current question lacks temporal signal: return CLARIFICATION
if authority-sensitive conflict: return REFUSE_CONFLICT
if bounded conflict: return CONSTRAINED_ANSWER
return FULL_ANSWER with accessible document/page/chunk citations
```

## Configuration mapping

- Output vocabulary, precedence, thresholds, supporting-chunk policy, conflict policy, and wording version: `backend_python/config/controlled_failure_v3.json`.
- Validated loader/config hash: `backend_python/controlled_failure_config.py`.
- Runtime gate: `backend_python/controlled_failure.py` and `backend_python/routers/chat.py`.
- Aggregate gate: `backend_python/aggregate_executor.py`.
- Development calibration/scorer and error taxonomy: `evaluation/d_gate.py`.
- Tests: `evaluation/tests/test_d_gate.py`, `backend_python/tests/test_aggregate_executor.py`, and existing evidence/routing tests.
