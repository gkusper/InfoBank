from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest
from fastapi import HTTPException

import models
import relevance
from document_processing import ProcessingConfig, chunk_pages, extract_pdf_pages, sha256_bytes, sha256_text
from routers import chat, documents
from source_storage import SourceStorage


DOCUMENT_ID = "00000000-0000-0000-0000-000000000040"
OWNER_ID = "00000000-0000-0000-0000-000000000041"
READER_ID = "00000000-0000-0000-0000-000000000042"
METADATA_ID = "00000000-0000-0000-0000-000000000043"
AGGREGATE_ID = "00000000-0000-0000-0000-000000000044"


def make_pdf(*pages: str) -> bytes:
    pdf = fitz.open()
    for text in pages:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    payload = pdf.tobytes()
    pdf.close()
    return payload


def add_document_with_permissions(db_session, source: bytes, storage: SourceStorage) -> models.Document:
    for user_id, username in (
        (OWNER_ID, "owner"),
        (READER_ID, "reader"),
        (METADATA_ID, "metadata"),
        (AGGREGATE_ID, "aggregate"),
    ):
        db_session.add(models.User(id=user_id, email=f"{username}@example.invalid", username=username, password_hash="not-used"))
    stored = storage.save(DOCUMENT_ID, source)
    document = models.Document(
        id=DOCUMENT_ID,
        file_path="synthetic-guide.pdf",
        original_filename="synthetic-guide.pdf",
        source_storage_path=stored.relative_path,
        source_sha256=stored.sha256,
        source_mime_type="application/pdf",
        source_byte_size=stored.byte_size,
        page_count=2,
        source_status="ACTIVE",
        processing_status="COMPLETE",
        visibility="Private",
    )
    db_session.add(document)
    for index, (user_id, permission) in enumerate(
        (
            (OWNER_ID, models.PermissionType.Owner),
            (READER_ID, models.PermissionType.Reader),
            (METADATA_ID, models.PermissionType.Metadata),
            (AGGREGATE_ID, models.PermissionType.Aggregate),
        )
    ):
        db_session.add(
            models.UserDocumentPermission(
                id=f"00000000-0000-0000-0000-00000000005{index}",
                user_id=user_id,
                document_id=DOCUMENT_ID,
                permission_type=permission,
            )
        )
    db_session.flush()
    return document


def test_citation_points_to_exact_page_chunk_and_contains_no_local_path(db_session, tmp_path: Path) -> None:
    source = make_pdf("Synthetic first page setup.", "Synthetic second page warranty.")
    storage = SourceStorage(tmp_path / "sources")
    document = add_document_with_permissions(db_session, source, storage)
    extraction = extract_pdf_pages(source)
    chunks = chunk_pages(DOCUMENT_ID, extraction.pages, ProcessingConfig(chunk_size=20, overlap=5))
    target = next(chunk for chunk in chunks if chunk.page_number == 2)
    row = models.DocumentChunk(
        id=target.id,
        document_id=DOCUMENT_ID,
        chunk_index=target.chunk_index,
        page_number=target.page_number,
        block_index=target.block_index,
        char_start=target.char_start,
        char_end=target.char_end,
        text_content=target.text,
        content_sha256=target.content_hash,
        source_sha256=sha256_bytes(source),
        chunk_config_version=target.config_version,
        chunk_config_hash=target.config_hash,
        vector_id=target.id,
    )
    db_session.add(row)
    db_session.flush()
    citation = chat.citation_from_chunk(document, row, relevance.USE_FULL)
    assert citation["page_number"] == 2
    assert citation["chunk_id"] == target.id
    assert citation["char_start"] == target.char_start
    assert citation["char_end"] == target.char_end
    serialized = json.dumps(citation)
    assert str(tmp_path) not in serialized
    assert "source_storage" not in serialized


def test_source_view_authorization_matrix_and_page_response(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf("Synthetic first page.", "Synthetic second page.")
    storage = SourceStorage(tmp_path / "sources")
    add_document_with_permissions(db_session, source, storage)
    monkeypatch.setattr(documents, "source_storage", storage)

    owner_page = documents.view_document_source(DOCUMENT_ID, page=2, user_id=OWNER_ID, db=db_session)
    reader_page = documents.view_document_source(DOCUMENT_ID, page=1, user_id=READER_ID, db=db_session)
    metadata = documents.view_document_source(DOCUMENT_ID, page=None, user_id=METADATA_ID, db=db_session)
    assert owner_page["page_number"] == 2 and "second" in owner_page["text"].lower()
    assert reader_page["page_number"] == 1
    assert metadata["status"] == "metadata_only"
    assert "text" not in metadata

    with pytest.raises(HTTPException) as aggregate_error:
        documents.view_document_source(DOCUMENT_ID, page=None, user_id=AGGREGATE_ID, db=db_session)
    assert aggregate_error.value.status_code == 403

    db_session.add(
        models.PolicyRule(
            id="00000000-0000-0000-0000-000000000060",
            owner_user_id=OWNER_ID,
            target_type="Document",
            target_id=DOCUMENT_ID,
            purpose="source_view",
            access_mode=models.PolicyAccessMode.Deny,
        )
    )
    db_session.flush()
    with pytest.raises(HTTPException) as deny_error:
        documents.view_document_source(DOCUMENT_ID, page=None, user_id=OWNER_ID, db=db_session)
    assert deny_error.value.status_code == 404

    with pytest.raises(HTTPException) as missing_error:
        documents.view_document_source("00000000-0000-0000-0000-000000000099", page=None, user_id=OWNER_ID, db=db_session)
    assert missing_error.value.status_code == 404


def test_non_full_citation_never_exposes_raw_source_reference() -> None:
    for decision in (relevance.USE_AGGREGATE, relevance.USE_METADATA, relevance.USE_DENY):
        citation = chat.citation_from_chunk(None, None, decision)
        assert citation == {"available": False, "reason": "raw_source_not_permitted"}


def test_legacy_full_source_without_page_trace_has_no_invalid_view_url() -> None:
    document = models.Document(id=DOCUMENT_ID, file_path="legacy.pdf", source_status="ACTIVE")
    chunk = models.DocumentChunk(
        id="00000000-0000-0000-0000-000000000061",
        document_id=DOCUMENT_ID,
        chunk_index=0,
        text_content="Legacy chunk",
        vector_id="legacy-vector",
    )
    citation = chat.citation_from_chunk(document, chunk, relevance.USE_FULL)
    assert citation == {"available": False, "reason": "traceability_unavailable"}


def test_citation_rejects_chunk_from_a_different_document() -> None:
    document = models.Document(
        id=DOCUMENT_ID,
        file_path="synthetic.pdf",
        source_storage_path=f"{DOCUMENT_ID}/source.pdf",
        source_status="ACTIVE",
    )
    chunk = models.DocumentChunk(
        id="00000000-0000-0000-0000-000000000062",
        document_id="00000000-0000-0000-0000-000000000099",
        chunk_index=0,
        page_number=1,
        char_start=0,
        char_end=5,
        text_content="Other",
        content_sha256="a" * 64,
        vector_id="other-vector",
    )
    assert chat.citation_from_chunk(document, chunk, relevance.USE_FULL) == {
        "available": False,
        "reason": "traceability_unavailable",
    }


@pytest.mark.parametrize("with_sql_chunk", [False, True])
def test_retrieval_rejects_orphan_or_content_mismatched_vector(
    db_session, monkeypatch, with_sql_chunk: bool
) -> None:
    document_id = "retrieval-integrity-doc"
    chunk_id = "retrieval-integrity-chunk"
    canonical_text = "Canonical permitted warranty text."
    vector_text = "STALE SECRET VECTOR TEXT"
    document = models.Document(
        id=document_id,
        file_path="integrity.pdf",
        source_status="ACTIVE",
        visibility="Private",
        source_sha256="1" * 64,
    )
    db_session.add(document)
    if with_sql_chunk:
        db_session.add(models.DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            chunk_index=0,
            page_number=1,
            char_start=0,
            char_end=len(canonical_text),
            text_content=canonical_text,
            content_sha256=sha256_text(canonical_text),
            source_sha256=document.source_sha256,
            chunk_config_hash="2" * 64,
            vector_id=chunk_id,
        ))
    db_session.flush()

    class Collection:
        @staticmethod
        def query(**_kwargs):
            return {
                "ids": [[chunk_id]],
                "documents": [[vector_text]],
                "metadatas": [[{
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "content_hash": sha256_text(vector_text),
                    "source_sha256": document.source_sha256,
                    "config_hash": "2" * 64,
                }]],
            }

    monkeypatch.setattr(chat.ai_service, "collection", Collection())
    governance = {
        "source_roles": {document_id: relevance.SOURCE_ROLE_PRIMARY},
        "use_decisions": {document_id: relevance.USE_FULL},
    }
    sources, blocks, contributions = chat.query_retrieved_sources(
        db_session,
        "What is the warranty?",
        [0.0],
        {"task_intent": "general_document_question"},
        governance,
        [document_id],
    )
    assert sources == []
    assert blocks == []
    assert contributions == []
    assert governance["integrity_reason_code"] == "stale_index_denied"
    assert governance["stale_index_rejections"][0]["reason"] == (
        "content_hash_mismatch" if with_sql_chunk else "missing_sql_chunk"
    )
    assert vector_text not in json.dumps({"sources": sources, "blocks": blocks})
