# Dataset and evaluation guide

Status: `PRE_FREEZE_NOT_FINAL_E1`

The owned-object builder creates privacy-safe synthetic device documents and
query strata for answerable, multi-document, no-answer, conflict, permission,
aggregate and hard-negative cases. The local MailEx builder reads the original
ZIP without modifying it, filters complete no-health threads, pseudonymizes
candidate output and preserves deterministic splits. Its licence remains
`LICENCE_PENDING_HUMAN_CONFIRMATION`; raw or derived text is not tracked.

Development and candidate holdout remain separate. Runtime consumes only
`QueryInput`; scoring consumes `GoldAnnotation` after a raw run is sealed. B0-B3
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
