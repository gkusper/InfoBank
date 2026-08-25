from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
from starlette.exceptions import HTTPException as StarletteHTTPException

import models
from database_errors import install_database_exception_handlers
from database_schema import (
    SCHEMA_COMPATIBLE,
    SCHEMA_INCOMPLETE_MIGRATION,
    SCHEMA_MIGRATION_REQUIRED,
    SCHEMA_UNSUPPORTED_NEWER,
    check_database_schema,
    migration_definitions,
    safe_public_schema_report,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _legacy_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(255), username VARCHAR(100), password_hash VARCHAR(255))"))
        connection.execute(text("CREATE TABLE documents (id VARCHAR(255) PRIMARY KEY, file_path VARCHAR(512) NOT NULL, upload_date DATETIME, visibility VARCHAR(50))"))
        connection.execute(text("CREATE TABLE document_chunks (id VARCHAR(36) PRIMARY KEY, document_id VARCHAR(255), chunk_index INTEGER, text_content TEXT, vector_id VARCHAR(255))"))
    return engine


def test_representative_legacy_schema_requires_migration() -> None:
    engine = _legacy_engine()
    report = check_database_schema(engine)
    engine.dispose()
    assert report["status"] == SCHEMA_MIGRATION_REQUIRED
    assert "original_filename" in report["missing_columns"]["documents"]
    assert "page_number" in report["missing_columns"]["document_chunks"]


def test_current_model_schema_is_compatible_without_tracking() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    report = check_database_schema(engine)
    engine.dispose()
    assert report["status"] == SCHEMA_COMPATIBLE
    assert report["migration_tracking"]["state"] == "STRUCTURALLY_COMPATIBLE_UNTRACKED"


def test_unknown_migration_is_classified_as_unsupported_newer() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(100) PRIMARY KEY, checksum CHAR(64), description VARCHAR(255), applied_at DATETIME)"))
        connection.execute(text("INSERT INTO schema_migrations VALUES ('999_future', 'x', 'future', CURRENT_TIMESTAMP)"))
    report = check_database_schema(engine)
    engine.dispose()
    assert report["status"] == SCHEMA_UNSUPPORTED_NEWER


def test_marked_but_structurally_legacy_schema_is_incomplete() -> None:
    engine = _legacy_engine()
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(100) PRIMARY KEY, checksum CHAR(64), description VARCHAR(255), applied_at DATETIME)"))
        for migration in migration_definitions():
            connection.execute(
                text("INSERT INTO schema_migrations VALUES (:version, :checksum, :description, CURRENT_TIMESTAMP)"),
                {"version": migration.version, "checksum": migration.checksum, "description": migration.path.name},
            )
    report = check_database_schema(engine)
    engine.dispose()
    assert report["status"] == SCHEMA_INCOMPLETE_MIGRATION


def test_public_schema_report_contains_no_missing_column_inventory() -> None:
    engine = _legacy_engine()
    public = safe_public_schema_report(check_database_schema(engine))
    engine.dispose()
    rendered = json.dumps(public).lower()
    assert public["schema"]["code"] == "DATABASE_MIGRATION_REQUIRED"
    assert "original_filename" not in rendered
    assert "document_chunks" not in rendered
    assert "select " not in rendered


def test_central_http_error_handler_removes_raw_database_details() -> None:
    app = FastAPI()
    install_database_exception_handlers(app)
    handler = app.exception_handlers[StarletteHTTPException]
    raw = (
        "(pymysql.err.OperationalError) (1054, Unknown column 'documents.original_filename') "
        "[SQL: SELECT documents.id FROM documents] C:\\private\\repo"
    )
    response = asyncio.run(handler(None, HTTPException(status_code=500, detail=raw)))
    body = response.body.decode("utf-8").lower()
    assert response.status_code == 500
    assert "database_operation_failed" in body
    for forbidden in (
        "select documents",
        "from documents",
        "pymysql",
        "sqlalchemy",
        "operationalerror",
        "original_filename",
        "c:\\private",
    ):
        assert forbidden not in body


def test_model_clean_schema_and_migrations_cover_required_document_columns() -> None:
    required = {
        "original_filename", "source_storage_path", "source_sha256", "source_mime_type",
        "source_byte_size", "page_count", "source_status", "processing_status",
        "processing_config_version", "processing_config_hash", "source_url", "source_license",
        "pdf_title", "pdf_author", "pdf_creation_date", "updated_at", "archived_at",
    }
    model_columns = {column.name for column in models.Document.__table__.columns}
    clean_schema = (REPOSITORY_ROOT / "infobank_db.sql").read_text(encoding="utf-8").lower()
    migration = (REPOSITORY_ROOT / "backend_python/migrations/infocom_a_gate_phase1_mysql.sql").read_text(encoding="utf-8-sig").lower()
    assert required <= model_columns
    for column in required:
        assert column in clean_schema
        assert column in migration


def test_canonical_runtime_is_shared_by_readme_and_quality_gate() -> None:
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    quality_gate = (REPOSITORY_ROOT / "scripts/run_local_quality_gate.ps1").read_text(encoding="utf-8")
    assert "backend_python\\.venv_r1a" in readme
    assert "backend_python/.venv_r1a/Scripts/python.exe" in quality_gate
    assert "backend_python\\venv\\Scripts\\python.exe -m uvicorn" not in readme


def test_mysql_varchar_model_columns_have_explicit_lengths() -> None:
    assert models.User.__table__.c.full_name.type.length == 255
    assert models.User.__table__.c.avatar_url.type.length == 1024
