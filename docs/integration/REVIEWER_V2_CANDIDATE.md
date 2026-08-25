# Reviewer-v2 pre-freeze candidate

Status: `READY_FOR_HUMAN_QA`. This candidate is not final, frozen, or held-out evaluation evidence.

The candidate builder does not itself establish empirical system performance. The historical D-GATE simulator consumed combined case/gold fields and is deprecated for performance claims; execution inputs and gold annotations must be separated before actual evaluation.

## Reproducible composition

`scripts/build_reviewer_v2_candidate.py` produces ignored artifacts at `artifacts/pre_freeze/reviewer_v2_candidate/`:

- 6 generated synthetic owned-object packages: 2 televisions, 2 routers, and 2 printers;
- 5 two-page PDFs per package: manual/user guide, quick-start/specification, warranty, synthetic purchase/service record, and thematic distractor;
- 90 gold-query candidates, exactly 6 for each of 15 required query classes;
- 60 permission-counterfactual groups with Full/Aggregate/Metadata/Deny variants (240 variants total);
- 60 browser-only cases whose gold action count is zero;
- 120 generated synthetic mail threads and action/closure preannotations;
- 24 pending second-annotation assignments (20% of mail threads).

All IDs, source text, PDFs, hashes, splits, counterfactuals, and assignments are deterministic. The development and candidate-holdout splits use disjoint object families, template families, and document packages. The builder emits a normalized-token near-duplicate report; this is an audit signal, not a human semantic-duplicate decision.

Run:

```powershell
python scripts/build_reviewer_v2_candidate.py --output artifacts/pre_freeze/reviewer_v2_candidate
python scripts/build_reviewer_v2_candidate.py --output artifacts/pre_freeze/reviewer_v2_candidate --validate-only
```

The output directory must be empty/nonexistent for a build. The builder refuses to mix a new candidate with stale artifacts.

## MailEx path and fallback

A local `data.zip` source passed the read-only path-safety preflight, but no licence, licence identifier, README or COPYING file was found. Status is `LICENCE_PENDING_HUMAN_CONFIRMATION`. `scripts/build_mailex_candidate.py` now parses the actual token/event JSON and delimiter-separated raw-thread format and produced an ignored 120-thread candidate. The synthetic fallback remains separately labelled. Derived output must remain untracked until a human licence decision permits otherwise.

Local build command:

```powershell
python scripts/build_mailex_candidate.py `
  --source-zip <local-data-zip> `
  --output artifacts/mailex_local/candidate `
  --limit 120
```

## Generated QA artifacts

The candidate directory contains dataset/source/provenance manifests, gold queries, counterfactuals, transformation and exclusion logs, an automated no-health report, a manual no-health sign-off template, split and near-duplicate reports, licence/redistribution status, annotation/adjudication sheets, an automated structural QA report, and SHA-256 checksums. PDFs, mail records, sheets, and generated reports are deliberately ignored and are not committed.

The JSON manifest contract is `evaluation/schemas/reviewer_v2_candidate.schema.json`; annotation decisions follow `docs/integration/ANNOTATION_GUIDELINE.md`.

## Limits

Generated templates and the pseudonymized MailEx candidate are suitable for engineering and reviewer preparation, not external-validity claims. Human source/page/message verification, MailEx licence approval, primary and second annotation, adjudication, manual citation audit, manual no-health sign-off, and final freeze approval remain outstanding.
