# Independent Reproduction Guide

This guide describes how another researcher can reproduce the current pre-pilot InfoBank state on Windows with PowerShell. Use your own OpenAI API key. Never send, print, or commit that key.

## 1. Clone and Check Out the Pre-Pilot State

```powershell
git clone https://github.com/hunti-ekke/InfoBank_LJ.git
Set-Location .\InfoBank_LJ
git fetch --all --tags
git checkout pre-pilot-v0.1
```

If the tag is not available yet, use the branch:

```powershell
git checkout evaluation-pilot
```

Check the commit:

```powershell
git rev-parse HEAD
```

The expected pre-pilot documentation commit is recorded in `docs/evaluation/STATUS.md`.

## 2. Start MariaDB

Install and start Docker Desktop first. Then start the repository MariaDB service:

```powershell
docker compose up -d db
docker compose ps
Test-NetConnection 127.0.0.1 -Port 3307
```

The normal development database is `infobank_db`. The evaluation database is separate and named `infobank_eval`.

## 3. Create a Python 3.12 Evaluation Environment

```powershell
py -3.12 -m venv backend_python\.venv_eval
.\backend_python\.venv_eval\Scripts\python.exe -m pip install --upgrade pip
.\backend_python\.venv_eval\Scripts\python.exe -m pip install -r backend_python\requirements.txt
.\backend_python\.venv_eval\Scripts\python.exe -m pip check
```

Expected dependency check:

```text
No broken requirements found.
```

## 4. Configure and Start the Backend

Create the normal backend environment file:

```powershell
Copy-Item backend_python\.env.example backend_python\.env
```

Edit `backend_python\.env` for your local setup. Do not commit it.

Start the backend:

```powershell
Set-Location .\backend_python
.\.venv_eval\Scripts\python.exe -m uvicorn main:app --reload
```

In a browser, check:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/test-db
```

`/docs` should load, and `/api/test-db` should return a JSON success response.

Return to the repository root in a second PowerShell window:

```powershell
Set-Location <repository root>
```

## 5. Serve the Frontend

```powershell
Set-Location .\frontend
python -m http.server 8080 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8080/index.html
```

## 6. Prepare the Evaluation Database

Create the isolated evaluation database and grant the existing local development DB user access to it. The command asks for the local MariaDB root password without storing it in Git:

```powershell
Set-Location <repository root>
$rootPassword = Read-Host "MariaDB root password"
Get-Content .\evaluation\prepare_eval_database.sql -Raw |
  docker compose exec -T -e MYSQL_PWD=$rootPassword db mariadb -u root
```

Initialize the `infobank_eval` schema from the tracked development schema without changing `infobank_db`:

```powershell
$schema = (Get-Content .\infobank_db.sql -Raw).Replace("infobank_db", "infobank_eval")
$schema |
  docker compose exec -T -e MYSQL_PWD=$rootPassword db mariadb -u root
Remove-Variable rootPassword
Remove-Variable schema
```

This procedure is idempotent where practical: it creates the database if missing and uses `CREATE TABLE IF NOT EXISTS` schema statements.

## 7. Configure Evaluation Runtime

Create the ignored evaluation environment file:

```powershell
Copy-Item backend_python\.env.eval.example backend_python\.env.eval
```

Edit `backend_python\.env.eval` so:

```text
DATABASE_URL points to infobank_eval
CHROMA_PERSIST_DIR=./chroma_eval
```

The runner resolves `./chroma_eval` from `backend_python/.env.eval` to `backend_python/chroma_eval`.

Do not put `OPENAI_API_KEY` in `.env.eval`.

## 8. Configure OpenAI API Access

Set your own API key in the Windows process environment. If you used `setx`, open a new PowerShell window before running the pilot.

Check key visibility without printing the key:

```powershell
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
  "OPENAI_API_KEY visible: NO"
} else {
  "OPENAI_API_KEY visible: YES"
}
```

## 9. Validate the Evaluation Harness and Fixtures

```powershell
.\backend_python\.venv_eval\Scripts\python.exe -m unittest discover -s evaluation\tests -v
.\backend_python\.venv_eval\Scripts\python.exe -m evaluation.validate_fixtures evaluation\fixtures\document_rag_v1.yaml
```

The fixture validator should print:

```text
VALIDATION: PASS
```

## 10. Run the Manual Pilot Preflight

```powershell
.\evaluation\run_document_rag_pilot.ps1 -CheckOnly
```

This verifies that:

- `DATABASE_URL` targets `infobank_eval`;
- `CHROMA_PERSIST_DIR` resolves to `backend_python/chroma_eval`;
- MariaDB is reachable;
- the isolated evaluation DB and Chroma store are clean.

If the state is not clean, reset or recreate the evaluation database and Chroma store before continuing.

## 11. Run the Seven-Case Real-API Pilot

```powershell
.\evaluation\run_document_rag_pilot.ps1
```

This runs exactly seven cases across three modes with one repetition:

```text
7 cases x 3 modes x 1 repetition = 21 result records
```

The real pilot uses:

- embedding model: `text-embedding-3-small`
- generator model: `gpt-4o-mini`
- temperature: `0.0`
- retrieval top-k: `4`

## 12. Find and Inspect Result Artifacts

Find the latest result directory:

```powershell
$latest = Get-ChildItem .\evaluation\results -Directory |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
$latest.FullName
Get-ChildItem $latest.FullName
```

Expected success artifacts:

- `results.jsonl`
- `run_manifest.json`
- `fixture_subset_manifest.json`
- `shared_retrieval.jsonl`
- `pilot_inspection.json`

If the run fails, inspect:

- `pilot_failure.json`

Check that the successful run produced 21 raw result records:

```powershell
(Get-Content (Join-Path $latest.FullName "results.jsonl") | Where-Object { $_.Trim() }).Count
```

Expected:

```text
21
```

## 13. Reset Before Another Evaluation Run

Pilot data remains loaded in `infobank_eval` and `backend_python/chroma_eval` after a successful run so it can be inspected. Before another pilot or the full experiment, reset or recreate the isolated evaluation database and Chroma store.

Do not reset or delete the development database `infobank_db` unless you intentionally want to recreate the normal local prototype state.
