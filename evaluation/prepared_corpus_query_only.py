"""Prepared-corpus query-only execution for real-provider readiness pilots.

This module reuses :class:`evaluation.actual_pipeline_runner.PipelineRuntime`
for C0/C1/P1/C2/C3 semantics while replacing the seeding initialization with
manifest-validated, disposable query state.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import re
import shutil
import time
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from .actual_pipeline_gold import load_gold_annotations
from .actual_pipeline_inputs import load_corpus_fixture, load_query_inputs, write_jsonl
from .actual_pipeline_runner import (
    DEFAULT_MODEL,
    EXECUTION_MODE_PREPARED_QUERY_ONLY,
    GENERATION_PROMPT_VERSION,
    GENERATION_TEMPERATURE,
    PROMPT_ONLY_GOVERNANCE_PROMPT_VERSION,
    QueryOnlyOperationCounters,
    ROUTING_PROMPT_VERSION,
    RAW_SCHEMA_VERSION,
    RUNNER_VERSION,
    SEAL_SCHEMA_VERSION,
    ActualPipelineConfig,
    PipelineRuntime,
    _canonical,
    _git_head,
    _sha256_bytes,
    _sha256_file,
    prompt_only_governance_prompt,
)
from .actual_pipeline_scorer import scan_record_safety, score_sealed_run
from .backend import REPO_ROOT, ensure_backend_path
from .provider_readiness import (
    MAX_CONTEXT_TOKEN_BUDGET_PER_CASE,
    READINESS_STATUS,
    ReadinessConfig,
)
from .schemas import EvaluationMode, utc_timestamp

ensure_backend_path()
from ai_provider import embedding_dimensions  # noqa: E402


PREPARED_QUERY_ONLY_RUN_SCHEMA_VERSION = "infobank-prepared-corpus-query-only-run-v1"
PREPARED_SELECTION_PLAN_SCHEMA_VERSION = "infobank-prepared-corpus-readiness-selection-plan-v1"
PREPARED_MANIFEST_SCHEMA_VERSION = "infobank-openai-prepared-corpus-v1"
EXPECTED_PREPARATION_STATUS = "READY"
EXPECTED_DATABASE_NAME = "infobank_eval_claude_prepare_20260904"
EXPECTED_DOCUMENT_COUNT = 41
EXPECTED_CHUNK_COUNT = 245
EXPECTED_VECTOR_COUNT = 245
EXPECTED_SOURCE_PDF_COUNT = 41
EXPECTED_EMBEDDING_PROVIDER = "openai"
EXPECTED_EMBEDDING_MODEL = "text-embedding-3-small"
EXPECTED_EMBEDDING_DIMENSIONS = 1536
PROVISIONAL_SCORE_LABEL = "PROVISIONAL - NOT FOR MANUSCRIPT USE"
FORBIDDEN_COUNTERS = (
    "document_pdf_parse_calls",
    "document_chunking_calls",
    "document_keyword_extraction_calls",
    "document_embedding_calls",
    "chroma_add_calls",
    "corpus_seed_calls",
)
REFERENCE_SELECTION_ORDER = (
    "FULL_ANSWER",
    "AGGREGATE_RESULT",
    "CONSTRAINED_ANSWER",
    "REFUSE_INSUFFICIENT_EVIDENCE",
    "REFUSE_AGGREGATION_THRESHOLD",
    "CLARIFICATION",
)
QUERY_ROUTING_MODES = {
    EvaluationMode.C1_VECTOR_ROUTING.value,
    EvaluationMode.P1_PROMPT_ONLY_GOVERNANCE.value,
    EvaluationMode.C3_FULL_ROLE_AWARE.value,
}
FULL_QUERY_ONLY_MODES = tuple(mode.value for mode in EvaluationMode)
BASE_INTEGRITY_TABLES = (
    "documents",
    "document_chunks",
    "user_document_permission",
    "policy_rules",
    "audit_logs",
    "document_audit_links",
)


@dataclass(frozen=True)
class PreparedCorpus:
    manifest_path: Path
    manifest_sha256: str
    manifest: dict[str, Any]
    database_name: str
    chroma_dir: Path
    chroma_collection_name: str
    source_storage_dir: Path
    corpus_fixture_path: Path
    corpus_fixture_sha256: str
    query_input_path: Path
    query_input_sha256: str
    dataset_version: str
    document_count: int
    chunk_count: int
    vector_count: int
    source_pdf_count: int
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    config_hash: str
    preparation_status: str
    created_at_utc: str

    @property
    def prepared_corpus_id(self) -> str:
        value = {
            "manifest_sha256": self.manifest_sha256,
            "corpus_fixture_sha256": self.corpus_fixture_sha256,
            "query_input_sha256": self.query_input_sha256,
            "config_hash": self.config_hash,
            "collection": self.chroma_collection_name,
        }
        return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:16]

    def metadata(
        self,
        *,
        disposable_database_name: str | None = None,
        disposable_workspace_path: Path | None = None,
        cache_namespace_version: str | None = None,
    ) -> dict[str, Any]:
        return {
            "prepared_manifest_path": _repo_relative(self.manifest_path),
            "prepared_manifest_sha256": self.manifest_sha256,
            "prepared_corpus_id": self.prepared_corpus_id,
            "base_database_name": self.database_name,
            "disposable_database_name": disposable_database_name,
            "disposable_workspace_path": None if disposable_workspace_path is None else _repo_relative(disposable_workspace_path),
            "source_corpus_version": self.dataset_version,
            "prepared_document_count": self.document_count,
            "prepared_chunk_count": self.chunk_count,
            "prepared_vector_count": self.vector_count,
            "prepared_source_pdf_count": self.source_pdf_count,
            "prepared_chroma_collection_name": self.chroma_collection_name,
            "prepared_embedding_provider": self.embedding_provider,
            "prepared_embedding_model": self.embedding_model,
            "prepared_embedding_dimensions": self.embedding_dimensions,
            "policy_configuration_hash": self.config_hash,
            "query_input_version": self.dataset_version,
            "cache_namespace_version": cache_namespace_version,
        }


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve()


def _repo_relative(path: str | Path) -> str:
    value = Path(path).resolve()
    try:
        return value.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(value)


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _directory_fingerprint(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    total_bytes = 0
    for item in files:
        relative = item.relative_to(path).as_posix()
        payload_hash = _file_sha256(item)
        size = item.stat().st_size
        total_bytes += size
        digest.update(f"{relative}\0{size}\0{payload_hash}\n".encode("utf-8"))
    return {
        "path": _repo_relative(path),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "sha256": digest.hexdigest(),
    }


def _source_file_count(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file())


def _database_name_from_url(database_url: str) -> str:
    parsed = make_url(database_url)
    return parsed.database or ""


def _validate_mysql_eval_database_name(database_name: str, *, label: str) -> str:
    if not database_name:
        raise ValueError(f"{label} database name is empty")
    if not re.fullmatch(r"[A-Za-z0-9_]+", database_name):
        raise ValueError(f"{label} database name contains unsafe characters")
    if not database_name.startswith("infobank_eval_"):
        raise ValueError(f"{label} database name must start with infobank_eval_")
    if database_name == "infobank_db":
        raise ValueError(f"{label} database name must not be infobank_db")
    return database_name


def _database_url_with_name(database_url: str, database_name: str) -> str:
    _validate_mysql_eval_database_name(database_name, label="target")
    return make_url(database_url).set(database=database_name).render_as_string(hide_password=False)


def _quote_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"Unsafe SQL identifier: {name}")
    return f"`{name}`"


def _query_table_counts(database_url: str, tables: Sequence[str] = BASE_INTEGRITY_TABLES) -> dict[str, int | None]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        counts: dict[str, int | None] = {}
        with engine.connect() as connection:
            for table_name in tables:
                if table_name not in existing_tables:
                    counts[table_name] = None
                    continue
                quoted = _quote_identifier(table_name) if engine.dialect.name == "mysql" else f'"{table_name}"'
                counts[table_name] = int(connection.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one())
        return counts
    finally:
        engine.dispose()


def _manifest_collection(manifest: dict[str, Any]) -> dict[str, Any]:
    collections = manifest.get("chroma", {}).get("collections")
    if not isinstance(collections, list) or len(collections) != 1 or not isinstance(collections[0], dict):
        raise ValueError("Prepared manifest must record exactly one Chroma collection")
    return collections[0]


def load_prepared_corpus_manifest(manifest_path: str | Path) -> PreparedCorpus:
    path = _repo_path(manifest_path)
    manifest = _read_json_object(path)
    collection = _manifest_collection(manifest)
    inputs = manifest.get("inputs", {})
    database = manifest.get("database", {})
    source_storage = manifest.get("source_storage", {})
    config = manifest.get("actual_pipeline_config", {})

    errors: list[str] = []
    schema_version = str(manifest.get("schema_version") or "")
    created_at_utc = str(manifest.get("created_at_utc") or "")
    database_name = str(database.get("name") or "")
    chroma_dir = _repo_path(str(manifest.get("chroma", {}).get("persist_dir") or ""))
    collection_name = str(collection.get("name") or "")
    source_storage_dir = _repo_path(str(source_storage.get("dir") or ""))
    corpus_fixture_path = _repo_path(str(inputs.get("corpus_fixture_path") or ""))
    query_input_path = _repo_path(str(inputs.get("query_input_path") or ""))
    dataset_version = str(inputs.get("dataset_version") or "")
    preparation_status = str(manifest.get("preparation_status") or "")
    embedding_provider = str(manifest.get("embedding_provider") or "")
    embedding_model = str(manifest.get("embedding_model") or "")
    embedding_dimension_value = manifest.get("embedding_dimensions")
    table_counts = database.get("table_counts") if isinstance(database.get("table_counts"), dict) else {}

    document_count = int(inputs.get("document_count") or table_counts.get("documents") or 0)
    chunk_count = int(table_counts.get("document_chunks") or 0)
    vector_count = int(manifest.get("chroma", {}).get("total_vector_count") or collection.get("count") or 0)
    source_pdf_count = int(source_storage.get("file_count") or 0)
    config_hash = str(config.get("config_hash") or "")
    corpus_fixture_sha256 = str(inputs.get("corpus_fixture_sha256") or "")
    query_input_sha256 = str(inputs.get("query_input_sha256") or "")

    if schema_version != PREPARED_MANIFEST_SCHEMA_VERSION:
        errors.append("manifest schema/version mismatch")
    if not created_at_utc:
        errors.append("preparation timestamp is missing")
    try:
        _validate_mysql_eval_database_name(database_name, label="prepared")
    except ValueError as exc:
        errors.append(str(exc))
    if database_name != EXPECTED_DATABASE_NAME:
        errors.append(f"database name mismatch: expected {EXPECTED_DATABASE_NAME}, got {database_name or '<missing>'}")
    if not collection_name:
        errors.append("Chroma collection name is missing")
    if document_count != EXPECTED_DOCUMENT_COUNT:
        errors.append(f"document count mismatch: expected {EXPECTED_DOCUMENT_COUNT}, got {document_count}")
    if chunk_count != EXPECTED_CHUNK_COUNT:
        errors.append(f"chunk count mismatch: expected {EXPECTED_CHUNK_COUNT}, got {chunk_count}")
    if vector_count != EXPECTED_VECTOR_COUNT:
        errors.append(f"vector count mismatch: expected {EXPECTED_VECTOR_COUNT}, got {vector_count}")
    if source_pdf_count != EXPECTED_SOURCE_PDF_COUNT:
        errors.append(f"source PDF count mismatch: expected {EXPECTED_SOURCE_PDF_COUNT}, got {source_pdf_count}")
    if embedding_provider != EXPECTED_EMBEDDING_PROVIDER:
        errors.append(f"embedding provider mismatch: expected {EXPECTED_EMBEDDING_PROVIDER}, got {embedding_provider or '<missing>'}")
    if embedding_model != EXPECTED_EMBEDDING_MODEL:
        errors.append(f"embedding model mismatch: expected {EXPECTED_EMBEDDING_MODEL}, got {embedding_model or '<missing>'}")
    if embedding_dimension_value != EXPECTED_EMBEDDING_DIMENSIONS:
        errors.append(
            f"embedding dimensions mismatch: expected {EXPECTED_EMBEDDING_DIMENSIONS}, got {embedding_dimension_value or '<missing>'}"
        )
    if config_hash != "002e7aea57218737b16baec95cb819a6b6264d4262581bd54ddb1f603db0e7cf":
        errors.append("actual pipeline configuration hash mismatch")
    if preparation_status != EXPECTED_PREPARATION_STATUS:
        errors.append(f"preparation status mismatch: expected {EXPECTED_PREPARATION_STATUS}, got {preparation_status or '<missing>'}")
    if int(manifest.get("queries_run") or 0) != 0:
        errors.append("preparation manifest records query execution")
    if int(manifest.get("generation_calls") or 0) != 0:
        errors.append("preparation manifest records generation calls")
    if int(manifest.get("keyword_selection_calls") or 0) != 0:
        errors.append("preparation manifest records keyword-selection calls")
    if int(manifest.get("openai_embedding_input_count") or 0) != EXPECTED_CHUNK_COUNT:
        errors.append("prepared document embedding input count mismatch")
    if not corpus_fixture_path.is_file():
        errors.append(f"corpus fixture is missing: {_repo_relative(corpus_fixture_path)}")
    elif corpus_fixture_sha256 and _file_sha256(corpus_fixture_path) != corpus_fixture_sha256:
        errors.append("corpus fixture SHA-256 mismatch")
    if not query_input_path.is_file():
        errors.append(f"query input is missing: {_repo_relative(query_input_path)}")
    elif query_input_sha256 and _file_sha256(query_input_path) != query_input_sha256:
        errors.append("query input SHA-256 mismatch")
    if not chroma_dir.is_dir():
        errors.append(f"Chroma persistence directory is missing: {_repo_relative(chroma_dir)}")
    if not source_storage_dir.is_dir():
        errors.append(f"source-storage directory is missing: {_repo_relative(source_storage_dir)}")
    elif _source_file_count(source_storage_dir) != EXPECTED_SOURCE_PDF_COUNT:
        errors.append(
            f"source-storage file count mismatch: expected {EXPECTED_SOURCE_PDF_COUNT}, got {_source_file_count(source_storage_dir)}"
        )

    if errors:
        raise ValueError("Prepared corpus manifest validation failed: " + "; ".join(errors))

    return PreparedCorpus(
        manifest_path=path,
        manifest_sha256=_file_sha256(path),
        manifest=manifest,
        database_name=database_name,
        chroma_dir=chroma_dir,
        chroma_collection_name=collection_name,
        source_storage_dir=source_storage_dir,
        corpus_fixture_path=corpus_fixture_path,
        corpus_fixture_sha256=corpus_fixture_sha256,
        query_input_path=query_input_path,
        query_input_sha256=query_input_sha256,
        dataset_version=dataset_version,
        document_count=document_count,
        chunk_count=chunk_count,
        vector_count=vector_count,
        source_pdf_count=source_pdf_count,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=int(embedding_dimension_value),
        config_hash=config_hash,
        preparation_status=preparation_status,
        created_at_utc=created_at_utc,
    )


def validate_prepared_database_url(prepared: PreparedCorpus, database_url: str) -> str:
    database_name = _database_name_from_url(database_url)
    _validate_mysql_eval_database_name(database_name, label="prepared")
    if database_name != prepared.database_name:
        raise ValueError(
            f"Prepared database URL points to {database_name!r}, but manifest requires {prepared.database_name!r}"
        )
    return database_name


def inspect_prepared_corpus(
    *,
    prepared_manifest_path: str | Path,
    database_url: str | None = None,
    chroma_probe: bool = True,
) -> dict[str, Any]:
    prepared = load_prepared_corpus_manifest(prepared_manifest_path)
    database_counts: dict[str, int | None] = {}
    if database_url:
        validate_prepared_database_url(prepared, database_url)
        database_counts = _query_table_counts(database_url)
        if database_counts.get("documents") != prepared.document_count:
            raise ValueError("Prepared database document count differs from manifest")
        if database_counts.get("document_chunks") != prepared.chunk_count:
            raise ValueError("Prepared database chunk count differs from manifest")
    source_fingerprint = _directory_fingerprint(prepared.source_storage_dir)
    chroma_fingerprint_before = _directory_fingerprint(prepared.chroma_dir)

    ensure_backend_path()
    import chromadb

    probe_parent = Path(tempfile.mkdtemp(prefix="infobank-chroma-probe-"))
    probe_dir = probe_parent / "chroma"
    shutil.copytree(prepared.chroma_dir, probe_dir)
    client = chromadb.PersistentClient(path=str(probe_dir))
    try:
        try:
            collection = client.get_collection(name=prepared.chroma_collection_name)
        except Exception as exc:
            raise RuntimeError(
                f"Prepared Chroma collection {prepared.chroma_collection_name!r} is missing; "
                "preflight refuses to create collections."
            ) from exc
        vector_count = int(collection.count())
        if vector_count != prepared.vector_count:
            raise ValueError("Prepared Chroma vector count differs from manifest")
        probe = {"performed": False}
        if chroma_probe:
            results = collection.query(
                query_embeddings=[[0.0] * prepared.embedding_dimensions],
                n_results=1,
                include=["documents", "metadatas", "distances"],
            )
            probe = {
                "performed": True,
                "result_count": len(results.get("ids", [[]])[0]),
                "metadata_present": bool(results.get("metadatas", [[]])[0]),
                "embedding_dimensions": prepared.embedding_dimensions,
            }
    finally:
        del client
        gc.collect()
        shutil.rmtree(probe_parent, ignore_errors=True)
    chroma_fingerprint_after = _directory_fingerprint(prepared.chroma_dir)
    return {
        "status": "PASS",
        "network_called": False,
        "api_key_read": False,
        "execution_mode": EXECUTION_MODE_PREPARED_QUERY_ONLY,
        "prepared_corpus_mode_available": True,
        "document_embeddings_reused_without_provider_calls": True,
        "manifest": prepared.metadata(),
        "database_counts": database_counts,
        "chroma_collection_count": vector_count,
        "source_storage_fingerprint": source_fingerprint,
        "chroma_fingerprint_before": chroma_fingerprint_before,
        "chroma_fingerprint_after": chroma_fingerprint_after,
        "chroma_byte_stable_after_probe": chroma_fingerprint_before["sha256"] == chroma_fingerprint_after["sha256"],
        "local_chroma_probe": probe,
        "forbidden_operation_counters": {name: 0 for name in FORBIDDEN_COUNTERS},
    }


def clone_mysql_database(*, source_url: str, target_url: str, admin_database_url: str | None = None) -> dict[str, Any]:
    source_name = _database_name_from_url(source_url)
    target_name = _database_name_from_url(target_url)
    _validate_mysql_eval_database_name(source_name, label="source")
    _validate_mysql_eval_database_name(target_name, label="target")
    if source_name == target_name:
        raise ValueError("Refusing to clone prepared database onto itself")
    if source_name == "infobank_db" or target_name == "infobank_db":
        raise ValueError("Refusing to touch infobank_db")

    ensure_backend_path()
    from database import Base
    import models  # noqa: F401
    from scripts.run_actual_pipeline_evaluation import _prepare_mysql_database

    _prepare_mysql_database(target_url, admin_database_url)
    table_names = [table.name for table in Base.metadata.sorted_tables]
    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        with target_engine.begin() as connection:
            connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table_name in reversed(table_names):
                connection.execute(text(f"DELETE FROM {_quote_identifier(table_name)}"))
            for table_name in table_names:
                table = _quote_identifier(table_name)
                connection.execute(
                    text(
                        f"INSERT INTO {_quote_identifier(target_name)}.{table} "
                        f"SELECT * FROM {_quote_identifier(source_name)}.{table}"
                    )
                )
            connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    finally:
        target_engine.dispose()
    return {
        "source_database_name": source_name,
        "target_database_name": target_name,
        "copied_tables": table_names,
        "target_counts": _query_table_counts(target_url),
    }


def drop_mysql_database(*, database_url: str, admin_database_url: str | None = None, protected_names: Iterable[str] = ()) -> None:
    database_name = _database_name_from_url(database_url)
    _validate_mysql_eval_database_name(database_name, label="drop-target")
    if database_name in set(protected_names) or database_name == EXPECTED_DATABASE_NAME:
        raise ValueError(f"Refusing to drop protected prepared database {database_name}")
    import pymysql

    parsed = make_url(database_url)
    admin = make_url(admin_database_url) if admin_database_url else parsed
    connection = pymysql.connect(
        host=admin.host or parsed.host or "127.0.0.1",
        port=admin.port or parsed.port or 3306,
        user=admin.username or "",
        password=admin.password or "",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS {_quote_identifier(database_name)}")
    finally:
        connection.close()


def safe_rmtree(path: Path, *, allowed_root: Path, protected_paths: Iterable[Path] = ()) -> None:
    target = path.resolve()
    root = allowed_root.resolve()
    if target == root:
        raise ValueError("Refusing to remove the workspace root itself")
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Refusing to remove a path outside the disposable workspace root") from exc
    protected = {item.resolve() for item in protected_paths}
    if target in protected:
        raise ValueError("Refusing to remove a protected prepared-corpus path")
    for protected_path in protected:
        try:
            protected_path.relative_to(target)
        except ValueError:
            continue
        raise ValueError("Refusing to remove a directory containing a protected prepared-corpus path")
    if target.exists():
        shutil.rmtree(target)


def copy_prepared_workspace(prepared: PreparedCorpus, workspace: Path, *, workspace_root: Path) -> dict[str, Any]:
    safe_rmtree(workspace, allowed_root=workspace_root, protected_paths=(prepared.chroma_dir, prepared.source_storage_dir))
    workspace.mkdir(parents=True, exist_ok=True)
    chroma_target = workspace / "chroma"
    source_target = workspace / "source_storage"
    shutil.copytree(prepared.chroma_dir, chroma_target)
    shutil.copytree(prepared.source_storage_dir, source_target)
    return {
        "workspace": workspace,
        "chroma_dir": chroma_target,
        "source_storage_dir": source_target,
        "chroma_fingerprint": _directory_fingerprint(chroma_target),
        "source_storage_fingerprint": _directory_fingerprint(source_target),
    }


def cleanup_prepared_workspace(prepared: PreparedCorpus, workspace: Path, *, workspace_root: Path) -> dict[str, Any]:
    try:
        safe_rmtree(workspace, allowed_root=workspace_root, protected_paths=(prepared.chroma_dir, prepared.source_storage_dir))
        return {"status": "removed", "workspace": _repo_relative(workspace)}
    except Exception as exc:
        return {"status": "retained", "workspace": _repo_relative(workspace), "reason": f"{type(exc).__name__}: {exc}"}


def _case_ids_from_file(case_ids_file: str | Path | None) -> list[str] | None:
    if case_ids_file is None:
        return None
    values = [
        line.strip()
        for line in Path(case_ids_file).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if len(values) != len(set(values)):
        raise ValueError("case-ids-file contains duplicates")
    return values


def _selected_queries(query_input_path: Path, case_ids: Sequence[str] | None) -> list[Any]:
    queries = load_query_inputs(query_input_path)
    if case_ids is None:
        return queries
    by_id = {query.case_id: query for query in queries}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"Unknown selected case IDs: {', '.join(missing)}")
    return [by_id[case_id] for case_id in case_ids]


def write_gold_subset(*, gold_annotation_path: str | Path, selected_case_ids: Sequence[str], output_path: str | Path) -> Path:
    output = Path(output_path)
    rows = [json.loads(line) for line in Path(gold_annotation_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {str(row["case_id"]): row for row in rows}
    missing = [case_id for case_id in selected_case_ids if case_id not in by_id]
    if missing:
        raise ValueError(f"Gold annotations missing selected case IDs: {', '.join(missing)}")
    write_jsonl(output, [by_id[case_id] for case_id in selected_case_ids])
    return output


def make_readiness_selection_plan(
    *,
    query_input_path: str | Path,
    gold_annotation_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    query_path = _repo_path(query_input_path)
    gold_path = _repo_path(gold_annotation_path)
    queries = load_query_inputs(query_path)
    query_ids = {query.case_id for query in queries}
    annotations = [item for item in load_gold_annotations(gold_path) if item.case_id in query_ids]
    by_category: dict[str, list[Any]] = defaultdict(list)
    for annotation in annotations:
        by_category[annotation.expected_output_class].append(annotation)
    selected: list[dict[str, Any]] = []
    for category in REFERENCE_SELECTION_ORDER:
        candidates = sorted(by_category.get(category, []), key=lambda item: item.case_id)
        if category == "FULL_ANSWER":
            multi_source = [item for item in candidates if len(item.required_source_ids) > 1]
            chosen = multi_source[0] if multi_source else candidates[0]
            rule = "lexicographically first FULL_ANSWER requiring multiple sources when available"
        else:
            chosen = candidates[0]
            rule = f"lexicographically first {category}"
        selected.append(
            {
                "case_id": chosen.case_id,
                "reference_category": category,
                "required_source_count": len(chosen.required_source_ids),
                "selection_rule": rule,
            }
        )
    plan = {
        "schema_version": PREPARED_SELECTION_PLAN_SCHEMA_VERSION,
        "created_at_utc": utc_timestamp(),
        "selection_status": "FROZEN_BEFORE_PROVIDER_OUTPUTS",
        "selection_rule": (
            "one case per reference category; FULL_ANSWER prefers a multi-source case; "
            "all other categories use lexicographic first eligible case"
        ),
        "query_input_path": _repo_relative(query_path),
        "query_input_sha256": _file_sha256(query_path),
        "gold_annotation_path": _repo_relative(gold_path),
        "gold_annotation_sha256": _file_sha256(gold_path),
        "selected_cases": selected,
        "selected_case_ids": [item["case_id"] for item in selected],
    }
    plan["plan_sha256"] = hashlib.sha256(_canonical(plan).encode("utf-8")).hexdigest()
    if output_path is not None:
        output = _repo_path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return plan


def make_two_case_smoke_selection_plan(
    *,
    query_input_path: str | Path,
    gold_annotation_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    full_plan = make_readiness_selection_plan(query_input_path=query_input_path, gold_annotation_path=gold_annotation_path)
    case_ids = []
    selected_cases = []
    for item in full_plan["selected_cases"]:
        if item["reference_category"] in {"FULL_ANSWER", "AGGREGATE_RESULT"}:
            case_ids.append(item["case_id"])
            selected_cases.append(item)
    plan = {
        "schema_version": PREPARED_SELECTION_PLAN_SCHEMA_VERSION,
        "created_at_utc": utc_timestamp(),
        "selection_status": "FROZEN_BEFORE_PROVIDER_OUTPUTS",
        "selection_rule": "two-case C3 smoke: multi-source FULL_ANSWER plus governed AGGREGATE_RESULT",
        "query_input_path": full_plan["query_input_path"],
        "query_input_sha256": full_plan["query_input_sha256"],
        "gold_annotation_path": full_plan["gold_annotation_path"],
        "gold_annotation_sha256": full_plan["gold_annotation_sha256"],
        "selected_cases": selected_cases,
        "selected_case_ids": case_ids,
    }
    plan["plan_sha256"] = hashlib.sha256(_canonical(plan).encode("utf-8")).hexdigest()
    if output_path is not None:
        output = _repo_path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return plan


def write_case_id_file(case_ids: Sequence[str], output_path: str | Path) -> Path:
    output = _repo_path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(f"{case_id}\n" for case_id in case_ids), encoding="utf-8")
    return output


def _runtime_fixture_identities(fixtures: dict[str, Any], queries: Sequence[Any]) -> dict[str, tuple[str, ...]]:
    fixture_identity_sets: dict[str, set[str]] = {
        fixture_id: {f"eval-{fixture_id}"}
        for fixture_id in fixtures
    }
    for query in queries:
        fixture_identity_sets.setdefault(query.policy_fixture_ref, {f"eval-{query.policy_fixture_ref}"})
    return {
        fixture_id: tuple(sorted(identities))
        for fixture_id, identities in fixture_identity_sets.items()
    }


def _sum_operation_counters(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for record in records:
        totals.update({key: int(value) for key, value in (record.get("operation_counters") or {}).items()})
    return {key: totals.get(key, 0) for key in QueryOnlyOperationCounters().snapshot()}


def _provider_usage_totals(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    totals = Counter()
    request_ids: list[str] = []
    for record in records:
        usage = record.get("provider_usage") or {}
        totals["generation_input_tokens"] += int(usage.get("input_tokens") or 0)
        totals["generation_output_tokens"] += int(usage.get("output_tokens") or 0)
        totals["generation_total_tokens"] += int(usage.get("total_tokens") or 0)
        totals["generation_retries"] += int(usage.get("retries") or 0)
        if usage.get("provider_request_id"):
            request_ids.append(str(usage["provider_request_id"]))
        keyword_trace = (record.get("routing_trace") or {}).get("keyword_provider_trace") or {}
        totals["keyword_input_tokens"] += int(keyword_trace.get("input_tokens") or 0)
        totals["keyword_output_tokens"] += int(keyword_trace.get("output_tokens") or 0)
        if keyword_trace.get("provider_request_id"):
            request_ids.append(str(keyword_trace["provider_request_id"]))
    total_input = totals["generation_input_tokens"] + totals["keyword_input_tokens"]
    total_output = totals["generation_output_tokens"] + totals["keyword_output_tokens"]
    return {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "generation_input_tokens": totals["generation_input_tokens"],
        "generation_output_tokens": totals["generation_output_tokens"],
        "keyword_input_tokens": totals["keyword_input_tokens"],
        "keyword_output_tokens": totals["keyword_output_tokens"],
        "generation_retries": totals["generation_retries"],
        "provider_request_ids_recorded": len(request_ids),
        "unique_provider_request_ids_recorded": len(set(request_ids)),
    }


def _anthropic_cost(input_tokens: int, output_tokens: int) -> float:
    return round(input_tokens / 1_000_000 * 1.0 + output_tokens / 1_000_000 * 5.0, 8)


def _preflight_estimate(
    *,
    selected_query_count: int,
    planned_records: int,
    modes: Sequence[str],
    repetitions: int,
    output_tokens_per_generation: int,
    prepared: PreparedCorpus,
) -> dict[str, Any]:
    keyword_operations = selected_query_count * repetitions * sum(1 for mode in modes if mode in QUERY_ROUTING_MODES)
    generation_upper_bound = planned_records
    query_embedding_operations = planned_records
    estimated_input_tokens = planned_records * MAX_CONTEXT_TOKEN_BUDGET_PER_CASE + keyword_operations * 512
    estimated_output_tokens = generation_upper_bound * output_tokens_per_generation + keyword_operations * 32
    cost = _anthropic_cost(estimated_input_tokens, estimated_output_tokens)
    return {
        "selected_query_count": selected_query_count,
        "planned_records": planned_records,
        "modes": list(modes),
        "repetitions": repetitions,
        "expected_claude_keyword_selection_calls": keyword_operations,
        "expected_claude_generation_calls_upper_bound": generation_upper_bound,
        "expected_generation_skipped_records": "computed from actual run; aggregate/governance records may skip generation",
        "expected_openai_query_embedding_calls": query_embedding_operations,
        "expected_openai_document_embedding_calls": 0,
        "expected_total_provider_operations_upper_bound": keyword_operations + generation_upper_bound,
        "projected_anthropic_input_tokens": estimated_input_tokens,
        "projected_anthropic_output_tokens": estimated_output_tokens,
        "estimated_anthropic_cost_usd": cost,
        "estimated_anthropic_cost_with_25_percent_margin_usd": round(cost * 1.25, 8),
        "estimated_openai_query_embedding_cost_usd": "not priced locally; query embeddings are OpenAI text-embedding-3-small only",
        "estimated_duration": "UNKNOWN_WITHOUT_PILOT_LATENCY",
        "estimated_duration_with_25_percent_margin": "UNKNOWN_WITHOUT_PILOT_LATENCY",
        "rate_limit_risks": "low for pilot, moderate for full 630-record run because all calls are synchronous provider calls",
        "disk_space": {
            "prepared_chroma_bytes": _directory_fingerprint(prepared.chroma_dir)["total_bytes"],
            "prepared_source_storage_bytes": _directory_fingerprint(prepared.source_storage_dir)["total_bytes"],
            "disposable_workspace_count": len(modes) * repetitions,
        },
    }


def _effective_output_token_budget(max_provider_output_tokens: int) -> int:
    try:
        configured = int(os.getenv("ANTHROPIC_MAX_TOKENS", "512"))
    except ValueError as exc:
        raise RuntimeError("ANTHROPIC_MAX_TOKENS must be an integer") from exc
    if configured < 1:
        raise RuntimeError("ANTHROPIC_MAX_TOKENS must be positive")
    return min(int(max_provider_output_tokens), configured)


def query_only_dry_run_plan(
    *,
    prepared_manifest_path: str | Path,
    database_url: str | None,
    case_ids_file: str | Path | None,
    modes: Sequence[str],
    repetitions: int,
    output_dir: str | Path | None,
    cache_dir: str | Path | None,
    max_provider_output_tokens: int,
    max_anthropic_estimated_cost: float,
    chroma_probe: bool = True,
) -> dict[str, Any]:
    preflight = inspect_prepared_corpus(
        prepared_manifest_path=prepared_manifest_path,
        database_url=database_url,
        chroma_probe=chroma_probe,
    )
    prepared = load_prepared_corpus_manifest(prepared_manifest_path)
    case_ids = _case_ids_from_file(case_ids_file)
    selected_query_count = len(_selected_queries(prepared.query_input_path, case_ids))
    resolved_modes = [EvaluationMode(mode).value for mode in modes]
    planned_records = selected_query_count * len(resolved_modes) * repetitions
    estimate = _preflight_estimate(
        selected_query_count=selected_query_count,
        planned_records=planned_records,
        modes=resolved_modes,
        repetitions=repetitions,
        output_tokens_per_generation=_effective_output_token_budget(max_provider_output_tokens),
        prepared=prepared,
    )
    return {
        "status": READINESS_STATUS,
        "preflight_only": True,
        "network_called": False,
        "api_key_read": False,
        "execution_mode": EXECUTION_MODE_PREPARED_QUERY_ONLY,
        "prepared_corpus_mode_available": True,
        "document_embeddings_reused_without_provider_calls": True,
        "prepared_preflight": preflight,
        "plan": estimate,
        "anthropic_cost_cap_usd": max_anthropic_estimated_cost,
        "anthropic_cost_cap_status": (
            "WITHIN_CAP"
            if estimate["estimated_anthropic_cost_with_25_percent_margin_usd"] <= max_anthropic_estimated_cost
            else "EXCEEDS_CAP"
        ),
        "output_dir": None if output_dir is None else _repo_relative(output_dir),
        "cache_dir": None if cache_dir is None else _repo_relative(cache_dir),
        "confirmation_guard": "real query-only execution requires --confirm-readiness-pilot; full run additionally requires --confirm-full-experiment",
        "requires_confirm_full_experiment": planned_records >= 630,
    }


def _assert_provider_guards(
    *,
    provider_name: str,
    allow_network_provider: bool,
    planned_provider_operations: int,
    max_provider_request_attempts: int,
    max_provider_output_tokens: int,
    max_provider_retries: int,
    max_anthropic_estimated_cost: float,
    estimated_cost: float,
) -> None:
    if provider_name == "anthropic":
        if not allow_network_provider:
            raise RuntimeError("anthropic query-only execution requires explicit --allow-network-provider")
        if max_provider_output_tokens > 1024:
            raise RuntimeError("--max-provider-output-tokens must be 1024 or lower")
        if max_provider_retries > 1:
            raise RuntimeError("--max-provider-retries must be 1 or lower")
        configured_max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "512"))
        configured_retries = int(os.getenv("ANTHROPIC_MAX_RETRIES", "1"))
        if configured_max_tokens > max_provider_output_tokens:
            raise RuntimeError(
                f"ANTHROPIC_MAX_TOKENS={configured_max_tokens} exceeds --max-provider-output-tokens {max_provider_output_tokens}"
            )
        if configured_retries > max_provider_retries:
            raise RuntimeError(
                f"ANTHROPIC_MAX_RETRIES={configured_retries} exceeds --max-provider-retries {max_provider_retries}"
            )
        if planned_provider_operations > max_provider_request_attempts:
            raise RuntimeError(
                f"Provider operations upper bound {planned_provider_operations} exceeds --max-provider-request-attempts "
                f"{max_provider_request_attempts}"
            )
        if estimated_cost > max_anthropic_estimated_cost:
            raise RuntimeError(
                f"Projected preliminary Anthropic cost {estimated_cost} exceeds --max-anthropic-estimated-cost "
                f"{max_anthropic_estimated_cost}"
            )


def _short_mode(mode: str) -> str:
    return {
        "C0_VECTOR_ONLY": "c0",
        "C1_VECTOR_ROUTING": "c1",
        "P1_PROMPT_ONLY_GOVERNANCE": "p1",
        "C2_PERMISSION_FILTERED": "c2",
        "C3_FULL_ROLE_AWARE": "c3",
    }[mode]


def _run_database_name(run_id: str, mode: str, repetition: int) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", run_id.lower())[:22].strip("_") or "run"
    suffix = hashlib.sha256(f"{run_id}:{mode}:{repetition}".encode("utf-8")).hexdigest()[:8]
    return f"infobank_eval_qo_{slug}_{_short_mode(mode)}_r{repetition}_{suffix}"[:64]


def _verify_payload_boundaries(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    safety_totals: Counter[str] = Counter()
    governed_modes = {EvaluationMode.C2_PERMISSION_FILTERED.value, EvaluationMode.C3_FULL_ROLE_AWARE.value}
    guarded_keys = {
        "prohibited_text_fragment_exposure",
        "aggregate_individual_value_exposure",
        "generator_visible_restricted_text",
        "archived_source_usage",
        "wrong_permission_citation",
        "local_path_exposure",
    }
    for record in records:
        safety = scan_record_safety(record)
        safety_totals.update(safety)
        if record.get("mode") in governed_modes:
            for key in guarded_keys:
                if safety.get(key):
                    failures.append({"case_id": str(record.get("case_id")), "mode": str(record.get("mode")), "failure": key})
            if record.get("actual_output_class") == "AGGREGATE_RESULT":
                counters = record.get("operation_counters") or {}
                if not record.get("generation_skipped") or counters.get("generation_calls", 0) != 0:
                    failures.append(
                        {
                            "case_id": str(record.get("case_id")),
                            "mode": str(record.get("mode")),
                            "failure": "governed_aggregate_invoked_claude_generation",
                        }
                    )
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "safety_totals": dict(sorted(safety_totals.items())),
        "c2_c3_assertions": "no restricted raw text, aggregate contributor values, archived source use, local paths, or wrong-permission citations",
        "local_aggregate_assertion": "governed aggregate records must have generation_skipped=true and generation_calls=0",
        "p1_expected_behavior": "P1 may send policy-labeled restricted source content by design",
    }


def run_prepared_query_only(
    *,
    prepared_manifest_path: str | Path,
    output_dir: str | Path,
    database_url: str,
    admin_database_url: str | None,
    provider_name: str,
    generation_model: str,
    embedding_provider_name: str,
    embedding_model: str,
    modes: Sequence[str],
    repetitions: int,
    case_ids_file: str | Path | None = None,
    gold_annotation_path: str | Path | None = None,
    allow_network_provider: bool = False,
    cache_dir: str | Path | None = None,
    pricing_config_path: str | Path | None = None,
    confirm_readiness_pilot: bool = False,
    confirm_full_experiment: bool = False,
    keep_workspaces: bool = False,
    max_provider_request_attempts: int = 70,
    max_provider_output_tokens: int = 1024,
    max_provider_retries: int = 1,
    max_anthropic_estimated_cost: float = 2.0,
    run_id: str | None = None,
) -> dict[str, Any]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least one")
    if not confirm_readiness_pilot:
        raise RuntimeError("query-only execution requires --confirm-readiness-pilot")
    prepared = load_prepared_corpus_manifest(prepared_manifest_path)
    validate_prepared_database_url(prepared, database_url)
    if generation_model != "claude-haiku-4-5-20251001" and provider_name == "anthropic":
        raise ValueError("Anthropic readiness pilot must use claude-haiku-4-5-20251001")
    if embedding_provider_name != prepared.embedding_provider or embedding_model != prepared.embedding_model:
        raise ValueError("Query-only mode must use the prepared OpenAI embedding provider/model")
    if embedding_dimensions(embedding_provider_name, embedding_model) != prepared.embedding_dimensions:
        raise ValueError("Configured query embedding dimensions do not match the prepared Chroma collection")

    resolved_modes = [EvaluationMode(mode).value for mode in modes]
    case_ids = _case_ids_from_file(case_ids_file)
    queries = _selected_queries(prepared.query_input_path, case_ids)
    planned_records = len(queries) * len(resolved_modes) * repetitions
    if planned_records >= 630 and not confirm_full_experiment:
        raise RuntimeError("The full query-only experiment requires --confirm-full-experiment")

    estimate = _preflight_estimate(
        selected_query_count=len(queries),
        planned_records=planned_records,
        modes=resolved_modes,
        repetitions=repetitions,
        output_tokens_per_generation=_effective_output_token_budget(max_provider_output_tokens),
        prepared=prepared,
    )
    _assert_provider_guards(
        provider_name=provider_name,
        allow_network_provider=allow_network_provider,
        planned_provider_operations=int(estimate["expected_total_provider_operations_upper_bound"]),
        max_provider_request_attempts=max_provider_request_attempts,
        max_provider_output_tokens=max_provider_output_tokens,
        max_provider_retries=max_provider_retries,
        max_anthropic_estimated_cost=max_anthropic_estimated_cost,
        estimated_cost=float(estimate["estimated_anthropic_cost_usd"]),
    )

    destination = _repo_path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing to overwrite query-only output: {destination}")
    raw_dir = destination / "raw"
    runtime_root = destination / "rt"
    raw_dir.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    cache_path = _repo_path(cache_dir) if cache_dir is not None else None
    if cache_path is not None:
        cache_path.mkdir(parents=True, exist_ok=True)
    current_run_id = run_id or f"prepared-query-only-{provider_name}-{int(time.time())}"
    documents, fixtures, corpus_metadata = load_corpus_fixture(prepared.corpus_fixture_path)
    fixture_identities = _runtime_fixture_identities(fixtures, queries)
    config = ActualPipelineConfig(
        generation_model=generation_model,
        embedding_model=embedding_model,
    )
    readiness = ReadinessConfig(
        provider=provider_name,
        embedding_provider=embedding_provider_name,
        generation_model=generation_model,
        embedding_model=embedding_model,
    )

    base_before = inspect_prepared_corpus(
        prepared_manifest_path=prepared.manifest_path,
        database_url=database_url,
        chroma_probe=True,
    )
    records: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []
    disposable_groups: list[dict[str, Any]] = []
    cleanup_rows: list[dict[str, Any]] = []
    created_databases: list[str] = []

    try:
        for repetition in range(1, repetitions + 1):
            for mode in resolved_modes:
                group_id = f"{_short_mode(mode)}-r{repetition}"
                disposable_name = _run_database_name(current_run_id, mode, repetition)
                disposable_url = _database_url_with_name(database_url, disposable_name)
                workspace = runtime_root / f"{_short_mode(mode)}r{repetition}"
                clone_result = clone_mysql_database(
                    source_url=database_url,
                    target_url=disposable_url,
                    admin_database_url=admin_database_url,
                )
                created_databases.append(disposable_name)
                target_counts = clone_result["target_counts"]
                if (
                    target_counts.get("documents") != prepared.document_count
                    or target_counts.get("document_chunks") != prepared.chunk_count
                    or target_counts.get("user_document_permission") != prepared.manifest["database"]["table_counts"]["user_document_permission"]
                ):
                    raise RuntimeError(
                        "Disposable database clone count mismatch; refusing provider execution against an incomplete query state"
                    )
                workspace_result = copy_prepared_workspace(prepared, workspace, workspace_root=runtime_root)
                counters = QueryOnlyOperationCounters()
                runtime = PipelineRuntime(
                    documents=documents,
                    fixtures=fixtures,
                    database_url=disposable_url,
                    chroma_dir=workspace_result["chroma_dir"],
                    source_storage_dir=workspace_result["source_storage_dir"],
                    config=config,
                    corpus_base_dir=prepared.corpus_fixture_path.parent,
                    dataset_version=str(corpus_metadata["dataset_version"]),
                    fixture_identities=fixture_identities,
                    provider_name=provider_name,
                    embedding_provider_name=embedding_provider_name,
                    allow_network_provider=allow_network_provider,
                    cache_dir=cache_path,
                    pricing_config_path=Path(pricing_config_path) if pricing_config_path is not None else None,
                    seed_corpus=False,
                    prepared_collection_name=prepared.chroma_collection_name,
                    operation_counters=counters,
                    prepared_metadata=prepared.metadata(
                        disposable_database_name=disposable_name,
                        disposable_workspace_path=workspace,
                        cache_namespace_version=readiness.config_hash,
                    ),
                )
                try:
                    for query in queries:
                        record, timings = runtime.run_case(query, mode)
                        record["run_id"] = current_run_id
                        record["repetition_index"] = repetition
                        record["configuration_group_id"] = group_id
                        record["stage_timings_ms"] = timings
                        records.append(record)
                        timing_rows.append(
                            {
                                "run_id": current_run_id,
                                "case_id": query.case_id,
                                "mode": mode,
                                "repetition_index": repetition,
                                "configuration_group_id": group_id,
                                "stage_timings_ms": timings,
                            }
                        )
                finally:
                    del runtime
                    gc.collect()
                disposable_groups.append(
                    {
                        "configuration_group_id": group_id,
                        "mode": mode,
                        "repetition_index": repetition,
                        "database_clone": clone_result,
                        "workspace": {
                            "path": _repo_relative(workspace),
                            "chroma_dir": _repo_relative(workspace_result["chroma_dir"]),
                            "source_storage_dir": _repo_relative(workspace_result["source_storage_dir"]),
                            "chroma_fingerprint": workspace_result["chroma_fingerprint"],
                            "source_storage_fingerprint": workspace_result["source_storage_fingerprint"],
                        },
                        "operation_counters": counters.snapshot(),
                    }
                )
                if keep_workspaces:
                    cleanup_rows.append({"status": "kept_by_request", "workspace": _repo_relative(workspace), "database": disposable_name})
                else:
                    cleanup_rows.append(cleanup_prepared_workspace(prepared, workspace, workspace_root=runtime_root) | {"database": disposable_name})
                    drop_mysql_database(
                        database_url=disposable_url,
                        admin_database_url=admin_database_url,
                        protected_names={prepared.database_name},
                    )
                    created_databases.remove(disposable_name)
    finally:
        if not keep_workspaces:
            for database_name in list(created_databases):
                try:
                    drop_mysql_database(
                        database_url=_database_url_with_name(database_url, database_name),
                        admin_database_url=admin_database_url,
                        protected_names={prepared.database_name},
                    )
                except Exception:
                    pass

    raw_path = raw_dir / "raw_records.jsonl"
    raw_path.write_text("".join(_canonical(record) + "\n" for record in records), encoding="utf-8")
    timing_path = raw_dir / "wall_clock_timings.jsonl"
    timing_path.write_text("".join(_canonical(item) + "\n" for item in timing_rows), encoding="utf-8")
    deterministic_path = raw_dir / "deterministic_content.jsonl"
    deterministic_path.write_text(
        "".join(
            _canonical({key: value for key, value in record.items() if key not in {"run_id", "stage_timings_ms"}}) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    operation_totals = _sum_operation_counters(records)
    forbidden_zero = all(operation_totals.get(name, 0) == 0 for name in FORBIDDEN_COUNTERS)
    provider_usage = _provider_usage_totals(records)
    payload_boundary = _verify_payload_boundaries(records)
    base_after = inspect_prepared_corpus(
        prepared_manifest_path=prepared.manifest_path,
        database_url=database_url,
        chroma_probe=False,
    )
    base_stable = (
        base_before["database_counts"] == base_after["database_counts"]
        and base_before["source_storage_fingerprint"]["sha256"] == base_after["source_storage_fingerprint"]["sha256"]
        and base_before["chroma_collection_count"] == base_after["chroma_collection_count"]
    )
    seal = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "prepared_query_only_schema_version": PREPARED_QUERY_ONLY_RUN_SCHEMA_VERSION,
        "run_id": current_run_id,
        "timestamp": utc_timestamp(),
        "raw_run_sha256": _sha256_file(raw_path),
        "deterministic_content_sha256": _sha256_file(deterministic_path),
        "timing_sidecar_sha256": _sha256_file(timing_path),
        "config_hash": config.config_hash,
        "config_version": config.config_version,
        "query_input_sha256": _sha256_file(prepared.query_input_path),
        "corpus_sha256": _sha256_file(prepared.corpus_fixture_path),
        "commit_sha": _git_head(),
        "provider": provider_name,
        "model": generation_model,
        "llm_provider": provider_name,
        "llm_model": generation_model,
        "embedding_provider": embedding_provider_name,
        "embedding_model": embedding_model,
        "execution_mode": EXECUTION_MODE_PREPARED_QUERY_ONLY,
        "runner_version": RUNNER_VERSION,
        "dataset_version": corpus_metadata["dataset_version"],
        "record_count": len(records),
        "modes": resolved_modes,
        "repetitions": repetitions,
        "selected_case_ids": [query.case_id for query in queries],
        "prepared_corpus": prepared.metadata(cache_namespace_version=readiness.config_hash),
        "disposable_groups": disposable_groups,
        "operation_counters": operation_totals,
        "forbidden_operation_counters_zero": forbidden_zero,
        "payload_boundary_verification": payload_boundary,
        "provider_usage_totals": provider_usage,
        "estimated_anthropic_cost_from_recorded_tokens_usd": _anthropic_cost(provider_usage["input_tokens"], provider_usage["output_tokens"]),
        "base_integrity_before": base_before,
        "base_integrity_after": base_after,
        "prepared_base_stable": base_stable,
        "cleanup": cleanup_rows,
        "wall_clock_separated_from_deterministic_hash": True,
        "generation_temperature": GENERATION_TEMPERATURE,
        "generation_prompt_version": GENERATION_PROMPT_VERSION,
        "routing_prompt_version": ROUTING_PROMPT_VERSION,
        "prompt_only_governance_prompt_version": PROMPT_ONLY_GOVERNANCE_PROMPT_VERSION,
        "prompt_only_governance_prompt_sha256": _sha256_bytes(prompt_only_governance_prompt().encode("utf-8")),
        "network_provider_explicitly_allowed": bool(allow_network_provider),
        "output_cache_enabled": cache_path is not None,
        "cache_namespace_version": readiness.config_hash,
        "provisional_score_label": PROVISIONAL_SCORE_LABEL,
        "scoring_started": False,
    }
    seal_path = raw_dir / "run_seal.json"
    seal_path.write_text(json.dumps(seal, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    scores = None
    if gold_annotation_path is not None:
        subset_gold = destination / "reference" / "selected_gold_annotations.jsonl"
        write_gold_subset(
            gold_annotation_path=gold_annotation_path,
            selected_case_ids=[query.case_id for query in queries],
            output_path=subset_gold,
        )
        scores = score_sealed_run(
            raw_run_path=raw_path,
            seal_path=seal_path,
            gold_annotation_path=subset_gold,
            output_dir=destination / "scores",
        )
        scores["score_label"] = PROVISIONAL_SCORE_LABEL
        (destination / "scores" / "summary.json").write_text(json.dumps(scores, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    technical_failures = []
    if any(record.get("actual_output_class") == "ERROR" or record.get("error") for record in records):
        technical_failures.append("record_runtime_error")
    if not forbidden_zero:
        technical_failures.append("forbidden_reprocessing_counter_nonzero")
    if payload_boundary["status"] != "PASS":
        technical_failures.append("payload_boundary_failure")
    if not base_stable:
        technical_failures.append("prepared_base_integrity_failure")
    total_attempts = int(estimate["expected_claude_keyword_selection_calls"]) + int(operation_totals.get("generation_calls", 0)) + int(provider_usage.get("generation_retries", 0))
    if total_attempts > max_provider_request_attempts:
        technical_failures.append("provider_attempt_limit_exceeded")
    return {
        "status": "PASS" if not technical_failures else "FAIL",
        "readiness_status": READINESS_STATUS,
        "technical_failures": technical_failures,
        "seal": seal,
        "scores": scores,
        "provider_request_attempts_estimated_from_records": total_attempts,
        "raw_records_path": _repo_relative(raw_path),
        "seal_path": _repo_relative(seal_path),
        "score_label": PROVISIONAL_SCORE_LABEL,
    }
