# API end-to-end workflows

Status: `PASS` (deterministic development workflow; not final E1)

The reproducible runner is `scripts/run_api_end_to_end_workflows.py`. It starts
the production FastAPI application in-process through `TestClient` after
configuring a dedicated `infobank_eval_*` MariaDB database, Chroma directory,
durable source directory, deterministic provider, JWT secret, and aggregate
threshold. The compatibility shim in the runner only removes the obsolete
`app=` keyword passed by the installed Starlette 0.27 client to httpx 0.28;
requests still traverse Starlette's real ASGI TestClient transport and the
production routers. No OpenAI or connector network operation is available.

The successful development execution wrote 42 privacy-safe HTTP trace rows.
Every row records the method/path and redacted request fields, HTTP status,
response schema, output class, reason, citations, public audit ID, local-path
and secret safety checks, assertions, and PASS/FAIL. The trace is generated
under ignored `artifacts/api_workflows/`; the accepted run reported trace hash
`c2ea4a198463eeb73e47f8cf9d89fca438625c4ad70cef0de6491805dcac63d6`.

## W1 — owned-object onboarding

Result: `PASS`.

- Registered and authenticated the synthetic owner through `/api/register`
  and `/api/login`.
- Uploaded two one-page TVX-900 package PDFs through `/api/upload`.
- Verified source SHA-256, byte count, page/chunk counts, processing status,
  durable processing report, automatic metadata, and reviewer links.
- Replaced extracted routing keywords through the owner correction endpoint and
  verified four keyword relations with `USER` provenance and `user_edited`.
- Re-indexed through `/api/documents/{id}/reindex`; the document UUID and
  deterministic chunk IDs remained stable and duplicate chunk/vector count was
  zero.
- Opened the authorized page through `/api/documents/{id}/source?page=1`.

## W2 — warranty and support

Result: `PASS`.

- Asked the production `/api/ask` endpoint for the warranty term and reset
  procedure; it returned real deterministic-provider text and two citations to
  two different documents.
- Opened both cited pages through the authenticated source endpoint.
- Verified `REFUSE_INSUFFICIENT_EVIDENCE` for an unsupported capability,
  `REFUSE_CONFLICT` for an authority-sensitive contradiction, and
  `REFUSE_NO_MATCH` for the wrong model identifier `TVX-999`.
- The exact-object and evidence-support guard runs after policy resolution and
  can only remove generator input; it cannot weaken governance.
- All answer calls returned public audit IDs that were found in `audit_logs`.

## W3 — permission lifecycle

Result: `PASS`.

- Created an owner and reader and granted `Reader` through the policy API.
- The reader obtained a grounded, cited `FULL_ANSWER`.
- Changed the relation to `Aggregate`, granted two more aggregate sources, and
  obtained `AGGREGATE_RESULT` at k=3 without individual citations.
- Revoking one source produced `REFUSE_AGGREGATION_THRESHOLD`; revoking the
  remaining relations produced immediate internal `REFUSE_PERMISSION` with an
  empty source list and no denied document identifier in the public response.
- Transferred an isolated OWN-700 document. The old owner immediately received
  a source-not-found response, while the new owner could open the page and
  obtain a cited grounded answer.

The runner validates the database-name prefix before clearing test rows. It
does not delete a Docker volume. Synthetic PDFs, Chroma files, source files,
and traces remain ignored and untracked.
