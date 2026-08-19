from __future__ import annotations

from pathlib import Path

import pytest

from source_storage import SourceStorage
import source_storage as source_storage_module


DOCUMENT_ID = "00000000-0000-0000-0000-000000000020"


def test_source_storage_atomic_roundtrip_integrity_and_no_overwrite(tmp_path: Path) -> None:
    storage = SourceStorage(tmp_path / "sources")
    content = b"%PDF-1.7\nsynthetic-source"
    stored = storage.save(DOCUMENT_ID, content)
    assert stored.relative_path == f"{DOCUMENT_ID}/source.pdf"
    assert stored.byte_size == len(content)
    assert storage.exists(stored.relative_path)
    assert storage.read(stored.relative_path) == content
    assert storage.verify(stored.relative_path, stored.sha256)
    with pytest.raises(FileExistsError):
        storage.save(DOCUMENT_ID, content)


@pytest.mark.parametrize(
    "unsafe",
    ["../source.pdf", "..\\source.pdf", "other/../../source.pdf", "C:/outside/source.pdf", "C:\\outside\\source.pdf"],
)
def test_source_storage_rejects_path_traversal(tmp_path: Path, unsafe: str) -> None:
    storage = SourceStorage(tmp_path / "sources")
    with pytest.raises(ValueError):
        storage.resolve(unsafe)


def test_staged_removal_can_be_restored_or_purged(tmp_path: Path) -> None:
    storage = SourceStorage(tmp_path / "sources")
    stored = storage.save(DOCUMENT_ID, b"%PDF synthetic")
    staged = storage.stage_remove(DOCUMENT_ID, stored.relative_path)
    assert staged and staged.exists()
    assert not storage.exists(stored.relative_path)
    storage.restore_staged(DOCUMENT_ID, staged)
    assert storage.exists(stored.relative_path)
    staged = storage.stage_remove(DOCUMENT_ID, stored.relative_path)
    storage.purge_staged(DOCUMENT_ID, staged)
    assert staged and not staged.exists()
    assert not storage.exists(stored.relative_path)


def test_document_namespace_must_be_canonical_uuid(tmp_path: Path) -> None:
    storage = SourceStorage(tmp_path / "sources")
    with pytest.raises(ValueError):
        storage.save("../../escape", b"payload")


def test_staged_restore_and_purge_reject_paths_outside_managed_trash(tmp_path: Path) -> None:
    storage = SourceStorage(tmp_path / "sources")
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ValueError):
        storage.restore_staged(DOCUMENT_ID, outside)
    with pytest.raises(ValueError):
        storage.purge_staged(DOCUMENT_ID, outside)
    assert outside.is_dir()


def test_atomic_replace_failure_removes_temporary_document_directory(tmp_path: Path, monkeypatch) -> None:
    storage = SourceStorage(tmp_path / "sources")
    monkeypatch.setattr(
        source_storage_module.os,
        "replace",
        lambda _source, _destination: (_ for _ in ()).throw(OSError("synthetic atomic replace failure")),
    )
    with pytest.raises(OSError, match="synthetic atomic replace failure"):
        storage.save(DOCUMENT_ID, b"%PDF synthetic", "application/pdf")
    assert not (storage.root / DOCUMENT_ID).exists()
