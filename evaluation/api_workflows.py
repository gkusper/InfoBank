"""Reproducible API-level reviewer workflows for owned-object evaluation.

The runner intentionally imports the FastAPI application only after its
isolated runtime environment has been configured.  Every externally visible
operation is performed through TestClient; direct database reads are used only
for durable-state assertions that have no public endpoint.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend_python"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pdf_bytes(title: str, lines: list[str]) -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), title, fontsize=16)
    y = 104
    for line in lines:
        page.insert_textbox((72, y, 540, y + 54), line, fontsize=11)
        y += 58
    payload = document.tobytes(garbage=4, deflate=True)
    document.close()
    return payload


def _safe_request(payload: dict[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in (payload or {}).items():
        if "password" in key.lower() or "token" in key.lower():
            safe[key] = "[REDACTED]"
        elif isinstance(value, bytes):
            safe[key] = {"byte_size": len(value), "sha256": _sha256(value)}
        else:
            safe[key] = value
    return safe


def _response_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _response_schema(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_response_schema(value[0])] if value else []
    if value is None:
        return "null"
    return type(value).__name__


def _reason_code(body: dict[str, Any]) -> str | None:
    failure = body.get("controlled_failure") or body.get("evidence_check", {}).get("controlled_failure") or {}
    return failure.get("reason") or body.get("evidence_check", {}).get("aggregate_execution", {}).get("reason_code")


def _citations(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        source.get("citation", {})
        for source in body.get("sources", [])
        if source.get("citation", {}).get("available")
    ]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@dataclass
class WorkflowRecorder:
    records: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        *,
        workflow: str,
        step: str,
        method: str,
        path: str,
        request: dict[str, Any] | None,
        response: Any,
        checks: dict[str, bool],
    ) -> dict[str, Any]:
        try:
            body = response.json()
        except Exception:
            body = {"content_type": response.headers.get("content-type"), "byte_size": len(response.content)}
        public_body = body if isinstance(body, dict) else {"value": body}
        row = {
            "workflow": workflow,
            "step": step,
            "request": {"method": method, "path": path, "fields": _safe_request(request)},
            "status_code": response.status_code,
            "response_schema": _response_schema(public_body),
            "output_class": public_body.get("output_mode"),
            "reason_code": _reason_code(public_body),
            "citations": _citations(public_body),
            "audit_id": public_body.get("audit_id"),
            "safety": {
                "no_secret_fields": not any(key.lower() in {"access_token", "password", "password_hash"} for key in public_body),
                "no_absolute_local_path": ":\\" not in json.dumps(public_body, ensure_ascii=True),
            },
            "checks": checks,
            "result": "PASS" if all(checks.values()) else "FAIL",
            "response": public_body,
        }
        self.records.append(row)
        _assert(row["result"] == "PASS", f"{workflow}/{step} failed: {row}")
        return public_body


class ApiHarness:
    def __init__(self, client: Any, recorder: WorkflowRecorder) -> None:
        self.client = client
        self.recorder = recorder

    @staticmethod
    def headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def request(
        self,
        workflow: str,
        step: str,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        checks: Callable[[Any, dict[str, Any]], dict[str, bool]] | None = None,
    ) -> dict[str, Any]:
        headers = self.headers(token) if token else {}
        response = self.client.request(method, path, headers=headers, json=json_body, data=data, files=files)
        try:
            body = response.json()
        except Exception:
            body = {}
        check_values = checks(response, body) if checks else {"http_success": response.status_code < 400}
        request_fields = json_body or data or {}
        if files:
            request_fields = dict(request_fields)
            request_fields["file"] = {
                "filename": files["file"][0],
                "byte_size": len(files["file"][1]),
                "sha256": _sha256(files["file"][1]),
            }
        return self.recorder.record(
            workflow=workflow,
            step=step,
            method=method,
            path=path,
            request=request_fields,
            response=response,
            checks=check_values,
        )


def _register_and_login(api: ApiHarness, label: str) -> tuple[str, str]:
    username = f"reviewer-{label}"
    email = f"{label}@example.invalid"
    password_parts = ("Deterministic", "Review", "47!")
    credential_value = "-".join(password_parts)
    api.request(
        "W1" if label == "owner" else "W3",
        f"register-{label}",
        "POST",
        "/api/register",
        json_body={"username": username, "email": email, "password": credential_value},
        checks=lambda response, body: {"registered": response.status_code == 200 and body.get("status") == "success"},
    )
    body = api.request(
        "W1" if label == "owner" else "W3",
        f"login-{label}",
        "POST",
        "/api/login",
        json_body={"email": email, "password": credential_value},
        checks=lambda response, value: {
            "authenticated": response.status_code == 200 and bool(value.get("access_token")),
            "user_id_present": bool(value.get("user_id")),
        },
    )
    return body["access_token"], body["user_id"]


def _upload(api: ApiHarness, workflow: str, step: str, token: str, filename: str, title: str, lines: list[str]) -> dict[str, Any]:
    payload = _pdf_bytes(title, lines)
    return api.request(
        workflow,
        step,
        "POST",
        "/api/upload",
        token=token,
        data={"permission_type": "Owner", "source_license": "Synthetic development fixture"},
        files={"file": (filename, payload, "application/pdf")},
        checks=lambda response, body: {
            "uploaded": response.status_code == 200 and body.get("status") == "success",
            "durable_hash": body.get("source_sha256") == _sha256(payload),
            "processed": body.get("chunk_count", 0) > 0 and body.get("page_count") == 1,
        },
    )


def _set_keywords(api: ApiHarness, workflow: str, step: str, token: str, doc_id: str, keywords: list[str]) -> None:
    api.request(
        workflow,
        step,
        "POST",
        "/api/documents/update-keywords",
        token=token,
        data={"doc_id": doc_id, "keywords": ", ".join(keywords)},
        checks=lambda response, body: {
            "updated": response.status_code == 200 and body.get("status") == "success",
            "exact_keywords": sorted(value.lower() for value in body.get("keywords", [])) == sorted(value.lower() for value in keywords),
        },
    )


def _ask(api: ApiHarness, workflow: str, step: str, token: str, question: str, expected_mode: str, *, citation_minimum: int = 0) -> dict[str, Any]:
    return api.request(
        workflow,
        step,
        "POST",
        "/api/ask",
        token=token,
        data={"question": question},
        checks=lambda response, body: {
            "http_success": response.status_code == 200,
            "expected_output_class": body.get("output_mode") == expected_mode,
            "audit_id_present": bool(body.get("audit_id")),
            "public_answer_present": bool(body.get("answer") or body.get("message")),
            "citation_minimum": len(_citations(body)) >= citation_minimum,
        },
    )


def _grant(api: ApiHarness, step: str, owner_token: str, doc_id: str, target_username: str, permission: str) -> None:
    api.request(
        "W3",
        step,
        "POST",
        f"/api/policy/documents/{doc_id}/permissions",
        token=owner_token,
        data={"target_username": target_username, "permission_type": permission},
        checks=lambda response, body: {
            "granted": response.status_code == 200 and body.get("permission_type") == permission,
        },
    )


def _run_workflows(client: Any, database: Any, models: Any, ai_service: Any, output_dir: Path) -> dict[str, Any]:
    recorder = WorkflowRecorder()
    api = ApiHarness(client, recorder)
    owner_token, owner_id = _register_and_login(api, "owner")
    reader_token, reader_id = _register_and_login(api, "reader")

    warranty = _upload(
        api, "W1", "upload-tv-warranty", owner_token, "tvx-900-warranty.pdf", "TVX-900 Warranty",
        ["The TVX-900 limited warranty term is twenty-four months from purchase.", "Keep the purchase record for warranty support."],
    )
    warranty_id = warranty["document_id"]
    support = _upload(
        api, "W1", "upload-tv-support", owner_token, "tvx-900-support.pdf", "TVX-900 Support",
        ["For TVX-900 support, hold the reset button for ten seconds.", "The status light flashes blue when the reset procedure is complete."],
    )
    support_id = support["document_id"]

    report = api.request(
        "W1", "processing-report", "GET", f"/api/documents/{warranty_id}/processing-report", token=owner_token,
        checks=lambda response, body: {
            "report_available": response.status_code == 200 and body.get("operation") == "upload",
            "report_matches_document": body.get("processing_report", {}).get("document_id") == warranty_id,
        },
    )
    api.request(
        "W1", "inspect-automatic-metadata", "GET", "/api/documents/me", token=owner_token,
        checks=lambda response, body: {
            "document_visible": response.status_code == 200 and any(row["document_id"] == warranty_id for row in body.get("documents", [])),
            "hash_status_counts_visible": all(
                {"source_sha256", "processing_status", "page_count", "chunk_count", "provenance"}.issubset(row)
                for row in body.get("documents", [])
            ),
        },
    )
    _set_keywords(api, "W1", "owner-keyword-correction-warranty", owner_token, warranty_id, ["TVX-900", "warranty"])
    _set_keywords(api, "W1", "owner-keyword-correction-support", owner_token, support_id, ["TVX-900", "support"])

    session = database.SessionLocal()
    try:
        user_keyword_count = session.query(models.DocumentKeyword).filter(
            models.DocumentKeyword.document_id.in_([warranty_id, support_id]),
            models.DocumentKeyword.provenance_type == models.ProvenanceType.User,
            models.DocumentKeyword.user_edited.is_(True),
        ).count()
        original_chunk_ids = [row[0] for row in session.query(models.DocumentChunk.id).filter(models.DocumentChunk.document_id == warranty_id).all()]
    finally:
        session.close()
    _assert(user_keyword_count == 4, "W1 keyword correction did not persist USER provenance")

    reindex = api.request(
        "W1", "api-reindex", "POST", f"/api/documents/{warranty_id}/reindex", token=owner_token,
        checks=lambda response, body: {
            "reindexed": response.status_code == 200 and body.get("status") == "success",
            "stable_document_id": body.get("document_id") == warranty_id,
            "user_keywords_preserved": all(
                value in [item.lower() for item in body.get("processing_report", {}).get("keywords", [])]
                for value in ["tvx-900", "warranty"]
            ),
        },
    )
    session = database.SessionLocal()
    try:
        current_chunk_ids = [row[0] for row in session.query(models.DocumentChunk.id).filter(models.DocumentChunk.document_id == warranty_id).all()]
        audit_ids = {row[0] for row in session.query(models.AuditLog.id).all()}
    finally:
        session.close()
    vector_ids = ai_service.collection.get(where={"document_id": warranty_id}).get("ids", [])
    _assert(current_chunk_ids == original_chunk_ids, "W1 reindex changed deterministic chunk IDs")
    _assert(len(vector_ids) == len(set(vector_ids)) == len(current_chunk_ids), "W1 duplicate or missing vectors after reindex")
    api.request(
        "W1", "open-authorized-source-page", "GET", f"/api/documents/{warranty_id}/source?page=1", token=owner_token,
        checks=lambda response, body: {
            "page_opened": response.status_code == 200 and body.get("page_number") == 1,
            "correct_object": "TVX-900" in body.get("text", ""),
        },
    )

    answer = _ask(
        api, "W2", "answerable-multi-document", owner_token,
        "What is the TVX-900 warranty term and support reset procedure?", "FULL_ANSWER", citation_minimum=2,
    )
    for index, citation in enumerate(_citations(answer), start=1):
        api.request(
            "W2", f"open-cited-page-{index:02d}", "GET",
            f"/api/documents/{citation['document_id']}/source?page={citation['page_number']}", token=owner_token,
            checks=lambda response, body: {
                "citation_page_opened": response.status_code == 200 and bool(body.get("text")),
            },
        )
    _ask(
        api, "W2", "insufficient-evidence", owner_token,
        "Does TVX-900 support satellite uplink cryptographic rotation?", "REFUSE_INSUFFICIENT_EVIDENCE",
    )
    conflict = _upload(
        api, "W2", "upload-conflict-source", owner_token, "tvx-900-conflict.pdf", "TVX-900 Conflicting Notice",
        ["This notice contradicts the warranty record and states a twelve-month term.", "It is unverified and does not establish final authority."],
    )
    _set_keywords(api, "W2", "conflict-keywords", owner_token, conflict["document_id"], ["TVX-900", "warranty", "conflict", "authority"])
    _ask(
        api, "W2", "conflict-authority", owner_token,
        "Which source is the final authority for the TVX-900 warranty conflict?", "REFUSE_CONFLICT",
    )
    _ask(
        api, "W2", "wrong-object-hard-negative", owner_token,
        "What is the warranty term for TVX-999?", "REFUSE_NO_MATCH",
    )

    _grant(api, "grant-reader", owner_token, warranty_id, "reviewer-reader", "Reader")
    _ask(api, "W3", "reader-grounded-query", reader_token, "What is the TVX-900 warranty term?", "FULL_ANSWER", citation_minimum=1)
    _set_keywords(api, "W3", "aggregate-keywords-primary", owner_token, warranty_id, ["aggregate", "approval", "statistics"])
    _grant(api, "change-reader-to-aggregate", owner_token, warranty_id, "reviewer-reader", "Aggregate")

    aggregate_ids = [warranty_id]
    for index, value in enumerate((12, 18), start=1):
        uploaded = _upload(
            api, "W3", f"upload-aggregate-{index}", owner_token, f"aggregate-{index}.pdf", f"Aggregate sample {index}",
            [f"Aggregate approval time sample value is {value} hours.", "This synthetic record is for threshold evaluation."],
        )
        aggregate_ids.append(uploaded["document_id"])
        _set_keywords(api, "W3", f"aggregate-keywords-{index}", owner_token, uploaded["document_id"], ["aggregate", "approval", "statistics"])
        _grant(api, f"grant-aggregate-{index}", owner_token, uploaded["document_id"], "reviewer-reader", "Aggregate")
    _ask(api, "W3", "aggregate-query-threshold-met", reader_token, "What is the average aggregate approval time statistics?", "AGGREGATE_RESULT")

    api.request(
        "W3", "revoke-one-for-below-threshold", "DELETE",
        f"/api/policy/documents/{aggregate_ids[-1]}/permissions/{reader_id}", token=owner_token,
        checks=lambda response, body: {"revoked": response.status_code == 200 and body.get("revoked") is True},
    )
    _ask(api, "W3", "aggregate-below-threshold", reader_token, "What is the average aggregate approval time statistics?", "REFUSE_AGGREGATION_THRESHOLD")
    for index, doc_id in enumerate(aggregate_ids[:-1], start=1):
        api.request(
            "W3", f"revoke-remaining-{index}", "DELETE", f"/api/policy/documents/{doc_id}/permissions/{reader_id}", token=owner_token,
            checks=lambda response, body: {"revoked": response.status_code == 200 and body.get("revoked") is True},
        )
    revoked = _ask(
        api,
        "W3",
        "immediate-permission-refusal-after-revoke",
        reader_token,
        "What is the average aggregate approval time statistics?",
        "REFUSE_PERMISSION",
    )
    revoked_public = json.dumps(revoked, sort_keys=True)
    for denied_identifier in aggregate_ids:
        _assert(denied_identifier not in revoked_public, "W3 revoked response disclosed a denied document identifier")

    ownership = _upload(
        api, "W3", "upload-transfer-object", owner_token, "own-700-transfer.pdf", "OWN-700 Ownership",
        ["The OWN-700 transfer-only review code is cedar-seven.", "Only the current owner may manage this source."],
    )
    ownership_id = ownership["document_id"]
    _set_keywords(api, "W3", "transfer-object-keywords", owner_token, ownership_id, ["OWN-700", "transfer-only", "ownership"])
    api.request(
        "W3", "transfer-ownership", "POST", "/api/documents/transfer", token=owner_token,
        data={"doc_id": ownership_id, "new_username": "reviewer-reader"},
        checks=lambda response, body: {"transferred": response.status_code == 200 and body.get("status") == "success"},
    )
    api.request(
        "W3", "old-owner-source-denied", "GET", f"/api/documents/{ownership_id}/source?page=1", token=owner_token,
        checks=lambda response, body: {"immediately_denied": response.status_code == 404},
    )
    api.request(
        "W3", "new-owner-source-allowed", "GET", f"/api/documents/{ownership_id}/source?page=1", token=reader_token,
        checks=lambda response, body: {"new_owner_allowed": response.status_code == 200 and "cedar-seven" in body.get("text", "")},
    )
    _ask(api, "W3", "new-owner-grounded-query", reader_token, "What is the OWN-700 transfer-only review code?", "FULL_ANSWER", citation_minimum=1)

    ask_audit_ids = {row["audit_id"] for row in recorder.records if row.get("audit_id")}
    session = database.SessionLocal()
    try:
        stored_audit_ids = {row[0] for row in session.query(models.AuditLog.id).filter(models.AuditLog.action == "CHAT_ASK").all()}
        user_provenance_count = session.query(models.DocumentKeyword).filter(
            models.DocumentKeyword.provenance_type == models.ProvenanceType.User,
            models.DocumentKeyword.user_edited.is_(True),
        ).count()
    finally:
        session.close()
    _assert(ask_audit_ids <= stored_audit_ids, "One or more public audit IDs were not persisted")

    output_dir.mkdir(parents=True, exist_ok=False)
    trace_path = output_dir / "api_workflow_trace.jsonl"
    trace_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in recorder.records), encoding="utf-8")
    workflow_results = {
        name: "PASS"
        for name in ("W1", "W2", "W3")
        if all(row["result"] == "PASS" for row in recorder.records if row["workflow"] == name)
    }
    summary = {
        "status": "PASS" if len(workflow_results) == 3 else "FAIL",
        "provider": "deterministic-mock",
        "network_provider_called": False,
        "workflow_results": workflow_results,
        "record_count": len(recorder.records),
        "ask_audit_id_count": len(ask_audit_ids),
        "persisted_audit_id_count": len(stored_audit_ids),
        "user_provenance_count": user_provenance_count,
        "w1": {
            "document_id_stable_after_reindex": reindex["document_id"] == warranty_id,
            "processing_config_hash": report["processing_report"]["processing_config_hash"],
            "duplicate_chunks_or_vectors": 0,
        },
        "w2": {
            "multi_document_citation_count": len(_citations(answer)),
            "insufficient_conflict_wrong_object_executed": True,
        },
        "w3": {
            "reader_aggregate_below_threshold_revoke_transfer_executed": True,
            "aggregate_threshold": int(os.getenv("AGGREGATE_K_THRESHOLD", "3")),
        },
        "trace_sha256": _sha256(trace_path.read_bytes()),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def run_api_workflows(
    *,
    output_dir: Path,
    database_url: str,
    admin_database_url: str | None,
    chroma_dir: Path,
    source_storage_dir: Path,
) -> dict[str, Any]:
    """Prepare an isolated runtime and execute W1, W2, and W3."""

    from scripts.run_actual_pipeline_evaluation import _prepare_mysql_database

    _prepare_mysql_database(database_url, admin_database_url)
    from sqlalchemy.engine import make_url

    parsed = make_url(database_url)
    database_name = parsed.database or ""
    if not database_name.startswith("infobank_eval_"):
        raise ValueError("API workflow database name must start with infobank_eval_")

    import pymysql

    connection = pymysql.connect(
        host=parsed.host or "127.0.0.1", port=parsed.port or 3306,
        user=parsed.username or "", password=parsed.password or "", database=database_name, autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE `{table}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    finally:
        connection.close()

    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to mix API workflow output: {output_dir}")
    chroma_dir.mkdir(parents=True, exist_ok=True)
    source_storage_dir.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        {
            "DATABASE_URL": database_url,
            "JWT_SECRET_KEY": "isolated-api-workflow-secret-not-for-production",
            "AI_PROVIDER": "deterministic-mock",
            "CHROMA_PERSIST_DIR": str(chroma_dir),
            "SOURCE_STORAGE_DIR": str(source_storage_dir),
            "AGGREGATE_K_THRESHOLD": "3",
        }
    )
    os.environ.pop("OPENAI_API_KEY", None)
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    import inspect
    import httpx
    from fastapi.testclient import TestClient
    import ai_service
    import database
    import main
    import models

    # Starlette 0.27 still passes the removed ``app=`` compatibility keyword
    # to httpx 0.28.  Keep the local evaluator usable without downloading or
    # changing the locked environment; ASGI requests still go through
    # Starlette's real TestClient transport.
    if "app" not in inspect.signature(httpx.Client.__init__).parameters:
        original_client_init = httpx.Client.__init__

        def compatible_client_init(self: Any, *args: Any, app: Any = None, **kwargs: Any) -> None:
            del app
            original_client_init(self, *args, **kwargs)

        httpx.Client.__init__ = compatible_client_init  # type: ignore[method-assign]

    with TestClient(main.app) as client:
        return _run_workflows(client, database, models, ai_service, output_dir)
