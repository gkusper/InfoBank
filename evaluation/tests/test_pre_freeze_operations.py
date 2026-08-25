from __future__ import annotations

from pathlib import Path

from evaluation.pre_freeze_operations import compare_inventories


def test_runtime_inventory_comparison_checks_all_restored_identity_surfaces() -> None:
    inventory = {
        "documents": [{"id": "doc", "source_sha256": "a" * 64, "page_count": 1}],
        "chunks": [{"id": "chunk", "document_id": "doc", "vector_id": "vector"}],
        "vectors": [{"id": "vector", "document_id": "doc", "chunk_id": "chunk"}],
        "permissions": [{"user_id": "user", "document_id": "doc", "permission_type": "Reader"}],
        "sources": [{"document_id": "doc", "sha256": "a" * 64, "byte_size": 4}],
        "orphan_scan": {"issue_count": 0},
    }
    assert compare_inventories(inventory, inventory)["status"] == "PASS"
    changed = {**inventory, "vectors": []}
    result = compare_inventories(inventory, changed)
    assert result["status"] == "FAIL" and result["checks"]["vector_count_and_ids_unchanged"] is False


def test_backup_manifest_relativizes_against_a_resolved_root() -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "run_pre_freeze_operations_smoke.ps1"
    ).read_text(encoding="utf-8")
    assert "$backupRoot = (Resolve-Path -LiteralPath $backup).Path" in script
    assert "Substring($backupRoot.Length)" in script
    assert "Substring($backup.Length)" not in script
