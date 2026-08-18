# WoLaLa 2026 Pilot Readiness Report v3

## Status

This report evaluates readiness for a later, separately authorized first held-out run under `WOLALA2026_PILOT_PROTOCOL_v2.md`. This task did not execute held-out retrieval, embedding, generation, scoring, or latency output.

## Starting State

- Branch: `wolala2026`
- Starting commit: `0bf388e2b0c65935d561433c0e6d827f6c80102e`
- Ending commit: recorded after commit; a commit cannot contain its own SHA.
- Original D1-D8 base ancestor: `5bb2cc742e105cc3238b022130126947c04bcd35`

## Frozen Checksums

- Protocol v1: `91c6e3279821abdd0c5b92006a4ce572293fc5ed29a77e7edbf5d1b47147f93e`
- Protocol v2: `34907efae5197fa9df610a5da6fdf50067d018c56b5885d8dbdb194d7fff58ba`
- Held-out dataset: `b86ddfa2a3db79a5d9e3e31b57000f1619f790040a6d9d814970ea2d1f54031b`
- Prompt-only prompt: `77d2d8ff8042f94fd7381580d6034deb19827d3502e06bf67a96b87103fb0af6`
- CFAF generator prompt: `0f6d54a1c9f5ccf3f0b4a1559cdb18c4dcd4a68f0c5f22895a440f50e45ba765`
- Statistical plan: `2639906b515589ba3fe15487567cc53aaf875823909eb077a2bd06f8ee149b1e`
- Latency definition: `4c0c87f6267ab18f68677479439d4347d8449f36ed850e87d7d94b89e02b02a7`
- Execution spec: `d170b43dc8426bb923588a19712546920be0f16004ef4a257fa0d6a0b4436344`
- Scorer: `5c8349ce5b690cff29b6f2948f6e01fa38eb15f921cdd76a7bbc121d1f86c0a2`
- Parser/adapters: `d11892deeec0dc3bd46de3fac7a5591d2f2a44460187e0f30cb4d3ab5739a2c9`

## Readiness Criteria

1. Protocol v2 exists and is complete: PASS.
2. Protocol v1 remains unchanged: PASS.
3. Held-out dataset checksum unchanged: PASS.
4. Prompts unchanged: PASS.
5. Provider/model configuration frozen: PASS.
6. Repetitions frozen at 3: PASS.
7. Execution counts frozen at 360 planned mode executions: PASS.
8. Call caps frozen: PASS.
9. Warm-up policy frozen at 0 external warm-up calls: PASS.
10. Retry policy frozen: PASS.
11. Invalid-run policy frozen: PASS.
12. Rerun policy frozen: PASS.
13. Statistical plan frozen: PASS.
14. Repetition aggregation implemented and tested: PASS.
15. Latency semantics frozen: PASS.
16. Latency derivation implemented and tested: PASS.
17. Scorer/parser sanity audit passed: PASS.
18. Execution spec validated: PASS.
19. Plan-only mode reports 360 planned executions: PASS.
20. No held-out model execution occurred: PASS.
21. No external model/provider API call occurred: PASS.
22. No frozen D1-D8 artifact changed: PASS.
23. No WoLaLa manuscript changed: PASS.
24. All relevant tests pass: PASS.
25. Working tree clean after final commit: PASS pending final commit gate.

## Test Results

- `python -m unittest discover -s evaluation/tests -p "test_wolala*.py" -v`: PASS, 42 tests.
- `python -m unittest evaluation.tests.test_harness evaluation.tests.test_d1_d8_evidence_loader_and_action_logic -v`: PASS, 24 tests.

## Remaining Blockers

No protocol or implementation blocker remains for a later, separately authorized held-out execution under Protocol v2. This report does not authorize that execution.

## Final Readiness Classification

READY_FOR_HELDOUT_EXECUTION_UNDER_PROTOCOL_V2
