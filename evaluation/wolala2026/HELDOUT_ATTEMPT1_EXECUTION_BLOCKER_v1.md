# WoLaLa 2026 Held-out Attempt 1 Execution Blocker

- Timestamp UTC: `2026-08-22T15:12:16Z`
- Authorization commit: `29e6e84a3b81c407f17183b2417ba9678921b3ea`
- Authorization tag: `wolala2026-heldout-attempt1-authorized`
- Freeze commit: `182f9d6c256526701ead65901fed0e90e2ff5e6a`

## Status

STOPPED_BEFORE_HELDOUT_MODEL_EXECUTION.

No held-out retrieval, embedding, generation, scoring, or raw-result writing was performed. The output directory exists only as an empty directory created before the guard raised; file count is `0`.

## Blocker

The frozen runner accepts the held-out Protocol v2 execution spec and requires `--allow-heldout` plus `--allow-real-api`, but then calls the legacy development-only `_execution_plan` path. That path rejects every `HELD_*` case ID and raises:

```text
RuntimeError: Plan contains held-out case IDs and cannot proceed: [...]
```

Because this occurs before provider initialization, external API calls executed: `0`.

## Next Required Action

Freeze a new protocol/runner revision that permits `heldout_pilot_v1` execution after explicit `--allow-heldout` and `--allow-real-api`, then repeat authorization under the new freeze. Do not rerun this failed command under Protocol v2 without a new freeze; the frozen runner cannot reach provider execution for `HELD_*` cases.
