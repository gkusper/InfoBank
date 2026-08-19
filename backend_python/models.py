from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.orm import relationship
from database import Base
import enum
import datetime

def _utcnow_naive():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

class PermissionType(str, enum.Enum):
    Owner = 'Owner'
    Reader = 'Reader'
    Aggregate = 'Aggregate'
    Metadata = 'Metadata'

class EvidenceSourceType(str, enum.Enum):
    Email = 'Email'
    BrowserHistory = 'BrowserHistory'
    Calendar = 'Calendar'
    ActivityTrace = 'ActivityTrace'
    DocumentNote = 'DocumentNote'
    Other = 'Other'

class PolicyAccessMode(str, enum.Enum):
    Full = 'Full'
    Aggregate = 'Aggregate'
    Metadata = 'Metadata'
    Deny = 'Deny'

class ProvenanceType(str, enum.Enum):
    Extracted = 'EXTRACTED'
    User = 'USER'
    Rule = 'RULE'
    AI = 'AI'

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

class Document(Base):
    __tablename__ = "documents"
    id = Column(String(255), primary_key=True)
    file_path = Column(String(512), nullable=False)
    original_filename = Column(String(512), nullable=True)
    source_storage_path = Column(String(512), nullable=True)
    source_sha256 = Column(String(64), nullable=True, index=True)
    source_mime_type = Column(String(100), nullable=True)
    source_byte_size = Column(BigInteger, nullable=True)
    page_count = Column(Integer, nullable=True)
    source_status = Column(String(30), nullable=False, default="ACTIVE", index=True)
    processing_status = Column(String(30), nullable=False, default="PENDING")
    processing_config_version = Column(String(100), nullable=True)
    processing_config_hash = Column(String(64), nullable=True)
    source_url = Column(String(2048), nullable=True)
    source_license = Column(String(255), nullable=True)
    pdf_title = Column(String(512), nullable=True)
    pdf_author = Column(String(512), nullable=True)
    pdf_creation_date = Column(String(100), nullable=True)
    upload_date = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)
    archived_at = Column(DateTime, nullable=True)
    visibility = Column(String(50), default="Private") 
    
    permissions = relationship("UserDocumentPermission", back_populates="document")
    chunks = relationship("DocumentChunk", back_populates="document")
    metadata_provenance = relationship("DocumentMetadataProvenance", back_populates="document", cascade="all, delete-orphan")
    processing_reports = relationship("DocumentProcessingReport", back_populates="document", cascade="all, delete-orphan")

class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), unique=True, nullable=False)

class DocumentKeyword(Base):
    __tablename__ = "document_keywords"
    document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id", ondelete="CASCADE"), primary_key=True)
    provenance_type = Column(
        Enum(ProvenanceType, values_callable=lambda members: [member.value for member in members]),
        nullable=False,
        default=ProvenanceType.Rule,
    )
    provenance_json = Column(Text, nullable=True)
    extraction_method = Column(String(100), nullable=True)
    model_version = Column(String(255), nullable=True)
    prompt_version = Column(String(100), nullable=True)
    user_edited = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(String(36), primary_key=True)
    document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    block_index = Column(Integer, nullable=True)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    text_content = Column(Text, nullable=False)
    content_sha256 = Column(String(64), nullable=True)
    source_sha256 = Column(String(64), nullable=True)
    chunk_config_version = Column(String(100), nullable=True)
    chunk_config_hash = Column(String(64), nullable=True)
    vector_id = Column(String(255), nullable=False)
    
    document = relationship("Document", back_populates="chunks")

class DocumentMetadataProvenance(Base):
    __tablename__ = "document_metadata_provenance"
    id = Column(String(36), primary_key=True)
    document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    field_value = Column(Text, nullable=True)
    provenance_type = Column(
        Enum(ProvenanceType, values_callable=lambda members: [member.value for member in members]),
        nullable=False,
    )
    method = Column(String(100), nullable=False)
    model_version = Column(String(255), nullable=True)
    prompt_version = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    document = relationship("Document", back_populates="metadata_provenance")

class DocumentProcessingReport(Base):
    __tablename__ = "document_processing_reports"
    id = Column(String(36), primary_key=True)
    document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    operation = Column(String(30), nullable=False)
    config_version = Column(String(100), nullable=False)
    config_hash = Column(String(64), nullable=False)
    report_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow_naive)

    document = relationship("Document", back_populates="processing_reports")

class UserDocumentPermission(Base):
    __tablename__ = "user_document_permission"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String(255), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    permission_type = Column(Enum(PermissionType), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    document = relationship("Document", back_populates="permissions")

class EvidenceUnit(Base):
    """Owned evidence unit for the CITDS action-list scenario.

    This table lets the prototype ingest email messages, browser-history items,
    calendar events, and other activity traces without connecting to external
    private services. It is the implementation hook for the paper's owned email
    and browser-history reconstruction scenario.
    """

    __tablename__ = "evidence_units"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(Enum(EvidenceSourceType), nullable=False, default=EvidenceSourceType.Other)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_timestamp = Column(DateTime, nullable=True)
    thread_id = Column(String(255), nullable=True, index=True)
    relation_key = Column(String(255), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PolicyRule(Base):
    """Purpose-aware policy rule for InfoBank governance experiments.

    The current application still primarily uses document visibility, but these
    rules allow a document or evidence unit to be marked Full/Aggregate/Metadata/Deny
    for a purpose such as action reconstruction or grounded question answering.
    """

    __tablename__ = "policy_rules"
    id = Column(String(36), primary_key=True)
    owner_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = Column(String(50), nullable=False)  # Document or EvidenceUnit
    target_id = Column(String(255), nullable=False, index=True)
    purpose = Column(String(100), nullable=False, default="any")
    access_mode = Column(Enum(PolicyAccessMode), nullable=False, default=PolicyAccessMode.Full)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ConnectorAccount(Base):
    """OAuth connector account state for external evidence sources.

    Used by the Gmail connector. Tokens are stored as JSON for the prototype;
    production should encrypt this column or move it to a secrets vault.
    """

    __tablename__ = "connector_accounts"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="connected")
    token_json = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(50), index=True)
    action = Column(String(50), index=True)
    target_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
