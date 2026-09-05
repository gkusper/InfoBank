# ISCMI 2026 MailEx Task Benchmark

This directory contains deterministic benchmark fixtures derived from the
corrected 50-thread MailEx pilot and the human-created
`MailEx_annotation_v1.6.xlsx` workbook. It prepares evaluation inputs and gold
targets only. It does not implement or run a RAG system.

## Information Levels

The benchmark keeps three information levels separate:

1. Original email evidence remains in the corrected external `P001.md` through
   `P050.md` packet. Committed fixtures contain only stable message references,
   never raw email bodies.
2. Human annotations are represented in `task_histories.jsonl` and retain their
   annotation status, confidence, notes, and source workbook row.
3. Derived benchmark ground truth is stored in `task_snapshots.jsonl` and the
   gold fields of `questions.jsonl` / `questions.csv`.

Human task IDs, transition labels, participants, and final states are not copied
into any retrieval corpus. `message_evidence_index.jsonl` contains only pilot,
thread, message, rank, and external source-file references.

## Primary Inclusion Rules

- Include `ANNOTATED` rows.
- Exclude `PENDING`, `NO_TASK`, and `SKIP_UNCERTAIN` from positive task truth.
- Require numerical confidence of at least 3. In v1.6, the observed usable
  confidence values are 3, 4, and 5.
- The v1.6 workbook has no `qc_status` column, so no QC value is invented. If a
  future workbook supplies that column, the primary build includes only `PASS`.
- `NO_TASK` rows may support explicitly marked negative-control questions.

## Task Histories And Snapshots

A task is keyed by `pilot_id + task_id`. History events are sorted by
`chronological_rank`, with the source workbook row as a deterministic tie-break.
Duplicate ranks within one task are rejected.

The final snapshot uses the last usable chronological annotation. Auxiliary
attributes are not forward-filled: an empty value in the last annotation remains
`null`. This avoids treating an ambiguous empty cell as an implicit "unchanged"
instruction.

## Questions

Questions use fixed templates and stable IDs (`ISCMI-Q0001`, ...). No LLM is
used for paraphrasing. The main families cover open and closed task sets,
responsible actors, requesters, multi-message task history, deadlines,
waiting-for information, blockers, and `NO_TASK` controls.

The natural-language question never names an internal task ID. Internal IDs are
present only in benchmark metadata and gold targets. Because v1.6 does not store
a separate task-description field, the build does not invent task descriptions;
it prefers thread-level questions and structured task references.

`CANCEL` has no usable examples and `REJECT` is very rare. They are retained in
statistics and closed-task descriptions but are not treated as headline
classification targets. Deadline, waiting-for, and blocker families are also
reported separately because their coverage is smaller.

## Evaluation Set

All 50 pilot threads form one fixed evaluation set. No train/dev/test split is
created. Any later partition must be made at pilot/thread level, never at row or
message level.

## Rebuild

The builder uses only the Python standard library and does not call an API:

```powershell
python experiments\iscmi2026\benchmark\build_benchmark.py `
  --annotations "C:\path\to\MailEx_annotation_v1.6.xlsx" `
  --pilot-packet "C:\path\to\mailex_pilot_external_packet" `
  --output experiments\iscmi2026\benchmark
```

Output ordering is deterministic. The manifest timestamp is the only
time-dependent value. Pass the recorded timestamp explicitly for byte-identical
rebuilds:

```powershell
python experiments\iscmi2026\benchmark\build_benchmark.py `
  --annotations "C:\path\to\MailEx_annotation_v1.6.xlsx" `
  --pilot-packet "C:\path\to\mailex_pilot_external_packet" `
  --output experiments\iscmi2026\benchmark `
  --generation-timestamp "2026-08-24T00:00:00Z"
```

## Generated Files

- `benchmark_manifest.json`: provenance, hashes, rules, and corpus/gold separation.
- `benchmark_statistics.json`: coverage and class/question distributions.
- `message_evidence_index.jsonl`: body-free references to corrected email evidence.
- `task_histories.jsonl`: ordered human annotations per task.
- `task_snapshots.jsonl`: deterministic final task ground truth.
- `questions.jsonl`: structured benchmark questions and gold answers.
- `questions.csv`: review-friendly representation of the same questions.

The build validates message/task references, question-family prerequisites,
final states, exclusions, body-free committed fixtures, and gold isolation before
writing the manifest.
