# Reviewer screenshot guide

Status: `DETERMINISTIC_LOCAL_CAPTURE`

This guide covers the four reviewer-minimum screens only. The seed contains
synthetic device and evidence data. Assistant content is copied without manual
editing from a successful local W2 API workflow using the deterministic
provider. Actions are reconstructed by the versioned local action-closure
engine. The seed contains no bearer token, password, private address, absolute
path, MailEx text, provider result, or health scenario.

## Review mapping

| Screen | Reviewer question answered | Visible evidence |
|---|---|---|
| Question / Answer / Sources | Review A and Review C | Complete focused question, answer, `FULL_ANSWER`, evidence decision, audit ID, safe next step, `KEYWORD_ROUTING`, source roles, effective `full` use, and expanded document/page/chunk citations. |
| Document / Data Store | Review A | UUID, SHA-256, processing/source state, page/chunk counts, keyword provenance, visibility, source/policy/re-index/archive/restore controls, and accessible control labels. |
| Permissions / Policy | Review C | Document, target user, Reader permission, purpose, concrete valid-from/until values, selected Full decision and Full/Aggregate/Metadata/Deny resolution matrix. |
| Actions / Evidence | Review D | OPEN, CLOSED_COMPLETED and SUPERSEDED results, primary and contrastive evidence, browser-only contextual evidence with zero false action, thread/evidence IDs, engine version, and audit/correction indicator. |

## Reproduction

First run the isolated API workflow as documented in
`API_END_TO_END_WORKFLOWS.md`. Then, from the repository root, generate the
ignored seed (substitute the selected successful trace directory):

```powershell
python .\scripts\generate_reviewer_demo_seed.py `
  --trace .\artifacts\api_workflows\<run>\api_workflow_trace.jsonl `
  --output .\artifacts\reviewer_screenshots\pre_freeze_hardening\demo_seed.json
python .\scripts\serve_reviewer_capture.py --port 8766
```

Open this local-only URL with the existing browser tooling:

```text
http://127.0.0.1:8766/frontend/index.html?reviewer_demo=/artifacts/reviewer_screenshots/pre_freeze_hardening/demo_seed.json
```

Capture the Assistant screen as loaded, then select Documents, Permissions,
and Actions & Evidence and capture each screen. The capture server emits a
Content Security Policy that allows localhost resources only, so the legacy CDN
tags cannot issue external requests; the scoped local evidence stylesheet keeps
the four screens reproducible. Record the viewport, dimensions, SHA-256, exact commit,
demo-seed version, timestamp, privacy-safe flag, DOM-text no-health scan, and
capture command in `screenshot_manifest.json` in the same ignored directory.

Expected logical filenames:

- `01-question-answer-sources.png`
- `02-document-data-store.png`
- `03-permissions-policy.png`
- `04-actions-evidence.png`

## Known limitations

- The screenshot seed is local evidence mode and cannot mutate API state.
- The Assistant evidence is an actual deterministic local API response, not a
  real network-provider response.
- Browser-only contextual evidence is intentionally prevented from creating an
  action.
- Screenshots are review artifacts, not tracked source and not a substitute for
  pending human screenshot acceptance.
