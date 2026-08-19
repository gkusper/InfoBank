-- InfoCom A-GATE Phase A1: durable source, provenance, page-aware chunks.
-- MariaDB idempotent upgrade for databases created from the R1 schema.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS original_filename VARCHAR(512) NULL AFTER file_path;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_storage_path VARCHAR(512) NULL AFTER original_filename;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_sha256 VARCHAR(64) NULL AFTER source_storage_path;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_mime_type VARCHAR(100) NULL AFTER source_sha256;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_byte_size BIGINT NULL AFTER source_mime_type;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS page_count INT NULL AFTER source_byte_size;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE' AFTER page_count;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_status VARCHAR(30) NOT NULL DEFAULT 'PENDING' AFTER source_status;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_config_version VARCHAR(100) NULL AFTER processing_status;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_config_hash VARCHAR(64) NULL AFTER processing_config_version;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_url VARCHAR(2048) NULL AFTER processing_config_hash;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_license VARCHAR(255) NULL AFTER source_url;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS pdf_title VARCHAR(512) NULL AFTER source_license;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS pdf_author VARCHAR(512) NULL AFTER pdf_title;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS pdf_creation_date VARCHAR(100) NULL AFTER pdf_author;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS updated_at DATETIME NULL AFTER upload_date;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS archived_at DATETIME NULL AFTER updated_at;

CREATE INDEX IF NOT EXISTS ix_documents_source_sha256 ON documents (source_sha256);
CREATE INDEX IF NOT EXISTS ix_documents_source_status ON documents (source_status);

UPDATE documents
SET original_filename = file_path
WHERE original_filename IS NULL;

ALTER TABLE document_keywords ADD COLUMN IF NOT EXISTS provenance_type ENUM('EXTRACTED', 'USER', 'RULE', 'AI') NOT NULL DEFAULT 'RULE';
ALTER TABLE document_keywords ADD COLUMN IF NOT EXISTS provenance_json TEXT NULL;
ALTER TABLE document_keywords ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(100) NULL;
ALTER TABLE document_keywords ADD COLUMN IF NOT EXISTS model_version VARCHAR(255) NULL;
ALTER TABLE document_keywords ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(100) NULL;
ALTER TABLE document_keywords ADD COLUMN IF NOT EXISTS user_edited BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE document_keywords ADD COLUMN IF NOT EXISTS created_at DATETIME NULL;
ALTER TABLE document_keywords ADD COLUMN IF NOT EXISTS updated_at DATETIME NULL;

ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_number INT NULL AFTER chunk_index;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS block_index INT NULL AFTER page_number;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS char_start INT NULL AFTER block_index;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS char_end INT NULL AFTER char_start;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64) NULL AFTER text_content;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS source_sha256 VARCHAR(64) NULL AFTER content_sha256;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunk_config_version VARCHAR(100) NULL AFTER source_sha256;
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunk_config_hash VARCHAR(64) NULL AFTER chunk_config_version;

CREATE TABLE IF NOT EXISTS document_metadata_provenance (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    field_value TEXT NULL,
    provenance_type ENUM('EXTRACTED', 'USER', 'RULE', 'AI') NOT NULL,
    method VARCHAR(100) NOT NULL,
    model_version VARCHAR(255) NULL,
    prompt_version VARCHAR(100) NULL,
    confidence DOUBLE NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    INDEX ix_document_metadata_provenance_document_id (document_id),
    INDEX ix_document_metadata_provenance_field_name (field_name),
    CONSTRAINT fk_metadata_provenance_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS document_processing_reports (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    operation VARCHAR(30) NOT NULL,
    config_version VARCHAR(100) NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    report_json TEXT NOT NULL,
    created_at DATETIME NULL,
    INDEX ix_document_processing_reports_document_id (document_id),
    CONSTRAINT fk_processing_reports_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB;

SELECT 'A_GATE_PHASE1_MIGRATION_OK' AS status;
