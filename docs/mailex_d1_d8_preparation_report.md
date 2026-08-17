# MailEx D1-D8 Benchmark Preparation Report

## 1. Executive Summary

This branch prepares InfoBank for a reproducible D1-D8 pilot evaluation. The
existing D1-D4 document-governance benchmark remains intact. A new
`document_rag_v2` fixture preserves D1-D4 and repairs D5 by removing explicit
evidential-role hints from generator-visible source prose. A separate
`evidence_unit_v1` benchmark adds a deterministic MailEx-based D6-D8 pilot:
10 D6 open-action cases, 10 matched D7 browser/search-only counterfactuals,
10 matched D8 natural closure cases, and 2 D8 non-closing controls.

The task completed deterministic preprocessing, validation scripts, automated
tests, provenance/licensing documentation, and a deterministic smoke test. It
does not claim that the final scientific experiment has been run; it prepares
the repository for that experiment.

## 2. Initial Repository State

Work started from branch `reproducibility-bootstrap-pre-pilot-v0.1`, commit
`d647548cb43301b9194746fd331825fa8897d90e`, which already contained the
pre-pilot reproduction bootstrap. A new branch was created:

```text
mailex-d1-d8-benchmark
```

Initial inspection found no uncommitted project changes beyond the work created
for this task. Relevant existing files included:

- `evaluation/fixtures/document_rag_v1.yaml`
- `evaluation/fixture_schema.py`
- `evaluation/validate_fixtures.py`
- `evaluation/run_case.py`
- `evaluation/run_suite.py`
- `evaluation/run_document_rag_pilot.py`
- `backend_python/models.py`
- `backend_python/evidence_service.py`
- `scripts/citds_11_smoke_test.py`

The existing `EvidenceUnit` implementation stores source type, content,
timestamp, thread/relation keys, and JSON metadata in `backend_python/models.py`.
The benchmark added here uses JSONL files rather than a database.

## 3. MailEx Source

Source repository:

```text
https://github.com/salokr/Email-Event-Extraction
```

Observed source commit:

```text
57507a458ce157378300d982914d7528448a381d
```

Dataset download URL:

```text
https://drive.google.com/file/d/1a336g4-wlEwsVbXLPB9wPQnBDRE933mb/view
```

Download method:

```powershell
.\backend_python\.venv_eval\Scripts\python.exe -m pip install --cache-dir .\.pip-cache gdown
$env:XDG_CACHE_HOME=(Resolve-Path .\.pip-cache).Path
.\backend_python\.venv_eval\Scripts\python.exe -m gdown 1a336g4-wlEwsVbXLPB9wPQnBDRE933mb -O data\external\mailex\mailex_dataset_download --no-cookies
```

Downloaded file:

```text
data/external/mailex/mailex_dataset_download
```

SHA-256:

```text
dda3ce5da5ffc3452dd9e5a58cd69e19e68bd655eafe1deec48e87204f6c37b4
```

Observed extracted structure:

```text
data/
  train/
  dev/
  test/
  raw_threads/
  full_data/
```

Observed source statistics:

| Statistic | Observed |
|---|---:|
| train threads | 1200 |
| dev threads | 150 |
| test threads | 150 |
| total threads | 1500 |
| total e-mail turns | 3936 |
| Request_Action events | 1048 |
| Deliver_Action_Data events | 1604 |
| Request_Action with Action Description, Members, and Date | 90 |
| request threads with later action-related messages | 411 |

The observed train/dev/test counts match the MailEx README.

## 4. Licensing and Redistribution Assessment

The MailEx README states that the dataset is distributed under CC BY-SA 4.0.
No separate `LICENSE`, `COPYING`, or dataset-internal license file was found in
the cloned repository or downloaded archive. No additional license terms were
found in the downloaded package.

Based on the README statement, the small derived benchmark subset is treated as
publishable under CC BY-SA 4.0, with attribution and ShareAlike handling. This
is not a legal guarantee and should be rechecked before public release. Because
MailEx is based on real Enron e-mail, the repository does not commit the raw
downloaded corpus. The committed benchmark includes only selected, modified,
pseudonymized action-related excerpts and deterministic synthetic D7 traces.
The excerpt sanitizer masks e-mail addresses, phone-like strings, participant
fields, and selected person-name tokens observed in the derived subset.

Documentation added:

- `data/benchmarks/evidence_unit_v1/LICENSE_DATA.md`
- `data/benchmarks/evidence_unit_v1/ATTRIBUTION.md`
- `data/benchmarks/evidence_unit_v1/SOURCE_PROVENANCE.md`

## 5. Transformation Pipeline

The preprocessing pipeline is deterministic and implemented with Python
standard-library modules plus the repository's existing test dependencies.

Scripts:

- `scripts/mailex/inspect_mailex.py`
- `scripts/mailex/build_evidence_benchmark.py`
- `scripts/mailex/validate_evidence_benchmark.py`
- `scripts/mailex/smoke_d1_d8.py`
- `scripts/mailex/mailex_utils.py`

Pipeline summary:

1. Inspect local MailEx split JSON files.
2. Extract candidate `Request_Action` items with useful `Action Description`.
3. Select cases with later `Deliver_Action_Data` evidence containing a
   conservative completion/cancellation/supersession lexical signal.
4. Convert selected request excerpts into D6 e-mail EvidenceUnits.
5. Deterministically derive D7 browser/search EvidenceUnits from the D6 action
   topic using `deterministic_topic_trace_v1`.
6. Convert later action-related excerpts into D8 contrastive EvidenceUnits.
7. Store runtime-visible inputs in `cases.jsonl`.
8. Store hidden scoring labels in `gold.jsonl`.
9. Store provenance, source checksum, and candidate counts in
   `source_manifest.json`.
10. Store benchmark-level curation decisions in `curation_overrides.json`.

## 6. D1-D4 Status

D1-D4 remain structurally unchanged from `document_rag_v1` in the new
`document_rag_v2` fixture.

| Scenario | Meaning | Count |
|---|---|---:|
| D1 | Full-access document QA | 8 |
| D2 | Metadata-only document | 8 |
| D3 | Aggregate-only source | 8 |
| D4 | Denied source | 8 |

Automated tests compare D1-D4 case dictionaries and scoped document content
between v1 and v2.

## 7. D5 Changes

The original D5 source prose contained explicit hints such as "primary evidence",
"contextual support only", and "cannot prove". These phrases made the expected
source role visible in the document text. The new `document_rag_v2.yaml` retains
the original D5 structure but rewrites generator-visible source text so roles
must be inferred from provenance, source genre, and semantics rather than
instructional prose.

D5 structure:

| Subtype | Count |
|---|---:|
| MIXED_PRIMARY | 4 |
| CONTEXT_ONLY | 4 |

Automated D5 leakage tests reject prohibited role-hint phrases in generator-
visible D5 document content.

## 8. D6 Construction

D6 starts from MailEx `Request_Action` candidates. The builder filters for
understandable action descriptions with request-like lexical signals and
constructs e-mail EvidenceUnits with `access_mode = full`.

Candidate summary:

| Measure | Count |
|---|---:|
| closure candidates available | 20 |
| selected D6 seeds | 10 |
| D6 cases built | 10 |

Each D6 gold row expects:

```text
expected_status = OPEN
expected_presence = true
gold_role = primary
```

## 9. D7 Construction

D7 is a controlled synthetic counterfactual derived from each D6 seed. The
transformation extracts a deterministic topic from the action description and
creates three browser/search-history EvidenceUnits:

- search query for the topic;
- visited reference page for the topic;
- search query for examples.

The transformation rule is recorded as:

```text
deterministic_topic_trace_v1
```

D7 contains no e-mail EvidenceUnits. Each D7 gold row expects:

```text
expected_status = ABSENT
expected_presence = false
gold_role = contextual
```

## 10. D8 Construction

D8 uses later MailEx action-related material in the same thread. The current
pilot includes only unambiguous lexical closure categories selected by the
builder and recorded in `curation_overrides.json`.

| D8 type | Count |
|---|---:|
| natural closure cases | 10 |
| completed | 9 |
| cancelled | 0 |
| superseded | 1 |
| non-closing controls | 2 |
| ambiguous/excluded from scored benchmark | not included |
| synthetic closure cases | 0 |

The D8 closure interpretation is InfoBank benchmark gold, not an original
MailEx annotation. D8_NONCLOSING cases remain OPEN and are included to prevent a
trivial rule that treats any later message as closure.

## 11. Final Benchmark Statistics

| Scenario | Dataset | Natural | Synthetic | Count |
|---|---|---:|---:|---:|
| D1 | document_rag_v2 | 0 | 8 | 8 |
| D2 | document_rag_v2 | 0 | 8 | 8 |
| D3 | document_rag_v2 | 0 | 8 | 8 |
| D4 | document_rag_v2 | 0 | 8 | 8 |
| D5 mixed | document_rag_v2 | 0 | 4 | 4 |
| D5 contextual-only | document_rag_v2 | 0 | 4 | 4 |
| D6 | evidence_unit_v1 | 10 | 0 | 10 |
| D7 | evidence_unit_v1 | 0 | 10 | 10 |
| D8 closure | evidence_unit_v1 | 10 | 0 | 10 |
| D8 non-closing | evidence_unit_v1 | 2 | 0 | 2 |

## 12. Validation Tests

Commands and results:

```powershell
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\inspect_mailex.py --source data\external\mailex\extracted\data --json-out work\mailex_inspection.json
```

Result: PASS; observed counts listed in Section 3.

```powershell
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\validate_evidence_benchmark.py --benchmark data\benchmarks\evidence_unit_v1
```

Result:

```text
VALIDATION: PASS
```

```powershell
.\backend_python\.venv_eval\Scripts\python.exe -m evaluation.validate_fixtures evaluation\fixtures\document_rag_v2.yaml
```

Result:

```text
VALIDATION: PASS
```

```powershell
.\backend_python\.venv_eval\Scripts\python.exe -m unittest discover -s evaluation\tests -v
```

Result:

```text
Ran 45 tests in 9.091s
OK
```

No skipped tests were reported in the current local run. The suite includes
D5 role-hint leakage checks, EvidenceUnit integrity checks, MailEx source
parsing when the local raw data is present, and selected person-name token
masking for the derived subset. The existing pilot runner tests intentionally
print mocked pilot PASS/FAIL messages while testing failure artifact behavior.

## 13. Smoke Test

Command:

```powershell
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\smoke_d1_d8.py --document-fixture evaluation\fixtures\document_rag_v2.yaml --evidence-benchmark data\benchmarks\evidence_unit_v1
```

Result:

```text
SMOKE: PASS
```

Smoke coverage:

| Label | Case |
|---|---|
| D1 | FULL_01 |
| D2 | METADATA_01 |
| D3 | AGG_SAFE_01 |
| D4 | DENY_01 |
| D5 mixed | MIXED_PRIMARY_01 |
| D5 contextual-only | CONTEXT_ONLY_01 |
| D6 | D6_001 |
| D7 | D7_001 |
| D8 | D8_001 |

This was a deterministic smoke test with mock generation for document-RAG and
structural EvidenceUnit checks. It was not a real-API empirical D1-D8 run.

## 14. Known Limitations

- MailEx is based on real Enron e-mail; privacy and redistribution should be
  reviewed again before public release.
- The D6-D8 pilot is small and should be expanded after curation review.
- D7 is intentionally synthetic because no real browser-history dataset is
  available for this experiment.
- D8 closure labels are InfoBank benchmark-level interpretations.
- The current D8 pilot has no cancelled examples.
- The smoke test is deterministic and structural, not a full LLM-backed
  experimental run.
- Query timestamps are deterministic thread-local synthetic timestamps because
  the MailEx split JSON does not expose original message timestamps.

## 15. Reproduction Instructions

From a fresh checkout:

```powershell
git checkout mailex-d1-d8-benchmark
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -SkipDocker -SkipPackageInstall
```

Download MailEx:

```powershell
.\backend_python\.venv_eval\Scripts\python.exe -m pip install --cache-dir .\.pip-cache gdown
$env:XDG_CACHE_HOME=(Resolve-Path .\.pip-cache).Path
.\backend_python\.venv_eval\Scripts\python.exe -m gdown 1a336g4-wlEwsVbXLPB9wPQnBDRE933mb -O data\external\mailex\mailex_dataset_download --no-cookies
```

Extract the ZIP to `data/external/mailex/extracted/`, then run:

```powershell
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\inspect_mailex.py --source data\external\mailex\extracted\data --json-out work\mailex_inspection.json
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\build_evidence_benchmark.py --source data\external\mailex\extracted\data --output data\benchmarks\evidence_unit_v1 --pilot-size 10 --nonclosing-size 2
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\validate_evidence_benchmark.py --benchmark data\benchmarks\evidence_unit_v1
.\backend_python\.venv_eval\Scripts\python.exe -m evaluation.validate_fixtures evaluation\fixtures\document_rag_v2.yaml
.\backend_python\.venv_eval\Scripts\python.exe -m unittest discover -s evaluation\tests -v
.\backend_python\.venv_eval\Scripts\python.exe scripts\mailex\smoke_d1_d8.py --document-fixture evaluation\fixtures\document_rag_v2.yaml --evidence-benchmark data\benchmarks\evidence_unit_v1
```

## 16. GitHub Publication Status

Target branch:

```text
mailex-d1-d8-benchmark
```

Remote:

```text
origin https://github.com/gkusper/InfoBank.git
```

Commit:

```text
Run `git rev-parse HEAD` on this branch; the final terminal summary from the
preparation run records the exact post-amend commit SHA.
```

Push status:

```text
Not pushed from the non-interactive Codex environment.
```

Reason: GitHub was reachable and `git ls-remote` succeeded, but `git push`
failed because no non-interactive GitHub credentials were available:

```text
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

The branch is committed locally and ready for the repository owner to push with
their configured Git credentials.

## 17. Next Steps For Full D1-D8 Experiment

1. Review D6-D8 selected excerpts and curation decisions.
2. Add cancelled D8 examples if unambiguous natural candidates can be found.
3. Expand D6-D8 toward approximately 40 seed actions.
4. Connect EvidenceUnit JSONL loading to the final D1-D8 experiment runner.
5. Run a real-API D1-D8 pilot after credentials and clean evaluation state are
   configured.
6. Implement final action precision/recall/F1, closure-status accuracy, and
   triplet-consistency scoring.
