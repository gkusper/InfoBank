"""Inventory and compare isolated InfoBank runtime stores for operations smoke."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from .orphan_repair import ConsistencySnapshot, scan_snapshot


OPERATIONS_VERSION = "infobank-pre-freeze-operations-v1"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rows(cursor: Any, sql: str) -> list[dict[str, Any]]:
    cursor.execute(sql)
    return [dict(row) for row in cursor.fetchall()]


def runtime_inventory(*, database_url: str, chroma_dir: Path, source_root: Path, trace_path: Path | None = None) -> dict[str, Any]:
    import chromadb
    import pymysql

    parsed = make_url(database_url)
    connection = pymysql.connect(
        host=parsed.host or "127.0.0.1", port=parsed.port or 3306,
        user=parsed.username or "", password=parsed.password or "", database=parsed.database,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with connection.cursor() as cursor:
            documents = _rows(cursor, "SELECT id, source_storage_path, source_sha256, source_byte_size, page_count, source_status, processing_status FROM documents ORDER BY id")
            chunks = _rows(cursor, "SELECT id, document_id, vector_id, page_number, chunk_index, content_sha256, source_sha256 FROM document_chunks ORDER BY id")
            permissions = _rows(cursor, "SELECT user_id, document_id, permission_type FROM user_document_permission ORDER BY user_id, document_id, permission_type")
            audit_count = _rows(cursor, "SELECT COUNT(*) AS value FROM audit_logs")[0]["value"]
    finally:
        connection.close()

    collection = chromadb.PersistentClient(path=str(chroma_dir)).get_or_create_collection(name="infobank_vectors")
    vector_data = collection.get(include=["metadatas"])
    vector_rows = sorted([
        {"id": vector_id, "document_id": (metadata or {}).get("document_id"), "chunk_id": (metadata or {}).get("chunk_id")}
        for vector_id, metadata in zip(vector_data.get("ids", []), vector_data.get("metadatas", []))
    ], key=lambda item: item["id"])

    sources = []
    if source_root.exists():
        for path in sorted(source_root.glob("*/source.pdf")):
            sources.append({"document_id": path.parent.name, "sha256": _hash_file(path), "byte_size": path.stat().st_size})

    citations = []
    if trace_path and trace_path.exists():
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            for index, citation in enumerate(row.get("citations", [])):
                citations.append({"citation_id": f"{row.get('workflow')}-{row.get('step')}-{index}", "document_id": citation.get("document_id"), "chunk_id": citation.get("chunk_id")})

    snapshot = ConsistencySnapshot(
        documents={row["id"]: {"source_sha256": row["source_sha256"], "source_status": row["source_status"]} for row in documents},
        chunks={row["id"]: {"document_id": row["document_id"], "vector_id": row["vector_id"]} for row in chunks},
        vectors={row["id"]: {"document_id": row["document_id"], "chunk_id": row["chunk_id"], "active": True} for row in vector_rows},
        sources={row["document_id"]: {"sha256": row["sha256"], "byte_size": row["byte_size"]} for row in sources},
        citations=citations,
    )
    scan = scan_snapshot(snapshot)
    payload = {
        "operations_version": OPERATIONS_VERSION,
        "database_name": parsed.database,
        "documents": documents,
        "chunks": chunks,
        "permissions": permissions,
        "vectors": vector_rows,
        "sources": sources,
        "audit_count": audit_count,
        "citation_count": len(citations),
        "orphan_scan": scan,
    }
    content = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    payload["inventory_sha256"] = hashlib.sha256(content).hexdigest()
    return payload


def compare_inventories(source: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "document_uuid_unchanged": [item["id"] for item in source["documents"]] == [item["id"] for item in restored["documents"]],
        "source_sha_unchanged": [(item["id"], item["source_sha256"]) for item in source["documents"]] == [(item["id"], item["source_sha256"]) for item in restored["documents"]],
        "page_count_unchanged": [(item["id"], item["page_count"]) for item in source["documents"]] == [(item["id"], item["page_count"]) for item in restored["documents"]],
        "chunk_count_and_ids_unchanged": source["chunks"] == restored["chunks"],
        "vector_count_and_ids_unchanged": source["vectors"] == restored["vectors"],
        "permissions_unchanged": source["permissions"] == restored["permissions"],
        "source_store_hashes_unchanged": source["sources"] == restored["sources"],
        "source_orphans_zero": source["orphan_scan"]["issue_count"] == 0,
        "restored_orphans_zero": restored["orphan_scan"]["issue_count"] == 0,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
