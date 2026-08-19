# Local MailEx source and candidate report

Source status: `LICENCE_PENDING_HUMAN_CONFIRMATION`

Candidate status: `READY_FOR_HUMAN_ANNOTATION_NOT_FREEZE`

## Local source evidence

- Source ZIP basename: `data.zip`.
- ZIP SHA-256: `dda3ce5da5ffc3452dd9e5a58cd69e19e68bd655eafe1deec48e87204f6c37b4`.
- ZIP size: 5,476,134 bytes.
- Non-directory entries: 4,754; logical entries after ignoring macOS resource metadata: 4,508.
- Split JSON files: train 1,200; dev 150; test 150; full_data 1,500.
- Raw-thread files: 1,506.
- Other logical source file: `prompt_data.txt`.
- Licence/readme files found: none.
- Locally evidenced licence identifier: none.

No licence was inferred from a dataset name, prior conversation, external site, or memory. Raw and derived MailEx content remains untracked. Human licence and redistribution confirmation is required before any tracked derived subset or freeze.

## Actual format and selected parser

The JSON records are objects with `sentences` and `events`. `sentences` is a turn-ordered list of token lists. `events` is keyed by `turn_N`; each event contains aligned `labels`, `triggers`, and `extras` lists. The raw-thread files contain two or more messages separated by long hyphen delimiters and use RFC-822-like `From`, `To`, `Subject`, and occasional `Cc`, `Date`, `Sent`, and `Message-ID` headers.

The selected parser reads the ZIP directly, rejects unsafe member names, joins full-data JSON to raw threads by normalized source filename, and retains source split membership. It preserves message order, pseudonymized participant relationships, subject/body, available timestamps, event/argument structures, and stable derived message IDs. Missing source IDs and timestamps are not invented as source facts: source message IDs become irreversible hashes or deterministic derived IDs, and missing timestamps remain null.

## Transformation and provenance

Transformation version: `infobank-mailex-local-transform-v1`.

For every selected thread the ignored candidate records an irreversible source-record hash, source split, stable pseudonymous participants, ordered messages, transformed annotations, source ZIP hash, selected raw-thread hash, selected annotation-file hash, and pending human state. Email addresses, observed participant display names, URLs, phone-like values, and local paths are deterministically pseudonymized. The candidate contains no raw absolute extraction path.

The automated source audit found 1,498 normalized JSON/raw matches across the complete 1,500-record full-data set, leaving 2 unmatched full-data JSON records. The deterministic selection traversed the source until 120 usable threads were selected. Three encountered threads were excluded in full by the automated no-health filter. The selected split counts are train 99, dev 9, and test 12.

## Candidate and annotation work

- Selected threads: 120.
- Parsed messages in selected threads: 322.
- Primary annotation assignments: 120.
- Independent second-annotation assignments: 24 (20%).
- Action/closure preannotations: 120, all labelled `MACHINE_SUGGESTION_NOT_GOLD`.
- Adjudication rows: 120, all pending.
- Agreement value: not calculated because no human labels exist.
- Automated scan of selected subjects, bodies, annotations, arguments, and derived records: zero retained prohibited-topic hits.
- Manual no-health status: `PENDING_HUMAN_SIGNOFF`.

The automated exclusion is not claimed sufficient for release. A human must review the selected candidate, source/licence state, annotation decisions, screenshots, traces, and publication-facing excerpts.

## Unresolved issues

- Licence and redistribution permission are not locally evidenced.
- Most raw messages lack source Message-ID and timestamp fields.
- Human primary annotation, second annotation, agreement calculation, and adjudication have not occurred.
- Manual no-health sign-off has not occurred.
- No MailEx candidate holdout result was inspected or used for tuning.
