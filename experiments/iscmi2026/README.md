# ISCMI 2026 MailEx Audit

This directory contains an isolated, deterministic audit of the MailEx dataset
for the planned ISCMI 2026 action-item / task-state reconstruction experiment.

It does not implement the RAG experiment, does not call any LLM API, and does
not create final ISCMI labels.

## Inputs

The audit script accepts a MailEx dataset path via `--dataset-path`. The path
may point to:

- the original `data.zip` downloaded from the MailEx Google Drive link,
- an extracted MailEx dataset directory, or
- a Git checkout/object tree containing the MailEx dataset.

Raw MailEx files should stay outside the InfoBank repository. For this audit,
the dataset was inspected from a local ZIP under the task `work/external`
directory.

## Run

```powershell
& "C:\Users\EKKE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" `
  experiments\iscmi2026\audit_mailex.py `
  --dataset-path "C:\Users\EKKE\Documents\Codex\2026-08-23\a-feladat-most-kiz-r-lag\work\external\mailex_data.zip" `
  --project-repo "C:\Users\EKKE\Documents\Codex\2026-08-23\a-feladat-most-kiz-r-lag\work\external\Email-Event-Extraction" `
  --hf-dataset-repo "C:\Users\EKKE\Documents\Codex\2026-08-23\a-feladat-most-kiz-r-lag\work\external\MailEx"
```

Generated outputs:

- `mailex_audit_report.md`
- `mailex_audit_summary.json`
- `mailex_event_statistics.csv`
- `mailex_thread_statistics.csv`
- `mailex_pilot_candidates.csv`
