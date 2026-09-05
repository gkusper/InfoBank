# Held-Out Runner Guard Root Cause v1

## Summary

The Protocol v2 runner correctly validated the held-out execution specification
for `heldout_pilot_v1`, then incorrectly reused a development-only execution
plan function before provider initialization. That function rejected held-out
case IDs and stopped the run before retrieval, embedding, generation, scoring,
or raw-result writing.

## Exact Defect

- File: `evaluation/wolala2026/run_pilot.py`
- Function before repair: `_execution_plan`
- Current condition before repair:
  `heldout_ids = [case_id for case_id in case_ids if case_id.startswith("HELD_")]`
  followed by `raise RuntimeError(...)` when any such ID exists.
- Additional development-only invariant before repair:
  `planned_mode_executions != 30 or max_mode_executions != 30` raises.

## Why It Was Correct For Development Runs

The development integration run contains exactly 10 `DEV_*` cases, three modes,
one repetition, and 30 planned mode executions. For that path, rejecting
`HELD_*` IDs prevents accidental held-out contamination and keeps development
artifacts from being mistaken for publication-ready held-out results.

## Why It Blocked An Authorized Held-Out Run

Protocol v2 held-out execution correctly requires 40 held-out cases, three
modes, and three repetitions, for 360 planned mode executions. The runner
validated the held-out spec but then still called the development-only plan
function. The function's `HELD_*` rejection and 30-execution invariant therefore
applied to an explicitly authorized held-out run, causing the blocker class:

`FROZEN_RUNNER_PROTOCOL_V2_EXECUTION_PLAN_GUARD_INCONSISTENCY`

## Minimal Correction

The repair keeps the development plan strict and development-only, but routes
held-out plan construction through the execution-spec path:

- development execution uses `_development_execution_plan`;
- development case IDs must be `DEV_*`;
- development execution refuses `--allow-heldout`;
- `heldout_pilot_v1` is explicitly retired and cannot execute;
- `heldout_pilot_v2` plan-only validation reads metadata/checksums only and
  performs no retrieval, embedding, adapter execution, generation, or scoring;
- `heldout_pilot_v2` execution requires `--allow-heldout`, `--allow-real-api`,
  `HELDOUT_EXECUTION_SPEC_v3.json`, matching dataset/protocol checksums, an
  empty output directory, a matching authorization artifact, and valid call caps
  before provider initialization.

No CFAF pipeline stage, adapter semantics, prompt, parser, scorer, statistical
analysis, latency logic, development result, or D1-D8 artifact is changed by the
repair.
