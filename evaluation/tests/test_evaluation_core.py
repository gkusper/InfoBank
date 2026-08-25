from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.manifest import (
    freeze_output_directory,
    git_identity,
    prepare_output_directory,
    sha256_file,
    stable_hash,
    write_json,
)
from evaluation.schemas import EvaluationMode, REDACTED, RunManifest, RunRecord, canonical_json
from evaluation.usage_logging import append_run_record, merge_usage


def manifest(**overrides) -> RunManifest:
    values = {
        "run_id": "run-1",
        "timestamp": "2026-08-19T12:00:00Z",
        "commit_sha": "a" * 40,
        "branch": "integration/main-rebuild-2026-08",
        "dataset_version": "dataset-v1",
        "scorer_version": "scorer-v1",
        "config_version": "config-v1",
        "provider": "mock",
        "model": "mock-model",
        "python_version": "3.12.0",
        "database_target": "local-test-db",
        "chroma_path": "local-test-chroma",
    }
    values.update(overrides)
    return RunManifest(**values)


def record(**overrides) -> RunRecord:
    values = {
        "run_id": "run-1",
        "case_id": "case-1",
        "mode": EvaluationMode.C0_VECTOR_ONLY,
        "retrieved_ids": ["chunk-2", "chunk-1"],
        "generator_visible_context_hash": "sha256:" + "b" * 64,
        "output_class": "answer",
        "reason_code": "supported",
        "latency_ms": 12.5,
        "input_tokens": 10,
        "output_tokens": 4,
        "total_tokens": 14,
        "metrics": {"z": 1, "a": 2},
    }
    values.update(overrides)
    return RunRecord(**values)


def test_deterministic_serialization_and_hashing() -> None:
    first = record(metrics={"z": 1, "a": 2})
    second = record(metrics={"a": 2, "z": 1})
    assert canonical_json(first) == canonical_json(second)
    assert stable_hash({"z": 1, "a": 2}) == stable_hash({"a": 2, "z": 1})


def test_manifest_and_file_hashing_are_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "dataset.json"
    path.write_text('{"case":1}\n', encoding="utf-8")
    assert sha256_file(path) == sha256_file(path)

    expected_commit = "a" * 40
    expected_branch = "test-branch"

    def fake_git(repo_root: Path, *args: str) -> str:
        responses = {
            ("rev-parse", "HEAD"): expected_commit,
            ("branch", "--show-current"): expected_branch,
        }
        try:
            return responses[args]
        except KeyError as exc:
            raise AssertionError(f"Unexpected git command: {args}") from exc

    monkeypatch.setattr("evaluation.manifest._git", fake_git)

    commit, branch = git_identity(tmp_path)

    assert commit == expected_commit
    assert branch == expected_branch


def test_required_fields_and_generic_modes_are_enforced() -> None:
    with pytest.raises(ValueError, match="run_id"):
        manifest(run_id="")
    with pytest.raises(ValueError, match="config_version or config_hash"):
        manifest(config_version=None, config_hash=None)
    with pytest.raises(ValueError, match="credential-bearing"):
        manifest(database_target="mysql://user:password@localhost/db")
    with pytest.raises(ValueError, match="Unsupported evaluation mode"):
        record(mode="paper-specific-mode")
    assert {mode.value for mode in EvaluationMode} == {
        "C0_VECTOR_ONLY",
        "C1_VECTOR_ROUTING",
        "C2_PERMISSION_FILTERED",
        "C3_FULL_ROLE_AWARE",
    }


def test_secret_and_protected_content_sanitization() -> None:
    payload = {
        "api_key": "synthetic-api-key-value",
        "nested": {"refresh_token": "refresh-secret", "content": "protected body"},
        "input_tokens": 7,
    }
    safe = json.loads(canonical_json(payload))
    assert safe["api_key"] == REDACTED
    assert safe["nested"]["refresh_token"] == REDACTED
    assert safe["nested"]["content"] == REDACTED
    assert safe["input_tokens"] == 7
    debug = json.loads(canonical_json(payload, include_protected_content=True))
    assert debug["nested"]["content"] == "protected body"
    assert debug["nested"]["refresh_token"] == REDACTED


def test_frozen_output_cannot_be_overwritten_without_new_version(tmp_path: Path) -> None:
    output = prepare_output_directory(tmp_path, "run-1", "v1")
    write_json(output / "manifest.json", manifest().to_dict())
    append_run_record(output / "records.jsonl", record())
    freeze_output_directory(output)
    with pytest.raises(PermissionError, match="frozen"):
        write_json(output / "manifest.json", manifest().to_dict())
    with pytest.raises(PermissionError, match="frozen"):
        append_run_record(output / "records.jsonl", record())
    with pytest.raises(FileExistsError):
        prepare_output_directory(tmp_path, "run-1", "v1")
    assert prepare_output_directory(tmp_path, "run-1", "v2").is_dir()


def test_usage_merge_is_provider_neutral() -> None:
    merged = merge_usage(
        {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5, "latency_ms": 4.0, "retries": 1},
        {"input_tokens": 7, "output_tokens": 1, "total_tokens": 8, "latency_ms": 6.5, "errors": ["timeout"]},
    )
    assert merged == {
        "input_tokens": 10,
        "output_tokens": 3,
        "total_tokens": 13,
        "latency_ms": 10.5,
        "errors": ["timeout"],
        "retries": 1,
    }
