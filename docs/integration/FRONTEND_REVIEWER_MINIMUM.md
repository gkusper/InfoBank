# Frontend reviewer minimum

Status: `IMPLEMENTED_AND_SCREENSHOT_EVIDENCE_READY`

The existing single-page frontend was extended only with reviewer-critical
fields. It was not generally redesigned.

| Roadmap screen | Implemented reviewer surface | Contract test | Screenshot |
|---|---|---|---|
| Document/data store | UUID, SHA-256, processing/source status, provenance, page/chunk counts, re-index, archive, restore, source-page and permission links; action controls have accessible labels/tooltips | PASS | `02-document-data-store.png` |
| Question/answer/sources | complete focused W2 question, actual runtime answer/output/evidence/audit, routing mode, safe next step, role, effective permission, and an expanded document/page/chunk citation | PASS | `01-question-answer-sources.png` |
| Permissions/policy | target user, Reader grant, purpose, concrete validity values, and explicit Full/Aggregate/Metadata/Deny resolution matrix | PASS | `03-permissions-policy.png` |
| Actions/evidence | OPEN, CLOSED_COMPLETED and SUPERSEDED engine results, primary/contextual/contrastive roles, browser-only non-action result, thread/evidence IDs and audit/correction trace | PASS | `04-actions-evidence.png` |

`backend_python/tests/test_reviewer_contracts.py` deterministically verifies the
four screen IDs, required field markers, accessible action labels,
lifecycle/policy/evidence API wiring, audit-ID response contract, exact-object
support guard, and uniqueness of HTTP method/path pairs.

`evaluation/reviewer_demo_seed.py` extracts the focused Assistant evidence from
an actual local W2 API trace and runs the real deterministic action-closure
engine for the Actions seed. It copies no authentication token or local path.
Generated seed, PNG, and screenshot-manifest files are ignored under
`artifacts/reviewer_screenshots/`; they must not be committed. Reproduction and
review mapping are in `REVIEWER_SCREENSHOT_GUIDE.md`.
