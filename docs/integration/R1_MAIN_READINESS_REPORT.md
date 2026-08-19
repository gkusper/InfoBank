# R1 Main Readiness Report

## Decision

**READY_FOR_MAIN**

Date: 2026-08-19

Branch assessed: `integration/main-rebuild-2026-08`

Exact assessed base HEAD: `f432112c850c0637f3465db6b887753b4d34237a`

This assessment reports technical readiness of the exact 22-file R1B change set after it becomes a commit. It does not claim that `main` has already been updated, and it does not perform or authorize a merge, commit, push, pull request, release-branch creation, or branch deletion.

## Readiness conditions

| Condition | Result | Evidence |
|---|---|---|
| R1A foundation | PASS | Committed R1A at assessed HEAD; R1A report status PASS |
| R1B local quality gate | PASS | Exit 0; 35 passed, 0 failed, 0 skipped |
| Docker/MariaDB/API smoke | PASS | MariaDB healthy; DB success with zero users; docs/OpenAPI HTTP 200 |
| Dependency resolution | PASS | Dev install and `pip check`; production requirements unchanged |
| Reproducible dependency capture | PASS | Production lock retained; dev lock exactly matches `pip freeze --all` |
| Secret handling | PASS | No real `.env` content inspected or displayed; no secret integrated; provider calls mocked/avoided |
| Research separation | PASS | No dataset, fixture, frozen/publication result, MailEx, or WoLaLa artifact integrated |
| Reproducible local command | PASS | `scripts/run_local_quality_gate.ps1` with optional `-SkipDocker` |
| Machine-readable result | PASS | Ignored `artifacts/local_quality_gate/latest.json` |
| Expected working-tree scope | PASS | Only documented R1B files are modified/new; no unexpected path |
| Schema/permission follow-ups documented | PASS | SQL-only UNIQUE and Metadata semantic distinction recorded |
| GitHub workflow requirement | NOT_APPLICABLE | GitHub CI and branch protection are deferred by agreement with Gábor |

## Non-blocking warnings

1. Known Chroma telemetry warnings do not affect import or runtime smoke behavior.
2. Existing naive UTC defaults/time capture produce Python deprecation warnings.
3. `user_document_permission` uniqueness is declared only in SQL, not SQLAlchemy metadata.
4. Persistent `Metadata` permission and query-time `Metadata` decision require later semantic hardening.
5. Gmail connector token storage requires production security hardening.

## Scope boundary

The common foundation contains generic runtime, tests, quality-gate tooling, implementation scope, and provider-neutral evaluation records only. It contains no research-specific evaluation data or frozen result artifact and makes no claim that reviewer evaluation is complete.

No commit or push was performed during R1B.

## Recommended next step

Accept R1B, then begin **A-GATE: metadata / keyword / chunking / durable source / page citation gap closure** on the existing integration branch under a separately approved task. Do not create `release/infocom-2026` yet.
