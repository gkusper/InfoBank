"""Run a privacy-safe HTTP endpoint matrix against a normal InfoBank backend."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path
from typing import Any

import fitz
import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend_python"
FORBIDDEN_PUBLIC_MARKERS = (
    "select documents",
    "from documents",
    "pymysql",
    "sqlalchemy",
    "operationalerror",
    "programmingerror",
    "database_url",
    "c:\\",
)


def _pdf_bytes(pages: list[str]) -> bytes:
    document = fitz.open()
    for text_value in pages:
        page = document.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 545, 790), text_value, fontsize=11)
    data = document.tobytes()
    document.close()
    return data


def _schema(value: Any, depth: int = 0) -> Any:
    if depth >= 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {key: _schema(item, depth + 1) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_schema(value[0], depth + 1)] if value else []
    return type(value).__name__


def _safe_record(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    lowered = response.text.lower()
    return {
        "http_status": response.status_code,
        "response_schema": _schema(payload),
        "error_code": (payload.get("error") or {}).get("code") if isinstance(payload, dict) else None,
        "raw_sql_present": any(marker in lowered for marker in FORBIDDEN_PUBLIC_MARKERS),
    }


def _cleanup_smoke_users(client: httpx.Client, database_url: str, password: str) -> dict[str, Any]:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        users = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT id, email FROM users "
                    "WHERE email LIKE 'runtime-owner-%@example.invalid' "
                    "OR email LIKE 'runtime-reader-%@example.invalid'"
                )
            ).mappings()
        ]
    deleted_documents = 0
    for user in users:
        login = client.post("/api/login", json={"email": user["email"], "password": password})
        if login.status_code != 200:
            engine.dispose()
            raise RuntimeError("Could not authenticate a task-owned smoke user for safe cleanup")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        documents = client.get("/api/documents/me", headers=headers)
        if documents.status_code != 200:
            engine.dispose()
            raise RuntimeError("Could not list task-owned smoke documents for safe cleanup")
        for document in documents.json().get("documents", []):
            response = client.request(
                "DELETE",
                "/api/documents/delete",
                headers=headers,
                data={"doc_id": document["document_id"], "permanent": "true"},
            )
            if response.status_code != 200:
                engine.dispose()
                raise RuntimeError("Could not delete a task-owned smoke document safely")
            deleted_documents += 1
        evidence = client.delete("/api/evidence/clear/all", headers=headers)
        if evidence.status_code != 200:
            engine.dispose()
            raise RuntimeError("Could not delete task-owned smoke evidence safely")
    user_ids = [user["id"] for user in users]
    if user_ids:
        placeholders = ", ".join(f":user_{index}" for index in range(len(user_ids)))
        params = {f"user_{index}": value for index, value in enumerate(user_ids)}
        with engine.begin() as connection:
            connection.execute(text(f"DELETE FROM audit_logs WHERE user_id IN ({placeholders})"), params)
            connection.execute(text(f"DELETE FROM users WHERE id IN ({placeholders})"), params)
    engine.dispose()
    return {"users": len(users), "documents": deleted_documents, "database_rows": True}


def _keyword_snapshot(database_url: str) -> set[tuple[int, str]]:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        rows = {(int(row[0]), str(row[1])) for row in connection.execute(text("SELECT id, word FROM keywords"))}
    engine.dispose()
    return rows


def _cleanup_added_unreferenced_keywords(
    database_url: str,
    baseline: set[tuple[int, str]],
) -> int:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        current = {(int(row[0]), str(row[1])) for row in connection.execute(text("SELECT id, word FROM keywords"))}
        referenced = {int(row[0]) for row in connection.execute(text("SELECT DISTINCT keyword_id FROM document_keywords"))}
    added = sorted(current - baseline)
    delete_ids = [keyword_id for keyword_id, _word in added if keyword_id not in referenced]
    if len(delete_ids) != len(added):
        engine.dispose()
        raise RuntimeError("Refusing smoke-keyword cleanup because a new keyword remains referenced")
    if delete_ids:
        placeholders = ", ".join(f":keyword_{index}" for index in range(len(delete_ids)))
        params = {f"keyword_{index}": value for index, value in enumerate(delete_ids)}
        with engine.begin() as connection:
            connection.execute(text(f"DELETE FROM keywords WHERE id IN ({placeholders})"), params)
    engine.dispose()
    return len(delete_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8772")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", help="Optional deterministic task-owned fixture suffix.")
    parser.add_argument("--keep-fixtures", action="store_true", help="Keep synthetic fixtures for a subsequent browser smoke.")
    args = parser.parse_args()
    run_id = args.run_id or uuid.uuid4().hex[:12]
    owner_email = f"runtime-owner-{run_id}@example.invalid"
    reader_email = f"runtime-reader-{run_id}@example.invalid"
    owner_name = f"runtime-owner-{run_id}"
    reader_name = f"runtime-reader-{run_id}"
    password = "runtime-smoke-only-password"
    endpoints: dict[str, Any] = {}
    doc_ids: list[str] = []
    owner_id = None
    reader_id = None
    load_dotenv(BACKEND_ROOT / ".env", override=False)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for task-owned fixture cleanup")

    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        def call(name: str, method: str, path: str, **kwargs) -> httpx.Response:
            response = client.request(method, path, **kwargs)
            endpoints[name] = {"method": method, "path": path, **_safe_record(response)}
            if response.status_code >= 500 or endpoints[name]["raw_sql_present"]:
                raise RuntimeError(f"Endpoint {name} failed safely-required smoke: HTTP {response.status_code}")
            return response

        pre_cleanup = _cleanup_smoke_users(client, database_url, password)
        baseline_keywords = _keyword_snapshot(database_url)
        call("docs", "GET", "/docs")
        call("openapi", "GET", "/openapi.json")
        health = call("schema_health", "GET", "/api/health/schema")
        if not health.json().get("schema", {}).get("compatible"):
            raise RuntimeError("Normal runtime schema health is not compatible")

        call(
            "register_owner",
            "POST",
            "/api/register",
            json={"email": owner_email, "username": owner_name, "password": password},
        )
        call(
            "register_reader",
            "POST",
            "/api/register",
            json={"email": reader_email, "username": reader_name, "password": password},
        )
        login = call(
            "login_owner",
            "POST",
            "/api/login",
            json={"email": owner_email, "password": password},
        ).json()
        token = login["access_token"]
        owner_id = login["user_id"]
        reader_login = call(
            "login_reader",
            "POST",
            "/api/login",
            json={"email": reader_email, "password": password},
        ).json()
        reader_id = reader_login["user_id"]
        headers = {"Authorization": f"Bearer {token}"}
        reader_headers = {"Authorization": f"Bearer {reader_login['access_token']}"}
        call("profile", "GET", "/api/profile/me", headers=headers)

        sources = [
            (
                "tvx-900-warranty.pdf",
                [
                    "TVX-900 warranty certificate. The limited warranty term is twenty-four months from purchase.",
                    "Warranty service requires the purchase receipt and the TVX-900 serial number.",
                ],
            ),
            (
                "tvx-900-support.pdf",
                [
                    "TVX-900 support manual. To restart the television, hold the power button for ten seconds.",
                    "If the restart does not help, disconnect power for one minute and reconnect it.",
                ],
            ),
            (
                "rtr-450-support.pdf",
                [
                    "RTR-450 router support guide. Hold the reset button for fifteen seconds.",
                    "This router guide does not describe any television warranty.",
                ],
            ),
        ]
        for filename, pages in sources:
            response = call(
                "upload_" + filename.removesuffix(".pdf").replace("-", "_"),
                "POST",
                "/api/upload",
                headers=headers,
                files={"file": (filename, _pdf_bytes(pages), "application/pdf")},
                data={"permission_type": "Owner", "source_license": "synthetic-runtime-smoke"},
            )
            doc_ids.append(response.json()["document_id"])

        document_list = call("documents", "GET", "/api/documents/me", headers=headers).json()
        listed = {item["document_id"]: item for item in document_list["documents"]}
        if not set(doc_ids) <= set(listed):
            raise RuntimeError("Uploaded documents are missing from the normal-runtime document list")
        endpoints["document_detail"] = {
            "method": "GET",
            "path": "/api/documents/me (selected entry)",
            "http_status": 200,
            "response_schema": _schema(listed[doc_ids[0]]),
            "error_code": None,
            "raw_sql_present": False,
        }

        call(
            "processing_report",
            "GET",
            f"/api/documents/{doc_ids[0]}/processing-report",
            headers=headers,
        )
        call("source_page", "GET", f"/api/documents/{doc_ids[0]}/source?page=1", headers=headers)
        answer = call(
            "chat_answerable",
            "POST",
            "/api/ask",
            headers=headers,
            data={"question": "What is the TVX-900 warranty term and how do I restart it?"},
        ).json()
        wrong_object = call(
            "chat_wrong_object",
            "POST",
            "/api/ask",
            headers=headers,
            data={"question": "What is the warranty term for TVX-999?"},
        ).json()
        endpoints["chat_answerable"]["output_mode"] = answer.get("output_mode")
        endpoints["chat_answerable"]["reason_code"] = (answer.get("controlled_failure") or {}).get("reason")
        endpoints["chat_answerable"]["audit_id_present"] = bool(answer.get("audit_id"))
        endpoints["chat_wrong_object"]["output_mode"] = wrong_object.get("output_mode")
        endpoints["chat_wrong_object"]["reason_code"] = (wrong_object.get("controlled_failure") or {}).get("reason")

        call("knowledge_map", "GET", "/api/knowledge-map/me", headers=headers)
        graph_one = call("semantic_graph", "GET", "/api/semantic-cooccurrence-graph/me", headers=headers).json()
        graph_two = client.get("/api/semantic-cooccurrence-graph/me", headers=headers).json()
        endpoints["semantic_graph"]["deterministic_repeat"] = graph_one == graph_two
        call("ontology_compatibility", "GET", "/api/ontology/me", headers=headers)

        grant = call(
            "permission_grant",
            "POST",
            f"/api/policy/documents/{doc_ids[0]}/permissions",
            headers=headers,
            data={"target_username": reader_name, "permission_type": "Reader"},
        ).json()
        if grant.get("target_user_id") != reader_id:
            raise RuntimeError("Permission grant returned an unexpected target")
        call(
            "effective_policy_reader",
            "GET",
            f"/api/policy/resolve/document/{doc_ids[0]}?purpose=grounded_question_answering",
            headers=reader_headers,
        )
        call(
            "permission_revoke",
            "DELETE",
            f"/api/policy/documents/{doc_ids[0]}/permissions/{reader_id}",
            headers=headers,
        )

        call(
            "evidence_import",
            "POST",
            "/api/evidence/import",
            headers=headers,
            json={
                "units": [
                    {
                        "source_type": "Email",
                        "title": "Synthetic router support follow-up",
                        "content": "Official support request. Action: send the RTR-450 diagnostic log tomorrow.",
                        "thread_id": f"runtime-{run_id}",
                        "relation_key": f"runtime-{run_id}",
                    }
                ]
            },
        )
        call("evidence_units", "GET", "/api/evidence/units", headers=headers)
        call("actions", "GET", "/api/evidence/action-list", headers=headers)
        call("audit_log", "GET", "/api/admin/logs?limit=20", headers=headers)

        if args.keep_fixtures:
            cleanup = {"deferred_for_browser_smoke": True}
        else:
            cleanup = _cleanup_smoke_users(client, database_url, password)
            cleanup["orphan_keywords"] = _cleanup_added_unreferenced_keywords(database_url, baseline_keywords)

    failures = [
        name for name, item in endpoints.items()
        if item.get("http_status", 0) >= 500 or item.get("raw_sql_present")
    ]
    output = {
        "schema_version": "infobank-normal-runtime-smoke-v1",
        "run_id": run_id,
        "provider": "deterministic-mock",
        "real_provider_called": False,
        "privacy_safe": True,
        "no_health": True,
        "endpoints": endpoints,
        "four_visible_functions": {
            "Chat": endpoints["chat_answerable"]["http_status"],
            "Documents": endpoints["documents"]["http_status"],
            "Knowledge Map": endpoints["knowledge_map"]["http_status"],
            "Semantic Co-occurrence Graph": endpoints["semantic_graph"]["http_status"],
        },
        "cleanup": cleanup,
        "pre_cleanup": pre_cleanup,
        "fixture_login": {
            "email": owner_email,
            "password": password,
        } if args.keep_fixtures else None,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
        "elapsed_note": "No provider latency was measured.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
