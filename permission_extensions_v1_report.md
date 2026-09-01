# Permission Extensions v1 Report

## Branch and Base

- Working branch: `feature/permission-extensions-v1`
- Base branch refreshed from: `origin/infocom2026`
- Base commit observed after fetch: `039dfac5c83266a54b725e614736bd4c3595e204`
- Push status: local implementation is complete; pushing the feature branch is blocked by this host's GitHub auth or transport environment. A post-network-permission retry exited with code 1 after `Pushing to https://github.com/gkusper/InfoBank.git`, and the remote feature branch was not created.

## Current Permission Model

### Persistent Permissions

Persistent document permissions are stored in `user_document_permission` and are user-specific document relations:

- `Owner`: full owner relation, not grantable through the persistent grant endpoint.
- `Reader`: grants full document use at query time.
- `Aggregate`: grants aggregate-only document use at query time.
- `Metadata`: grants metadata-only document use at query time.
- `Audit`: grants document-scoped audit visibility only and does not grant document content, metadata, source, or graph access.

The persistent permission table now supports only the retained governance extensions:

- `max_queries`
- `queries_used`
- `requires_explainability`

It deliberately does not include persistent grant `purpose`, `valid_from`, or `valid_until` columns.

### Query-Time Effective Decisions

Runtime policy resolution still produces the CITDS use decisions:

- `Full`
- `Aggregate`
- `Metadata`
- `Deny`

Resolution order remains:

1. Missing or archived documents deny access.
2. Active document-level `PolicyRule` entries apply, with explicit `Deny` taking priority.
3. Direct persistent user-document permissions apply.
4. Public document visibility can provide aggregate or metadata access.
5. Private documents without an active grant or rule deny access.

Query-limited grants and explainability-required grants are enforced only when the runtime decision flows through the direct persistent permission path. Policy-rule and public-visibility paths remain independent.

### Document-Level PolicyRule Conditions

The existing document-level and evidence-unit `PolicyRule` model still supports:

- `purpose`
- `valid_from`
- `valid_until`

This behavior is preserved and regression-tested. It is the supported mechanism for purpose and time conditions in the current prototype. It was not removed or redesigned.

### Document Inventory Caveat

Document inventory currently follows direct account permissions rather than the full document policy-rule path. This caveat is preserved. The only narrow inventory change in this scope is that `Audit`-only persistent permissions are withheld from the chat document inventory so audit-only users do not receive metadata access through that path.

## Newly Implemented Mechanisms

### 1. Query-Limited Access

Status: implemented.

- `max_queries` and `queries_used` are stored on persistent user-document permissions.
- Resolvers deny exhausted direct persistent grants with `persistent_permission_quota_exhausted`.
- Quota consumption happens once per used quota-limited permission during `/api/ask`.
- Diagnostic resolution, policy previews, document inventory, source viewing, and audit viewing do not consume query quota.
- Consumption uses an atomic conditional update so concurrent requests cannot overspend a grant.
- Query-limit exhaustion is returned through the controlled governance failure path with public-safe redaction.

### 2. Explainability-Required Access

Status: implemented.

- `requires_explainability` is stored on persistent user-document permissions.
- Runtime governance tracks documents whose access path requires explainability.
- Full-source answers must have traceable citation metadata.
- Metadata-only and governed aggregate responses satisfy the requirement through their public trace paths.
- Unsatisfied requirements produce a controlled governance refusal with `EXPLAINABILITY_REQUIRED_UNSATISFIED`.
- Public responses expose only aggregate counts and safe reason codes, not document or permission identifiers.

### 3. Audit-Only Access

Status: implemented.

- `Audit` is a persistent permission type.
- Audit-only grants do not map to `Full`, `Aggregate`, or `Metadata` document use decisions.
- Audit-only users cannot view document source, semantic graph content, raw metadata rows, or chat inventory rows.
- `document_audit_links` indexes audit-log to document relations.
- `/api/admin/documents/{doc_id}/audit` returns redacted document-scoped audit records to document owners and audit-only grantees.
- Permission grant and revoke audit events are linked to the affected document without exposing raw document content.

## Deliberately Out Of Scope

### Persistent Time-Bounded Grants

Status: not implemented, out of scope.

Persistent user-specific grants do not have `valid_from` or `valid_until` constraints. Existing document-level `PolicyRule.valid_from` and `PolicyRule.valid_until` functionality remains the supported time-bound mechanism.

### Persistent Purpose-Bound Grants

Status: not implemented, out of scope.

Persistent user-specific grants do not have a `purpose` constraint. Existing document-level `PolicyRule.purpose` functionality remains the supported purpose-bound mechanism.

## Schema and API Summary

- `PermissionType` includes `Audit`.
- `user_document_permission` includes `max_queries`, `queries_used`, and `requires_explainability`.
- `user_document_permission` excludes `purpose`, `valid_from`, and `valid_until`.
- `policy_rules` still includes `purpose`, `valid_from`, and `valid_until`.
- `document_audit_links` records structured audit-to-document relationships.
- Persistent grant API accepts `permission_type`, `max_queries`, and `requires_explainability`.
- Persistent grant API no longer accepts persistent grant `purpose`, `valid_from`, or `valid_until`.
- Policy-rule API continues to accept `purpose`, `valid_from`, and `valid_until`.

## Verification

Commands run with workspace-local pytest temp storage:

- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests/test_permission_unit_specs.py`
  - Result: 25 passed, 23 warnings.
- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests/test_permission_extensions_v1.py`
  - Result: 10 passed, 18 warnings.
- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests/test_permission_unit_specs.py backend_python/tests/test_permission_extensions_v1.py backend_python/tests/test_policy_invariants.py backend_python/tests/test_aggregate_executor.py backend_python/tests/test_citations.py backend_python/tests/test_document_inventory.py backend_python/tests/test_security_invariants.py backend_python/tests/test_semantic_graph.py`
  - Result: 83 passed, 61 warnings.
- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests/test_permission_extensions_v1.py backend_python/tests/test_policy_invariants.py backend_python/tests/test_schema_contract.py backend_python/tests/test_database_schema.py backend_python/tests/test_citations.py backend_python/tests/test_document_inventory.py`
  - Result: 51 passed, 42 warnings.
- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests/test_reviewer_contracts.py backend_python/tests/test_security_invariants.py backend_python/tests/test_semantic_graph.py`
  - Result: 43 passed, 11 warnings.
- `python -m pytest -q -p no:cacheprovider --basetemp pytest-tmp backend_python/tests`
  - Result: 268 passed, 101 warnings.

Warnings are existing dependency and `datetime.utcnow()` deprecation warnings.

## Console Summary

Implemented query-limited access, explainability-required access, and audit-only access with runtime enforcement plus requirement-coded unit tests. Preserved existing document-level `PolicyRule` purpose/time behavior. Persistent time-bounded grants and persistent purpose-bound grants are intentionally not implemented and remain out of scope.
