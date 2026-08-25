"""UUID-namespaced durable PDF storage with atomic writes and safe deletion."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_STORAGE_DIR = BACKEND_DIR / "runtime" / "source_storage"


@dataclass(frozen=True)
class StoredSource:
    relative_path: str
    sha256: str
    byte_size: int
    mime_type: str


class SourceStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or os.getenv("SOURCE_STORAGE_DIR") or DEFAULT_SOURCE_STORAGE_DIR
        configured_path = Path(configured).expanduser()
        if not configured_path.is_absolute():
            configured_path = BACKEND_DIR / configured_path
        self.root = configured_path.resolve()

    @staticmethod
    def validate_document_id(document_id: str) -> str:
        try:
            parsed = uuid.UUID(document_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("document_id must be a UUID") from exc
        canonical = str(parsed)
        if canonical != document_id.lower():
            raise ValueError("document_id must use canonical UUID form")
        return canonical

    def relative_path(self, document_id: str) -> Path:
        canonical = self.validate_document_id(document_id)
        return Path(canonical) / "source.pdf"

    def resolve(self, relative_path: str | Path) -> Path:
        value = Path(relative_path)
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("Unsafe source-storage path")
        candidate = (self.root / value).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Source path escapes configured storage root") from exc
        return candidate

    def save(self, document_id: str, content: bytes, mime_type: str = "application/pdf") -> StoredSource:
        if not content:
            raise ValueError("Source content must not be empty")
        relative = self.relative_path(document_id)
        destination = self.resolve(relative)
        destination.parent.mkdir(parents=True, exist_ok=False)
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(prefix="source-", suffix=".tmp", dir=destination.parent)
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if destination.exists():
                raise FileExistsError(f"Source already exists for document {document_id}")
            os.replace(temporary_path, destination)
            temporary_path = None
        except Exception:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
            if destination.parent.exists() and not any(destination.parent.iterdir()):
                destination.parent.rmdir()
            raise
        return StoredSource(
            relative_path=relative.as_posix(),
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            mime_type=mime_type or "application/pdf",
        )

    def read(self, relative_path: str | Path) -> bytes:
        path = self.resolve(relative_path)
        if not path.is_file():
            raise FileNotFoundError("Durable source file is missing")
        return path.read_bytes()

    def open(self, relative_path: str | Path, mode: str = "rb"):
        if mode not in {"rb", "r"}:
            raise ValueError("Source storage can only be opened read-only")
        path = self.resolve(relative_path)
        if not path.is_file():
            raise FileNotFoundError("Durable source file is missing")
        return path.open(mode)

    def exists(self, relative_path: str | Path) -> bool:
        return self.resolve(relative_path).is_file()

    def verify(self, relative_path: str | Path, expected_sha256: str) -> bool:
        return hashlib.sha256(self.read(relative_path)).hexdigest() == expected_sha256

    def remove(self, document_id: str, relative_path: str | Path) -> None:
        canonical = self.validate_document_id(document_id)
        path = self.resolve(relative_path)
        document_dir = path.parent
        if document_dir.name != canonical or document_dir.parent != self.root:
            raise ValueError("Source path does not belong to document namespace")
        if document_dir.exists():
            shutil.rmtree(document_dir)

    def stage_remove(self, document_id: str, relative_path: str | Path) -> Path | None:
        canonical = self.validate_document_id(document_id)
        path = self.resolve(relative_path)
        document_dir = path.parent
        if document_dir.name != canonical or document_dir.parent != self.root:
            raise ValueError("Source path does not belong to document namespace")
        if not document_dir.exists():
            return None
        trash_root = self.root / ".trash"
        trash_root.mkdir(parents=True, exist_ok=True)
        staged = trash_root / f"{canonical}-{uuid.uuid4()}"
        os.replace(document_dir, staged)
        return staged

    def _validate_staged(self, document_id: str, staged: Path) -> Path:
        canonical = self.validate_document_id(document_id)
        trash_root = (self.root / ".trash").resolve()
        candidate = Path(staged).resolve()
        try:
            candidate.relative_to(trash_root)
        except ValueError as exc:
            raise ValueError("Staged source path escapes the storage trash directory") from exc
        if candidate.parent != trash_root or not candidate.name.startswith(f"{canonical}-"):
            raise ValueError("Staged source does not belong to the document namespace")
        return candidate

    def restore_staged(self, document_id: str, staged: Path | None) -> None:
        if staged is None:
            return
        staged = self._validate_staged(document_id, staged)
        destination = self.root / self.validate_document_id(document_id)
        if destination.exists():
            raise FileExistsError("Cannot restore staged source over an existing document source")
        os.replace(staged, destination)

    def purge_staged(self, document_id: str, staged: Path | None) -> None:
        if staged:
            staged = self._validate_staged(document_id, staged)
            if staged.exists():
                shutil.rmtree(staged)

    def purge_document_trash(self, document_id: str) -> int:
        canonical = self.validate_document_id(document_id)
        trash_root = self.root / ".trash"
        if not trash_root.is_dir():
            return 0
        removed = 0
        for candidate in trash_root.glob(f"{canonical}-*"):
            validated = self._validate_staged(canonical, candidate)
            if validated.is_dir():
                shutil.rmtree(validated)
                removed += 1
        return removed
