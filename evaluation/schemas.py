from __future__ import annotations

import dataclasses
import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (_dt.datetime, _dt.date)):
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
