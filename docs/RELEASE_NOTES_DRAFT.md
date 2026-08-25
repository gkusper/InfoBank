# InfoBank release notes draft

Status: `DRAFT_NOT_RELEASED`

Implemented reviewer-critical functionality includes durable UUID PDF storage,
page-aware deterministic chunks/citations, provenance, re-index/archive/restore,
governed permissions and aggregate behavior, controlled failures, offline
provider abstraction, B0-B3 development evaluation, MailEx preparation,
W1/W2/W3 API workflows, four reviewer screens and operations/QA tooling.

Existing MariaDB installations require review and application of
`citds_11_mysql.sql` and `infocom_a_gate_phase1_mysql.sql`; clean installs use
`infobank_db.sql`. Chroma and source storage must be backed up with MariaDB.
Compatibility is Python 3.11 plus MariaDB 11.4 in the tested Docker setup. OCR,
distributed transactions and broad aggregate operators are not implemented.

Rollback is backup-based, not an automatic reverse migration. Blockers are
MailEx licence/redistribution approval, human gold and MailEx annotation,
agreement/adjudication decisions, citation audit, manual no-health sign-off,
screenshot acceptance, provider/model/cost approval, freeze approval and final
E1. See `KNOWN_LIMITATIONS.md`. This draft authorizes no release action.
