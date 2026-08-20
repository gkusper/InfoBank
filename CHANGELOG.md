# Changelog

This file records development milestones; no entry is a final release.

## Pre-freeze hardening — unreleased

- `384c35c`: aligned permission/no-match controlled-failure semantics, safe public payloads, W3 revoke behavior and complete local MailEx reconciliation.
- `430fdc3`: added deterministic actual-W2 reviewer seed, accessible reviewer controls, local-only capture styling/CSP server, screenshot guide and contract tests. Screenshot binaries remain ignored.
- Added pre-freeze manuals, backup/restore/rollback/orphan smoke tooling and pending-only human-QA preparation/validation tools.
- Added manifest-driven full E1 estimate-only planning for one, two and three
  B0-B3 repeats plus a separately reported optional scale subset, without a
  provider call.

Earlier A/C/D-gate, actual-pipeline, MailEx candidate and API workflow commits
remain described in `docs/integration/FACTS_FOR_AUTHORS.md` and the integration
reports. Human QA, MailEx licence, freeze, final E1 and release remain pending.
