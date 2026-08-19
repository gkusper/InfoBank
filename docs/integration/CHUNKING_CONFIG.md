# Page-aware Chunking Configuration

## Processing configuration

- Config version: `infocom-a1-v1`.
- Extraction: PyMuPDF with recorded binding version.
- Page policy: preserve one-based pages; empty pages count in statistics and create no chunks.
- Strategy: fixed character windows within one page.
- Default chunk size: 1000 characters.
- Default overlap: 200 characters.
- Separator policy: character offsets, never cross a page boundary.
- Embedding model: `text-embedding-3-small`.
- Config hash: SHA-256 of canonical, sorted, compact JSON for the entire processing configuration.

Invalid sizes, negative overlap, or overlap greater than or equal to size are rejected before chunking.

## Trace fields

Every chunk records document ID, deterministic chunk ID, global chunk index, one-based page number, optional block index, page-relative `[char_start, char_end)` range, content SHA-256, source SHA-256, config version/hash, and vector ID.

The Chroma metadata contains:

```text
document_id, chunk_id, chunk_index, page_number, block_index,
char_start, char_end, config_hash, content_hash, source_sha256
```

Chunk IDs are UUIDv5 values derived from document ID, page, offsets, content hash, and config hash. Unchanged source/config therefore produces stable IDs. Re-index snapshots the current document vectors, installs the deterministic replacement set, and restores the snapshot if vector work or the MariaDB commit fails. A changed config produces a different set.

## Citations

Full-content sources expose a structured citation with page, chunk, offsets, content hash, effective decision, evidence role, and repository-relative API URL. Metadata, Aggregate, and Deny decisions receive no raw source reference. Local storage paths are never serialized.

## Current limitations

- Character windows do not yet perform semantic boundary optimization.
- Block indices are recorded only when PyMuPDF block text can be mapped reliably into page text.
- OCR for image-only PDFs is not included.
- Phase A2 routing/hard-negative ablation is not included.
- There is no distributed transaction or general orphan scanner across MariaDB, Chroma, and the filesystem. Operations use tested snapshot/staging compensation; UUID-scoped staged-source cleanup has a repair helper.
