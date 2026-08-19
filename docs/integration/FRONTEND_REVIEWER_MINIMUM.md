# Frontend reviewer minimum

Status: `IMPLEMENTED_AND_SMOKE_TESTED`

The existing single-page frontend was extended only with reviewer-critical
fields. It was not generally redesigned.

| Roadmap screen | Implemented reviewer surface | Contract test | Screenshot |
|---|---|---|---|
| Document/data store | UUID, SHA-256, processing/source status, provenance, page/chunk counts, re-index, archive, restore, delete, source-page and permission links | PASS | `02-document-data-store.png` |
| Question/answer/sources | output class, evidence decision, audit ID, safe next step, role, effective permission badge, document/page/chunk citation and authorized source-page action | PASS | `01-question-answer-sources.png` |
| Permissions/policy | Owner/Reader/Aggregate grant/change, revoke, transfer link, purpose, validity/expiry, Full/Aggregate/Metadata/Deny rule and effective resolution | PASS | `03-permissions-policy.png` |
| Actions/evidence | OPEN, CLOSED_COMPLETED, CLOSED_CANCELLED, SUPERSEDED, primary/contextual/contrastive roles, browser-only rule and audit/correction trace statement | PASS | `04-actions-evidence.png` |

`backend_python/tests/test_reviewer_contracts.py` deterministically verifies the
four screen IDs, required field markers, lifecycle/policy/evidence API wiring,
audit-ID response contract, exact-object support guard, and uniqueness of HTTP
method/path pairs. The local browser run used the synthetic API workflow data;
all four PNGs were captured outside the repository in the task's output
directory. No screenshot contains real personal, email, health, or provider
data. Consequently manual screenshot capture is not pending for this gate.
