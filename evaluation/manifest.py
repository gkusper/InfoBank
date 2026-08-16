from __future__ import annotations

import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from .backend import REPO_ROOT


RELEVANT_PACKAGES = [
    "chromadb",
    "openai",
    "pydantic",
    "SQLAlchemy",
    "PyMySQL",
    "PyYAML",
    "fastapi",
]


def git_info(repo_root: Path = REPO_ROOT) -> dict[str, str | None]:
    safe = repo_root.as_posix()

    def run(args: list[str]) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-c", f"safe.directory={safe}", "-C", str(repo_root), *args],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return None

    return {
        "git_commit": run(["rev-parse", "HEAD"]),
        "git_branch": run(["branch", "--show-current"]),
    }


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in RELEVANT_PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def build_manifest(
    *,
    run_id: str,
    retrieval_top_k: int,
    repetitions: int,
    generation_config: Any,
    clean_state_report: Any | None = None,
    fixture_path: str | None = None,
    fixture_identifier: str | None = None,
) -> dict[str, Any]:
    info = git_info()
    return {
        "run_id": run_id,
        "git_commit": info["git_commit"],
        "git_branch": info["git_branch"],
        "python_version": sys.version,
        "python_platform": platform.platform(),
        "package_versions": package_versions(),
        "database_name": getattr(clean_state_report, "database_name", None),
        "CHROMA_PERSIST_DIR": getattr(clean_state_report, "chroma_persist_dir", None),
        "chroma_collection_name": getattr(clean_state_report, "chroma_collection_name", "infobank_vectors"),
        "document_count": _count(clean_state_report, "documents"),
        "chunk_count": _count(clean_state_report, "document_chunks"),
        "vector_count": getattr(clean_state_report, "vector_count", None),
        "embedding_model": generation_config.embedding_model,
        "generator_model": generation_config.generator_model,
        "retrieval_top_k": retrieval_top_k,
        "temperature": generation_config.temperature,
        "repetitions": repetitions,
        "fixture_identifier": fixture_identifier,
        "fixture_path": fixture_path,
    }


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _count(report: Any | None, table: str) -> int | None:
    if report is None:
        return None
    return getattr(report, "table_counts", {}).get(table)
