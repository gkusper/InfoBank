CREATE DATABASE IF NOT EXISTS infobank_db
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE infobank_db;

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR(255) NULL,
    avatar_url VARCHAR(1024) NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(255) PRIMARY KEY,
    file_path VARCHAR(512) NOT NULL,
    original_filename VARCHAR(512) NULL,
    source_storage_path VARCHAR(512) NULL,
    source_sha256 VARCHAR(64) NULL,
    source_mime_type VARCHAR(100) NULL,
    source_byte_size BIGINT NULL,
    page_count INT NULL,
    source_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    processing_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    processing_config_version VARCHAR(100) NULL,
    processing_config_hash VARCHAR(64) NULL,
    source_url VARCHAR(2048) NULL,
    source_license VARCHAR(255) NULL,
    pdf_title VARCHAR(512) NULL,
    pdf_author VARCHAR(512) NULL,
    pdf_creation_date VARCHAR(100) NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL,
    archived_at DATETIME NULL,
    INDEX ix_documents_source_sha256 (source_sha256),
    INDEX ix_documents_source_status (source_status),
    visibility VARCHAR(50) DEFAULT 'Private'
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS keywords (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word VARCHAR(100) UNIQUE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS document_keywords (
    document_id VARCHAR(255) NOT NULL,
    keyword_id INT NOT NULL,
    provenance_type ENUM('EXTRACTED', 'USER', 'RULE', 'AI') NOT NULL DEFAULT 'RULE',
    provenance_json TEXT NULL,
    extraction_method VARCHAR(100) NULL,
    model_version VARCHAR(255) NULL,
    prompt_version VARCHAR(100) NULL,
    user_edited BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (document_id, keyword_id),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS document_chunks (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    page_number INT NULL,
    block_index INT NULL,
    char_start INT NULL,
    char_end INT NULL,
    text_content TEXT NOT NULL,
    content_sha256 VARCHAR(64) NULL,
    source_sha256 VARCHAR(64) NULL,
    chunk_config_version VARCHAR(100) NULL,
    chunk_config_hash VARCHAR(64) NULL,
    vector_id VARCHAR(255) NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB;

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
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
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
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS user_document_permission (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    document_id VARCHAR(255) NOT NULL,
    permission_type ENUM('Owner', 'Reader', 'Aggregate', 'Metadata') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(user_id, document_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS evidence_units (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    source_type ENUM('Email', 'BrowserHistory', 'Calendar', 'ActivityTrace', 'DocumentNote', 'Other') NOT NULL DEFAULT 'Other',
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    source_timestamp DATETIME NULL,
    thread_id VARCHAR(255) NULL,
    relation_key VARCHAR(255) NULL,
    metadata_json TEXT NULL,
    created_at DATETIME NULL,
    INDEX ix_evidence_units_user_id (user_id),
    INDEX ix_evidence_units_thread_id (thread_id),
    INDEX ix_evidence_units_relation_key (relation_key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS policy_rules (
    id VARCHAR(36) PRIMARY KEY,
    owner_user_id VARCHAR(36) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id VARCHAR(255) NOT NULL,
    purpose VARCHAR(100) NOT NULL DEFAULT 'any',
    access_mode ENUM('Full', 'Aggregate', 'Metadata', 'Deny') NOT NULL DEFAULT 'Full',
    valid_from DATETIME NULL,
    valid_until DATETIME NULL,
    created_at DATETIME NULL,
    INDEX ix_policy_rules_owner_user_id (owner_user_id),
    INDEX ix_policy_rules_target_id (target_id),
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS connector_accounts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'connected',
    token_json TEXT NOT NULL,
    metadata_json TEXT NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    INDEX ix_connector_accounts_user_id (user_id),
    INDEX ix_connector_accounts_provider (provider),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NULL,
    action VARCHAR(50) NULL,
    target_id VARCHAR(50) NULL,
    details TEXT NULL,
    timestamp DATETIME NULL,
    INDEX ix_audit_logs_id (id),
    INDEX ix_audit_logs_user_id (user_id),
    INDEX ix_audit_logs_action (action)
) ENGINE=InnoDB;
