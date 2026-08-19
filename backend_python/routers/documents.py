from __future__ import annotations

import csv
import datetime as dt
import io
import json
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

import ai_service
import models
import policy_engine
import relevance
import security
from database import get_db
from document_processing import (
    DEFAULT_PROCESSING_CONFIG,
    KeywordAssignment,
    KeywordExtractionResult,
    ProcessingConfig,
    chunk_pages,
    deterministic_keyword_candidates,
    extract_keywords,
    extract_pdf_pages,
    merge_keyword_candidates,
    processing_statistics,
    sha256_bytes,
)
from source_storage import SourceStorage


router = APIRouter(prefix="/api", tags=["Documents"])
source_storage = SourceStorage()


def require_owner(db: Session, doc_id: str, user_id: str) -> models.UserDocumentPermission:
    perm_record = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.document_id == doc_id,
        models.UserDocumentPermission.user_id == user_id,
    ).first()
    if not perm_record or perm_record.permission_type != models.PermissionType.Owner:
        raise HTTPException(status_code=403, detail="Only the Owner can perform this operation.")
    return perm_record


def visibility_from_permission(permission_type: models.PermissionType | str) -> str:
    value = permission_type.value if hasattr(permission_type, "value") else str(permission_type)
    if value == "Aggregate":
        return "Aggregate"
    if value == "Metadata":
        return "Metadata"
    return "Private"


def display_permission(doc: models.Document, permission: models.UserDocumentPermission) -> str:
    if doc.visibility in {"Aggregate", "Metadata"}:
        return doc.visibility
    return permission.permission_type.value if hasattr(permission.permission_type, "value") else str(permission.permission_type)


def deterministic_keywords_from_text(text: str) -> list[str]:
    """Backward-compatible deterministic keyword helper."""

    return [value for value, _ in deterministic_keyword_candidates(text)]


def _safe_original_filename(filename: str | None) -> str:
    basename = Path((filename or "document.pdf").replace("\\", "/")).name or "document.pdf"
    sanitized = "".join(character for character in basename if character >= " " and character not in {'"', "'"})
    return sanitized[:512] or "document.pdf"


def _audit(db: Session, user_id: str, action: str, document_id: str, details: dict[str, Any]) -> None:
    db.add(
        models.AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            target_id=document_id,
            details=json.dumps(details, ensure_ascii=False, sort_keys=True),
        )
    )


def _keyword_client() -> Any | None:
    try:
        return ai_service.get_ai_provider()
    except Exception:
        return None


def _embed_chunks(chunks, embedding_model: str = DEFAULT_PROCESSING_CONFIG.embedding_model) -> dict[str, list[float]]:
    vectors = ai_service.embed_texts([chunk.text for chunk in chunks], model=embedding_model)
    if len(vectors) != len(chunks):
        raise RuntimeError("AI provider returned an invalid embedding count")
    return {chunk.id: vector for chunk, vector in zip(chunks, vectors)}


def _empty_vector_snapshot() -> dict[str, list[Any]]:
    return {"ids": [], "embeddings": [], "metadatas": [], "documents": []}


def _as_plain_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def _snapshot_document_vectors(document_id: str) -> dict[str, list[Any]]:
    result = ai_service.collection.get(
        where={"document_id": document_id},
        include=["embeddings", "metadatas", "documents"],
    )
    return {
        "ids": _as_plain_list(result.get("ids")),
        "embeddings": _as_plain_list(result.get("embeddings")),
        "metadatas": _as_plain_list(result.get("metadatas")),
        "documents": _as_plain_list(result.get("documents")),
    }


def _restore_document_vectors(document_id: str, snapshot: dict[str, list[Any]]) -> None:
    ai_service.collection.delete(where={"document_id": document_id})
    if snapshot["ids"]:
        ai_service.collection.add(
            ids=snapshot["ids"],
            embeddings=snapshot["embeddings"],
            metadatas=snapshot["metadatas"],
            documents=snapshot["documents"],
        )


def _replace_document_vectors(
    document_id: str,
    *,
    ids: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
    documents: list[str],
    previous: dict[str, list[Any]],
) -> None:
    try:
        ai_service.collection.delete(where={"document_id": document_id})
        ai_service.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
    except Exception:
        _restore_document_vectors(document_id, previous)
        raise


def _provenance_type(value: str) -> models.ProvenanceType:
    mapping = {
        "EXTRACTED": models.ProvenanceType.Extracted,
        "USER": models.ProvenanceType.User,
        "RULE": models.ProvenanceType.Rule,
        "AI": models.ProvenanceType.AI,
    }
    return mapping[value]


def _persist_keywords(
    db: Session,
    document_id: str,
    result: KeywordExtractionResult,
    *,
    preserve_user: bool,
) -> None:
    existing = db.query(models.DocumentKeyword).filter(models.DocumentKeyword.document_id == document_id).all()
    user_relations: dict[str, models.DocumentKeyword] = {}
    for relation in existing:
        keyword = db.query(models.Keyword).filter(models.Keyword.id == relation.keyword_id).first()
        if preserve_user and relation.user_edited and keyword:
            user_relations[keyword.word] = relation
        else:
            db.delete(relation)
    db.flush()

    for assignment in result.assignments:
        db_keyword = db.query(models.Keyword).filter(models.Keyword.word == assignment.value).first()
        if not db_keyword:
            db_keyword = models.Keyword(word=assignment.value)
            db.add(db_keyword)
            db.flush()
        provenance = list(assignment.provenance)
        if assignment.value in user_relations:
            relation = user_relations[assignment.value]
            prior = json.loads(relation.provenance_json or "[]")
            relation.provenance_json = json.dumps(prior + [item for item in provenance if item not in prior], sort_keys=True)
            continue
        primary = provenance[0] if provenance else {"type": "RULE", "method": "unknown"}
        db.add(
            models.DocumentKeyword(
                document_id=document_id,
                keyword_id=db_keyword.id,
                provenance_type=_provenance_type(str(primary.get("type", "RULE"))),
                provenance_json=json.dumps(provenance, sort_keys=True),
                extraction_method=str(primary.get("method", "unknown")),
                model_version=primary.get("model"),
                prompt_version=primary.get("prompt_version"),
                user_edited=False,
            )
        )


def _set_metadata_provenance(
    db: Session,
    document_id: str,
    fields: dict[str, tuple[Any, str, str]],
    *,
    preserve_user: bool,
) -> None:
    query = db.query(models.DocumentMetadataProvenance).filter(
        models.DocumentMetadataProvenance.document_id == document_id
    )
    for record in query.all():
        if not (preserve_user and record.provenance_type == models.ProvenanceType.User):
            db.delete(record)
    db.flush()
    user_fields = {
        row.field_name
        for row in query.all()
        if row.provenance_type == models.ProvenanceType.User
    }
    for field_name, (value, provenance, method) in sorted(fields.items()):
        if preserve_user and field_name in user_fields:
            continue
        db.add(
            models.DocumentMetadataProvenance(
                id=str(uuid.uuid4()),
                document_id=document_id,
                field_name=field_name,
                field_value=None if value is None else str(value),
                provenance_type=_provenance_type(provenance),
                method=method,
            )
        )


def _metadata_fields(document: models.Document, extraction, config: ProcessingConfig) -> dict[str, tuple[Any, str, str]]:
    pdf_metadata = extraction.pdf_metadata
    return {
        "original_filename": (document.original_filename, "USER", "upload-form"),
        "source_storage_path": (document.source_storage_path, "RULE", "uuid-source-storage-v1"),
        "mime_type": (document.source_mime_type, "EXTRACTED", "upload-content-type"),
        "source_sha256": (document.source_sha256, "EXTRACTED", "sha256"),
        "source_byte_size": (document.source_byte_size, "EXTRACTED", "byte-count"),
        "page_count": (extraction.page_count, "EXTRACTED", "PyMuPDF"),
        "pdf_title": (pdf_metadata.get("title"), "EXTRACTED", "PyMuPDF-metadata"),
        "pdf_author": (pdf_metadata.get("author"), "EXTRACTED", "PyMuPDF-metadata"),
        "pdf_creation_date": (pdf_metadata.get("creationDate"), "EXTRACTED", "PyMuPDF-metadata"),
        "processing_config_version": (config.config_version, "RULE", "document-processing-config"),
        "processing_config_hash": (config.config_hash, "RULE", "document-processing-config"),
        "source_status": (document.source_status, "RULE", "document-lifecycle-v1"),
        "processing_status": (document.processing_status, "RULE", "document-processing-v1"),
        "visibility": (document.visibility, "USER", "upload-permission-form"),
        "source_url": (document.source_url, "USER", "upload-form"),
        "source_license": (document.source_license, "USER", "upload-form"),
    }


def process_document_source(
    *,
    db: Session,
    document: models.Document,
    source_bytes: bytes,
    user_id: str,
    operation: str,
    config: ProcessingConfig = DEFAULT_PROCESSING_CONFIG,
    preserve_user: bool = True,
    previous_vectors: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    actual_sha = sha256_bytes(source_bytes)
    if document.source_sha256 and actual_sha != document.source_sha256:
        raise ValueError("Durable source SHA-256 does not match the database integrity record")
    extraction = extract_pdf_pages(source_bytes)
    if not any(page.text.strip() for page in extraction.pages):
        raise ValueError("The PDF is empty or text could not be extracted")
    full_text = "\n".join(page.text for page in extraction.pages)
    keyword_result = extract_keywords(
        full_text,
        client=_keyword_client(),
        model=config.keyword_model,
        prompt_version=config.keyword_prompt_version,
    )
    if preserve_user:
        user_keyword_candidates: list[tuple[str, dict[str, Any]]] = []
        user_relations = db.query(models.DocumentKeyword).filter(
            models.DocumentKeyword.document_id == document.id,
            models.DocumentKeyword.user_edited.is_(True),
        ).all()
        for relation in user_relations:
            keyword = db.query(models.Keyword).filter(models.Keyword.id == relation.keyword_id).first()
            if not keyword:
                continue
            provenance = json.loads(relation.provenance_json or "[]") or [{"type": "USER", "method": "owner-keyword-edit"}]
            user_keyword_candidates.extend((keyword.word, item) for item in provenance)
        combined_candidates = [
            (assignment.value, item)
            for assignment in keyword_result.assignments
            for item in assignment.provenance
        ] + user_keyword_candidates
        keyword_result = KeywordExtractionResult(
            assignments=merge_keyword_candidates(combined_candidates),
            mode=keyword_result.mode,
            model=keyword_result.model,
            prompt_version=keyword_result.prompt_version,
            warnings=keyword_result.warnings,
        )
    chunks = chunk_pages(document.id, extraction.pages, config)
    if not chunks:
        raise ValueError("No indexable chunks were produced")
    embeddings = _embed_chunks(chunks, config.embedding_model)

    previous_vectors = previous_vectors if previous_vectors is not None else _snapshot_document_vectors(document.id)
    _replace_document_vectors(
        document.id,
        ids=[chunk.id for chunk in chunks],
        embeddings=[embeddings[chunk.id] for chunk in chunks],
        metadatas=[chunk.chroma_metadata() | {"source_sha256": actual_sha} for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        previous=previous_vectors,
    )

    db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == document.id).delete()
    for chunk in chunks:
        db.add(
            models.DocumentChunk(
                id=chunk.id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                block_index=chunk.block_index,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                text_content=chunk.text,
                content_sha256=chunk.content_hash,
                source_sha256=actual_sha,
                chunk_config_version=chunk.config_version,
                chunk_config_hash=chunk.config_hash,
                vector_id=chunk.id,
            )
        )

    document.source_sha256 = actual_sha
    document.page_count = extraction.page_count
    document.processing_config_version = config.config_version
    document.processing_config_hash = config.config_hash
    document.processing_status = "COMPLETE"
    document.source_status = "ACTIVE"
    document.archived_at = None
    user_metadata = {
        row.field_name: row.field_value
        for row in db.query(models.DocumentMetadataProvenance).filter(
            models.DocumentMetadataProvenance.document_id == document.id,
            models.DocumentMetadataProvenance.provenance_type == models.ProvenanceType.User,
        ).all()
    }
    document.pdf_title = user_metadata.get("pdf_title", extraction.pdf_metadata.get("title"))
    document.pdf_author = user_metadata.get("pdf_author", extraction.pdf_metadata.get("author"))
    document.pdf_creation_date = extraction.pdf_metadata.get("creationDate")

    _persist_keywords(db, document.id, keyword_result, preserve_user=preserve_user)
    _set_metadata_provenance(
        db,
        document.id,
        _metadata_fields(document, extraction, config),
        preserve_user=preserve_user,
    )
    report = processing_statistics(
        document_id=document.id,
        source_sha256=actual_sha,
        extraction=extraction,
        chunks=chunks,
        keywords=keyword_result,
        config=config,
        started_at=started_at,
    )
    report["providers"] = {
        "keyword": ai_service.provider_manifest(operation="keyword_extraction", model=config.keyword_model),
        "embedding": ai_service.provider_manifest(operation="embedding", model=config.embedding_model),
    }
    db.add(
        models.DocumentProcessingReport(
            id=str(uuid.uuid4()),
            document_id=document.id,
            operation=operation,
            config_version=config.config_version,
            config_hash=config.config_hash,
            report_json=json.dumps(report, ensure_ascii=False, sort_keys=True),
        )
    )
    _audit(db, user_id, f"DOCUMENT_{operation.upper()}", document.id, report)
    return report | {
        "keywords": keyword_result.keywords,
        "keyword_extraction_mode": keyword_result.mode,
        "processing_warnings": list(keyword_result.warnings),
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    permission_type: models.PermissionType = Form(...),
    source_url: str | None = Form(None),
    source_license: str | None = Form(None),
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    content = await file.read()
    document_id = str(uuid.uuid4())
    stored = None
    previous_vectors = _empty_vector_snapshot()
    vector_work_started = False
    try:
        extract_pdf_pages(content)
        stored = source_storage.save(document_id, content, "application/pdf")
        original_filename = _safe_original_filename(file.filename)
        document = models.Document(
            id=document_id,
            file_path=original_filename,
            original_filename=original_filename,
            source_storage_path=stored.relative_path,
            source_sha256=stored.sha256,
            source_mime_type=stored.mime_type,
            source_byte_size=stored.byte_size,
            source_status="ACTIVE",
            processing_status="PROCESSING",
            visibility=visibility_from_permission(permission_type),
            source_url=source_url,
            source_license=source_license,
        )
        db.add(document)
        db.add(
            models.UserDocumentPermission(
                id=str(uuid.uuid4()),
                user_id=user_id,
                document_id=document_id,
                permission_type=models.PermissionType.Owner,
            )
        )
        db.flush()
        vector_work_started = True
        report = process_document_source(
            db=db,
            document=document,
            source_bytes=content,
            user_id=user_id,
            operation="upload",
            preserve_user=False,
            previous_vectors=previous_vectors,
        )
        db.commit()
        return {
            "status": "success",
            "keywords": report["keywords"],
            "document_id": document_id,
            "visibility": document.visibility,
            "source_sha256": stored.sha256,
            "page_count": report["page_count"],
            "processing_config_hash": report["processing_config_hash"],
            "keyword_extraction_mode": report["keyword_extraction_mode"],
            "chunk_count": report["chunk_count"],
            "processing_warnings": report["processing_warnings"],
            "processing_report_url": f"/api/documents/{document_id}/processing-report",
        }
    except HTTPException:
        db.rollback()
        if vector_work_started:
            _restore_document_vectors(document_id, previous_vectors)
        if stored:
            source_storage.remove(document_id, stored.relative_path)
        raise
    except Exception as exc:
        db.rollback()
        if vector_work_started:
            try:
                _restore_document_vectors(document_id, previous_vectors)
            except Exception as cleanup_exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Upload failed and vector compensation also failed: {type(cleanup_exc).__name__}",
                ) from cleanup_exc
        if stored:
            source_storage.remove(document_id, stored.relative_path)
        status = 400 if isinstance(exc, ValueError) else 500
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/documents/me")
def get_my_documents(user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    return build_document_list(user_id, db)


@router.get("/documents/{requested_user_id}")
def get_user_documents(requested_user_id: str, user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    if requested_user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only access your own document list.")
    return build_document_list(user_id, db)


def build_document_list(user_id: str, db: Session):
    permissions = db.query(models.UserDocumentPermission).filter(models.UserDocumentPermission.user_id == user_id).all()
    documents = []
    for permission in permissions:
        document = db.query(models.Document).filter(models.Document.id == permission.document_id).first()
        if not document:
            continue
        keyword_rows = db.query(models.Keyword.word).join(
            models.DocumentKeyword, models.Keyword.id == models.DocumentKeyword.keyword_id
        ).filter(models.DocumentKeyword.document_id == document.id).all()
        chunk_count = db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == document.id).count()
        provenance_rows = db.query(models.DocumentMetadataProvenance).filter(
            models.DocumentMetadataProvenance.document_id == document.id
        ).order_by(models.DocumentMetadataProvenance.field_name.asc()).all()
        documents.append(
            {
                "document_id": document.id,
                "file_name": document.original_filename or document.file_path,
                "permission": display_permission(document, permission),
                "visibility": document.visibility,
                "is_owner": permission.permission_type == models.PermissionType.Owner,
                "keywords": [row[0] for row in keyword_rows],
                "upload_date": document.upload_date.strftime("%Y-%m-%d %H:%M") if document.upload_date else "N/A",
                "source_status": document.source_status,
                "source_sha256": document.source_sha256,
                "page_count": document.page_count,
                "processing_status": document.processing_status,
                "chunk_count": chunk_count,
                "provenance": [
                    {
                        "field": row.field_name,
                        "type": row.provenance_type.value if hasattr(row.provenance_type, "value") else str(row.provenance_type),
                        "method": row.method,
                    }
                    for row in provenance_rows
                ],
                "reviewer_links": {
                    "source": f"/api/documents/{document.id}/source",
                    "processing_report": f"/api/documents/{document.id}/processing-report",
                    "reindex": f"/api/documents/{document.id}/reindex",
                    "archive": f"/api/documents/{document.id}/archive",
                    "restore": f"/api/documents/{document.id}/restore",
                    "permission": f"/api/policy/resolve/document/{document.id}",
                },
            }
        )
    return {"status": "success", "documents": documents}


@router.post("/documents/update-keywords")
def update_keywords(
    doc_id: str = Form(...),
    keywords: str = Form(...),
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    require_owner(db, doc_id, user_id)
    assignments = merge_keyword_candidates(
        [
            (value, {"type": "USER", "method": "owner-keyword-edit"})
            for value in keywords.split(",")
            if value.strip()
        ]
    )
    result = KeywordExtractionResult(
        assignments=assignments,
        mode="user_edit",
        model=None,
        prompt_version="not-applicable",
    )
    db.query(models.DocumentKeyword).filter(models.DocumentKeyword.document_id == doc_id).delete()
    _persist_keywords(db, doc_id, result, preserve_user=False)
    db.flush()
    for relation in db.query(models.DocumentKeyword).filter(models.DocumentKeyword.document_id == doc_id).all():
        relation.user_edited = True
        relation.provenance_type = models.ProvenanceType.User
    _audit(db, user_id, "DOCUMENT_KEYWORDS_UPDATED", doc_id, {"keywords": [item.value for item in assignments]})
    db.commit()
    return {"status": "success", "message": "Keywords updated", "keywords": [item.value for item in assignments]}


@router.post("/documents/{doc_id}/metadata")
def update_document_metadata(
    doc_id: str,
    title: str | None = Form(None),
    author: str | None = Form(None),
    source_url: str | None = Form(None),
    source_license: str | None = Form(None),
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    require_owner(db, doc_id, user_id)
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    updates = {"pdf_title": title, "pdf_author": author, "source_url": source_url, "source_license": source_license}
    changed: dict[str, str] = {}
    for field_name, value in updates.items():
        if value is None:
            continue
        setattr(document, field_name, value)
        changed[field_name] = value
        db.query(models.DocumentMetadataProvenance).filter(
            models.DocumentMetadataProvenance.document_id == doc_id,
            models.DocumentMetadataProvenance.field_name == field_name,
        ).delete()
        db.add(
            models.DocumentMetadataProvenance(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                field_name=field_name,
                field_value=value,
                provenance_type=models.ProvenanceType.User,
                method="owner-metadata-edit",
            )
        )
    _audit(db, user_id, "DOCUMENT_METADATA_UPDATED", doc_id, {"fields": sorted(changed)})
    db.commit()
    return {"status": "success", "updated_fields": changed}


@router.post("/documents/update-permission")
def update_permission(doc_id: str = Form(...), new_perm: str = Form(...), user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    require_owner(db, doc_id, user_id)
    if new_perm not in {"Owner", "Reader", "Aggregate", "Metadata"}:
        raise HTTPException(status_code=400, detail="Invalid permission/visibility mode.")
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    document.visibility = visibility_from_permission(new_perm)
    db.query(models.DocumentMetadataProvenance).filter(
        models.DocumentMetadataProvenance.document_id == doc_id,
        models.DocumentMetadataProvenance.field_name == "visibility",
    ).delete()
    db.add(
        models.DocumentMetadataProvenance(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            field_name="visibility",
            field_value=document.visibility,
            provenance_type=models.ProvenanceType.User,
            method="owner-permission-edit",
        )
    )
    _audit(db, user_id, "DOCUMENT_PERMISSION_UPDATED", doc_id, {"visibility": document.visibility})
    db.commit()
    return {"status": "success", "message": "Permission updated", "visibility": document.visibility}


def _load_verified_source(document: models.Document) -> bytes:
    if not document.source_storage_path or not document.source_sha256:
        raise FileNotFoundError("Document has no durable source record")
    source = source_storage.read(document.source_storage_path)
    if sha256_bytes(source) != document.source_sha256:
        raise ValueError("Durable source integrity check failed")
    return source


@router.post("/documents/{doc_id}/reindex")
def reindex_document(doc_id: str, user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    require_owner(db, doc_id, user_id)
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    previous_vectors = None
    try:
        source = _load_verified_source(document)
        previous_vectors = _snapshot_document_vectors(doc_id)
        report = process_document_source(
            db=db,
            document=document,
            source_bytes=source,
            user_id=user_id,
            operation="reindex",
            preserve_user=True,
            previous_vectors=previous_vectors,
        )
        db.commit()
        return {"status": "success", "document_id": doc_id, "processing_report": report}
    except (FileNotFoundError, ValueError) as exc:
        db.rollback()
        if previous_vectors is not None:
            _restore_document_vectors(doc_id, previous_vectors)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        if previous_vectors is not None:
            _restore_document_vectors(doc_id, previous_vectors)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/{doc_id}/archive")
def archive_document(doc_id: str, user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    require_owner(db, doc_id, user_id)
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if document.source_status == "ARCHIVED":
        return {"status": "success", "document_id": doc_id, "source_status": "ARCHIVED", "idempotent": True}
    previous_vectors = _snapshot_document_vectors(doc_id)
    vectors_deleted = False
    try:
        ai_service.collection.delete(where={"document_id": doc_id})
        vectors_deleted = True
        db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == doc_id).delete()
        document.source_status = "ARCHIVED"
        document.processing_status = "ARCHIVED"
        document.archived_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
        for field_name in ("source_status", "processing_status"):
            db.query(models.DocumentMetadataProvenance).filter(
                models.DocumentMetadataProvenance.document_id == doc_id,
                models.DocumentMetadataProvenance.field_name == field_name,
            ).delete()
            db.add(
                models.DocumentMetadataProvenance(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    field_name=field_name,
                    field_value="ARCHIVED",
                    provenance_type=models.ProvenanceType.Rule,
                    method="document-lifecycle-v1",
                )
            )
        _audit(db, user_id, "DOCUMENT_ARCHIVED", doc_id, {"source_preserved": True})
        db.commit()
        return {"status": "success", "document_id": doc_id, "source_status": "ARCHIVED", "source_preserved": True}
    except Exception as exc:
        db.rollback()
        if vectors_deleted:
            _restore_document_vectors(doc_id, previous_vectors)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/{doc_id}/restore")
def restore_document(doc_id: str, user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    require_owner(db, doc_id, user_id)
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if document.source_status == "ACTIVE":
        return {"status": "success", "document_id": doc_id, "source_status": "ACTIVE", "idempotent": True}
    previous_vectors = None
    try:
        source = _load_verified_source(document)
        previous_vectors = _snapshot_document_vectors(doc_id)
        report = process_document_source(
            db=db,
            document=document,
            source_bytes=source,
            user_id=user_id,
            operation="restore",
            preserve_user=True,
            previous_vectors=previous_vectors,
        )
        db.commit()
        return {"status": "success", "document_id": doc_id, "source_status": "ACTIVE", "processing_report": report}
    except (FileNotFoundError, ValueError) as exc:
        db.rollback()
        if previous_vectors is not None:
            _restore_document_vectors(doc_id, previous_vectors)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        if previous_vectors is not None:
            _restore_document_vectors(doc_id, previous_vectors)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/documents/{doc_id}/source")
def view_document_source(
    doc_id: str,
    page: int | None = Query(None, ge=1),
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    access = policy_engine.resolve_document_access(db, user_id, doc_id, purpose="source_view")
    decision = access["use_decision"]
    if decision == relevance.USE_DENY:
        raise HTTPException(status_code=404, detail="Source not found")
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Source not found")
    metadata = {
        "document_id": document.id,
        "original_filename": document.original_filename or document.file_path,
        "source_sha256": document.source_sha256,
        "page_count": document.page_count,
        "source_status": document.source_status,
        "use_decision": decision,
    }
    if decision == relevance.USE_METADATA:
        return {"status": "metadata_only", "metadata": metadata}
    if decision != relevance.USE_FULL:
        raise HTTPException(status_code=403, detail="Raw source access is not permitted")
    try:
        source = _load_verified_source(document)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if page is not None:
        extraction = extract_pdf_pages(source)
        if page > extraction.page_count:
            raise HTTPException(status_code=404, detail="Page not found")
        page_record = extraction.pages[page - 1]
        return {"status": "success", "metadata": metadata, "page_number": page, "text": page_record.text}
    safe_name = _safe_original_filename(document.original_filename or document.file_path)
    return Response(
        content=source,
        media_type=document.source_mime_type or "application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"', "X-Content-SHA256": document.source_sha256 or ""},
    )


@router.get("/documents/{doc_id}/processing-report")
def get_processing_report(
    doc_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    require_owner(db, doc_id, user_id)
    record = db.query(models.DocumentProcessingReport).filter(
        models.DocumentProcessingReport.document_id == doc_id
    ).order_by(models.DocumentProcessingReport.created_at.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail="Processing report not found")
    report = json.loads(record.report_json)
    if format == "json":
        return {"status": "success", "operation": record.operation, "processing_report": report}
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["metric", "value"])
    for key, value in sorted(report.items()):
        writer.writerow([key, json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value])
    return Response(content=buffer.getvalue(), media_type="text/csv")


@router.delete("/documents/delete")
def delete_document(doc_id: str = Form(...), user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    permission = db.query(models.UserDocumentPermission).filter(
        models.UserDocumentPermission.document_id == doc_id,
        models.UserDocumentPermission.user_id == user_id,
    ).first()
    if not permission:
        raise HTTPException(status_code=404, detail="The requested document or permission could not be found.")
    if permission.permission_type != models.PermissionType.Owner:
        db.delete(permission)
        db.commit()
        return {"status": "success", "message": "Successfully unsubscribed from the document."}
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    staged_source = None
    previous_vectors = _snapshot_document_vectors(doc_id)
    vectors_deleted = False
    database_committed = False
    try:
        ai_service.collection.delete(where={"document_id": doc_id})
        vectors_deleted = True
        if document and document.source_storage_path:
            staged_source = source_storage.stage_remove(doc_id, document.source_storage_path)
        db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == doc_id).delete()
        db.query(models.DocumentKeyword).filter(models.DocumentKeyword.document_id == doc_id).delete()
        db.query(models.DocumentMetadataProvenance).filter(models.DocumentMetadataProvenance.document_id == doc_id).delete()
        db.query(models.DocumentProcessingReport).filter(models.DocumentProcessingReport.document_id == doc_id).delete()
        db.query(models.UserDocumentPermission).filter(models.UserDocumentPermission.document_id == doc_id).delete()
        if document:
            db.delete(document)
        db.commit()
        database_committed = True
        try:
            source_storage.purge_staged(doc_id, staged_source)
        except Exception as cleanup_exc:
            return {
                "status": "success",
                "message": "The document and vectors were deleted; staged source cleanup remains pending.",
                "source_cleanup_status": "PENDING",
                "cleanup_document_id": doc_id,
                "cleanup_error": type(cleanup_exc).__name__,
            }
        return {
            "status": "success",
            "message": "The document, vectors, and durable source have been permanently deleted.",
            "source_cleanup_status": "COMPLETE",
        }
    except Exception as exc:
        if not database_committed:
            db.rollback()
            if vectors_deleted:
                _restore_document_vectors(doc_id, previous_vectors)
            if staged_source:
                source_storage.restore_staged(doc_id, staged_source)
        raise HTTPException(status_code=500, detail=f"An error occurred while deleting: {exc}") from exc


@router.post("/documents/transfer")
def transfer_document_ownership(doc_id: str = Form(...), new_username: str = Form(...), user_id: str = Depends(security.get_current_user_id), db: Session = Depends(get_db)):
    target_user = db.query(models.User).filter(models.User.username == new_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="The provided user was not found in the system.")
    if target_user.id == user_id:
        raise HTTPException(status_code=400, detail="You are not permitted to transfer this document to yourself.")
    try:
        policy_engine.transfer_document_ownership(
            db,
            owner_user_id=user_id,
            document_id=doc_id,
            target_user_id=target_user.id,
        )
        db.commit()
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, LookupError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", "message": f"Ownership successfully transferred to the user: {target_user.username}"}
