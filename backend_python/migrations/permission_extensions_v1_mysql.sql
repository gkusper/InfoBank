-- Permission/governance extensions v1.
-- Adds constrained persistent grants and document-scoped audit indexing without
-- changing existing document identities or stored source records.

ALTER TABLE user_document_permission
    MODIFY permission_type ENUM('Owner', 'Reader', 'Aggregate', 'Metadata', 'Audit') NOT NULL;

ALTER TABLE user_document_permission
    ADD COLUMN IF NOT EXISTS max_queries INT NULL AFTER permission_type,
    ADD COLUMN IF NOT EXISTS queries_used INT NOT NULL DEFAULT 0 AFTER max_queries,
    ADD COLUMN IF NOT EXISTS requires_explainability BOOLEAN NOT NULL DEFAULT FALSE AFTER queries_used;

UPDATE user_document_permission
SET queries_used = 0
WHERE queries_used IS NULL;

CREATE TABLE IF NOT EXISTS document_audit_links (
    id VARCHAR(36) PRIMARY KEY,
    audit_log_id VARCHAR(50) NOT NULL,
    document_id VARCHAR(255) NOT NULL,
    relation_type VARCHAR(50) NOT NULL DEFAULT 'governance',
    created_at DATETIME NULL,
    INDEX ix_document_audit_links_audit_log_id (audit_log_id),
    INDEX ix_document_audit_links_document_id (document_id),
    FOREIGN KEY (audit_log_id) REFERENCES audit_logs(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB;
