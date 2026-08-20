# Reproduction commands

Status: `PRE_FREEZE`

Use PowerShell from the repository root with Python 3.11 and the locked local
virtual environment. Replace angle-bracket parameters with task-owned names.

## Install, migration and gates

```powershell
docker compose up -d db
py -3.11 -m venv backend_python\.venv_r1a
backend_python\.venv_r1a\Scripts\python.exe -m pip install -r backend_python\requirements-dev-lock.txt
docker exec -i infobank-mariadb mariadb -uroot "-p$env:INFOBANK_SMOKE_ADMIN_PASSWORD" < .\backend_python\migrations\citds_11_mysql.sql
docker exec -i infobank-mariadb mariadb -uroot "-p$env:INFOBANK_SMOKE_ADMIN_PASSWORD" < .\backend_python\migrations\infocom_a_gate_phase1_mysql.sql
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1 -SkipDocker
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_quality_gate.ps1
```

Apply migrations only to the intended database after backup; the smoke script
uses separate isolated targets and avoids shell redirection for imports.

## A, C and D development runners

```powershell
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_a_gate_phase2.py --help
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_c_gate.py --help
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_d_gate.py --help
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_actual_pipeline_evaluation.py --help
```

## MailEx, API workflows and screenshots

```powershell
backend_python\.venv_r1a\Scripts\python.exe .\scripts\reconcile_mailex_source.py --zip <read-only-zip> --candidate-dir <candidate> --output <ignored-run>
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_api_end_to_end_workflows.py --output <ignored-run> --database-url <isolated-eval-url> --admin-database-url <admin-url> --chroma-dir <ignored-chroma> --source-storage-dir <ignored-source-store>
backend_python\.venv_r1a\Scripts\python.exe .\scripts\generate_reviewer_demo_seed.py --trace <api-trace> --output .\artifacts\reviewer_screenshots\pre_freeze_hardening\demo_seed.json
python .\scripts\serve_reviewer_capture.py --port 8766
```

Open the local reviewer-demo URL in `REVIEWER_SCREENSHOT_GUIDE.md`; the local CSP
blocks external resources.

## Operations and human QA

```powershell
$env:INFOBANK_SMOKE_DB_PASSWORD = '<local-compose-user-password>'
$env:INFOBANK_SMOKE_ADMIN_PASSWORD = '<local-compose-admin-password>'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_pre_freeze_operations_smoke.ps1 -OutputRoot .\artifacts\pre_freeze\operations-smoke
backend_python\.venv_r1a\Scripts\python.exe .\scripts\prepare_blinded_annotation_assignments.py --help
backend_python\.venv_r1a\Scripts\python.exe .\scripts\validate_human_qa_package.py --help
backend_python\.venv_r1a\Scripts\python.exe .\scripts\compute_annotation_agreement.py --help
```

## E1 estimate-only

```powershell
$modes = 'B0_VECTOR_ONLY','B1_VECTOR_ROUTING','B2_PERMISSION_FILTERED','B3_FULL_ROLE_AWARE'
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_real_provider_evaluation.py --estimate-only --repeats 1 --modes $modes --include-scale-subset --output .\artifacts\pre_freeze\e1_estimate_only\e1-r1.json
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_real_provider_evaluation.py --estimate-only --repeats 2 --modes $modes --output .\artifacts\pre_freeze\e1_estimate_only\e1-r2.json
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_real_provider_evaluation.py --estimate-only --repeats 3 --modes $modes --output .\artifacts\pre_freeze\e1_estimate_only\e1-r3.json
```

The optional scale estimate is a separate row/bundle scope and is never added
to the base counts. Final provider execution is
`NOT_AUTHORIZED / DO_NOT_RUN_YET`; do not remove `--estimate-only` and do not
provide a real API key before human provider/cost and freeze approval.
