# Shared Retrieval Root-Cause Report v1

## Exact Location

The defect is in `evaluation/wolala2026/run_pilot.py`, function `run_pilot`.

The relevant helper is `_real_retrieval_snapshot(case, active_provider)`, which
performs the query embedding through `provider.embed_query(case["query"])` and
then builds the retrieval snapshot.

## Old Control Flow

Before this repair, the runner used this structure:

```text
for repetition in repetitions:
    for case in cases:
        snapshot = retrieve(case)
        for mode in modes:
            execute_mode(case, repetition, mode, snapshot)
```

This made retrieval shared across modes within a single repetition, but not
shared across repetitions.

## Why One-Repetition Tests Missed It

The development and real-API integration tests covered `repetitions = 1`.
With one repetition, the defective loop still produces one retrieval snapshot
per case and the same snapshot hash across all three modes. The defect becomes
visible only when `repetitions > 1`, because the outer repetition loop causes
the same case to be embedded and snapshotted again.

## Expected Formula

For `N` unique cases, `M` modes, and `R` repetitions:

- logical retrieval requests: `N`
- embedding attempts without retry: `N`
- retrieval snapshots: `N`
- result records: `N * M * R`
- snapshot references: `N * M * R`
- unique snapshot hashes per case: `1`

For the WoLaLa held-out design:

- `N = 40`
- `M = 3`
- `R = 3`
- logical retrieval requests: `40`
- result records: `360`
- snapshot references: `360`

## Failed-Run Formula

The failed run followed:

```text
embedding attempts = N * repetition_prefix_completed
```

It completed one full repetition for 40 cases and then 20 more case retrievals
in the second repetition:

```text
40 + 20 = 60 embedding attempts
```

The next case would have requested embedding attempt 61, so the hard cap
stopped the run.

## Relation To The 60-Call Cap

Protocol v3 froze `planned_unique_embedding_requests = 40` and
`max_embedding_calls = 60`. The cap allowed 20 retry-slack embedding attempts,
not a second and third full repetition of embeddings. Because the runner
multiplied embeddings by repetition, the 60-call cap was exhausted before the
61st request.

## Effect On Snapshot Hashes

The real-API retrieval snapshot included embedding response metadata and timing
fields. Recomputing retrieval in a later repetition created a new snapshot hash
for the same case. The failed run therefore produced multiple
`retrieval_snapshot_hash` values for cases that reached more than one
repetition.

## Effect On Latency Measurement

Shared retrieval latency was intended to be measured once per case and then
referenced by every mode/repetition record for that case. The old loop measured
retrieval latency once per case per repetition, inflating external call counts
and changing latency observations across repetitions.

## Effect On Repetition Aggregation

The frozen statistical plan requires three repetitions per case and mode before
majority or any-event aggregation. Because the cap stopped the run after 180 of
360 planned mode executions, no case had all three repetitions and no
confirmatory aggregation was valid.

## Minimal Repair

Move retrieval outside the repetition loop and keep a case-keyed immutable
snapshot cache. Execute all repetitions and modes from the same snapshot.

Before:

```text
for repetition in repetitions:
    for case in cases:
        snapshot = retrieve(case)
        for mode in modes:
            execute_mode(case, repetition, mode, snapshot)
```

After:

```text
for case in cases:
    shared_snapshot = retrieve_once(case)

    for repetition in repetitions:
        for mode in modes:
            execute_mode(
                case=case,
                repetition=repetition,
                mode=mode,
                retrieval_snapshot=shared_snapshot,
            )
```

The repair does not change prompts, parser behavior, scorer behavior, mode
selection, labels, response contracts, statistical definitions, latency
definitions, or dataset contents.
