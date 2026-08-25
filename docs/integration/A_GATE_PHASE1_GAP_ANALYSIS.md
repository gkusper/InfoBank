# A-GATE Phase A1 Gap Analysis

Starting branch: `feature/infocom-a-gate`
Starting commit: `077c85c44f570c6a6b3f15edcd584f834f335ea1`

This is an implementation audit for Phase A1. Phase A2 routing ablation and the final W1/W2 demonstration are outside this scope.

| Capability | Current behavior before A1 | Module / endpoint | Exact gap | Minimal A1 implementation | Planned evidence | Migration impact | Compatibility risk |
|---|---|---|---|---|---|---|---|
| A1 durable PDF source | Filename only; uploaded bytes discarded | `routers/documents.py`, `POST /api/upload` | No recoverable original or integrity record | UUID namespace, atomic PDF write, SHA-256, size/MIME/status, compensated delete | Storage and lifecycle tests | New nullable document fields | Low; existing filename response retained |
| A2 metadata/keyword provenance | Keywords stored without origin; metadata implicit | Upload and keyword-edit endpoints | Cannot distinguish extracted, rule, AI, or user values | Field-level provenance table and provenance-bearing keyword relation | Fallback, merge, user-preservation, 100% field-coverage tests | New table and join columns | Medium; existing keyword list retained |
| A3 page/offset chunking | All pages concatenated before 1000/200 chunking | `ai_service.chunk_text`, upload | Chunks cannot identify page or source offsets | Page-preserving extraction and within-page deterministic chunks | Generated one/multi/empty-page tests | Chunk trace columns | Low; legacy helper retained |
| A4 versioned config/statistics | Parameters hidden in helper defaults | `ai_service.py` | No version/hash or reproducibility report | Immutable serializable config, SHA-256 hash, persisted processing report | Hash/validation/statistics tests | Report table and document fields | Low; defaults remain 1000/200 |
| A5 idempotent re-index | No source and no complete re-index operation | None | Repeated processing can duplicate or cannot be reproduced | Owner endpoint, source-integrity check, deterministic chunk IDs, snapshot-compensated vector/chunk replacement | Same/config-change/mismatch and failure-injection tests | Uses new source/config fields | Medium; provider remains current OpenAI adapter and no distributed transaction exists |
| A6 page/chunk citation | Filename/document ID plus text | `routers/chat.py`, `POST /api/ask` | No page, offsets, chunk/hash or view reference | Structured citation built from DB chunk and safe API URL | Citation serialization and page tests | No separate table | Low; existing source fields retained |
| A7 source viewing/traceability | No source endpoint | None | Authorized users cannot inspect cited source | Governed source/page endpoint; metadata-only response; aggregate/deny withholding | Owner/Reader/Metadata/Aggregate/Deny tests | Durable source required | Medium; new endpoint only |
| A8 tests/docs/artifacts | R1B generic gate only | `backend_python/tests`, `docs/integration` | No A1 proof or synthetic workflow | Focused tests, migration, pipeline docs, ignored deterministic demo generator | Local gates and MariaDB migration smoke | New migration | Low |

## Compatibility decisions

- `Document.file_path` and the existing `file_name` response remain available; new code treats them as compatibility filename fields, never as a local storage path.
- `ai_service.chunk_text` remains unchanged for callers outside ingestion.
- Existing upload response fields remain and are extended with trace/report fields.
- Permanent delete remains explicit; archive and restore are separate owner-only endpoints.
- No local absolute storage path is returned by an API.
