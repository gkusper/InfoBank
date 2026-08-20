# Known limitations

Status: `PRE_FREEZE`

- PDFs have no OCR path; image-only scans may yield insufficient text.
- Durable source storage is local filesystem storage, not distributed object storage.
- No distributed transaction spans MariaDB, Chroma and filesystem; compensation and consistency scans reduce but do not eliminate crash-window risk.
- Aggregate execution supports a limited deterministic operation vocabulary and enforces k-threshold disclosure control.
- The deterministic provider validates contracts but cannot establish real provider quality, latency or cost.
- MailEx licence and redistribution are pending human confirmation.
- Gold QA, primary/secondary annotation, agreement/adjudication, citation audit and manual no-health sign-off are pending.
- A real provider run and final E1 are pending authorization; runtime estimate is unknown without an explicit local latency assumption.
- Dataset/scorer/config/code freeze and release approval are pending.
- GitHub CI is deferred; local SkipDocker and Docker/API gates are authoritative pre-freeze checks.
- Gmail token storage has no claimed application-level encryption.
- Provider pricing is unknown unless supplied through an explicit local config.
