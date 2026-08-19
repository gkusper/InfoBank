# R1B Test and Evaluation Foundation Report

## Identification

- Date: 2026-08-19
- Branch: `integration/main-rebuild-2026-08`
- Starting local HEAD: `f432112c850c0637f3465db6b887753b4d34237a`
- Starting remote branch HEAD after fetch: `f432112c850c0637f3465db6b887753b4d34237a`
- R1A commit: `f432112c850c0637f3465db6b887753b4d34237a`
- R1B result: **PASS**
- Quality-gate schema: `r1b-local-quality-gate-v1`

The initial working tree was clean. `git fetch --all --prune` and `git pull --ff-only` completed non-destructively and reported that the branch was already up to date. No branch switch, merge, release branch, pull request, history rewrite, commit, or push was performed.

## Donor refs inspected

- `origin/d1-d8-end-to-end-pilot` at `e6a3cd032a3e431899bda56632ffc1389b636f15`
- `origin/d1-d8-large-scale-final-evaluation` at `5bb2cc742e105cc3238b022130126947c04bcd35`

The ten requested candidate files had identical blobs on both refs. Detailed purpose, dependency, fixture coupling, classification, reason, and destination are recorded in `docs/integration/R1B_EVALUATION_TOOLING_INVENTORY.md`.

Refactored concepts reused:

- repository/backend path resolution;
- exact Git identity capture;
- deterministic dataclass serialization;
- manifest/checksum helpers;
- provider-neutral usage accounting.

Kept research-only or rejected:

- fixture schema and fixture loading;
- paper-specific standard/governance/role-aware runners;
- complete suite orchestration;
- live OpenAI/Chroma evaluation retrieval;
- D1-D8 harness tests and raw fixture-like content.

## Files created or modified

Modified runtime/foundation files:

- `.gitignore`
- `backend_python/ai_service.py`
- `backend_python/policy_engine.py`

Created dependency and test files:

- `backend_python/requirements-dev.txt`
- `backend_python/requirements-dev-lock.txt`
- `backend_python/tests/conftest.py`
- `backend_python/tests/test_runtime_and_chunking.py`
- `backend_python/tests/test_policy_invariants.py`
- `backend_python/tests/test_evidence_invariants.py`
- `backend_python/tests/test_schema_contract.py`

Created generic evaluation-core files:

- `evaluation/__init__.py`
- `evaluation/backend.py`
- `evaluation/schemas.py`
- `evaluation/manifest.py`
- `evaluation/usage_logging.py`
- `evaluation/tests/test_evaluation_core.py`

Created quality-gate and documentation files:

- `scripts/run_api_smoke.ps1`
- `scripts/run_local_quality_gate.ps1`
- `docs/integration/IMPLEMENTATION_SCOPE.csv`
- `docs/integration/R1B_EVALUATION_TOOLING_INVENTORY.md`
- `docs/integration/R1B_TEST_AND_EVALUATION_FOUNDATION_REPORT.md`
- `docs/integration/R1_MAIN_READINESS_REPORT.md`

Generated local evidence is written under `artifacts/local_quality_gate/` and is ignored by Git.

## Minimal runtime changes

1. `ai_service.chunk_text` now rejects non-positive chunk sizes, negative overlap, and `overlap >= chunk_size`, preventing a non-progressing infinite loop.
2. Document and EvidenceUnit bulk policy resolution now iterates over `sorted(set(ids))`, making maps and ID lists deterministic without changing access semantics.

No permission semantic redesign was made.

## Dependency changes

Production `backend_python/requirements.txt` is unchanged.

`backend_python/requirements-dev.txt` contains:

```text
-r requirements.txt
pytest==8.3.5
```

The dev lock was generated from the existing ignored Python 3.12 `.venv_r1a` environment after installing the pinned dev dependency. The only new test stack packages are `pytest==8.3.5`, `iniconfig==2.3.0`, and `pluggy==1.6.0`; other entries are the already validated R1A runtime environment. `pip freeze --all` and `requirements-dev-lock.txt` match exactly.

## Tests added

| Test group | Passed | Failed | Skipped | Scope |
|---|---:|---:|---:|---|
| Runtime/configuration | 4 | 0 | 0 | No-key import, lazy missing-key failure, deterministic paths, no Gemini |
| Chunking | 7 | 0 | 0 | Defaults, overlap, ordering, losslessness, short/empty input, invalid progress |
| Policy invariants | 9 | 0 | 0 | Missing/Owner/Reader/Aggregate/Metadata/private/Deny/purpose/time/bulk determinism |
| Evidence invariants | 5 | 0 | 0 | Browser-only, primary/context, linked closure, unrelated/earlier closure, idempotency |
| Schema/runtime contract | 4 | 0 | 0 | Tables, enums, lengths/FKs, known SQL-only UNIQUE mismatch |
| Generic evaluation core | 6 | 0 | 0 | Serialization, hashes, required fields/modes, sanitization, frozen output, usage merge |
| **Total pytest** | **35** | **0** | **0** | |
| Docker/MariaDB/API smoke | 4 endpoint/service checks | 0 | 0 | MariaDB health, DB endpoint, docs, OpenAPI |

All automated tests use isolated SQLite data or temporary Chroma paths. No real OpenAI or Gmail call was made. No health-related data or health-related scenario was added.

## Generic evaluation core

The R1B core provides infrastructure only:

- versioned `RunManifest` with run, Git, dataset, scorer, config, provider/model, Python, database target, and Chroma fields;
- provider-neutral `RunRecord` with mode, retrieval IDs, generator-visible context hash, output/reason, latency, optional tokens, error, and metrics;
- deterministic canonical JSON/JSONL serialization;
- secret and protected-content redaction by default, with an explicit local debug flag for protected content only;
- SHA-256 helpers for files and stable objects;
- exact commit and branch capture;
- versioned output-directory creation and frozen-output overwrite protection;
- generic labels `B0_VECTOR_ONLY`, `B1_VECTOR_ROUTING`, `B2_PERMISSION_FILTERED`, and `B3_FULL_ROLE_AWARE`.

No B0-B3 retrieval/generation pipeline, reviewer dataset, scorer, or result is implemented or claimed in R1B.

## Quality gate

Canonical command from repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1
```

Non-Docker-only command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1 -SkipDocker
```

Final successful machine-readable summary:

- status: `PASS`
- commit: `f432112c850c0637f3465db6b887753b4d34237a`
- elapsed: `20.045` seconds
- tests: 35 passed, 0 failed, 0 skipped
- `pip_check`: PASS, exit 0
- `compileall`: PASS, exit 0
- `pytest`: PASS, exit 0
- `import_smoke`: PASS, exit 0
- `docker_api_smoke`: PASS, exit 0
- MariaDB: healthy
- `/api/test-db`: `status=success`, `users_in_db=0`
- `/docs`: HTTP 200
- `/openapi.json`: HTTP 200
- Docker volume deleted: false

## Exact validation commands

```powershell
git branch --show-current
git rev-parse HEAD
git rev-parse '@{u}'
git status --short
git log -3 --oneline
git diff
git rev-list --left-right --count HEAD...origin/main
git rev-list --left-right --count HEAD...origin/d1-d8-end-to-end-pilot
git merge-base HEAD origin/main
git merge-base HEAD origin/d1-d8-end-to-end-pilot
git fetch --all --prune
git pull --ff-only
git ls-tree <donor-ref> -- <candidate-path>
git show <donor-ref>:<candidate-path>
backend_python\.venv_r1a\Scripts\python.exe -m pip install --dry-run -r backend_python\requirements-dev.txt
backend_python\.venv_r1a\Scripts\python.exe -m pip install -r backend_python\requirements-dev.txt
backend_python\.venv_r1a\Scripts\python.exe -m pip check
backend_python\.venv_r1a\Scripts\python.exe -m pip freeze --all
backend_python\.venv_r1a\Scripts\python.exe -m pytest backend_python/tests evaluation/tests -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1 -SkipDocker
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1
git diff --check
git diff --stat
```

## Validation table

| Check | Result | Evidence |
|---|---|---|
| Initial branch and clean worktree | PASS | Expected branch; empty initial status and diff |
| Local/remote synchronization | PASS | Same local/upstream HEAD; already up to date |
| R1A presence | PASS | HEAD is the committed R1A integration |
| Donor candidate inspection | PASS | Both requested refs and all ten files classified |
| Mandatory donor exclusions | PASS | No benchmark, fixture, frozen/publication result, MailEx, or WoLaLa path integrated |
| Production dependency separation | PASS | Production requirements unchanged |
| Dev dependency dry run/install | PASS | Python 3.12; pinned pytest installed in ignored environment |
| `pip check` | PASS | No broken requirements |
| Dev lock equality | PASS | Exact `pip freeze --all` match |
| Runtime/config tests | PASS | 4/4 |
| Chunking tests | PASS | 7/7 |
| Policy tests | PASS | 9/9 |
| Evidence tests | PASS | 5/5 |
| Schema contract tests | PASS | 4/4 |
| Evaluation-core tests | PASS | 6/6 |
| Compileall | PASS | Exit 0 for backend and evaluation core |
| Import smoke | PASS | `R1B_IMPORT_OK`; no provider calls |
| Docker/MariaDB startup | PASS | MariaDB healthy; existing volume preserved |
| `/api/test-db` | PASS | `status=success`, `users_in_db=0` |
| `/docs` | PASS | HTTP 200 |
| `/openapi.json` | PASS | HTTP 200 |
| Scope matrix | PASS | 44 capabilities, all required columns/status values |
| Secret/research/workflow audit | PASS | No secret, research result, or GitHub Actions workflow added |
| Local quality gate | PASS | Exit 0, machine-readable summary written to ignored artifact path |

## Warnings and known gaps

- Chroma 0.4.24 emits the two known non-blocking telemetry warnings during import; `R1B_IMPORT_OK` follows them.
- The policy tests emit ten non-blocking Python deprecation warnings from existing naive `datetime.datetime.utcnow()` defaults and policy time capture.
- `user_document_permission` has SQL `UNIQUE(user_id, document_id)` without an equivalent SQLAlchemy `UniqueConstraint`.
- Persistent `Metadata` permission and query-time `Metadata` decision remain distinct concepts requiring later semantic hardening.
- Gmail connector token storage requires production encryption or a secrets vault.
- B0-B3 pipelines, datasets, scorers, stress runs, provider migration, and frontend redesign remain future milestones.

GitHub CI and branch protection remain deferred by agreement with Gábor. No `.github/workflows` file was added.

No research dataset, frozen result, publication artifact, MailEx record, or WoLaLa artifact was integrated.

No commit or push was performed.

## Next milestone

After R1B acceptance, the exact next milestone is **A-GATE: metadata / keyword / chunking / durable source / page citation gap closure**. R1B does not begin that implementation.
