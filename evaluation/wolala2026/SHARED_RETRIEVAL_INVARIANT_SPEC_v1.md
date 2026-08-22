# Shared Retrieval Invariant Specification v1

## SR1 - One Logical Retrieval Per Unique Case

For a run with `N` unique cases:

```text
planned_logical_retrieval_requests = N
```

This value is independent of the number of modes and repetitions.

## SR2 - One Immutable Snapshot Per Case

For a given case:

```text
unique(retrieval_snapshot_hash) = 1
```

across all modes and repetitions.

## SR3 - Reuse Count

For `M` modes and `R` repetitions, each case snapshot must be referenced by:

```text
M * R
```

result records. For the WoLaLa design, `3 * 3 = 9` references per case.

## SR4 - Call Accounting

Without retries:

```text
actual_embedding_attempts = number_of_unique_cases
```

With retries:

```text
actual_embedding_attempts =
    number_of_unique_cases + embedding_retry_attempts
```

The manifest distinguishes planned logical embedding requests, successful
logical embedding requests, actual provider attempts, retry attempts, cache
hits, snapshot count, and snapshot reuse count.

## SR5 - Cap Planning

A real-API run must be rejected before provider initialization when:

```text
max_embedding_calls < planned_unique_embedding_requests
```

The repetition count must not multiply the required embedding cap.

## SR6 - Latency

`shared_retrieval_ms` is measured once per case. Each mode/repetition record
may reference the same shared retrieval duration, but retrieval must not
execute again.

```text
user_visible_end_to_end_ms =
    shared_retrieval_ms + mode_processing_ms
```

## SR7 - No Mode-Specific Retrieval

All compared modes receive exactly the same candidate IDs, candidate order,
source text, metadata, retrieval scores, and snapshot hash for a case.

## SR8 - No Gold Contamination

Gold labels and expected CFAF outcomes must not influence retrieval.
