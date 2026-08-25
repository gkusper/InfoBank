# Dataset and evaluation guide

Status: `PRE_FREEZE_NOT_FINAL_E1`

The owned-object builder creates privacy-safe synthetic device documents and
query strata for answerable, multi-document, no-answer, conflict, permission,
aggregate and hard-negative cases. The local MailEx builder reads the original
ZIP without modifying it, filters complete no-health threads, pseudonymizes
candidate output and preserves deterministic splits. Its licence remains
`LICENCE_PENDING_HUMAN_CONFIRMATION`; raw or derived text is not tracked.

Development and candidate holdout remain separate. Runtime consumes only
`QueryInput`; scoring consumes `GoldAnnotation` after a raw run is sealed. C0-C3
compare no retrieval, routing-off, keyword routing and full role-aware behavior.
Scale stress is a separate deterministic workload. Scoring covers output class,
reason, retrieval/candidate behavior, false exclusion, citations, evidence roles
and latency measurements where locally observed.

Automated candidate QA does not replace human work. Gold review, primary and
20% second annotation, agreement/adjudication, 40-row citation audit and manual
no-health sign-off remain pending. The human-QA tools blind/order/validate and
compute descriptive percent agreement and Cohen's kappa only after labels are
complete; they select no threshold.

Provider execution follows: local readiness checks, complete estimate-only
plan, provider/model/cost approval, freeze approval, immutable input/config/code
identities, complete non-cherry-picked run, raw-run sealing, then scoring. The
optional scale subset is costed separately. Final E1 and every freeze step are
`DO_NOT_RUN_FINAL_E1_YET` / `NOT_AUTHORIZED`.

## Roadmap v1.8 ScenarioPack authoring

`evaluation/scenario_pack.py` defines the evaluation-only ScenarioPack contract
and the S1-S6 story descriptions. It does not add production database fields,
upload metadata or gold information to `/api/ask`. In particular,
`required_sources`, `reference_answer`, `reference_citations` and
`negative_reason` remain authoring/scoring data and are not added to
`QueryInput`.

The deterministic builder writes manifests to an explicitly supplied,
non-repository dataset root:

```powershell
& .\backend_python\.venv_r1a\Scripts\python.exe scripts\build_scenario_pack_descriptions.py `
  --output '<dataset-root>'
```

Each pack receives a `scenario_pack.json` and an initially empty
`source_documents` directory. The validation report deliberately records
missing reference answers/citations and the current 4-5 example questions per
story as readiness gaps. These fields are completed only while the matching
S1-S6 documents and real-system runs are built; page, message or record
citations must never be fabricated before the corresponding artifact is
stable.

When one pack has stable reference answers and a locator for every required
source, it can be projected into physically separated runtime and scorer
inputs:

```powershell
& .\backend_python\.venv_r1a\Scripts\python.exe scripts\export_scenario_pack_projection.py `
  --scenario-pack '<dataset-root>\scenario_packs\S1_SOFA_01\scenario_pack.json' `
  --output '<dataset-root>\projections\S1_SOFA_01'
```

The command refuses incomplete evidence. Its `runtime/query_inputs.jsonl`
contains no expected result, required source, reference answer, citation or
negative reason. Those fields are written only to
`scorer/gold_annotations.jsonl`. The projection status is
`READY_FOR_CORPUS_BINDING`, not a claim that the referenced PDFs have already
been ingested or that a real-system run has completed. Legacy
`gold_document_ids` and `gold_page_or_message_ranges` remain readable; new
artifacts also carry canonical `required_sources` and `reference_citations`.
