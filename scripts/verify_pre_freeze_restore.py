#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend_python"
for root in (REPOSITORY_ROOT, BACKEND_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from evaluation.pre_freeze_operations import compare_inventories, runtime_inventory


def runtime_api_query(database_url: str, chroma_dir: Path, source_root: Path) -> dict:
    os.environ.update({
        "DATABASE_URL": database_url,
        "JWT_SECRET_KEY": "isolated-restore-verification-secret",
        "AI_PROVIDER": "deterministic-mock",
        "CHROMA_PERSIST_DIR": str(chroma_dir),
        "SOURCE_STORAGE_DIR": str(source_root),
        "AGGREGATE_K_THRESHOLD": "3",
    })
    os.environ.pop("OPENAI_API_KEY", None)
    import httpx
    if "app" not in inspect.signature(httpx.Client.__init__).parameters:
        original = httpx.Client.__init__
        def compatible(self, *args, app=None, **kwargs):
            del app
            original(self, *args, **kwargs)
        httpx.Client.__init__ = compatible
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as client:
        db = client.get("/api/test-db")
        login = client.post("/api/login", json={"email": "owner@example.invalid", "password": "Deterministic-Review-47!"})
        login.raise_for_status()
        token = login.json()["access_token"]
        answer = client.post("/api/ask", headers={"Authorization": f"Bearer {token}"}, data={"question": "What is the TVX-900 warranty term and support reset procedure?"})
        answer.raise_for_status()
        body = answer.json()
        citations = [item.get("citation", {}) for item in body.get("sources", []) if item.get("citation", {}).get("available")]
        docs = client.get("/docs")
        openapi = client.get("/openapi.json")
    return {
        "database_test_status": db.status_code,
        "docs_status": docs.status_code,
        "openapi_status": openapi.status_code,
        "output_class": body.get("output_mode"),
        "audit_id_present": bool(body.get("audit_id")),
        "citation_count": len(citations),
        "citations_valid": all(item.get("document_id") and item.get("page_number") and item.get("chunk_id") for item in citations),
        "network_provider_called": False,
    }


def fresh_api_query(database_url: str, chroma_dir: Path, source_root: Path) -> dict:
    process = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--api-only", "--database-url", database_url,
         "--chroma", str(chroma_dir), "--source-store", str(source_root)],
        check=False, text=True, capture_output=True,
    )
    if process.returncode != 0:
        raise RuntimeError(f"Fresh API verification failed: {process.stderr}")
    return json.loads(process.stdout)


def main() -> int:
    if "--api-only" in sys.argv:
        api_parser = argparse.ArgumentParser()
        api_parser.add_argument("--api-only", action="store_true")
        api_parser.add_argument("--database-url", required=True)
        api_parser.add_argument("--chroma", type=Path, required=True)
        api_parser.add_argument("--source-store", type=Path, required=True)
        api_args = api_parser.parse_args()
        print(json.dumps(runtime_api_query(api_args.database_url, api_args.chroma, api_args.source_store), sort_keys=True))
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-database-url", required=True)
    parser.add_argument("--restored-database-url", required=True)
    parser.add_argument("--source-chroma", type=Path, required=True)
    parser.add_argument("--restored-chroma", type=Path, required=True)
    parser.add_argument("--source-store", type=Path, required=True)
    parser.add_argument("--restored-source-store", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = runtime_inventory(database_url=args.source_database_url, chroma_dir=args.source_chroma, source_root=args.source_store, trace_path=args.trace)
    restored = runtime_inventory(database_url=args.restored_database_url, chroma_dir=args.restored_chroma, source_root=args.restored_source_store, trace_path=args.trace)
    comparison = compare_inventories(source, restored)
    source_api = fresh_api_query(args.source_database_url, args.source_chroma, args.source_store)
    restored_api = fresh_api_query(args.restored_database_url, args.restored_chroma, args.restored_source_store)
    api_pass = all(
        api["database_test_status"] == api["docs_status"] == api["openapi_status"] == 200
        and api["audit_id_present"] and api["citation_count"] >= 2 and api["citations_valid"]
        for api in (source_api, restored_api)
    ) and source_api["output_class"] == restored_api["output_class"]
    result = {"status": "PASS" if comparison["status"] == "PASS" and api_pass else "FAIL", "comparison": comparison, "source_api": source_api, "restored_api": restored_api, "source_inventory": source, "restored_inventory": restored}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "comparison": comparison["status"], "source_api": source_api, "restored_api": restored_api, "output_class_unchanged": source_api["output_class"] == restored_api["output_class"]}, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
