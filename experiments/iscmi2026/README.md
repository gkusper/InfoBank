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

## Manual Pilot Preparation

The manual pilot preparation step uses the fixed 50-row candidate pool from
`mailex_pilot_candidates.csv`. It adds:

- `mailex_annotation_guideline_v0.1.md`
- `mailex_pilot_index.csv`
- `mailex_pilot_annotation_template.csv`
- `mailex_pilot_task_summary_template.csv`
- `prepare_mailex_pilot.py`

The CSV templates intentionally leave semantic ISCMI fields blank for later
human annotation. To generate the full-text packet outside the repository:

```powershell
& "C:\Users\EKKE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" `
  experiments\iscmi2026\prepare_mailex_pilot.py `
  --dataset "C:\path\outside\repo\mailex_data.zip" `
  --output "C:\path\outside\repo\mailex_pilot"
```

The packet includes original MailEx annotations for reviewer context only. It
does not create ISCMI semantic ground-truth labels.

### Message Alignment

MailEx JSON `turn_N` order is treated as the intended conversational order. The
original MailEx processing code uses earlier `sentences[:idx]` as conversation
history, so `chronological_rank` is generated as `turn_N + 1`.

The `raw_threads` positional order must not be assumed to match JSON order.
`prepare_mailex_pilot.py` aligns each JSON sentence to the corresponding raw
message by deterministic text evidence before displaying sender, recipient,
subject, and body metadata.

`chronological_rank` is not an independently reconstructed send-time chronology,
and `sent_at` is not generated because timestamp coverage in MailEx is too
sparse for reliable ordering.
