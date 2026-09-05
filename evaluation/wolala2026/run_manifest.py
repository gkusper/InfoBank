from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .common import sha256_file, write_json


PACKAGE_DIR = Path(__file__).resolve().parent


RUN_MANIFEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "WoLaLa 2026 Pilot Run Manifest",
    "type": "object",
    "properties": {
        "planned_logical_embedding_requests": {"type": "integer"},
        "successful_logical_embedding_requests": {"type": "integer"},
        "actual_embedding_attempts": {"type": "integer"},
        "embedding_retry_attempts": {"type": "integer"},
        "retrieval_cache_hits": {"type": "integer"},
        "retrieval_snapshot_count": {"type": "integer"},
        "snapshot_reuse_count": {"type": "integer"},
        "unique_retrieval_snapshot_hashes": {"type": "integer"},
        "result_record_count": {"type": "integer"},
        "planned_logical_generation_requests_maximum": {"type": "integer"},
        "planned_external_requests_without_retries_maximum": {"type": "integer"},
        "actual_provider_attempts": {"type": "integer"},
        "actual_retry_attempts": {"type": "integer"},
        "retry_events": {"type": "array"},
        "max_total_retry_attempts": {"type": "integer"},
        "max_retries_per_logical_request": {"type": "integer"},
        "external_warmup_calls": {"type": "integer"},
        "run_attempt": {"type": "integer"},
        "invalidation_class": {"type": ["string", "null"]},
        "protocol_v2_checksum": {"type": "string"},
        "statistical_plan_checksum": {"type": ["string", "null"]},
        "latency_definition_checksum": {"type": ["string", "null"]},
        "execution_spec_checksum": {"type": "string"},
    },
    "required": [
        "run_id",
        "run_type",
        "development_or_heldout",
        "git_commit",
        "git_branch",
        "dataset_name",
        "dataset_checksum",
        "protocol_version",
        "protocol_checksum",
        "prompt_versions",
        "prompt_checksums",
        "provider",
        "embedding_model",
        "generator_model",
        "temperature",
        "top_k",
        "max_output_tokens",
        "random_seed",
        "operating_system",
        "python_version",
        "dependency_versions",
        "start_time_utc",
        "end_time_utc",
        "case_ids",
        "modes",
        "repetitions",
        "max_mode_executions",
        "max_embedding_calls",
        "max_generation_calls",
        "max_total_external_calls",
        "actual_embedding_calls",
        "actual_generation_calls",
        "actual_total_external_calls",
        "cold_or_warm_state",
        "cache_configuration",
        "errors",
        "completion_status",
    ],
}


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_value(args: list[str], default: str = "UNKNOWN") -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=PACKAGE_DIR.parents[1], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return default


def dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ["pydantic", "PyYAML", "SQLAlchemy", "openai", "chromadb"]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def prompt_checksums() -> dict[str, str]:
    prompts = {
        "prompt_only_v1": PACKAGE_DIR / "prompts" / "prompt_only_v1.txt",
        "cfaf_generator_v1": PACKAGE_DIR / "prompts" / "cfaf_generator_v1.txt",
    }
    return {name: sha256_file(path) if path.exists() else "missing" for name, path in prompts.items()}


def build_manifest(
    *,
    run_id: str,
    run_type: str,
    development_or_heldout: str,
    dataset_name: str,
    dataset_checksum: str,
    protocol_checksum: str,
    case_ids: list[str],
    modes: list[str],
    repetitions: int,
    max_mode_executions: int,
    max_embedding_calls: int,
    max_generation_calls: int,
    max_total_external_calls: int,
    start_time_utc: str,
    allow_real_api: bool,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_type": run_type,
        "development_or_heldout": development_or_heldout,
        "git_commit": git_value(["rev-parse", "HEAD"]),
        "git_branch": git_value(["branch", "--show-current"]),
        "git_working_tree_status": git_value(["status", "--short"]),
        "dataset_name": dataset_name,
        "dataset_checksum": dataset_checksum,
        "protocol_version": "WOLALA2026_PILOT_PROTOCOL_v1",
        "protocol_checksum": protocol_checksum,
        "prompt_versions": {"prompt_only": "prompt_only_v1", "cfaf_generator": "cfaf_generator_v1"},
        "prompt_checksums": prompt_checksums(),
        "provider": "deterministic-local" if not allow_real_api else "openai",
        "embedding_model": "deterministic-shared-retrieval-v1" if not allow_real_api else os.getenv("WOLALA_EMBEDDING_MODEL", "text-embedding-3-small"),
        "generator_model": "deterministic-envelope-generator-v1" if not allow_real_api else os.getenv("WOLALA_GENERATOR_MODEL", "gpt-4o-mini"),
        "temperature": 0,
        "top_k": 4,
        "max_output_tokens": 160,
        "random_seed": 20260818,
        "operating_system": platform.platform(),
        "python_version": sys.version,
        "dependency_versions": dependency_versions(),
        "start_time_utc": start_time_utc,
        "end_time_utc": None,
        "case_ids": case_ids,
        "modes": modes,
        "repetitions": repetitions,
        "max_mode_executions": max_mode_executions,
        "max_embedding_calls": max_embedding_calls,
        "max_generation_calls": max_generation_calls,
        "max_total_external_calls": max_total_external_calls,
        "actual_embedding_calls": 0,
        "actual_generation_calls": 0,
        "actual_total_external_calls": 0,
        "cold_or_warm_state": "cold-deterministic-process",
        "cache_configuration": {"external_cache": "not-used", "retrieval_cache": "none"},
        "errors": [],
        "completion_status": "RUNNING",
        "allow_real_api": allow_real_api,
        "heldout_approval_supplied": False,
    }


def write_schema(path: str | Path = PACKAGE_DIR / "run_manifest_schema.json") -> None:
    write_json(path, RUN_MANIFEST_SCHEMA)
