# Source capability rules, version 1.0

The registry is a reusable, versioned list of typed `Rule` records. Each contains a source type, claim/relation family, capability state, permitted use, additional-evidence requirement, rule ID and version. `capability(..., registry=...)` accepts an application-configured registry. The frozen pilot uses the committed default registry. Configuration is a trusted application input, not document text or an LLM instruction.

Source provenance is provided at the ingestion boundary through a `Provenance` object bound to neutral view ID, source type and content SHA-256. The original synthetic InfoBank fixtures provide an explicitly trusted test-ingestion source type; this does not demonstrate production connector authentication. RefusalBench passages receive no invented connector provenance. Aggregate and metadata view types are authoritative policy projections. Missing, unknown or stale provenance produces UNKNOWN, which alone is not a veto against otherwise supported evidence.

| Rule | Trusted type | Relation | State / permitted use |
|---|---|---|---|
| SRC-BROWSER-VISIT | BrowserHistory | PAGE_VISIT | PERMITTED: recorded visit |
| SRC-BROWSER-OBLIGATION | BrowserHistory | OBLIGATION | ADDITIONAL_EVIDENCE_REQUIRED: obligation evidence |
| SRC-BROWSER-ACTION | BrowserHistory | RECORDED_ACTION | ADDITIONAL_EVIDENCE_REQUIRED: acceptance/recorded action |
| SRC-BROWSER-COMPLETION | BrowserHistory | COMPLETION | ADDITIONAL_EVIDENCE_REQUIRED: completion evidence |
| SRC-EMAIL-REQUEST | Email | COMMUNICATED_REQUEST | PERMITTED: communicated request/statement |
| SRC-EMAIL-COMPLETION | Email | COMPLETION | ADDITIONAL_EVIDENCE_REQUIRED: evidence of actual completion |
| SRC-INVOICE-ISSUE | Invoice | ISSUANCE | PERMITTED: issuance |
| SRC-INVOICE-AMOUNT | Invoice | AMOUNT | PERMITTED: stated invoiced amount |
| SRC-INVOICE-PAYMENT | Invoice | PAYMENT | ADDITIONAL_EVIDENCE_REQUIRED: payment evidence |
| SRC-RECEIPT-PAYMENT | PaymentReceipt | PAYMENT | PERMITTED: documented payment |
| SRC-RECEIPT-CLOSURE | PaymentReceipt | ALL_OBLIGATIONS_CLOSED | ADDITIONAL_EVIDENCE_REQUIRED: all requested closures |
| SRC-TASK-ACTION | TaskNote | RECORDED_ACTION | PERMITTED: recorded task/next action |
| SRC-TASK-COMPLETION | TaskNote | COMPLETION | ADDITIONAL_EVIDENCE_REQUIRED: completion evidence |
| SRC-AGGREGATE | AggregateReport | AGGREGATE | PERMITTED: authorized aggregate |
| SRC-AGGREGATE-INDIVIDUAL | AggregateReport | INDIVIDUAL | FORBIDDEN in this view |
| SRC-METADATA | DocumentMetadata | METADATA | PERMITTED: whitelisted fields |
| SRC-METADATA-BODY | DocumentMetadata | DOCUMENT_BODY | FORBIDDEN in this view |

PERMITTED means the source kind is compatible with the use; semantic sufficiency remains unproved. FORBIDDEN means the stated view cannot establish that disclosure. ADDITIONAL_EVIDENCE_REQUIRED means a task description, request or financial record is insufficient by itself for the stronger requested fact. Another authorized PRIMARY source can supply the missing relation. UNKNOWN leaves the original semantic assessment operative and records the provenance limitation.

These are conservative defaults for claim-relative uses, not assertions that all emails or task notes lack completion evidence. Deployments with authenticated completion records should configure a more specific trusted source capability or provide the additional evidence. This pilot does not empirically validate such exceptions. A source can be PRIMARY for a recorded visit and CONTEXTUAL for an obligation; the rule changes effective role per requirement, not globally by source type.

Relation families are conservatively derived from existing query requirements and limited query-text patterns. Unrecognized relations stay UNSPECIFIED/UNKNOWN. Type labels appearing in document body text have no authority. An LLM cannot supply trusted provenance or overwrite the registry. The source layer makes zero model calls.

Access remains independent: the registry never opens a DENY view, discloses an individual record from an aggregate or reveals document-body content through metadata. The inherited policy gate remains authoritative in every configuration, including A0 and source-only A2.
