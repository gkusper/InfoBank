# Permission Unit Test Report

## Summary

Added `backend_python/tests/test_permission_unit_specs.py` with 25 deterministic unit-style tests derived from the permission/governance descriptions. The new tests focus on resolver behavior, helper-level enforcement, safe projections, and redaction boundaries. They avoid LLM calls, live HTTP servers, browser/UI flows, and real external services.

## New Unit Test Coverage

### Core Persistent Permissions

- `PERM-OWN-01`: owner resolves to `Full`.
- `PERM-OWN-04`: owner can grant `Reader`, `Aggregate`, `Metadata`, and `Audit`; owner/self replacement is rejected.
- `PERM-OWN-06`: ownership transfer is immediate and replaces an existing non-owner relation.
- `PERM-OWN-07`: non-owner permissions cannot perform owner administration.
- `PERM-READ-01`: reader resolves to `Full`.
- `PERM-READ-04`: reader cannot grant, revoke, transfer, or pass owner checks.
- `PERM-META-01`: metadata permission exposes metadata-safe representation only.
- `PERM-META-02`: metadata permission does not provide document text as content context.
- `PERM-META-03`: metadata-only sources do not produce content citations.
- `PERM-META-05`: metadata does not imply reader/full access.
- `PERM-DENY-01`: private document without permission resolves to `Deny`.
- `PERM-DENY-02`: active explicit `Deny` overrides permissive access.
- `PERM-DENY-05`: archived documents are denied.

### Query-Limited Access

- `QL-01`: unlimited grants preserve legacy behavior and never enter quota consumption.
- `QL-02`: first eligible use of a single-use style grant consumes one unit.
- `QL-03`: exhausted grants no longer authorize access.
- `QL-04`: an N-query permission allows exactly N consumptions.
- `QL-05`: duplicate internal references to the same permission consume at most once per request.
- `QL-06`: policy diagnostic resolution does not consume quota.
- `QL-07`: document inventory reads do not consume quota.
- `QL-09`: an exhausted grant does not suppress an independent active policy-rule authorization path.
- `QL-10`: query-limit refusal/public projection does not leak document names, IDs, permission IDs, or query counter internals.

`QL-08` remains covered by the existing focused concurrency test in `test_permission_extensions_v1.py`, because it is inherently concurrent and therefore not a pure unit test.

### Explainability-Required Access

- `EX-02`: explainability-required full access succeeds with valid citation provenance.
- `EX-03`: untraceable full access is blocked by the explainability gate.
- `EX-05`: invalid provenance does not fabricate citations.
- `EX-06`: explainability-required aggregate output remains anonymous.
- `EX-07`: explainability does not re-enable aggregate document-level citations.
- `EX-08`: metadata explanation remains metadata-only.
- `EX-09`: explainability-required state is visible in the internal document audit summary.

`EX-01` and `EX-04` are already exercised by the existing permission-extension and controlled-failure tests; they are broader behavioral regressions rather than better new unit boundaries.

### Audit-Only Access

- `AUD-01`: owner can resolve document audit access.
- `AUD-02`: audit permission grants document-scoped audit visibility.
- `AUD-03`: audit permission does not grant full/content access.
- `AUD-05`: audit permission does not grant aggregate access.
- `AUD-06`: audit permission does not grant metadata access through normal document inventory surfaces.
- `AUD-07`: audit user cannot administer the document.
- `AUD-08`: safe audit projection excludes raw document/chunk text.
- `AUD-09`: safe audit projection excludes generated answer bodies.
- `AUD-10`: safe audit projection excludes aggregate individual values.
- `AUD-11`: safe audit projection excludes private file paths.
- `AUD-12`: audit permission is document-scoped.
- `AUD-13`: revoked audit permission stops future audit access.

### Policy and Precedence Regression

- `POL-01`: active document policy rules are applied before direct permission fallback.
- `POL-02`: future `valid_from` rules are ignored.
- `POL-03`: expired `valid_until` rules are ignored.
- `POL-04`: purpose-mismatching rules are ignored.
- `POL-05`: active explicit `Deny` has highest priority.
- `POL-06`: `purpose`, `valid_from`, and `valid_until` remain document-level `PolicyRule` conditions and are not modeled as user-specific persistent grant constraints.

### Cross-Channel Leakage

- `SEC-03`: non-full decisions never produce full document citations, even with valid document/chunk inputs.
- `SEC-04`: public policy/governance projection does not reveal hidden document data or permission internals.
- `SEC-06`: metadata-only access cannot provide hidden document text to generation helpers.

## Not Added As New Unit Tests

The following descriptions are better kept as integration, endpoint, or e2e tests because they involve source-file retrieval, full `/api/ask` orchestration, semantic routing, graph export, or UI-level workflows:

- `PERM-OWN-02`
- `PERM-OWN-03`
- `PERM-READ-02`
- `PERM-READ-03`
- `PERM-AGG-01`
- `PERM-META-04`
- `PERM-DENY-03`
- `QL-08`
- `EX-04`
- `AUD-04`
- `SEC-01`
- `SEC-02`
- `SEC-05`

Several of these are already represented in existing integration-style regression files such as `test_citations.py`, `test_document_inventory.py`, `test_permission_extensions_v1.py`, `test_semantic_graph.py`, and `test_reviewer_contracts.py`.

## Verification

Commands run with workspace-local pytest temp storage:

- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests/test_permission_unit_specs.py`
  - Result: 25 passed, 23 warnings.
- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests/test_permission_unit_specs.py backend_python/tests/test_permission_extensions_v1.py backend_python/tests/test_policy_invariants.py backend_python/tests/test_aggregate_executor.py backend_python/tests/test_citations.py backend_python/tests/test_document_inventory.py backend_python/tests/test_security_invariants.py backend_python/tests/test_semantic_graph.py`
  - Result: 83 passed, 61 warnings.
- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests`
  - Result: 268 passed, 101 warnings.

Warnings are existing dependency and `datetime.utcnow()` deprecation warnings.
