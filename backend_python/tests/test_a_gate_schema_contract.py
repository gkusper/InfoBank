from __future__ import annotations

from pathlib import Path

import models


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = (REPO_ROOT / "infobank_db.sql").read_text(encoding="utf-8-sig").lower()
MIGRATION = (REPO_ROOT / "backend_python" / "migrations" / "infocom_a_gate_phase1_mysql.sql").read_text(encoding="utf-8-sig").lower()


def test_document_source_traceability_columns_exist_in_models_and_clean_schema() -> None:
    required = {
        "original_filename",
        "source_storage_path",
        "source_sha256",
        "source_mime_type",
        "source_byte_size",
        "page_count",
        "source_status",
        "processing_status",
        "processing_config_version",
        "processing_config_hash",
        "source_url",
        "source_license",
        "archived_at",
    }
    assert required <= set(models.Document.__table__.columns.keys())
    assert all(column in SCHEMA for column in required)


def test_chunk_traceability_columns_exist_in_models_and_clean_schema() -> None:
    required = {
        "page_number",
        "block_index",
        "char_start",
        "char_end",
        "content_sha256",
        "source_sha256",
        "chunk_config_version",
        "chunk_config_hash",
    }
    assert required <= set(models.DocumentChunk.__table__.columns.keys())
    assert all(column in SCHEMA for column in required)


def test_provenance_and_processing_report_tables_exist() -> None:
    assert "document_metadata_provenance" in models.Base.metadata.tables
    assert "document_processing_reports" in models.Base.metadata.tables
    assert "create table if not exists document_metadata_provenance" in SCHEMA
    assert "create table if not exists document_processing_reports" in SCHEMA


def test_migration_is_rerunnable_and_contains_no_data_fixture() -> None:
    assert "add column if not exists" in MIGRATION
    assert "create table if not exists document_metadata_provenance" in MIGRATION
    assert "create table if not exists document_processing_reports" in MIGRATION
    assert "update documents" in MIGRATION
    assert "insert into" not in MIGRATION
    assert "d1-d8" not in MIGRATION


def test_provenance_enum_and_document_indexes_match_mariadb_contract() -> None:
    expected = ["EXTRACTED", "USER", "RULE", "AI"]
    assert models.DocumentKeyword.__table__.c.provenance_type.type.enums == expected
    assert models.DocumentMetadataProvenance.__table__.c.provenance_type.type.enums == expected
    assert "create index if not exists ix_documents_source_sha256" in MIGRATION
    assert "create index if not exists ix_documents_source_status" in MIGRATION
    assert "index ix_documents_source_sha256" in SCHEMA
    assert "index ix_documents_source_status" in SCHEMA
