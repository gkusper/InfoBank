from __future__ import annotations

from evaluation.orphan_repair import ConsistencySnapshot, TASK_OWNED_SCOPE, repair_snapshot, scan_snapshot, source_record


def _fixture() -> ConsistencySnapshot:
    good = source_record(b"good")
    return ConsistencySnapshot(
        documents={
            "doc-missing-source": {"source_sha256": "0" * 64, "source_status": "ACTIVE", "scope": TASK_OWNED_SCOPE},
            "doc-sha": {"source_sha256": "1" * 64, "source_status": "ACTIVE", "scope": TASK_OWNED_SCOPE},
            "doc-archived": {"source_sha256": good["sha256"], "source_status": "ARCHIVED", "scope": TASK_OWNED_SCOPE},
        },
        sources={
            "doc-sha": source_record(b"wrong"), "doc-archived": good,
            "source-orphan": {**source_record(b"orphan"), "scope": TASK_OWNED_SCOPE},
        },
        chunks={
            "chunk-no-doc": {"document_id": "ghost", "vector_id": "vector-no-doc", "scope": TASK_OWNED_SCOPE},
            "chunk-no-vector": {"document_id": "doc-sha", "vector_id": "missing-vector", "scope": TASK_OWNED_SCOPE},
            "chunk-archived": {"document_id": "doc-archived", "vector_id": "vector-archived", "scope": TASK_OWNED_SCOPE},
        },
        vectors={
            "vector-no-doc": {"document_id": "ghost", "chunk_id": "chunk-no-doc", "active": True, "scope": TASK_OWNED_SCOPE},
            "vector-archived": {"document_id": "doc-archived", "chunk_id": "chunk-archived", "active": True, "scope": TASK_OWNED_SCOPE},
            "vector-no-chunk": {"document_id": "doc-sha", "chunk_id": "ghost-chunk", "active": True, "scope": TASK_OWNED_SCOPE},
        },
        staged_sources={"staged-doc": {"document_deleted": True, "pending_purge": True, "scope": TASK_OWNED_SCOPE}},
        citations=[{"citation_id": "citation-cross", "document_id": "doc-sha", "chunk_id": "chunk-archived", "scope": TASK_OWNED_SCOPE}],
    )


def test_scanner_covers_every_required_cross_store_orphan_type() -> None:
    scan = scan_snapshot(_fixture())
    assert set(scan["issue_type_counts"]) == {
        "DB_DOCUMENT_MISSING_SOURCE", "SOURCE_DIRECTORY_WITHOUT_DB_DOCUMENT", "CHUNK_MISSING_DOCUMENT",
        "VECTOR_MISSING_DOCUMENT_OR_CHUNK", "DB_CHUNK_MISSING_VECTOR", "ARCHIVED_DOCUMENT_ACTIVE_VECTORS",
        "DELETED_DOCUMENT_STAGED_SOURCE_PENDING_PURGE", "SOURCE_SHA_MISMATCH",
        "CROSS_DOCUMENT_CITATION_CHUNK_MISMATCH",
    }


def test_repair_defaults_to_dry_run_and_apply_is_fixture_scoped_and_idempotent() -> None:
    fixture = _fixture()
    untouched, dry_run = repair_snapshot(fixture)
    assert untouched == fixture and dry_run["applied_count"] == 0
    repaired, applied = repair_snapshot(fixture, apply=True)
    assert applied["applied_count"] > 0
    assert repaired.vectors["vector-archived"]["active"] is False
    assert repaired.vectors["missing-vector"]["recreated"] is True
    second, second_log = repair_snapshot(repaired, apply=True)
    assert second == repaired
    assert all(not item["applied"] for item in second_log["actions"])


def test_apply_never_mutates_unknown_or_external_scope() -> None:
    fixture = _fixture()
    fixture.documents["doc-archived"]["scope"] = "EXTERNAL_OR_UNKNOWN"
    original = fixture.vectors["vector-archived"].copy()
    repaired, log = repair_snapshot(fixture, apply=True)
    assert repaired.vectors["vector-archived"] == original
    assert any(item["reason"] == "NOT_TASK_OWNED" for item in log["actions"])
