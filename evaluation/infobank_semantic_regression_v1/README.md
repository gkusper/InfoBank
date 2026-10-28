# InfoBank governed semantic regression experiment

This directory contains a local development experiment on the previously exposed 40-case InfoBank dataset. It is not an independent holdout or third-party validation. See REPORT.md for findings and limitations.

The supported entry point is `python -m evaluation.infobank_semantic_regression_v1.run_experiment_v3 pilot` and then `...run_experiment_v3 full`, from the repository root, with OPENAI_API_KEY supplied through the environment. Existing run directories deliberately block accidental reruns. Use a new version/output directory for another experiment. Do not delete or overwrite frozen observations.

Version history: the first controller confused an inconsistent inferred evidence role with a structural failure. `integration_v2.py` preserves that semantic error and lets the deterministic sufficiency gate reject it. `run_experiment_v2.py` encountered an API read timeout. `run_experiment_v3.py` resumes using its one successful case; no semantic prompt was tuned. Earlier code and attempts remain here. Current policy projection is shared by all versions.

Run API-free tests with `python -m pytest evaluation/infobank_semantic_regression_v1/test_governed.py -q`. Phase A XML files document earlier regression suites, run before integration; one known historical authorization-presence test failure is recorded separately.

Public model input consists of the actual query, neutral permitted source IDs and permitted provenance, policy-projected text, and deterministic span references. Both generators receive the same inferred assessment. Only CFAF receives its response contract. Gold, case IDs and raw restricted documents remain in trusted local evaluation code. P5 cases have no external calls and byte-equivalent public response/trace objects. Internal audit files are not public response channels.

Frozen full-run observations reuse the ten pilot cases and execute the remaining thirty once. These are forty unique development observations, not fifty independent observations. API ledgers identify copied call records. Timeout attempts remain charged in the overall accounting.
