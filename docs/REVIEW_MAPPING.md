# Reviewer requirement mapping

Status: `PRE_FREEZE`

| Review | Requirement | Module / endpoint | Deterministic test | Commit | Technical artifact | Status | Pending human work |
|---|---|---|---|---|---|---|---|
| Review A | Durable source, provenance, page chunks and citations | `source_storage.py`, `document_processing.py`, document/source endpoints | `test_source_storage.py`, `test_document_processing.py`, `test_citations.py` | `feature/infocom-a-gate`, integrated here | A-gate reports; W1 trace; Document screenshot | PASS_AUTOMATED | screenshot acceptance; citation audit |
| Review A | Routing scope and actual-pipeline evaluation | `routers/chat.py`, `actual_pipeline_runner.py` | `test_actual_pipeline.py`, `test_reviewer_contracts.py` | A2/C/D development commits | routing report, sealed raw-run manifests | PASS_DEVELOPMENT | gold validation; freeze; final E1 |
| Review C | Persistent permissions, purpose/expiry and safe failures | `policy_engine.py`, `/api/policy/*`, `/api/ask` | `test_policy_invariants.py`, `test_reviewer_contracts.py` | `384c35c` | W3 API trace; Permissions screenshot | PASS_AUTOMATED | screenshot acceptance |
| Review C | Aggregate and metadata governance | `aggregate_executor.py`, policy/chat endpoints | `test_aggregate_executor.py`, `test_policy_invariants.py` | C-gate commits | C-gate report; W3 trace | PASS_AUTOMATED | approve final evaluation protocol |
| Review D | Evidence roles and controlled output | `evidence_service.py`, `controlled_failure.py` | `test_evidence_invariants.py`, `test_controlled_failure.py` | D-gate commits and `384c35c` | D-gate report; Assistant screenshot | PASS_DEVELOPMENT | human citation/gold QA |
| Review D | Action closure and contextual-only safety | `action_closure.py`, `/api/evidence/action-list` | `test_action_closure.py`, `test_reviewer_demo_seed.py` | `430fdc3` | Actions/Evidence screenshot and demo seed | PASS_AUTOMATED | screenshot acceptance; MailEx annotation |
| Review A | Recoverability and consistency | `pre_freeze_operations.py`, `orphan_repair.py` | operations/orphan tests | pre-freeze operations/tooling commit | ignored operations smoke report and backup manifest | PASS_WHEN_LOCAL_SMOKE_PASSES | production policy/retention approval |

No row represents human acceptance, a final evaluation, freeze or release.
