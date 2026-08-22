# heldout_pilot_v1 Retirement Record

Retirement status:

`RETIRED_AFTER_PREEXECUTION_IMPLEMENTATION_GUARD_FAILURE`

## Scope

The retired dataset is:

`evaluation/wolala2026/data/heldout_pilot_v1/`

This record does not modify the dataset, gold labels, manifest, provenance, or
checksums. It preserves `heldout_pilot_v1` as an audit artifact only.

## Reason

`heldout_pilot_v1` attempt 1 was authorized, but the frozen Protocol v2 runner
stopped before provider initialization because a development-only execution
plan guard rejected held-out case IDs. The recorded blocker class is:

`FROZEN_RUNNER_PROTOCOL_V2_EXECUTION_PLAN_GUARD_INCONSISTENCY`

## Nonexecution Statement

No model ever saw `heldout_pilot_v1`.

The attempt stopped before:

- provider initialization;
- held-out retrieval;
- embedding;
- generation;
- scoring;
- raw-result creation.

Recorded held-out counts for attempt 1 are:

- held-out model executions: `0`
- held-out embedding calls: `0`
- held-out generation calls: `0`
- held-out external calls: `0`
- held-out raw outputs: `0`

## Final-Experiment Status

`heldout_pilot_v1` is not used in the final CFAF-focused held-out experiment.
The final experiment uses a fresh deterministic synthetic dataset,
`heldout_pilot_v2`, with case IDs beginning `HELD2_`.
