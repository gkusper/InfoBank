# Metadata and Keyword Pipeline

## Field-level metadata

Every stored document metadata field listed below has a `document_metadata_provenance` record. Derived report metrics (for example chunk counts and duration), intrinsic identifiers, permission rows, and policy decisions have explicit system provenance through their named calculation, database relation, or policy-engine method rather than a metadata-provenance row.

| Field | Source | Provenance | Method |
|---|---|---|---|
| `original_filename` | Upload form, basename-normalized | USER | `upload-form` |
| `source_storage_path` | UUID namespace and generated filename | RULE | `uuid-source-storage-v1` |
| `mime_type` | Upload content type | EXTRACTED | `upload-content-type` |
| `source_sha256` | Exact uploaded bytes | EXTRACTED | `sha256` |
| `source_byte_size` | Exact uploaded bytes | EXTRACTED | `byte-count` |
| `page_count` | PDF parser | EXTRACTED | `PyMuPDF` |
| `pdf_title`, `pdf_author`, `pdf_creation_date` | Available PDF metadata | EXTRACTED | `PyMuPDF-metadata` |
| `processing_config_version`, `processing_config_hash` | Versioned configuration | RULE | `document-processing-config` |
| `source_status`, `processing_status` | Processing/lifecycle state machine | RULE | `document-lifecycle-v1` / `document-processing-v1` |
| `visibility` | Upload permission selection | USER | `upload-permission-form` |
| `source_url`, `source_license` | Optional owner input | USER | `upload-form` / `owner-metadata-edit` |

Provenance types are `EXTRACTED`, `USER`, `RULE`, and `AI`. Re-index replaces extracted/rule provenance but preserves explicit USER metadata.

## Keyword extraction

- Prompt version: `keyword-v1`.
- Default model: `gpt-4o-mini`.
- Processing reports distinguish the configured prompt version from the actually used AI prompt/model; used prompt/model fields are null during deterministic fallback.
- AI method: `openai-chat` with normalized lowercase single tokens.
- Rule method: `routing-rules-v1`.
- Deterministic fallback: `token-frequency-v1`, a small stop-word set, frequency descending and lexical tie-breaking.
- Duplicate values are represented by one document-keyword relation whose `provenance_json` retains all distinct provenance entries.
- Missing provider configuration selects deterministic fallback without making a provider call.
- A configured provider/API failure is caught after the attempted call and then selects deterministic fallback.
- Malformed provider output is treated as a caught provider-output failure and selects deterministic fallback.
- Owner keyword edits replace the editable set and mark relations `USER` with `user_edited=true`.
- Re-index preserves user-edited keywords unless a later API explicitly requests reset semantics.

## Endpoint and module mapping

| Operation | Endpoint / module |
|---|---|
| Initial extraction | `POST /api/upload`, `document_processing.py` |
| Owner metadata edit | `POST /api/documents/{document_id}/metadata` |
| Owner keyword edit | `POST /api/documents/update-keywords` |
| Reprocessing | `POST /api/documents/{document_id}/reindex` |
| Latest report JSON/CSV | `GET /api/documents/{document_id}/processing-report` |

Readers, Aggregate users, Metadata users, and denied users cannot edit metadata or keywords. Tests use mocked provider/embedding calls: missing-key coverage makes no call, while provider-error coverage verifies a caught attempted mock call. No test makes a real provider request.
