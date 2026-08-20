# InfoBank user manual

Status: `PRE_FREEZE_TECHNICAL_MANUAL`

## Core workflow

1. Log in with an administrator-created or locally registered account. A failed login shows a generic authentication error; do not share credentials.
2. Open **Documents**, choose a PDF and an initial Owner/Aggregate/Metadata visibility, then select **Upload & Ingest**. Processing stores the PDF by UUID, extracts text per page, creates deterministic chunks and proposes keywords.
3. Review the UUID, source SHA-256, processing/source state, page/chunk counts, metadata and keyword provenance. Owners can edit keywords. **Re-index** preserves the document UUID and reviewed keywords; **Archive** removes active retrieval use without deleting the durable source; **Restore** reprocesses it.
4. Use **source** or a citation's **Open cited source page** action to inspect an authorized page. The UI never exposes an internal filesystem path.
5. Ask one focused question in **Assistant**. Check the output class, evidence decision, audit ID, routing trace, source role, effective use decision, and document/page/chunk citation before relying on the answer.

## Output classes and citations

`FULL_ANSWER` is supported by permitted primary evidence. Other successful but
bounded modes include `CONSTRAINED_ANSWER`, `AGGREGATE_RESULT`, and
`METADATA_ONLY`. Controlled failures include permission, no-match,
insufficient-evidence, conflict, aggregation-threshold, clarification, and
escalation modes. A refusal is expected safety behavior, not a transport error.
Permission and no-match messages are deliberately non-enumerating and do not
identify denied or absent sources. A citation is valid only when document UUID,
page and chunk are present and the source-page endpoint authorizes access.

## Permissions and actions

In **Permissions**, an owner grants or changes Reader, Aggregate, or Metadata
access for a target user, can revoke it, and can add purpose/validity rules with
Full, Aggregate, Metadata, or Deny resolution. Deny, revocation, archive,
purpose mismatch and invalid time windows block content before routing.

**Actions & Evidence** reconstructs actions only from primary evidence.
Contextual browser history cannot create an action. Later linked contrastive
evidence can close, cancel, or supersede an action; evidence IDs and audit
signals remain visible.

## W1, W2 and W3

- W1: owner uploads, reviews provenance/keywords, re-indexes and opens a cited source while stable identity and deduplication are checked.
- W2: multi-document warranty/support answering plus insufficient-evidence, conflict and wrong-object hard-negative behavior.
- W3: Reader/Aggregate/threshold/revoke/archive/transfer policy behavior. After all relevant grants are revoked, the expected internal class is `REFUSE_PERMISSION` with safe public wording.

## Common visible errors

- `401/403`: session expired or access/purpose is not effective; log in again or ask the owner to review policy. Do not expect the UI to confirm a denied source.
- Upload/re-index failure: verify PDF format, source integrity, DB connectivity, source-store write access and Chroma location; OCR-only scans are unsupported.
- `REFUSE_NO_MATCH`: the permitted corpus is searchable but no exact relevant object/source match was found; check the object identifier.
- `REFUSE_PERMISSION`: governance blocked the request; use the safe next step.
- Aggregate threshold refusal: fewer than the configured k permitted members were available; individual values are not disclosed.
- Source open failure: the citation may be stale, archived, missing, corrupt or no longer authorized. An administrator should run the dry-run consistency scan.
