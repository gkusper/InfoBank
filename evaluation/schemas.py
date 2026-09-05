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
    C0_VECTOR_ONLY = "C0_VECTOR_ONLY"
    C1_VECTOR_ROUTING = "C1_VECTOR_ROUTING"
    P1_PROMPT_ONLY_GOVERNANCE = "P1_PROMPT_ONLY_GOVERNANCE"
    C2_PERMISSION_FILTERED = "C2_PERMISSION_FILTERED"
    C3_FULL_ROLE_AWARE = "C3_FULL_ROLE_AWARE"


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


MODE_STANDARD = "standard_rag"
MODE_GOVERNANCE = "governance_only_rag"
MODE_ROLE_AWARE = "role_aware_rag"


@dataclass
class GenerationConfig:
    generator_model: str
    embedding_model: str
    temperature: float = 0.0
    top_p: float | None = None
    seed: int | None = None
    max_tokens: int | None = None


@dataclass
class RetrievedCandidate:
    rank: int
    chunk_id: str
    document_id: str
    file_name: str
    raw_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    distance: float | None = None
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class SharedRetrievalResult:
    question: str
    query_profile: dict[str, Any]
    query_embedding_identifier: str | None
    retrieved_candidates: list[RetrievedCandidate]
    retrieval_top_k: int = 4
    embedding_model: str = "text-embedding-3-small"
    api_usage: dict[str, Any] = field(default_factory=dict)

    @property
    def retrieved_chunk_ids(self) -> list[str]:
        return [candidate.chunk_id for candidate in self.retrieved_candidates]

    def raw_chunks(self) -> list[dict[str, Any]]:
        return [candidate.to_dict() for candidate in self.retrieved_candidates]


@dataclass
class GenerationOutput:
    answer: str
    api_usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    run_id: str
    case_id: str
    mode: str
    repetition: int
    git_commit: str | None
    timestamp: str
    question: str
    query_profile: dict[str, Any]
    query_embedding_identifier: str | None
    document_ids: list[str]
    chunk_ids: list[str]
    retrieved_chunk_ids: list[str]
    retrieval_distances: list[float | None]
    retrieval_rank: list[int]
    retrieval_top_k: int
    raw_retrieved_chunks: list[dict[str, Any]]
    generator_context_blocks: list[str]
    system_prompt: str | None
    user_prompt: str | None
    answer: str | None
    output_mode: str | None
    use_decisions: dict[str, Any] | None
    source_roles: dict[str, Any] | None
    source_role_summary: dict[str, Any] | None
    relevance_level_summary: dict[str, Any] | None
    evidence_decision: str | None
    evidence_check: dict[str, Any] | None
    controlled_failure_status: str | None
    controlled_failure_reason: str | None
    controlled_failure: dict[str, Any] | None
    withheld_document_ids: list[str]
    redacted_chunk_ids: list[str]
    protected_content_disclosed: bool | None
    embedding_model: str
    generator_model: str
    generation_temperature: float
    generation_top_p: float | None
    generation_seed: int | None
    generation_max_tokens: int | None
    api_usage: dict[str, Any]
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(dataclasses.asdict(self))


def now_timestamp() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return value


def write_jsonl_record(path: str | Path, result: EvaluationResult) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def read_jsonl_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def base_result_fields(
    *,
    run_id: str,
    case_id: str,
    mode: str,
    repetition: int,
    git_commit: str | None,
    retrieval: SharedRetrievalResult,
    generation_config: GenerationConfig,
) -> dict[str, Any]:
    candidates = retrieval.retrieved_candidates
    document_ids = list(dict.fromkeys(candidate.document_id for candidate in candidates))
    chunk_ids = [candidate.chunk_id for candidate in candidates]
    return {
        "run_id": run_id,
        "case_id": case_id,
        "mode": mode,
        "repetition": repetition,
        "git_commit": git_commit,
        "timestamp": now_timestamp(),
        "question": retrieval.question,
        "query_profile": retrieval.query_profile,
        "query_embedding_identifier": retrieval.query_embedding_identifier,
        "document_ids": document_ids,
        "chunk_ids": chunk_ids,
        "retrieved_chunk_ids": chunk_ids,
        "retrieval_distances": [candidate.distance for candidate in candidates],
        "retrieval_rank": [candidate.rank for candidate in candidates],
        "retrieval_top_k": retrieval.retrieval_top_k,
        "raw_retrieved_chunks": retrieval.raw_chunks(),
        "embedding_model": generation_config.embedding_model,
        "generator_model": generation_config.generator_model,
        "generation_temperature": generation_config.temperature,
        "generation_top_p": generation_config.top_p,
        "generation_seed": generation_config.seed,
        "generation_max_tokens": generation_config.max_tokens,
    }
