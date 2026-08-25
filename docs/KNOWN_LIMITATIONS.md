# Known limitations

Status: `PRE_FREEZE`

- PDFs have no OCR path; image-only scans may yield insufficient text.
- Durable source storage is local filesystem storage, not distributed object storage.
- PDF processing runs in the API worker rather than a distributed job queue. Durable processing state and same-UUID re-index retry are implemented, but multi-worker scheduling and automatic backoff are not.
- No distributed transaction spans MariaDB, Chroma and filesystem; compensation and consistency scans reduce but do not eliminate crash-window risk.
- Aggregate execution supports a limited deterministic operation vocabulary and enforces k-threshold disclosure control.
- Free-text aggregate input is accepted only when a retrieved chunk contains one unambiguous numeric token; structured multi-metric aggregation is future work.
- The deterministic provider validates contracts but cannot establish real provider quality, latency or cost.
- MailEx licence and redistribution are pending human confirmation.
- Gold QA, primary/secondary annotation, agreement/adjudication, citation audit and manual no-health sign-off are pending.
- A real provider run and final E1 are pending authorization; runtime estimate is unknown without an explicit local latency assumption.
- Dataset/scorer/config/code freeze and release approval are pending.
- GitHub CI is deferred; local SkipDocker and Docker/API gates are authoritative pre-freeze checks.
- Gmail OAuth/token cryptography has deterministic local tests, but no real Google-provider callback/sync run is claimed. Key rotation currently requires Gmail reconnection rather than online token re-encryption.
- Provider pricing is unknown unless supplied through an explicit local config.
