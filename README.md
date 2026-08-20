# InfoBank

InfoBank is a governed, citation-bearing document assistant and evidence/action
prototype. This branch is a pre-freeze technical workstream, not a release.

## Local quick start

Supported runtime: Python 3.11. Docker Desktop with Docker Compose and MariaDB
is required for the integrated runtime.

```powershell
docker compose up -d db
py -3.11 -m venv backend_python\.venv_r1a
backend_python\.venv_r1a\Scripts\python.exe -m pip install -r backend_python\requirements-dev-lock.txt
Copy-Item backend_python\.env.example backend_python\.env
backend_python\.venv_r1a\Scripts\python.exe -m uvicorn main:app --app-dir backend_python --host 127.0.0.1 --port 8000
```

In another terminal, serve the frontend with `python -m http.server 8765` and
open `http://127.0.0.1:8765/frontend/`. Required environment-variable names are
`DATABASE_URL`, `JWT_SECRET_KEY`, `AI_PROVIDER`, `CHROMA_PERSIST_DIR`,
`SOURCE_STORAGE_DIR`, and `AGGREGATE_K_THRESHOLD`. Provider-backed operation
also needs provider-specific model names and `OPENAI_API_KEY`; never commit
values or a real `.env`. The deterministic provider needs no network key.

## Deterministic demos and quality gates

```powershell
# One-command start after the one-time venv/.env setup:
powershell -NoProfile -Command "docker compose up -d db; & backend_python\.venv_r1a\Scripts\python.exe -m uvicorn main:app --app-dir backend_python --host 127.0.0.1 --port 8000"
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_api_end_to_end_workflows.py --help
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1 -SkipDocker
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1
```

The API workflow command requires an isolated database whose name starts with
`infobank_eval_`, plus task-owned Chroma, source-store, and output directories;
the exact reproducible command is in `docs/REPRODUCTION.md`.

`main` is the protected integration/release baseline. The current
`feature/infocom-cd-gates` branch contains reviewer and evaluation hardening and
must be reviewed before integration. Final E1, dataset/code/config freeze,
release branch, merge, tag, pull request, and release are **not authorized**.

See `docs/USER_MANUAL.md`, `docs/DEVELOPER_GUIDE.md`,
`docs/ADMIN_OPERATIONS.md`, and `docs/DATASET_AND_EVALUATION.md`. Project code
is under the repository `LICENSE`; the local MailEx source has the separate
state `LICENCE_PENDING_HUMAN_CONFIRMATION` and is not authorized for
redistribution.
