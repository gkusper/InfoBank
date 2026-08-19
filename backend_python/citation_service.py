"""Traceable citation construction shared by API and evaluation workflows."""

from __future__ import annotations

from typing import Any

import relevance


def citation_from_chunk(document: Any | None, chunk: Any | None, use_decision: str) -> dict:
    if use_decision != relevance.USE_FULL or not document or not chunk:
        return {"available": False, "reason": "raw_source_not_permitted"}
    if (
        not document.source_storage_path
        or chunk.document_id != document.id
        or chunk.page_number is None
        or chunk.char_start is None
        or chunk.char_end is None
        or chunk.char_start < 0
        or chunk.char_end <= chunk.char_start
        or not chunk.content_sha256
    ):
        return {"available": False, "reason": "traceability_unavailable"}
    return {
        "available": True,
        "document_id": document.id,
        "chunk_id": chunk.id,
        "original_filename": document.original_filename or document.file_path,
        "page_number": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "content_hash": chunk.content_sha256,
        "source_view_url": f"/api/documents/{document.id}/source?page={chunk.page_number}",
        "evidence_role": relevance.SOURCE_ROLE_PRIMARY,
        "effective_use_decision": use_decision,
    }
