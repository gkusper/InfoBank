from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
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


def build_manifest(
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


def write_manifest(path: str | Path, manifest: RunManifest) -> None:
    write_json(path, manifest.to_dict())


def runtime_fingerprint() -> dict[str, str]:
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }
