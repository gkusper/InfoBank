# R1A Runtime Foundation Integration Report

## Identification

- Date: 2026-08-19
- Repository: `<repository-root>`
- Current branch: `integration/main-rebuild-2026-08`
- Starting commit: `e9dc92b903b36de31e267993671d8f31d3a176ea`
- Donor branch: `origin/d1-d8-end-to-end-pilot`
- Donor commit: `e6a3cd032a3e431899bda56632ffc1389b636f15`
- Overall result: **PASS**

No branch switch, merge, branch deletion, pull request, history rewrite, destructive Git command, destructive Docker command, or Docker volume deletion was performed. No commit or push had been performed at the time of the validation.

## Included foundation files

The reusable runtime/configuration/schema integration includes:

- `.gitignore`
- `docker-compose.yml`
- `backend_python/.env.example`
- `backend_python/.env.eval.example`
- `backend_python/ai_service.py`
- `backend_python/evidence_service.py`
- `backend_python/routers/evidence.py`
- `backend_python/requirements.txt`
- `backend_python/requirements-lock.txt`
- `infobank_db.sql`
- `docs/integration/R1A_RUNTIME_FOUNDATION_REPORT.md`

The restored runtime source, schema, compose file, and example environment files match the donor versions except for the intentional direct-dependency cleanup, the `bcrypt==4.0.1` compatibility correction, placeholder hardening in `.env.example`, and local-environment ignore hardening. The lock and this report are newly generated integration artifacts.

## Deliberately excluded donor material

The following research/evaluation-specific donor paths were not integrated:

- `data/benchmarks/evidence_unit_v1/**`
- `evaluation/**`, including fixtures, runners, test suites, frozen/generated results, database preparation, scoring, and reproduction tooling
- `scripts/mailex/**`
- `docs/evaluation/**`
- `docs/d1_d8_end_to_end_pilot_report.md`
- `docs/mailex_d1_d8_preparation_report.md`
- donor-specific `README.md` changes

No research-specific evaluation data, evaluation dataset, frozen result artifact, publication output, generated fixture, personal-data file, virtual environment, Chroma runtime database, cache, or runtime/configuration absolute local path was integrated. This report necessarily records the repository path and exact commands for traceability. Credential-shaped-value scanning found no secret. Local `.env` files were identified by filename only and their contents were not read or displayed.

## Dependency review

`backend_python/requirements.txt` contains 18 explicitly pinned direct runtime dependencies plus the explicit `numpy==1.26.4` Chroma 0.4.x compatibility pin. It is not a full-machine `pip freeze`.

- `chromadb==0.4.24` declares `bcrypt >=4.0.1`.
- `bcrypt==4.0.1` satisfies Chroma and successfully hashes/verifies through passlib 1.7.4.
- No Gemini import, `google-generativeai` dependency, or Gemini package remains in the R1A environment.
- `google-auth`, `google-auth-oauthlib`, and `google-api-python-client` remain because `gmail_connector.py` uses Google OAuth credentials, OAuth flow, and the Gmail API client.
- Python 3.12.0 dry-run resolution reported every direct requirement already satisfied, and `pip check` reported no broken requirements.
- `backend_python/requirements-lock.txt` is the exact output of `.venv_r1a` `pip freeze --all` on 2026-08-19; a `Compare-Object` check returned `REQUIREMENTS_LOCK_MATCH`.

## Runtime and configuration review

- OpenAI client creation is lazy, allowing startup/import without an API key; OpenAI-backed operations still fail clearly when the key is absent.
- Chroma persistence can be configured with `CHROMA_PERSIST_DIR`.
- The evidence import router supports both Pydantic v1 (`dict`) and v2 (`model_dump`) serialization.
- The imported evidence/policy code is application runtime code. No evaluation harness, benchmark dataset, frozen output, or publication artifact is included.
- `.gitignore` now covers `.venv*`, `venv`, `.env`, `.env.eval`, Python caches, pip cache, Chroma runtime data, and generated evaluation result/fixture paths.
- Both `.env.example` files contain placeholders or local non-secret URLs only. The previous concrete development database password in `.env.example` was replaced with `replace-with-local-db-password`.

## Database and schema review

The SQL and SQLAlchemy declarations agree for the R1A runtime tables:

| Table | Result | Notes |
|---|---|---|
| `evidence_units` | PASS | `VARCHAR(36)` IDs/user IDs, source enum values, nullable timestamps/metadata, user FK, and user/thread/relation indexes agree. |
| `policy_rules` | PASS | `VARCHAR(36)` ID/owner ID, target fields, purpose, `Full/Aggregate/Metadata/Deny` enum, validity fields, owner FK, and owner/target indexes agree. |
| `connector_accounts` | PASS | ID/user lengths, provider/status, token/metadata text, timestamps, user FK, and user/provider indexes agree. |
| `audit_logs` | PASS with follow-up | String lengths, nullability, timestamp, and indexes agree. `user_id` intentionally has no FK in both declarations. |
| UUID/string compatibility | PASS | Runtime UUIDs are serialized as strings into compatible `VARCHAR(36)` columns. Audit IDs use `VARCHAR(50)` consistently. |
| Enum compatibility | PASS | Evidence-source and policy-access enum names/values match the SQL enum literals. |

Known non-blocking schema follow-up: `infobank_db.sql` has `UNIQUE(user_id, document_id)` on `user_document_permission`, while `models.py` does not declare the equivalent SQLAlchemy `UniqueConstraint`. This predates the current R1A diff and was not changed because it is not a blocking runtime-foundation issue.

Permission-hardening follow-up: `Metadata` is both a persistent `PermissionType` and a query-time `PolicyAccessMode`. The current resolver distinguishes these through separate model fields/types, but the duplicated label needs an explicit semantic/security review later. No permission-model redesign was made in R1A.

## Validation results

| Check | Result | Evidence |
|---|---|---|
| Branch is `integration/main-rebuild-2026-08` | PASS | `git branch --show-current` |
| Starting commit captured | PASS | `e9dc92b903b36de31e267993671d8f31d3a176ea` |
| Full diff and untracked-file review | PASS | Only reusable runtime/config/schema/lock/report paths are present. |
| `git diff --check` | PASS | No output. |
| Forbidden research/generated/runtime data | PASS | No such tracked or untracked path is included. |
| Secret/personal-data/absolute-path scan | PASS | No credential-shaped value or runtime/configuration absolute local path; false-positive regex hits were Python raw-regex strings only. The report contains the required repository/command paths. |
| `.gitignore` coverage | PASS | `git check-ignore --no-index` passed for `.venv_r1a`, `.venv_eval`, `venv`, `.env`, `.env.eval`, pip cache, both Chroma paths, and generated evaluation paths. |
| `.env.example` placeholder review | PASS | Concrete development DB password removed; secrets are empty or explicit placeholders. |
| Direct dependency review | PASS | 18 pinned direct runtime dependencies plus NumPy compatibility pin; no uncontrolled freeze. |
| Python version | PASS | Python 3.12.0. |
| Requirements dry run | PASS | All requirements already satisfied on Python 3.12. |
| `pip check` | PASS | `No broken requirements found.` |
| `python -m compileall backend_python` | PASS | Exit code 0. The exact requested command also traversed ignored local virtual environments. |
| Chroma import/version | PASS | `0.4.24`. |
| passlib/bcrypt hash and verify | PASS | `PASSLIB_BCRYPT_OK 4.0.1`. |
| `ai_service`, `evidence_service`, `routers.evidence` imports | PASS | `R1A_IMPORT_OK`. |
| Gemini source/dependency search | PASS | No matches; no Gemini package in `.venv_r1a`. |
| Gmail Google dependency justification | PASS | Active imports in `gmail_connector.py`. |
| SQL/model/evidence/policy consistency | PASS with follow-ups | Runtime table fields, enums, FKs, and indexes agree; follow-ups documented above. |
| `requirements-lock.txt` generation/equality | PASS | Exact `.venv_r1a` `pip freeze --all`; equality check passed. |
| Docker availability and Compose | PASS | Docker became available for the completed smoke validation. |
| Docker/MariaDB startup | PASS | MariaDB started successfully; no Docker volume was deleted. |
| FastAPI `/api/test-db` | PASS | `status=success`, `users_in_db=0`. |
| FastAPI `/docs` | PASS | HTTP 200. |
| FastAPI `/openapi.json` | PASS | HTTP 200. |

The Chroma import smoke emitted these known non-blocking warnings:

```text
Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
Failed to send telemetry event ClientCreateCollectionEvent: capture() takes 1 positional argument but 3 were given
```

Both warnings occurred before `R1A_IMPORT_OK` and did not affect application behavior in the smoke test.

The Docker/MariaDB and API smoke validation completed successfully. The database volume was preserved; no Docker volume was deleted.

## Commands executed

All substantive commands executed during this R1A check are recorded below. Output-label-only `Write-Output` wrappers are omitted; no destructive command was run.

```powershell
rg --files -g AGENTS.md -g '!backend_python/.venv_r1a/**' -g '!backend_python/.venv/**' <repository-root>
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
git diff --stat
git ls-files --others --exclude-standard
git diff --name-status
git rev-parse origin/d1-d8-end-to-end-pilot
Get-ChildItem -LiteralPath .\backend_python -Force -File -Filter '.env*'
git diff --no-ext-diff -- .gitignore backend_python/requirements.txt
Get-Content -LiteralPath .\backend_python\.env.example
Get-Content -LiteralPath .\backend_python\.env.eval.example
Get-Content -LiteralPath .\docker-compose.yml
git diff --no-ext-diff -- backend_python/ai_service.py backend_python/evidence_service.py backend_python/routers/evidence.py
git diff --no-ext-diff -- infobank_db.sql
rg -n -i --glob '!backend_python/.venv*/**' --glob '!backend_python/__pycache__/**' --glob '!backend_python/chroma*/**' --glob '!evaluation/**' 'google\.generativeai|google-generativeai|from\s+google\s+import\s+genai|google\.genai|gemini' backend_python .gitignore docker-compose.yml infobank_db.sql
rg -n --glob '!backend_python/.venv*/**' --glob '!backend_python/__pycache__/**' 'google_auth_oauthlib|googleapiclient|google\.oauth2|google\.auth|gmail' backend_python
rg -n -A 35 -B 5 'class (EvidenceUnit|PolicyRule|ConnectorAccount|AuditLog|UserDocumentPermission)|EvidenceSourceType|PermissionType|AccessMode' backend_python/models.py backend_python/policy_engine.py backend_python/evidence_service.py backend_python/routers/evidence.py
git diff --quiet origin/d1-d8-end-to-end-pilot -- <each included donor path>
git diff --name-only HEAD origin/d1-d8-end-to-end-pilot
git diff --name-status HEAD origin/d1-d8-end-to-end-pilot
git hash-object -- <each included donor path>
git rev-parse origin/d1-d8-end-to-end-pilot:<each included donor path>
git diff origin/d1-d8-end-to-end-pilot -- backend_python/requirements.txt
Get-ChildItem -LiteralPath .\backend_python -Force -Directory
git check-ignore -v -- <each local environment/runtime path>
git ls-files | rg -i '(^|/)(\.env($|\.)|\.venv|venv|__pycache__|chroma_data|chroma_eval|\.pip-cache|evaluation/results|evaluation/generated_fixtures|\.pytest_cache|\.mypy_cache|node_modules)(/|$)|\.(pyc|pyo|sqlite3|db)$'
git diff -U0 -- . ':!*.lock' | rg -n '^[+]([^+]|$).*(?:[A-Za-z]:\\|C:/|Users\\|Users/)'
rg -l -i '<credential-shaped-value patterns>' <changed-and-new-files>
& .\backend_python\.venv_r1a\Scripts\python.exe --version
& .\backend_python\.venv_r1a\Scripts\python.exe -m pip --version
& .\backend_python\.venv_r1a\Scripts\python.exe -m pip check
Get-Content -LiteralPath .\backend_python\.venv_r1a\pyvenv.cfg
Get-Item -LiteralPath .\backend_python\.venv_r1a\Scripts\python.exe
Test-Path -LiteralPath C:\Users\Lenar\AppData\Local\Programs\Python\Python312\python.exe -PathType Leaf
Get-Command py -ErrorAction SilentlyContinue
& .\backend_python\.venv_r1a\Scripts\python.exe -m compileall backend_python
& .\.venv_r1a\Scripts\python.exe -c 'import chromadb; print(chromadb.__version__)'
& .\.venv_r1a\Scripts\python.exe -c 'import bcrypt; from passlib.context import CryptContext; ctx=CryptContext(schemes=["bcrypt"], deprecated="auto"); hashed=ctx.hash("r1a-smoke"); assert ctx.verify("r1a-smoke", hashed); print("PASSLIB_BCRYPT_OK", bcrypt.__version__)'
$env:CHROMA_PERSIST_DIR='.\chroma_eval'; & .\.venv_r1a\Scripts\python.exe -c 'import ai_service, evidence_service, routers.evidence; print("R1A_IMPORT_OK")'
docker version
docker info
docker compose ps
Test-Path -LiteralPath 'C:\Program Files\Docker\Docker\resources\bin\docker.exe' -PathType Leaf
Test-Path -LiteralPath 'C:\Program Files\Docker\Docker\resources\bin\com.docker.cli.exe' -PathType Leaf
& .\backend_python\.venv_r1a\Scripts\python.exe -m pip install --dry-run -r .\backend_python\requirements.txt
& .\backend_python\.venv_r1a\Scripts\python.exe -m pip freeze --all | rg -i 'gemini|generative'
& .\backend_python\.venv_r1a\Scripts\python.exe -c 'from importlib.metadata import requires; print([item for item in (requires("chromadb") or []) if item.lower().startswith("bcrypt")])'
& .\backend_python\.venv_r1a\Scripts\python.exe -m pip freeze --all
Test-Path -LiteralPath .\docs\integration -PathType Container
$env:CHROMA_PERSIST_DIR='.\backend_python\chroma_eval'; & .\backend_python\.venv_r1a\Scripts\python.exe -c '<SQLAlchemy table/column/FK/index introspection>'
rg -n -C 4 'create_all|infobank_db\.sql|Base\.metadata|init_db' backend_python docker-compose.yml README.md
rg -n -C 3 'UserDocumentPermission|user_document_permission|permission_type' backend_python --glob '!backend_python/.venv*/**' --glob '!backend_python/venv/**'
New-Item -ItemType Directory -Path .\docs\integration -Force
Compare-Object -ReferenceObject (& .\backend_python\.venv_r1a\Scripts\python.exe -m pip freeze --all) -DifferenceObject (Get-Content .\backend_python\requirements-lock.txt)
git check-ignore -v --no-index -- <each local environment/runtime probe path>
rg -n 'replace-with|<password>|=$|127\.0\.0\.1|localhost' backend_python/.env.example backend_python/.env.eval.example
rg -n -i --glob '!backend_python/.venv*/**' --glob '!backend_python/venv/**' --glob '!backend_python/__pycache__/**' 'google\.generativeai|google-generativeai|from\s+google\s+import\s+genai|google\.genai|gemini' backend_python
& .\backend_python\.venv_r1a\Scripts\python.exe -m pip check
& .\backend_python\.venv_r1a\Scripts\python.exe -c 'import chromadb; assert chromadb.__version__ == "0.4.24"; print("CHROMA_OK", chromadb.__version__)'
& .\backend_python\.venv_r1a\Scripts\python.exe -c '<final passlib/bcrypt hash-and-verify smoke>'
$env:CHROMA_PERSIST_DIR='.\chroma_eval'; & .\.venv_r1a\Scripts\python.exe -c 'import ai_service, evidence_service, routers.evidence; print("R1A_IMPORT_OK")'
Compare-Object -ReferenceObject (& .\backend_python\.venv_r1a\Scripts\python.exe -m pip freeze --all) -DifferenceObject (Get-Content .\backend_python\requirements-lock.txt)
git status --short
git diff --check
git diff --stat
$ignorePath=(Resolve-Path .\.gitignore).Path; $ignoreText=[IO.File]::ReadAllText($ignorePath); $ignoreText=[Text.RegularExpressions.Regex]::Replace($ignoreText,'\r?\n',"`r`n"); [IO.File]::WriteAllText($ignorePath,$ignoreText,[Text.UTF8Encoding]::new($false))
git status --short
git diff --check
git diff --stat
```

The first sandboxed attempts to execute `.venv_r1a` failed because its base Python is under the user profile. The same commands were immediately rerun with approved external execution and passed; this was an execution-sandbox limitation, not a virtual-environment failure.

The report/lock/configuration files were created or updated with patch-based file edits. Final verification commands are listed in the final-state section below.

## Completed Docker and API smoke

The completed smoke validation reported:

| Check | Result | Observed result |
|---|---|---|
| Docker/MariaDB startup | PASS | MariaDB started successfully. |
| `/api/test-db` | PASS | `status=success`, `users_in_db=0` |
| `/docs` | PASS | HTTP 200 |
| `/openapi.json` | PASS | HTTP 200 |
| Docker volume preservation | PASS | No Docker volume was deleted. |

## Known follow-up issues

1. Review and align the SQL-only `user_document_permission(user_id, document_id)` uniqueness constraint with SQLAlchemy metadata in a separately scoped schema-hardening change.
2. Perform a permission-hardening review of the persistent `Metadata` permission versus query-time `Metadata` semantics without changing R1A semantics.
3. Investigate or disable the non-blocking Chroma/PostHog telemetry mismatch in a separate dependency-maintenance task.
4. Encrypt `connector_accounts.token_json` or move tokens to a secrets vault before production deployment.

GitHub CI and branch protection are deferred by agreement with GĂˇbor. No GitHub Actions workflow was added.

No commit or push had been performed at the time of the validation.

## Final repository state

Exact `git status --short`:

```text
 M .gitignore
 M backend_python/ai_service.py
 M backend_python/evidence_service.py
 M backend_python/requirements.txt
 M backend_python/routers/evidence.py
 M infobank_db.sql
?? backend_python/.env.eval.example
?? backend_python/.env.example
?? backend_python/requirements-lock.txt
?? docker-compose.yml
?? docs/integration/
```

Exact `git diff --check`:

```text
```

Exact `git diff --stat`:

```text
 .gitignore                         |  13 ++-
 backend_python/ai_service.py       |  30 ++++++-
 backend_python/evidence_service.py | 178 +++++++++++++++++++++++++++++++++----
 backend_python/requirements.txt    |  38 ++++----
 backend_python/routers/evidence.py |   8 +-
 infobank_db.sql                    |  79 ++++++++++++++--
 6 files changed, 298 insertions(+), 48 deletions(-)
```
