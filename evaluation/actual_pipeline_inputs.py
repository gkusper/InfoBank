"""Gold-independent schemas and loaders for actual-pipeline evaluation inputs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


QUERY_SCHEMA_VERSION = "infobank-query-input-v1"
CORPUS_SCHEMA_VERSION = "infobank-actual-corpus-v1"


@dataclass(frozen=True)
class QueryInput:
    case_id: str
    evaluation_identity: str
    query_text: str
    declared_purpose: str
    corpus_package_ref: str
    policy_fixture_ref: str
    runtime_parameters: dict[str, Any] = field(default_factory=dict)
    schema_version: str = QUERY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        required = (
            self.case_id,
            self.evaluation_identity,
            self.query_text,
            self.declared_purpose,
            self.corpus_package_ref,
            self.policy_fixture_ref,
        )
        if not all(str(value).strip() for value in required):
            raise ValueError("QueryInput required fields must not be empty")
        if self.schema_version != QUERY_SCHEMA_VERSION:
            raise ValueError(f"Unsupported query schema: {self.schema_version}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CorpusDocument:
    document_id: str
    package_ref: str
    object_id: str
    document_type: str
    original_filename: str
    pages: tuple[str, ...]
    keywords: tuple[str, ...]
    archived: bool = False

    def __post_init__(self) -> None:
        if not self.document_id or not self.package_ref or not self.object_id or not self.pages:
            raise ValueError("CorpusDocument identity and pages are required")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["pages"] = list(self.pages)
        value["keywords"] = list(self.keywords)
        return value


@dataclass(frozen=True)
class PolicyFixture:
    fixture_id: str
    access_by_document: dict[str, str]
    purpose: str = "grounded_question_answering"
    conflict_policy: str = "query_sensitive"
    aggregate_k: int = 3
    prohibited_markers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["prohibited_markers"] = list(self.prohibited_markers)
        return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        case_id = str(value.get("case_id", ""))
        if not case_id or case_id in seen:
            raise ValueError(f"Missing or duplicate case_id at line {line_number}")
        seen.add(case_id)
        rows.append(value)
    return rows


def load_query_inputs(path: str | Path) -> list[QueryInput]:
    return [QueryInput(**row) for row in _read_jsonl(Path(path))]


def load_corpus_fixture(path: str | Path) -> tuple[list[CorpusDocument], dict[str, PolicyFixture], dict[str, Any]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != CORPUS_SCHEMA_VERSION:
        raise ValueError("Corpus schema/version mismatch")
    documents = [
        CorpusDocument(
            **{
                **item,
                "pages": tuple(item["pages"]),
                "keywords": tuple(item["keywords"]),
            }
        )
        for item in value["documents"]
    ]
    fixtures = {
        item["fixture_id"]: PolicyFixture(
            **{**item, "prohibited_markers": tuple(item.get("prohibited_markers", []))}
        )
        for item in value["policy_fixtures"]
    }
    return documents, fixtures, value["metadata"]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
