# EvidenceUnit v2 Holdout

This directory contains the frozen 340-case D6-D8 holdout benchmark for InfoBank action reconstruction.

## Contents

- `cases.jsonl`: runtime inputs only.
- `gold.jsonl`: hidden scorer labels.
- `triplets.jsonl`: D6/D7/D8 matched seed relationships.
- `source_manifest.json`: source, exclusion, and privacy-transform metadata.
- `benchmark_statistics.json`: scenario, closure, and natural/synthetic counts.
- `curation_overrides.json` and `curation_report.md`: compact curation audit.
- `LICENSE_DATA.md`, `ATTRIBUTION.md`, `SOURCE_PROVENANCE.md`: data-use notes.

## Counts

```text
D6 open action: 100
D7 browser-only counterfactual: 100
D8 closure: 100
D8 non-closing control: 40
Total: 340
```

Runtime cases intentionally omit scorer-only fields such as expected status, gold role, evidence IDs, closure type, and action description.

Raw MailEx downloads are not redistributed by this repository. They remain ignored under `data/external/` when locally available.

Validate with:

```powershell
python scripts/mailex/validate_evidence_benchmark.py --benchmark data/benchmarks/evidence_unit_v2_holdout
```
