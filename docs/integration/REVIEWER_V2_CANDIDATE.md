# Reviewer-v2 pre-freeze candidate

Status: `READY_FOR_HUMAN_QA`. This candidate is not final, frozen, or held-out evaluation evidence.

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

No MailEx dataset or licence manifest was found in the authorized repository or adjacent evaluation-artifact directory on 2026-08-19. The candidate therefore uses clearly marked generated synthetic threads. `scripts/build_mailex_candidate.py` provides the preferred MailEx-derived path when an authorized local source and licence identifier are supplied. It preserves threads, pseudonymizes addresses, excludes an entire thread on a configured no-health term, records the source SHA-256 and licence identifier, and leaves licence confirmation and annotation pending. Its derived output must remain under ignored `artifacts/pre_freeze/` until a human licence decision permits otherwise.

Example after authorized source acquisition:

```powershell
python scripts/build_mailex_candidate.py `
  --source C:\authorized\mailex\threads.jsonl `
  --output artifacts/pre_freeze/mailex_candidate `
  --licence-id PENDING-CONFIRMATION `
  --limit 120
```

## Generated QA artifacts

The candidate directory contains dataset/source/provenance manifests, gold queries, counterfactuals, transformation and exclusion logs, an automated no-health report, a manual no-health sign-off template, split and near-duplicate reports, licence/redistribution status, annotation/adjudication sheets, an automated structural QA report, and SHA-256 checksums. PDFs, mail records, sheets, and generated reports are deliberately ignored and are not committed.

The JSON manifest contract is `evaluation/schemas/reviewer_v2_candidate.schema.json`; annotation decisions follow `docs/integration/ANNOTATION_GUIDELINE.md`.

## Limits

Generated templates are suitable for deterministic engineering and reviewer preparation, not external-validity claims. Human source/page/message verification, MailEx selection or a documented synthetic-only decision, second annotation, adjudication, manual citation audit, manual no-health sign-off, and final freeze approval remain outstanding.
