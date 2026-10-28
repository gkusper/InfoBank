# InfoBank semantic integration v2

Development branch: experiment/infobank-semantic-integration-v2. Parent commit: 5a95abe933cda134ff4f1be0e82614df6934d987. Earlier experimental artifacts are immutable. Read REPORT.md for actual findings, query_profile_spec.md for the request grammar and metadata_binding_spec.md for the authorization-bound retrieval interface.

From the repository root, run API-free tests with `python -m pytest evaluation/infobank_semantic_integration_v2/test_integration.py -q`. Generate and evaluate the thirty construction-rule scenarios with `python -m evaluation.infobank_semantic_integration_v2.synthetic_cases`. Synthetic tests use controlled semantic responses and no external API; their mode accuracy is not LLM semantic accuracy.

After preflight tests pass, run `python -m evaluation.infobank_semantic_integration_v2.run_experiment pilot`, then `...run_experiment full` only if all required pilot checks pass. OPENAI_API_KEY must be provided through the environment. Frozen directories refuse accidental reruns. Any code/prompt/scoring correction requires a new version/output manifest. The full experiment makes fresh observations for all forty cases under one frozen implementation; it does not reuse pilot results or any v1 outputs.

The shared control sees the same actual query, permitted views, query profile, binding assertions and semantic assessment as CFAF. It sees no gate mode, fulfilment flag or response contract. Public responses use the same strict six-field schema. P5 is handled by the identical deterministic zero-view path for both systems. Raw private content, original IDs, titles, runtime answers and gold labels remain local. Reports and raw research logs are internal deliverables, not public response channels.

Historical regression tests run in a disposable exact-Git-blob checkout with a writable workspace temp directory. The known authorization-presence test is recorded separately. Initial attempts using Windows TEMP or archive-converted line endings are retained as diagnostic logs; they are not semantic regressions.
