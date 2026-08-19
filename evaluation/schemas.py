from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REDACTED = "[REDACTED]"

SECRET_KEYS = {
    "api_key",
    "authorization",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "refresh_token",
    "secret",
    "token_json",
}
PROTECTED_CONTENT_KEYS = {
    "answer",
    "content",
    "context",
    "prompt",
    "question",
    "raw_content",
    "system_prompt",
    "user_prompt",
}
SECRET_VALUE_PATTERNS = [
    re.compile(r"^sk-[A-Za-z0-9_-]{16,}$"),
    re.compile(r"^AIza[0-9A-Za-z_-]{20,}$"),
    re.compile(r"^gh[pousr]_[A-Za-z0-9]{20,}$"),
    re.compile(r"^xox[baprs]-", re.IGNORECASE),
]


class EvaluationMode(str, enum.Enum):
    B0_VECTOR_ONLY = "B0_VECTOR_ONLY"
    B1_VECTOR_ROUTING = "B1_VECTOR_ROUTING"
    B2_PERMISSION_FILTERED = "B2_PERMISSION_FILTERED"
    B3_FULL_ROLE_AWARE = "B3_FULL_ROLE_AWARE"


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    timestamp: str
    commit_sha: str
    branch: str
    dataset_version: str
    scorer_version: str
    provider: str
    model: str
    python_version: str
    database_target: str
    chroma_path: str
    config_version: str | None = None
    config_hash: str | None = None

    def __post_init__(self) -> None:
        required = {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "commit_sha": self.commit_sha,
            "branch": self.branch,
            "dataset_version": self.dataset_version,
            "scorer_version": self.scorer_version,
            "provider": self.provider,
            "model": self.model,
            "python_version": self.python_version,
            "database_target": self.database_target,
            "chroma_path": self.chroma_path,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"Missing required manifest fields: {', '.join(sorted(missing))}")
        if not self.config_version and not self.config_hash:
            raise ValueError("Either config_version or config_hash is required")
        if "://" in self.database_target and "@" in self.database_target:
            raise ValueError("database_target must be a non-secret logical target, not a credential-bearing URL")

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_log(dataclasses.asdict(self))


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    case_id: str
    mode: EvaluationMode | str
    retrieved_ids: list[str]
    generator_visible_context_hash: str
    output_class: str
    reason_code: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "generator_visible_context_hash": self.generator_visible_context_hash,
            "output_class": self.output_class,
            "reason_code": self.reason_code,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"Missing required run-record fields: {', '.join(sorted(missing))}")
        try:
            EvaluationMode(self.mode)
        except ValueError as exc:
            raise ValueError(f"Unsupported evaluation mode: {self.mode}") from exc
        if self.latency_ms < 0:
            raise ValueError("latency_ms must not be negative")

    def to_dict(self, *, include_protected_content: bool = False) -> dict[str, Any]:
        return sanitize_for_log(dataclasses.asdict(self), include_protected_content=include_protected_content)


def utc_timestamp() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_for_log(value: Any, *, include_protected_content: bool = False) -> Any:
    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in SECRET_KEYS or normalized.endswith("_api_key") or normalized.endswith("_secret"):
                sanitized[str(key)] = REDACTED
            elif normalized in PROTECTED_CONTENT_KEYS and not include_protected_content:
                sanitized[str(key)] = REDACTED
            else:
                sanitized[str(key)] = sanitize_for_log(item, include_protected_content=include_protected_content)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_log(item, include_protected_content=include_protected_content) for item in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        return REDACTED
    return value


def canonical_json(value: Any, *, include_protected_content: bool = False) -> str:
    sanitized = sanitize_for_log(value, include_protected_content=include_protected_content)
    return json.dumps(sanitized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
