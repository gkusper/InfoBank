from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


REQUIRED_ZERO_TABLES = [
    "documents",
    "document_chunks",
    "document_keywords",
    "user_document_permission",
    "evidence_units",
    "policy_rules",
    "connector_accounts",
]

PREFERRED_ZERO_TABLES = [
    "users",
    "audit_logs",
    "keywords",
]


class CleanStateError(RuntimeError):
    def __init__(self, message: str, report: "CleanStateReport | None" = None):
        super().__init__(message)
        self.report = report


@dataclass
class CleanStateReport:
    database_url_visible: bool
    database_name: str | None
    chroma_persist_dir: str | None
    chroma_collection_name: str
    table_counts: dict[str, int]
    vector_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_url_visible": self.database_url_visible,
            "database_name": self.database_name,
            "chroma_persist_dir": self.chroma_persist_dir,
            "chroma_collection_name": self.chroma_collection_name,
            "table_counts": self.table_counts,
            "vector_count": self.vector_count,
        }


def check_clean_state(
    *,
    database_url: str | None = None,
    chroma_persist_dir: str | None = None,
    chroma_collection_name: str = "infobank_vectors",
    required_zero_tables: list[str] | None = None,
    preferred_zero_tables: list[str] | None = None,
) -> CleanStateReport:
    database_url = database_url or os.getenv("DATABASE_URL")
    chroma_persist_dir = chroma_persist_dir or os.getenv("CHROMA_PERSIST_DIR")
    if not database_url:
        raise CleanStateError("DATABASE_URL is not visible in the process environment.")
    if not chroma_persist_dir:
        raise CleanStateError("CHROMA_PERSIST_DIR is not visible in the process environment.")
    database_name = database_name_from_url(database_url)
    if database_name != "infobank_eval":
        raise CleanStateError(f"DATABASE_URL must point to infobank_eval, not {database_name!r}.")
    if "chroma_eval" not in Path(chroma_persist_dir).as_posix():
        raise CleanStateError(f"CHROMA_PERSIST_DIR must point to chroma_eval, not {chroma_persist_dir!r}.")

    tables = list(required_zero_tables or REQUIRED_ZERO_TABLES) + list(preferred_zero_tables or PREFERRED_ZERO_TABLES)
    table_counts = read_table_counts(database_url, tables)
    vector_count = read_chroma_vector_count(chroma_persist_dir, chroma_collection_name)
    report = CleanStateReport(
        database_url_visible=True,
        database_name=database_name,
        chroma_persist_dir=chroma_persist_dir,
        chroma_collection_name=chroma_collection_name,
        table_counts=table_counts,
        vector_count=vector_count,
    )
    assert_clean_counts(table_counts, vector_count, required_zero_tables=tables, report=report)
    return report


def database_name_from_url(database_url: str) -> str | None:
    return make_url(database_url).database


def read_table_counts(database_url: str, tables: list[str]) -> dict[str, int]:
    engine = create_engine(database_url)
    counts: dict[str, int] = {}
    with engine.connect() as conn:
        active = conn.execute(text("SELECT DATABASE()")).scalar()
        if active != "infobank_eval":
            raise CleanStateError(f"Connected database must be infobank_eval, not {active!r}.")
        for table_name in tables:
            counts[table_name] = int(conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar())
    return counts


def read_chroma_vector_count(chroma_persist_dir: str, collection_name: str = "infobank_vectors") -> int:
    client = chromadb.PersistentClient(path=chroma_persist_dir)
    names = {collection.name for collection in client.list_collections()}
    if collection_name not in names:
        return 0
    return int(client.get_collection(collection_name).count())


def assert_clean_counts(
    table_counts: dict[str, int],
    vector_count: int,
    *,
    required_zero_tables: list[str] | None = None,
    report: CleanStateReport | None = None,
) -> None:
    contaminated = {name: count for name, count in table_counts.items() if count != 0}
    if vector_count != 0:
        contaminated["chroma_vectors"] = vector_count
    if contaminated:
        raise CleanStateError(f"Evaluation environment is contaminated: {contaminated}", report)
