# EvidenceUnit v1 Benchmark

`evidence_unit_v1` is the first InfoBank pilot dataset for D6-D8 action-list
reconstruction. It is separate from the document-RAG fixtures because these
scenarios evaluate EvidenceUnit behavior rather than document governance.

## Scenarios

- D6: a permitted e-mail request creates an OPEN action item.
- D7: browser/search-history-like activity about the same topic does not create
  an action item by itself.
- D8: later e-mail evidence in the same thread closes, cancels, or supersedes
  the original action.
- D8_NONCLOSING: later progress or future-commitment evidence does not close
  the original action.

## Relationship To MailEx

D6 and natural D8 cases are selected, excerpted, and pseudonymized from MailEx,
which is based on Enron e-mail threads. The published subset masks e-mail
addresses, phone-like strings, participant fields, and selected person-name
tokens. MailEx event annotations are used only for deterministic candidate
discovery and provenance. The labels `Request_Action` and
`Deliver_Action_Data` are not exposed to the evaluated system as answer hints.

D7 browser/search traces are controlled synthetic counterfactuals derived from
the D6 action topic. They preserve semantic similarity while removing the
communicative force of an e-mail request.

The InfoBank OPEN/CLOSED/ABSENT status is an additional benchmark-level
interpretation for action-list evaluation. It is not claimed to be an original
MailEx annotation.

## Files

- `cases.jsonl`: runtime input visible to the tested system.
- `gold.jsonl`: hidden scoring labels.
- `source_manifest.json`: source, checksum, counts, transformation, and matched
  relation metadata.
- `curation_overrides.json`: explicit benchmark-level status decisions.
- `LICENSE_DATA.md`: data license and redistribution decision.
- `ATTRIBUTION.md`: MailEx and InfoBank attribution.
- `SOURCE_PROVENANCE.md`: provenance and transformation details.

## Regeneration

Download MailEx locally under `data/external/mailex/`, then run:

```powershell
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\inspect_mailex.py --source data\external\mailex\extracted\data --json-out work\mailex_inspection.json
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\build_evidence_benchmark.py --source data\external\mailex\extracted\data --output data\benchmarks\evidence_unit_v1 --pilot-size 10 --nonclosing-size 2
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\validate_evidence_benchmark.py --benchmark data\benchmarks\evidence_unit_v1
```

## Current Pilot Size

- D6: 10 natural MailEx-derived e-mail request cases.
- D7: 10 synthetic browser/search counterfactual cases.
- D8: 10 natural MailEx-derived closure cases.
- D8_NONCLOSING: 2 natural MailEx-derived non-closing later-message cases.

The scripts are deterministic and can be expanded to a larger pilot by changing
`--pilot-size` after reviewing the resulting curation decisions.
