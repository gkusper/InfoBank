from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from .backend import REPO_ROOT
from .schemas import RunManifest, canonical_json, sanitize_for_log, utc_timestamp


SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def git_identity(repo_root: Path = REPO_ROOT) -> tuple[str, str]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    branch = _git(repo_root, "branch", "--show-current")
    if not commit or not branch:
        raise RuntimeError("Unable to capture exact Git commit and branch")
    return commit, branch


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), *args],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_json(value, include_protected_content=True).encode("utf-8"))


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


def build_run_manifest(
    *,
    run_id: str,
    dataset_version: str,
    scorer_version: str,
    provider: str,
    model: str,
    database_target: str,
    chroma_path: str,
    config_version: str | None = None,
    config_hash: str | None = None,
    repo_root: Path = REPO_ROOT,
) -> RunManifest:
    commit, branch = git_identity(repo_root)
    return RunManifest(
        run_id=run_id,
        timestamp=utc_timestamp(),
        commit_sha=commit,
        branch=branch,
        dataset_version=dataset_version,
        scorer_version=scorer_version,
        config_version=config_version,
        config_hash=config_hash,
        provider=provider,
        model=model,
        python_version=sys.version.split()[0],
        database_target=database_target,
        chroma_path=chroma_path,
    )


def build_evaluation_manifest(
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


def build_manifest(
    *,
    run_id: str,
    dataset_version: str | None = None,
    scorer_version: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    database_target: str | None = None,
    chroma_path: str | None = None,
    config_version: str | None = None,
    config_hash: str | None = None,
    repo_root: Path = REPO_ROOT,
    retrieval_top_k: int | None = None,
    repetitions: int | None = None,
    generation_config: Any | None = None,
    clean_state_report: Any | None = None,
    fixture_path: str | None = None,
    fixture_identifier: str | None = None,
) -> RunManifest | dict[str, Any]:
    if generation_config is not None or retrieval_top_k is not None or repetitions is not None:
        if generation_config is None or retrieval_top_k is None or repetitions is None:
            raise TypeError("generation_config, retrieval_top_k, and repetitions are required together")
        return build_evaluation_manifest(
            run_id=run_id,
            retrieval_top_k=retrieval_top_k,
            repetitions=repetitions,
            generation_config=generation_config,
            clean_state_report=clean_state_report,
            fixture_path=fixture_path,
            fixture_identifier=fixture_identifier,
        )

    required = {
        "dataset_version": dataset_version,
        "scorer_version": scorer_version,
        "provider": provider,
        "model": model,
        "database_target": database_target,
        "chroma_path": chroma_path,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise TypeError(f"Missing run-manifest fields: {', '.join(sorted(missing))}")
    return build_run_manifest(
        run_id=run_id,
        dataset_version=dataset_version or "",
        scorer_version=scorer_version or "",
        provider=provider or "",
        model=model or "",
        database_target=database_target or "",
        chroma_path=chroma_path or "",
        config_version=config_version,
        config_hash=config_hash,
        repo_root=repo_root,
    )


def prepare_output_directory(root: str | Path, run_id: str, result_version: str) -> Path:
    for name, value in {"run_id": run_id, "result_version": result_version}.items():
        if not SAFE_COMPONENT.fullmatch(value):
            raise ValueError(f"Unsafe {name}: {value!r}")
    destination = Path(root) / run_id / result_version
    if destination.exists():
        raise FileExistsError(f"Result directory already exists: {destination}")
    destination.mkdir(parents=True)
    return destination


def freeze_output_directory(directory: str | Path) -> Path:
    marker = Path(directory) / ".frozen"
    marker.write_text("frozen\n", encoding="utf-8", errors="strict")
    return marker


def ensure_not_frozen(path: str | Path) -> None:
    candidate = Path(path).resolve()
    for parent in [candidate.parent, *candidate.parents]:
        if (parent / ".frozen").exists():
            raise PermissionError(f"Refusing to overwrite frozen output under: {parent}")


def write_json(path: str | Path, value: Any, *, include_protected_content: bool = False) -> None:
    destination = Path(path)
    ensure_not_frozen(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = sanitize_for_log(value, include_protected_content=include_protected_content)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def write_manifest(path: str | Path, manifest: RunManifest | dict[str, Any]) -> None:
    payload = manifest.to_dict() if isinstance(manifest, RunManifest) else manifest
    write_json(path, payload)


def runtime_fingerprint() -> dict[str, str]:
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }


def _count(report: Any | None, table: str) -> int | None:
    if report is None:
        return None
    return getattr(report, "table_counts", {}).get(table)
