# MailEx local-source reconciliation

Status: `PASS_NOT_LICENCE_APPROVAL`

Reconciliation version: `infobank-mailex-reconciliation-v1`. The procedure reads the local ZIP directly and writes only paths, irreversible record IDs, hashes, byte counts, relationship scores, categories, and explanations. It does not write raw subjects, bodies, participant mappings, or annotation text.

## Source inventory

| Property | Recomputed value |
|---|---:|
| ZIP SHA-256 | `dda3ce5da5ffc3452dd9e5a58cd69e19e68bd655eafe1deec48e87204f6c37b4` |
| ZIP bytes | 5,476,134 |
| Non-directory entries | 4,754 |
| `__MACOSX` entries | 246 |
| `.DS_Store` entries | 1 |
| Logical entries after all macOS metadata | 4,507 |
| Legacy count excluding only `__MACOSX` | 4,508 |
| JSON train/dev/test/full_data | 1200 / 150 / 150 / 1500 |
| Raw thread files | 1,506 |
| Non-thread logical files | 1 (`data/prompt_data.txt`) |
| Malformed records | 0 |

The eight-record raw/full-data difference is completely categorized: two alternate raw duplicates and six unmatched raw records. It is not eight unexplained records.

## Relationship accounting

| Relationship/category | Count | Factual basis |
|---|---:|---|
| `MATCHED_ONE_TO_ONE` | 1,496 | normalized stem plus content evidence |
| `MATCHED_ALIAS` | 4 | different path or additional annotation with token-set similarity 0.907563–1.0 |
| `DUPLICATE_RAW` | 2 | alternate raw version for a matched JSON record; similarity 0.792857 or 1.0 |
| `DUPLICATE_JSON` | 0 | no duplicate JSON category required |
| `UNMATCHED_JSON` | 0 | both formerly unmatched JSON records are content aliases |
| `UNMATCHED_RAW` | 6 | no JSON record has sufficient content evidence |
| Unexplained | 0 | every record has a category and non-empty factual explanation |

The four alias relations are:

- `corman-s_inbox_archives110.json` → `corman-s_inbox_archives111.` (additional annotation alias, similarity 0.907563025);
- `schoolcraft-d_inbox35.json` → `schoolcraft-d_inbox_34` (additional annotation alias, similarity 1.0);
- `nemec-g_inbox431.json` → `example.` (exact content alias; the similarly named raw record is not a content match);
- `steffes-j_inbox394.json` → `steffes-j_inbox394CORR.` (exact corrected content alias).

The two alternate raw records are `steffes-j_inbox394.` and one of the two normalized `kaminski-v_inbox233` raw paths. The six explicitly unmatched raw logical paths and their full SHA-256 values are recorded in the ignored `unmatched_raw_records.csv`; they contain no unresolved classification and are not used by the 120-thread candidate.

## Parser correction and candidate effect

The prior parser used a dictionary keyed by normalized filename, so five raw stem collisions overwrote an entry and four JSON stem collisions could produce repeated thread IDs. The corrected planner performs deterministic one-to-one matching using normalized stems, exact logical basename affinity, token-set content hashes, and Jaccard evidence; it then records only high-evidence aliases and duplicates.

The rebuilt candidate retains 120 threads, 322 messages, train/dev/test counts 99/9/12, 24 second-annotation assignments, three complete no-health exclusions, and zero duplicate selected thread IDs. Human labels remain blank or pending.

## Reproduction and generated artifacts

```powershell
backend_python\.venv_r1a\Scripts\python.exe scripts\build_mailex_candidate.py --source-zip <local-data.zip> --output <ignored-candidate-dir> --limit 120
backend_python\.venv_r1a\Scripts\python.exe scripts\reconcile_mailex_source.py --source-zip <local-data.zip> --candidate-dir <ignored-candidate-dir> --output <ignored-reconciliation-dir>
```

Generated files are `source_entry_inventory.jsonl`, `json_raw_match_table.csv`, `unmatched_json_records.csv`, `unmatched_raw_records.csv`, `duplicate_or_alias_records.csv`, `reconciliation_summary.json`, and `reconciliation_checksums.csv`. Two complete runs produced the same checksum-manifest SHA-256: `d711d80a4289ac5cc7495832a96f5aa1129658fe4d7088a94135aaa172f0fce2`.

Licence state remains `LICENCE_PENDING_HUMAN_CONFIRMATION`. This reconciliation is not licence evidence, redistribution approval, human annotation, a freeze, or final E1.
