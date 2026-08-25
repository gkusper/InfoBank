from __future__ import annotations

import asyncio
import json
from pathlib import Path

import fitz
import pytest
from fastapi import HTTPException

import models
import policy_engine
from document_processing import ProcessingConfig, sha256_bytes
from routers import documents
from source_storage import SourceStorage


USER_ID = "00000000-0000-0000-0000-000000000030"
DOCUMENT_ID = "00000000-0000-0000-0000-000000000031"


def make_pdf(text: str = "Synthetic setup instructions and warranty details.") -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    payload = pdf.tobytes()
    pdf.close()
    return payload


class FakeCollection:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def delete(self, *, where: dict) -> None:
        document_id = where["document_id"]
        self.records = {
            key: value for key, value in self.records.items() if value["metadata"]["document_id"] != document_id
        }

    def add(self, *, ids, embeddings, metadatas, documents) -> None:
        for record_id, embedding, metadata, text in zip(ids, embeddings, metadatas, documents):
            self.records[record_id] = {"embedding": embedding, "metadata": metadata, "text": text}

    def get(self, *, where: dict, include: list[str]) -> dict:
        records = [
            (record_id, record)
            for record_id, record in self.records.items()
            if record["metadata"]["document_id"] == where["document_id"]
        ]
        return {
            "ids": [record_id for record_id, _record in records],
            "embeddings": [record["embedding"] for _record_id, record in records],
            "metadatas": [record["metadata"] for _record_id, record in records],
            "documents": [record["text"] for _record_id, record in records],
        }


def configure_processing(monkeypatch: pytest.MonkeyPatch, collection: FakeCollection) -> None:
    monkeypatch.setattr(documents.ai_service, "collection", collection)
    monkeypatch.setattr(documents, "_keyword_client", lambda: None)
    monkeypatch.setattr(
        documents,
        "_embed_chunks",
        lambda chunks, _model: {chunk.id: [float(index), 1.0] for index, chunk in enumerate(chunks)},
    )


def add_user_and_document(db_session, source: bytes) -> models.Document:
    db_session.add(models.User(id=USER_ID, email="a1@example.invalid", username="a1-user", password_hash="not-used"))
    document = models.Document(
        id=DOCUMENT_ID,
        file_path="synthetic.pdf",
        original_filename="synthetic.pdf",
        source_storage_path=f"{DOCUMENT_ID}/source.pdf",
        source_sha256=sha256_bytes(source),
        source_mime_type="application/pdf",
        source_byte_size=len(source),
        source_status="ACTIVE",
        processing_status="PENDING",
        visibility="Private",
    )
    db_session.add(document)
    db_session.add(
        models.UserDocumentPermission(
            id="00000000-0000-0000-0000-000000000032",
            user_id=USER_ID,
            document_id=DOCUMENT_ID,
            permission_type=models.PermissionType.Owner,
        )
    )
    db_session.flush()
    return document


def test_same_source_and_config_reindex_is_idempotent_and_preserves_user_data(db_session, monkeypatch) -> None:
    source = make_pdf("Synthetic setup guide. Approval instructions. " * 60)
    document = add_user_and_document(db_session, source)
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)

    first = documents.process_document_source(
        db=db_session,
        document=document,
        source_bytes=source,
        user_id=USER_ID,
        operation="reindex",
        preserve_user=True,
    )
    db_session.flush()
    first_ids = [row.id for row in db_session.query(models.DocumentChunk).order_by(models.DocumentChunk.chunk_index).all()]
    first_hashes = [row.content_sha256 for row in db_session.query(models.DocumentChunk).order_by(models.DocumentChunk.chunk_index).all()]
    provenance_fields = {
        row.field_name
        for row in db_session.query(models.DocumentMetadataProvenance).filter(
            models.DocumentMetadataProvenance.document_id == DOCUMENT_ID
        ).all()
    }
    assert provenance_fields == {
        "original_filename",
        "source_storage_path",
        "mime_type",
        "source_sha256",
        "source_byte_size",
        "page_count",
        "pdf_title",
        "pdf_author",
        "pdf_creation_date",
        "processing_config_version",
        "processing_config_hash",
        "source_status",
        "processing_status",
        "visibility",
        "source_url",
        "source_license",
    }
    keyword_relation = db_session.query(models.DocumentKeyword).first()
    keyword_relation.user_edited = True
    keyword_relation.provenance_type = models.ProvenanceType.User
    keyword_relation.provenance_json = json.dumps([{"type": "USER", "method": "test-owner-edit"}])
    db_session.add(
        models.DocumentMetadataProvenance(
            id="00000000-0000-0000-0000-000000000033",
            document_id=DOCUMENT_ID,
            field_name="pdf_title",
            field_value="Owner title",
            provenance_type=models.ProvenanceType.User,
            method="owner-metadata-edit",
        )
    )
    db_session.flush()

    second = documents.process_document_source(
        db=db_session,
        document=document,
        source_bytes=source,
        user_id=USER_ID,
        operation="reindex",
        preserve_user=True,
    )
    db_session.flush()
    second_rows = db_session.query(models.DocumentChunk).order_by(models.DocumentChunk.chunk_index).all()

    assert [row.id for row in second_rows] == first_ids
    assert [row.content_sha256 for row in second_rows] == first_hashes
    assert len(collection.records) == len(first_ids)
    assert first["chunk_count"] == second["chunk_count"] == len(first_ids)
    assert first["keyword_model"] is None
    assert first["keyword_prompt_version"] is None
    assert first["configured_keyword_prompt_version"] == ProcessingConfig().keyword_prompt_version
    assert db_session.query(models.DocumentKeyword).filter(models.DocumentKeyword.user_edited.is_(True)).count() == 1
    user_title = db_session.query(models.DocumentMetadataProvenance).filter(
        models.DocumentMetadataProvenance.field_name == "pdf_title",
        models.DocumentMetadataProvenance.provenance_type == models.ProvenanceType.User,
    ).one()
    assert user_title.field_value == "Owner title"
    assert document.pdf_title == "Owner title"
    assert second["keyword_count_by_provenance"]["USER"] == 1


def test_changed_config_replaces_chunks_and_source_mismatch_stops_processing(db_session, monkeypatch) -> None:
    source = make_pdf("Synthetic reference instructions. " * 80)
    document = add_user_and_document(db_session, source)
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    documents.process_document_source(
        db=db_session,
        document=document,
        source_bytes=source,
        user_id=USER_ID,
        operation="reindex",
    )
    db_session.flush()
    first_ids = {row.id for row in db_session.query(models.DocumentChunk).all()}

    changed = ProcessingConfig(chunk_size=300, overlap=50)
    documents.process_document_source(
        db=db_session,
        document=document,
        source_bytes=source,
        user_id=USER_ID,
        operation="reindex",
        config=changed,
    )
    db_session.flush()
    second_ids = {row.id for row in db_session.query(models.DocumentChunk).all()}
    assert second_ids
    assert second_ids.isdisjoint(first_ids)
    assert document.processing_config_hash == changed.config_hash
    assert set(collection.records) == second_ids

    document.source_sha256 = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        documents.process_document_source(
            db=db_session,
            document=document,
            source_bytes=source,
            user_id=USER_ID,
            operation="reindex",
        )


class FakeUpload:
    filename = "../unsafe-name.pdf"
    content_type = "application/pdf"

    def __init__(self, content: bytes, *, filename: str | None = None, content_type: str | None = None) -> None:
        self.content = content
        if filename is not None:
            self.filename = filename
        if content_type is not None:
            self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        return self.content if size < 0 else self.content[:size]


@pytest.mark.parametrize(
    ("filename", "content_type", "message"),
    [
        ("document.txt", "application/pdf", "Only .pdf"),
        ("document.pdf", "text/plain", "MIME type"),
    ],
)
def test_upload_rejects_invalid_extension_or_mime_before_persistence(
    db_session, monkeypatch, tmp_path: Path, filename: str, content_type: str, message: str
) -> None:
    source = make_pdf()
    storage = SourceStorage(tmp_path / "sources")
    monkeypatch.setattr(documents, "source_storage", storage)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(documents.upload_document(
            file=FakeUpload(source, filename=filename, content_type=content_type),
            permission_type=models.PermissionType.Owner,
            source_url=None,
            source_license=None,
            user_id=USER_ID,
            db=db_session,
        ))
    assert exc.value.status_code == 400
    assert message in exc.value.detail
    assert not storage.root.exists()


def test_upload_rejects_configured_size_limit_before_persistence(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf()
    storage = SourceStorage(tmp_path / "sources")
    monkeypatch.setattr(documents, "source_storage", storage)
    monkeypatch.setenv("MAX_UPLOAD_BYTES", str(len(source) - 1))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(documents.upload_document(
            file=FakeUpload(source),
            permission_type=models.PermissionType.Owner,
            source_url=None,
            source_license=None,
            user_id=USER_ID,
            db=db_session,
        ))
    assert exc.value.status_code == 400
    assert "exceeds" in exc.value.detail
    assert not storage.root.exists()


def test_upload_survives_keyword_provider_failure_and_creates_index(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf()
    db_session.add(models.User(id=USER_ID, email="upload@example.invalid", username="upload-user", password_hash="not-used"))
    db_session.flush()
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    monkeypatch.setattr(documents, "source_storage", SourceStorage(tmp_path / "sources"))

    result = asyncio.run(
        documents.upload_document(
            file=FakeUpload(source),
            permission_type=models.PermissionType.Owner,
            source_url=None,
            source_license=None,
            user_id=USER_ID,
            db=db_session,
        )
    )
    document = db_session.query(models.Document).filter(models.Document.id == result["document_id"]).one()
    assert result["status"] == "success"
    assert result["keyword_extraction_mode"] == "deterministic_fallback"
    assert result["chunk_count"] > 0
    assert document.original_filename == "unsafe-name.pdf"
    assert document.source_storage_path == f"{document.id}/source.pdf"
    assert collection.records


def test_archive_restore_is_idempotent_and_source_survives(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf("Synthetic archive and restore instructions.")
    storage = SourceStorage(tmp_path / "sources")
    stored = storage.save(DOCUMENT_ID, source)
    document = add_user_and_document(db_session, source)
    document.source_storage_path = stored.relative_path
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    monkeypatch.setattr(documents, "source_storage", storage)
    documents.process_document_source(
        db=db_session,
        document=document,
        source_bytes=source,
        user_id=USER_ID,
        operation="upload",
    )
    db_session.commit()

    archived = documents.archive_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert archived["source_status"] == "ARCHIVED"
    assert storage.exists(stored.relative_path)
    assert db_session.query(models.DocumentChunk).count() == 0
    assert collection.records == {}
    assert policy_engine.resolve_document_access(db_session, USER_ID, DOCUMENT_ID)["reason"] == "document_archived"
    assert documents.archive_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)["idempotent"] is True

    restored = documents.restore_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert restored["source_status"] == "ACTIVE"
    assert db_session.query(models.DocumentChunk).count() > 0
    assert documents.restore_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)["idempotent"] is True


def test_lifecycle_requires_owner(db_session, monkeypatch) -> None:
    source = make_pdf()
    add_user_and_document(db_session, source)
    other_id = "00000000-0000-0000-0000-000000000039"
    db_session.add(models.User(id=other_id, email="other@example.invalid", username="other-user", password_hash="not-used"))
    db_session.flush()
    with pytest.raises(HTTPException) as exc:
        documents.archive_document(DOCUMENT_ID, user_id=other_id, db=db_session)
    assert exc.value.status_code == 403


def test_metadata_keyword_and_visibility_updates_are_owner_only_and_provenanced(db_session) -> None:
    source = make_pdf()
    add_user_and_document(db_session, source)
    other_id = "00000000-0000-0000-0000-000000000039"
    db_session.add(models.User(id=other_id, email="editor@example.invalid", username="editor", password_hash="not-used"))
    db_session.flush()
    with pytest.raises(HTTPException) as metadata_error:
        documents.update_document_metadata(DOCUMENT_ID, title="Denied", user_id=other_id, db=db_session)
    assert metadata_error.value.status_code == 403
    with pytest.raises(HTTPException) as keyword_error:
        documents.update_keywords(DOCUMENT_ID, "denied", user_id=other_id, db=db_session)
    assert keyword_error.value.status_code == 403

    result = documents.update_permission(DOCUMENT_ID, "Metadata", user_id=USER_ID, db=db_session)
    assert result["visibility"] == "Metadata"
    provenance = db_session.query(models.DocumentMetadataProvenance).filter(
        models.DocumentMetadataProvenance.document_id == DOCUMENT_ID,
        models.DocumentMetadataProvenance.field_name == "visibility",
    ).one()
    assert provenance.provenance_type == models.ProvenanceType.User
    assert provenance.field_value == "Metadata"
    assert provenance.method == "owner-permission-edit"


def test_permanent_delete_removes_database_vectors_and_durable_source(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf("Synthetic permanent deletion test source.")
    storage = SourceStorage(tmp_path / "sources")
    stored = storage.save(DOCUMENT_ID, source)
    document = add_user_and_document(db_session, source)
    document.source_storage_path = stored.relative_path
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    monkeypatch.setattr(documents, "source_storage", storage)
    documents.process_document_source(
        db=db_session,
        document=document,
        source_bytes=source,
        user_id=USER_ID,
        operation="upload",
    )
    db_session.commit()
    result = documents.delete_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert result["status"] == "success"
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).count() == 0
    assert db_session.query(models.DocumentChunk).count() == 0
    assert collection.records == {}
    assert not storage.exists(stored.relative_path)


def test_permanent_delete_failure_preserves_source_and_database(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf("Synthetic compensated deletion test source.")
    storage = SourceStorage(tmp_path / "sources")
    stored = storage.save(DOCUMENT_ID, source)
    document = add_user_and_document(db_session, source)
    document.source_storage_path = stored.relative_path
    db_session.commit()

    class FailingCollection(FakeCollection):
        def delete(self, **_kwargs):
            raise RuntimeError("synthetic vector cleanup failure")

    monkeypatch.setattr(documents.ai_service, "collection", FailingCollection())
    monkeypatch.setattr(documents, "source_storage", storage)
    with pytest.raises(HTTPException) as exc:
        documents.delete_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 500
    assert storage.exists(stored.relative_path)
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).count() == 1


class PartiallyFailingAddCollection(FakeCollection):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_add = False

    def add(self, *, ids, embeddings, metadatas, documents) -> None:
        if self.fail_next_add:
            self.fail_next_add = False
            if ids:
                super().add(
                    ids=ids[:1],
                    embeddings=embeddings[:1],
                    metadatas=metadatas[:1],
                    documents=documents[:1],
                )
            raise RuntimeError("synthetic partial vector add failure")
        super().add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)


def prepare_durable_index(db_session, monkeypatch, tmp_path: Path, *, collection=None):
    source = make_pdf("Synthetic cross-store compensation instructions. " * 40)
    storage = SourceStorage(tmp_path / "sources")
    stored = storage.save(DOCUMENT_ID, source)
    document = add_user_and_document(db_session, source)
    document.source_storage_path = stored.relative_path
    collection = collection or FakeCollection()
    configure_processing(monkeypatch, collection)
    monkeypatch.setattr(documents, "source_storage", storage)
    documents.process_document_source(
        db=db_session,
        document=document,
        source_bytes=source,
        user_id=USER_ID,
        operation="upload",
    )
    db_session.commit()
    return source, storage, stored, document, collection


def test_upload_partial_vector_add_is_compensated_and_failure_is_preserved(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf("Synthetic partial upload failure source.")
    db_session.add(models.User(id=USER_ID, email="partial@example.invalid", username="partial", password_hash="not-used"))
    db_session.flush()
    collection = PartiallyFailingAddCollection()
    collection.fail_next_add = True
    configure_processing(monkeypatch, collection)
    storage = SourceStorage(tmp_path / "sources")
    monkeypatch.setattr(documents, "source_storage", storage)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            documents.upload_document(
                file=FakeUpload(source),
                permission_type=models.PermissionType.Owner,
                source_url=None,
                source_license=None,
                user_id=USER_ID,
                db=db_session,
            )
        )
    assert exc.value.status_code == 500
    assert collection.records == {}
    document = db_session.query(models.Document).one()
    assert document.processing_status == "FAILED"
    assert storage.exists(document.source_storage_path)
    assert exc.value.detail["document_id"] == document.id
    assert exc.value.detail["retry_url"] == f"/api/documents/{document.id}/reindex"


def test_upload_report_persistence_failure_preserves_source_and_failed_status(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf("Synthetic processing report failure source.")
    db_session.add(models.User(id=USER_ID, email="report@example.invalid", username="report", password_hash="not-used"))
    db_session.flush()
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    storage = SourceStorage(tmp_path / "sources")
    monkeypatch.setattr(documents, "source_storage", storage)
    original_add = db_session.add

    def fail_report_add(instance):
        if isinstance(instance, models.DocumentProcessingReport):
            raise RuntimeError("synthetic processing report persistence failure")
        return original_add(instance)

    monkeypatch.setattr(db_session, "add", fail_report_add)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            documents.upload_document(
                file=FakeUpload(source),
                permission_type=models.PermissionType.Owner,
                source_url=None,
                source_license=None,
                user_id=USER_ID,
                db=db_session,
            )
        )
    assert exc.value.status_code == 500
    assert collection.records == {}
    document = db_session.query(models.Document).one()
    assert document.processing_status == "FAILED"
    assert storage.exists(document.source_storage_path)


def test_upload_validation_fails_before_source_persistence(db_session, monkeypatch, tmp_path: Path) -> None:
    db_session.add(models.User(id=USER_ID, email="invalid@example.invalid", username="invalid", password_hash="not-used"))
    db_session.flush()
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    storage = SourceStorage(tmp_path / "sources")
    monkeypatch.setattr(documents, "source_storage", storage)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            documents.upload_document(
                file=FakeUpload(b"not-a-pdf"),
                permission_type=models.PermissionType.Owner,
                source_url=None,
                source_license=None,
                user_id=USER_ID,
                db=db_session,
            )
        )
    assert exc.value.status_code == 400
    assert not storage.root.exists()
    assert collection.records == {}


def test_upload_db_commit_failure_removes_source_database_and_vectors(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf("Synthetic upload commit failure source.")
    db_session.add(models.User(id=USER_ID, email="commit@example.invalid", username="commit", password_hash="not-used"))
    db_session.flush()
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    storage = SourceStorage(tmp_path / "sources")
    monkeypatch.setattr(documents, "source_storage", storage)
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("synthetic DB commit failure")))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            documents.upload_document(
                file=FakeUpload(source),
                permission_type=models.PermissionType.Owner,
                source_url=None,
                source_license=None,
                user_id=USER_ID,
                db=db_session,
            )
        )
    assert exc.value.status_code == 500
    assert collection.records == {}
    assert db_session.query(models.Document).count() == 0
    assert not storage.root.exists() or not any(storage.root.iterdir())


def test_upload_embedding_failure_preserves_retryable_document(db_session, monkeypatch, tmp_path: Path) -> None:
    source = make_pdf("Synthetic upload embedding failure source.")
    db_session.add(models.User(id=USER_ID, email="embedding@example.invalid", username="embedding", password_hash="not-used"))
    db_session.flush()
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    storage = SourceStorage(tmp_path / "sources")
    monkeypatch.setattr(documents, "source_storage", storage)
    monkeypatch.setattr(
        documents,
        "_embed_chunks",
        lambda _chunks, _model: (_ for _ in ()).throw(RuntimeError("synthetic embedding failure")),
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            documents.upload_document(
                file=FakeUpload(source),
                permission_type=models.PermissionType.Owner,
                source_url=None,
                source_license=None,
                user_id=USER_ID,
                db=db_session,
            )
        )
    assert exc.value.status_code == 500
    assert collection.records == {}
    document = db_session.query(models.Document).one()
    assert document.processing_status == "FAILED"
    assert storage.exists(document.source_storage_path)

    monkeypatch.setattr(
        documents,
        "_embed_chunks",
        lambda chunks, _model: {chunk.id: [float(index), 1.0] for index, chunk in enumerate(chunks)},
    )
    retried = documents.reindex_document(document.id, user_id=USER_ID, db=db_session)
    assert retried["status"] == "success"
    assert db_session.query(models.Document).one().processing_status == "COMPLETE"
    assert collection.records


def test_reindex_commit_failure_restores_previous_vectors_and_database(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, _storage, _stored, document, collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    previous_records = {key: dict(value) for key, value in collection.records.items()}
    previous_hash = document.processing_config_hash
    monkeypatch.setattr(
        documents,
        "_embed_chunks",
        lambda chunks, _model: {chunk.id: [99.0, float(index)] for index, chunk in enumerate(chunks)},
    )
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("synthetic DB commit failure")))
    with pytest.raises(HTTPException) as exc:
        documents.reindex_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 500
    assert collection.records == previous_records
    refreshed = db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).one()
    assert refreshed.processing_config_hash == previous_hash
    assert db_session.query(models.DocumentChunk).count() == len(previous_records)


def test_reindex_embedding_and_partial_add_failures_preserve_previous_index(db_session, monkeypatch, tmp_path: Path) -> None:
    collection = PartiallyFailingAddCollection()
    _source, _storage, _stored, _document, collection = prepare_durable_index(
        db_session, monkeypatch, tmp_path, collection=collection
    )
    previous_records = {key: dict(value) for key, value in collection.records.items()}
    monkeypatch.setattr(
        documents,
        "_embed_chunks",
        lambda _chunks, _model: (_ for _ in ()).throw(RuntimeError("synthetic embedding failure")),
    )
    with pytest.raises(HTTPException) as embedding_error:
        documents.reindex_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert embedding_error.value.status_code == 500
    assert collection.records == previous_records

    monkeypatch.setattr(
        documents,
        "_embed_chunks",
        lambda chunks, _model: {chunk.id: [float(index), 1.0] for index, chunk in enumerate(chunks)},
    )
    collection.fail_next_add = True
    with pytest.raises(HTTPException) as add_error:
        documents.reindex_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert add_error.value.status_code == 500
    assert collection.records == previous_records
    assert db_session.query(models.DocumentChunk).count() == len(previous_records)


def test_reindex_extraction_failure_preserves_previous_index(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, storage, stored, document, collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    previous_records = {key: dict(value) for key, value in collection.records.items()}
    malformed = b"synthetic-not-a-readable-pdf"
    storage.resolve(stored.relative_path).write_bytes(malformed)
    document.source_sha256 = sha256_bytes(malformed)
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        documents.reindex_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 409
    assert collection.records == previous_records
    assert db_session.query(models.DocumentChunk).count() == len(previous_records)


def test_archive_commit_failure_restores_active_index(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, storage, stored, _document, collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    previous_records = {key: dict(value) for key, value in collection.records.items()}
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("synthetic DB commit failure")))
    with pytest.raises(HTTPException) as exc:
        documents.archive_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 500
    assert collection.records == previous_records
    assert storage.exists(stored.relative_path)
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).one().source_status == "ACTIVE"


def test_archive_vector_cleanup_failure_keeps_document_active(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, storage, stored, _document, collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    previous_records = {key: dict(value) for key, value in collection.records.items()}
    original_delete = collection.delete

    def fail_delete(*, where):
        raise RuntimeError("synthetic archive vector cleanup failure")

    monkeypatch.setattr(collection, "delete", fail_delete)
    with pytest.raises(HTTPException) as exc:
        documents.archive_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 500
    assert collection.records == previous_records
    assert storage.exists(stored.relative_path)
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).one().source_status == "ACTIVE"
    monkeypatch.setattr(collection, "delete", original_delete)


def test_restore_partial_vector_failure_leaves_document_archived(db_session, monkeypatch, tmp_path: Path) -> None:
    collection = PartiallyFailingAddCollection()
    _source, storage, stored, _document, collection = prepare_durable_index(
        db_session, monkeypatch, tmp_path, collection=collection
    )
    documents.archive_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    collection.fail_next_add = True
    with pytest.raises(HTTPException) as exc:
        documents.restore_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 500
    assert collection.records == {}
    assert storage.exists(stored.relative_path)
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).one().source_status == "ARCHIVED"
    assert db_session.query(models.DocumentChunk).count() == 0


def test_restore_missing_source_is_controlled_and_remains_archived(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, storage, stored, _document, _collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    documents.archive_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    storage.remove(DOCUMENT_ID, stored.relative_path)
    with pytest.raises(HTTPException) as exc:
        documents.restore_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 409
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).one().source_status == "ARCHIVED"


def test_restore_source_hash_mismatch_is_controlled_and_remains_archived(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, storage, stored, _document, collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    documents.archive_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    storage.resolve(stored.relative_path).write_bytes(b"tampered synthetic source")
    with pytest.raises(HTTPException) as exc:
        documents.restore_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 409
    assert collection.records == {}
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).one().source_status == "ARCHIVED"


def test_delete_db_commit_failure_restores_source_database_and_vectors(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, storage, stored, _document, collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    previous_records = {key: dict(value) for key, value in collection.records.items()}
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("synthetic DB commit failure")))
    with pytest.raises(HTTPException) as exc:
        documents.delete_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 500
    assert collection.records == previous_records
    assert storage.exists(stored.relative_path)
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).count() == 1


def test_delete_staging_failure_restores_vectors_and_keeps_database(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, storage, stored, _document, collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    previous_records = {key: dict(value) for key, value in collection.records.items()}
    monkeypatch.setattr(
        storage,
        "stage_remove",
        lambda _document_id, _relative_path: (_ for _ in ()).throw(RuntimeError("synthetic staging failure")),
    )
    with pytest.raises(HTTPException) as exc:
        documents.delete_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert exc.value.status_code == 500
    assert collection.records == previous_records
    assert storage.exists(stored.relative_path)
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).count() == 1


def test_delete_purge_failure_is_explicit_and_repairable(db_session, monkeypatch, tmp_path: Path) -> None:
    _source, storage, stored, _document, collection = prepare_durable_index(db_session, monkeypatch, tmp_path)
    monkeypatch.setattr(
        storage,
        "purge_staged",
        lambda _document_id, _staged: (_ for _ in ()).throw(RuntimeError("synthetic purge failure")),
    )
    result = documents.delete_document(DOCUMENT_ID, user_id=USER_ID, db=db_session)
    assert result["status"] == "success"
    assert result["source_cleanup_status"] == "PENDING"
    assert collection.records == {}
    assert db_session.query(models.Document).filter(models.Document.id == DOCUMENT_ID).count() == 0
    assert not storage.exists(stored.relative_path)
    assert SourceStorage(storage.root).purge_document_trash(DOCUMENT_ID) == 1


def test_generated_synthetic_tv_workflow_exports_json_and_stable_csv(db_session, monkeypatch, tmp_path: Path) -> None:
    from scripts.generate_a_gate_owned_object_demo import generate

    output_dir = tmp_path / "demo"
    manifest = generate(output_dir)
    tv_entry = next(item for item in manifest["files"] if item["filename"] == "synthetic-tv-user-guide.pdf")
    source = (output_dir / tv_entry["filename"]).read_bytes()
    storage = SourceStorage(tmp_path / "sources")
    stored = storage.save(DOCUMENT_ID, source)
    document = add_user_and_document(db_session, source)
    document.source_storage_path = stored.relative_path
    collection = FakeCollection()
    configure_processing(monkeypatch, collection)
    monkeypatch.setattr(documents, "source_storage", storage)
    report = documents.process_document_source(
        db=db_session,
        document=document,
        source_bytes=source,
        user_id=USER_ID,
        operation="upload",
    )
    db_session.commit()

    json_result = documents.get_processing_report(DOCUMENT_ID, format="json", user_id=USER_ID, db=db_session)
    csv_result = documents.get_processing_report(DOCUMENT_ID, format="csv", user_id=USER_ID, db=db_session)
    assert json_result["processing_report"]["source_sha256"] == tv_entry["sha256"] == report["source_sha256"]
    assert json_result["processing_report"]["page_count"] == 2
    assert csv_result.body.decode("utf-8").splitlines()[0] == "metric,value"
    assert "chunk_length" in csv_result.body.decode("utf-8")
