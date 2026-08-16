from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from importlib import metadata as package_metadata
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from .backend import BACKEND_DIR, REPO_ROOT, ensure_backend_path
from .clean_state import CleanStateError, check_clean_state
from .fixture_schema import EvaluationFixture, FixtureCase, load_fixture
from .generate_fixture_documents import generate_documents
from .load_fixtures import (
    MockEmbeddingProvider,
    build_id_mappings,
    load_fixture_data,
    policy_context_for_case,
    selected_document_aliases,
)
from .manifest import git_info, package_versions
from .modes import OpenAIGenerator
from .retrieval import build_query_profile, run_shared_retrieval
from .run_case import run_case
from .run_suite import MockGenerator, mock_role_aware_services
from .schemas import (
    GenerationConfig,
    MODE_GOVERNANCE,
    MODE_ROLE_AWARE,
    MODE_STANDARD,
    SharedRetrievalResult,
)
from .usage_logging import empty_usage, merge_usage, usage_from_openai_response
from .validate_fixtures import validate_fixture


APPROVED_PILOT_CASE_IDS = [
    "FULL_01",
    "METADATA_01",
    "DENY_01",
    "AGG_SAFE_01",
    "AGG_INDIVIDUAL_01",
    "MIXED_PRIMARY_01",
    "CONTEXT_ONLY_01",
]
PILOT_MODES = [MODE_STANDARD, MODE_GOVERNANCE, MODE_ROLE_AWARE]
DEFAULT_FIXTURE_PATH = REPO_ROOT / "evaluation" / "fixtures" / "document_rag_v1.yaml"
DEFAULT_RESULTS_DIR = REPO_ROOT / "evaluation" / "results"
DEFAULT_ENV_FILE = BACKEND_DIR / ".env.eval"
EXPECTED_CHROMA_DIR = BACKEND_DIR / "chroma_eval"
GENERATOR_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
TEMPERATURE = 0.0
ZERO_TABLES = [
    "users",
    "documents",
    "document_chunks",
    "document_keywords",
    "user_document_permission",
    "evidence_units",
    "policy_rules",
    "connector_accounts",
    "audit_logs",
    "keywords",
]


@dataclass
class PilotConfig:
    real_api: bool = False
    mock_generation: bool = False
    check_only: bool = False
    results_dir: Path = DEFAULT_RESULTS_DIR
    fixture_path: Path = DEFAULT_FIXTURE_PATH
    env_file: Path = DEFAULT_ENV_FILE
    top_k: int = 4
    repetitions: int = 1
    case_ids: list[str] | None = None
    mock_fail_stage: str | None = None

    @property
    def selected_case_ids(self) -> list[str]:
        return list(self.case_ids or APPROVED_PILOT_CASE_IDS)


class PilotError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        classification: str,
        current_case: str | None = None,
        current_mode: str | None = None,
        exit_code: int = 2,
        original_error: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.classification = classification
        self.current_case = current_case
        self.current_mode = current_mode
        self.exit_code = exit_code
        self.original_error = original_error


class UsageEmbeddingProvider:
    def __init__(self, model: str = EMBEDDING_MODEL) -> None:
        ensure_backend_path()
        import ai_service

        self._client = ai_service.openai_client
        self.model = model
        self.calls = 0
        self.usage = empty_usage()

    def embed(self, text_value: str) -> list[float]:
        response = self._client.embeddings.create(input=text_value, model=self.model)
        self.calls += 1
        self.usage = merge_usage(self.usage, usage_from_openai_response(response, embedding_calls=1))
        return response.data[0].embedding


class CountingEmbeddingClient:
    def __init__(self, real_api: bool, model: str = EMBEDDING_MODEL, fail: bool = False) -> None:
        self.model = model
        self.real_api = real_api
        self.fail = fail
        self.calls = 0
        self.usage = empty_usage()
        self.embeddings = self
        if real_api:
            ensure_backend_path()
            import ai_service

            self._client = ai_service.openai_client
        else:
            self._client = None

    def create(self, **kwargs: Any) -> Any:
        if self.fail:
            raise RuntimeError("mock query embedding failure")
        self.calls += 1
        if self.real_api:
            response = self._client.embeddings.create(**kwargs)
            self.usage = merge_usage(self.usage, usage_from_openai_response(response, embedding_calls=1))
            return response
        response = FakeEmbeddingResponse(str(kwargs.get("input", "")))
        self.usage = merge_usage(self.usage, usage_from_openai_response(response, embedding_calls=1))
        return response


class FailingMockEmbeddingProvider(MockEmbeddingProvider):
    def embed(self, text_value: str) -> list[float]:
        raise RuntimeError("mock fixture-index embedding failure")


class FakeEmbeddingResponse:
    def __init__(self, text_value: str) -> None:
        digest = hashlib.sha256(text_value.encode("utf-8")).digest()
        self.data = [type("EmbeddingData", (), {"embedding": [round(byte / 255.0, 6) for byte in digest[:16]]})()]
        self.usage = type("Usage", (), {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1})()


class CountingCollection:
    def __init__(self, collection: Any) -> None:
        self.collection = collection
        self.query_calls = 0

    def query(self, **kwargs: Any) -> Any:
        self.query_calls += 1
        return self.collection.query(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.collection, name)


class FakeCollection:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def add(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str],
    ) -> None:
        for item_id, embedding, metadata, document in zip(ids, embeddings, metadatas, documents):
            self._records.append(
                {
                    "id": item_id,
                    "embedding": embedding,
                    "metadata": metadata,
                    "document": document,
                }
            )

    def count(self) -> int:
        return len(self._records)

    def query(self, **kwargs: Any) -> dict[str, Any]:
        where = kwargs.get("where") or {}
        n_results = int(kwargs.get("n_results") or 4)
        filtered = [record for record in self._records if _matches_where(record["metadata"], where)]
        selected = filtered[:n_results]
        return {
            "ids": [[record["id"] for record in selected]],
            "documents": [[record["document"] for record in selected]],
            "metadatas": [[record["metadata"] for record in selected]],
            "distances": [[round(index / 10.0, 4) for index, _ in enumerate(selected)]],
        }


def _matches_where(metadata: dict[str, Any], where: dict[str, Any]) -> bool:
    if not where:
        return True
    expected = where.get("document_id")
    actual = metadata.get("document_id")
    if isinstance(expected, dict):
        return actual in set(expected.get("$in") or [])
    return actual == expected


def parse_case_ids(value: str | None) -> list[str]:
    if not value:
        return list(APPROVED_PILOT_CASE_IDS)
    return [part.strip() for part in value.split(",") if part.strip()]


def expected_result_count(case_ids: Iterable[str], repetitions: int) -> int:
    return len(list(case_ids)) * len(PILOT_MODES) * repetitions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the seven-case InfoBank document-RAG pilot.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--real-api", action="store_true", help="Use real OpenAI embeddings and generation.")
    mode.add_argument("--mock-generation", action="store_true", help="Use mock embeddings, collection, DB, and generation.")
    mode.add_argument("--check-only", action="store_true", help="Run preflight checks only; do not load fixtures or call OpenAI.")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE_PATH))
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--case-ids", default=",".join(APPROVED_PILOT_CASE_IDS))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--mock-fail-stage", choices=["indexing", "query"], default=None, help=argparse.SUPPRESS)
    return parser


def config_from_args(args: argparse.Namespace) -> PilotConfig:
    return PilotConfig(
        real_api=args.real_api,
        mock_generation=args.mock_generation,
        check_only=args.check_only,
        results_dir=resolve_path(args.results_dir, REPO_ROOT),
        fixture_path=resolve_path(args.fixture, REPO_ROOT),
        env_file=resolve_path(args.env_file, REPO_ROOT),
        top_k=args.top_k,
        repetitions=args.repetitions,
        case_ids=parse_case_ids(args.case_ids),
        mock_fail_stage=args.mock_fail_stage,
    )


def resolve_path(value: str | Path, base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (base / path).resolve()


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise PilotError(
            f"Environment file not found: {path}",
            stage="environment",
            classification="environment/configuration",
        )
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def configure_real_environment(env_file: Path) -> dict[str, Any]:
    values = read_env_file(env_file)
    database_url = values.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    chroma_value = values.get("CHROMA_PERSIST_DIR") or os.environ.get("CHROMA_PERSIST_DIR")
    if not database_url:
        raise PilotError(
            "PILOT BLOCKED: DATABASE_URL NOT CONFIGURED",
            stage="environment",
            classification="environment/configuration",
        )
    if not chroma_value:
        raise PilotError(
            "PILOT BLOCKED: CHROMA_PERSIST_DIR NOT CONFIGURED",
            stage="environment",
            classification="environment/configuration",
        )
    chroma_path = resolve_chroma_path(chroma_value, env_file, REPO_ROOT)
    validate_runtime_targets(database_url=database_url, chroma_path=chroma_path)
    os.environ["DATABASE_URL"] = database_url
    os.environ["CHROMA_PERSIST_DIR"] = str(chroma_path)
    return {
        "database_name": database_name_from_url(database_url),
        "chroma_persist_dir": str(chroma_path),
        "env_file": str(env_file),
    }


def resolve_chroma_path(value: str, env_file: Path, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    if path.parts and path.parts[0] == "backend_python":
        return (repo_root / path).resolve()
    base = env_file.resolve().parent
    if base == BACKEND_DIR.resolve():
        return (base / path).resolve()
    return (repo_root / path).resolve()


def database_name_from_url(database_url: str) -> str | None:
    return make_url(database_url).database


def validate_runtime_targets(*, database_url: str, chroma_path: Path) -> None:
    database_name = database_name_from_url(database_url)
    if database_name != "infobank_eval":
        raise PilotError(
            f"DATABASE_URL must point to infobank_eval, not {database_name!r}.",
            stage="environment",
            classification="environment/configuration",
        )
    expected_chroma = EXPECTED_CHROMA_DIR.resolve()
    if chroma_path.resolve() != expected_chroma:
        raise PilotError(
            f"CHROMA_PERSIST_DIR must resolve to {expected_chroma}, not {chroma_path.resolve()}.",
            stage="environment",
            classification="environment/configuration",
        )
    if "chroma_data" in chroma_path.parts:
        raise PilotError(
            "PILOT BLOCKED: development Chroma path selected.",
            stage="environment",
            classification="environment/configuration",
        )


def require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise PilotError(
            "PILOT BLOCKED: OPENAI_API_KEY NOT CONFIGURED",
            stage="environment",
            classification="environment/configuration",
        )


def run_preflight(config: PilotConfig, *, require_key: bool) -> dict[str, Any]:
    runtime = configure_real_environment(config.env_file)
    if require_key:
        require_openai_key()
    git = git_info()
    if sys.version_info[:2] != (3, 12):
        raise PilotError(
            f"Python 3.12 is required, found {platform.python_version()}.",
            stage="preflight",
            classification="environment/configuration",
        )
    pip_check = run_subprocess([sys.executable, "-m", "pip", "check"])
    if pip_check["returncode"] != 0:
        raise PilotError(
            "pip check failed.",
            stage="preflight",
            classification="environment/configuration",
        )
    bcrypt_version = package_metadata.version("bcrypt")
    if bcrypt_version != "4.1.3":
        raise PilotError(
            f"bcrypt==4.1.3 is required, found {bcrypt_version}.",
            stage="preflight",
            classification="environment/configuration",
        )
    if not is_tcp_reachable("127.0.0.1", 3307):
        raise PilotError(
            "MariaDB is not reachable at 127.0.0.1:3307.",
            stage="preflight",
            classification="environment/configuration",
        )
    try:
        clean_report = check_clean_state()
    except CleanStateError as exc:
        raise PilotError(
            "PILOT BLOCKED: EVALUATION STATE NOT CLEAN",
            stage="preflight",
            classification="environment/configuration",
            original_error=exc,
        ) from exc
    validate_fixture(load_fixture(config.fixture_path))
    return {
        "git": git,
        "tracked_status": tracked_status(),
        "python_version": platform.python_version(),
        "pip_check": "PASS",
        "bcrypt": bcrypt_version,
        "database_name": runtime["database_name"],
        "chroma_persist_dir": runtime["chroma_persist_dir"],
        "openai_key_visible": bool(os.environ.get("OPENAI_API_KEY")),
        "clean_state": clean_report.to_dict(),
    }


def run_subprocess(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def is_tcp_reachable(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(2.0)
        return sock.connect_ex((host, port)) == 0


def tracked_status() -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO_ROOT.as_posix()}", "-C", str(REPO_ROOT), "status", "--short", "--untracked-files=no"],
        text=True,
    ).strip()


def run_document_rag_pilot(config: PilotConfig) -> dict[str, Any]:
    if config.check_only:
        return {"check_only": run_preflight(config, require_key=False)}
    run_id = "pilot_" + dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = unique_run_dir(config.results_dir, run_id)
    try:
        summary = _run_document_rag_pilot(config, run_id=run_dir.name, run_dir=run_dir)
        print(
            "PILOT RUN: PASS "
            f"run_id={summary['run_id']} records={summary['result_record_count']} "
            f"results_dir={summary['run_dir']}"
        )
        return summary
    except PilotError as exc:
        write_failure_artifact(run_dir, exc)
        print(f"PILOT FAILED: {exc}")
        raise
    except Exception as exc:
        pilot_error = PilotError(
            str(exc),
            stage="unexpected",
            classification=classify_exception(exc),
            original_error=exc,
        )
        write_failure_artifact(run_dir, pilot_error)
        print(f"PILOT FAILED: {pilot_error}")
        raise pilot_error from exc


def _run_document_rag_pilot(config: PilotConfig, *, run_id: str, run_dir: Path) -> dict[str, Any]:
    if config.real_api:
        preflight = run_preflight(config, require_key=True)
        collection, db_session, cleanup, fixture_embedding_provider, query_embedding_client, generator, real_services = open_real_runtime(config)
    else:
        preflight = {"mocked_test_mode": True, "git": git_info(), "tracked_status": tracked_status()}
        collection, db_session, cleanup, fixture_embedding_provider, query_embedding_client, generator, real_services = open_mock_runtime(config)
    try:
        fixture = load_fixture(config.fixture_path)
        validate_fixture(fixture)
        selected_cases = select_cases(fixture, config.selected_case_ids)
        selected_aliases = sorted(selected_document_aliases(fixture, config.selected_case_ids))
        subset_fixture = fixture.copy(
            deep=True,
            update={
                "documents": [document for document in fixture.documents if document.alias in selected_aliases],
                "cases": selected_cases,
                "case_count": len(selected_cases),
            },
        )
        pdf_manifest = generate_documents(subset_fixture, run_dir / "generated_pdfs")
        load_manifest = load_fixture_data(
            fixture=fixture,
            db=db_session,
            collection=collection,
            embedding_provider=fixture_embedding_provider,
            clean_checker=check_clean_state if config.real_api else None,
            case_ids=config.selected_case_ids,
        )
        db_counts = read_runtime_counts(db_session)
        fixture_subset_manifest = build_fixture_subset_manifest(
            fixture=fixture,
            selected_cases=selected_cases,
            selected_aliases=selected_aliases,
            pdf_manifest=pdf_manifest,
            load_manifest=load_manifest.to_dict(),
            db_counts=db_counts,
            vector_count=collection.count(),
            fixture_index_embedding_calls=fixture_embedding_provider.calls,
            fixture_index_embedding_usage=fixture_embedding_provider.usage,
        )
        fixture_subset_path = run_dir / "fixture_subset_manifest.json"
        write_json(fixture_subset_path, fixture_subset_manifest)

        generation_config = GenerationConfig(
            generator_model=GENERATOR_MODEL,
            embedding_model=EMBEDDING_MODEL,
            temperature=TEMPERATURE,
            max_tokens=160,
        )
        git = git_info()
        results_path = run_dir / "results.jsonl"
        retrieval_path = run_dir / "shared_retrieval.jsonl"
        all_records: list[dict[str, Any]] = []
        retrieval_records: list[dict[str, Any]] = []
        id_mappings = build_id_mappings(fixture)
        counting_collection = CountingCollection(collection)
        current_case = None
        current_mode = None
        for case in selected_cases:
            current_case = case.case_id
            retrieval = run_case_retrieval(
                fixture=fixture,
                case=case,
                id_mappings=id_mappings,
                collection=counting_collection,
                embedding_client=query_embedding_client,
                top_k=config.top_k,
            )
            retrieval_record = build_retrieval_record(run_id, case, retrieval, counting_collection.query_calls)
            append_jsonl(retrieval_path, retrieval_record)
            retrieval_records.append(retrieval_record)
            policy_context = policy_context_for_case(fixture, case)
            services = None if real_services else mock_role_aware_services(policy_context)
            for result in run_case(
                run_id=run_id,
                case_id=case.case_id,
                user_id=id_mappings["users"][case.user_alias],
                retrieval=retrieval,
                generation_config=generation_config,
                generator=generator,
                repetitions=config.repetitions,
                modes=PILOT_MODES,
                git_commit=git.get("git_commit"),
                db=db_session if config.real_api else None,
                policy_context=policy_context,
                services=services,
                results_jsonl=None,
            ):
                current_mode = result.mode
                record = result.to_dict()
                append_jsonl(results_path, record)
                all_records.append(record)
                if record.get("error"):
                    raise PilotError(
                        str(record["error"]),
                        stage="generation",
                        classification="generation",
                        current_case=current_case,
                        current_mode=current_mode,
                    )
        expected = expected_result_count(config.selected_case_ids, config.repetitions)
        if len(all_records) != expected:
            raise PilotError(
                f"Expected {expected} result records, found {len(all_records)}.",
                stage="artifact persistence",
                classification="artifact persistence",
            )
        inspection = build_pilot_inspection(fixture, all_records, retrieval_records)
        write_json(run_dir / "pilot_inspection.json", inspection)
        final_counts = read_runtime_counts(db_session) | {"chroma_vectors": collection.count()}
        run_manifest = build_run_manifest(
            config=config,
            run_id=run_id,
            run_dir=run_dir,
            preflight=preflight,
            result_record_count=len(all_records),
            retrieval_record_count=len(retrieval_records),
            fixture_subset_manifest_path=fixture_subset_path,
            api_usage=summarize_api_usage(
                all_records,
                fixture_embedding_provider=fixture_embedding_provider,
                query_embedding_client=query_embedding_client,
            ),
            final_counts=final_counts,
        )
        write_json(run_dir / "run_manifest.json", run_manifest)
        write_json(run_dir / "run_manifest.json", run_manifest | {"artifact_hashes": artifact_hashes(run_dir)})
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "result_record_count": len(all_records),
            "retrieval_record_count": len(retrieval_records),
            "artifact_hashes": artifact_hashes(run_dir),
        }
    except PilotError as exc:
        if exc.current_case is None:
            exc.current_case = locals().get("current_case")
        if exc.current_mode is None:
            exc.current_mode = locals().get("current_mode")
        raise
    except Exception as exc:
        raise PilotError(
            str(exc),
            stage=stage_from_exception(exc),
            classification=classify_exception(exc),
            current_case=locals().get("current_case"),
            current_mode=locals().get("current_mode"),
            original_error=exc,
        ) from exc
    finally:
        cleanup()


def open_real_runtime(config: PilotConfig) -> tuple[Any, Any, Any, Any, Any, Any, bool]:
    import chromadb

    ensure_backend_path()
    database_module = importlib.import_module("database")
    collection = chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_DIR"]).get_or_create_collection("infobank_vectors")
    db_session = database_module.SessionLocal()
    embedding_provider = UsageEmbeddingProvider(EMBEDDING_MODEL)
    query_client = CountingEmbeddingClient(real_api=True, model=EMBEDDING_MODEL)
    return collection, db_session, db_session.close, embedding_provider, query_client, OpenAIGenerator(), True


def open_mock_runtime(config: PilotConfig) -> tuple[Any, Any, Any, Any, Any, Any, bool]:
    ensure_backend_path()
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    database_module = importlib.import_module("database")
    importlib.reload(database_module)
    if "models" in sys.modules:
        importlib.reload(sys.modules["models"])
    else:
        importlib.import_module("models")

    engine = create_engine("sqlite:///:memory:")
    database_module.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = Session()
    collection = FakeCollection()
    if config.mock_fail_stage == "indexing":
        embedding_provider = FailingMockEmbeddingProvider()
        embedding_provider.calls = 0
        embedding_provider.usage = empty_usage()
    else:
        embedding_provider = MockEmbeddingProvider()
        embedding_provider.calls = 0
        embedding_provider.usage = empty_usage()
        original_embed = embedding_provider.embed

        def counted_embed(text_value: str) -> list[float]:
            embedding_provider.calls += 1
            embedding_provider.usage = merge_usage(
                embedding_provider.usage,
                {"embedding_calls": 1, "generation_calls": 0, "keyword_routing_calls": 0, "input_tokens": 1, "output_tokens": 0, "total_tokens": 1, "errors": [], "retries": 0},
            )
            return original_embed(text_value)

        embedding_provider.embed = counted_embed  # type: ignore[method-assign]
    query_client = CountingEmbeddingClient(real_api=False, model=EMBEDDING_MODEL, fail=config.mock_fail_stage == "query")

    def cleanup() -> None:
        db_session.close()
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url

    return collection, db_session, cleanup, embedding_provider, query_client, MockGenerator(), False


def select_cases(fixture: EvaluationFixture, case_ids: list[str]) -> list[FixtureCase]:
    by_id = {case.case_id: case for case in fixture.cases}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise PilotError(
            f"Selected pilot case IDs are missing from the fixture: {missing}",
            stage="fixture loading",
            classification="fixture loading",
        )
    return [by_id[case_id] for case_id in case_ids]


def run_case_retrieval(
    *,
    fixture: EvaluationFixture,
    case: FixtureCase,
    id_mappings: dict[str, dict[str, str]],
    collection: CountingCollection,
    embedding_client: CountingEmbeddingClient,
    top_k: int,
) -> SharedRetrievalResult:
    before = collection.query_calls
    retrieval = run_shared_retrieval(
        question=case.question,
        top_k=top_k,
        collection=collection,
        embedding_client=embedding_client,
        embedding_model=EMBEDDING_MODEL,
        query_profile=build_query_profile(case.question),
        document_ids=[id_mappings["documents"][alias] for alias in case.scope],
    )
    if collection.query_calls - before != 1:
        raise PilotError(
            f"Expected one shared retrieval for {case.case_id}.",
            stage="shared retrieval",
            classification="shared retrieval",
            current_case=case.case_id,
        )
    verify_retrieval_scope(fixture, case, retrieval)
    return retrieval


def verify_retrieval_scope(fixture: EvaluationFixture, case: FixtureCase, retrieval: SharedRetrievalResult) -> None:
    allowed_doc_ids = {candidate.metadata.get("document_id") for candidate in retrieval.retrieved_candidates}
    candidate_doc_ids = {candidate.document_id for candidate in retrieval.retrieved_candidates}
    if candidate_doc_ids != allowed_doc_ids:
        raise PilotError(
            f"Retrieval metadata/document ID mismatch for {case.case_id}.",
            stage="shared retrieval",
            classification="shared retrieval",
            current_case=case.case_id,
        )
    all_markers = {
        marker
        for other in fixture.cases
        if other.case_id != case.case_id
        for marker in other.protected + other.forbidden_answer_markers
    }
    own_markers = set(case.protected + case.forbidden_answer_markers)
    text_surface = "\n".join(candidate.raw_text for candidate in retrieval.retrieved_candidates)
    leaks = [marker for marker in sorted(all_markers - own_markers) if marker and marker in text_surface]
    if leaks:
        raise PilotError(
            f"Unrelated protected markers entered retrieval for {case.case_id}: {leaks}",
            stage="shared retrieval",
            classification="shared retrieval",
            current_case=case.case_id,
        )


def build_retrieval_record(run_id: str, case: FixtureCase, retrieval: SharedRetrievalResult, query_calls_total: int) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "case_id": case.case_id,
        "question": retrieval.question,
        "document_scope": case.scope,
        "query_profile": retrieval.query_profile,
        "query_embedding_identifier": retrieval.query_embedding_identifier,
        "retrieval_top_k": retrieval.retrieval_top_k,
        "embedding_model": retrieval.embedding_model,
        "api_usage": retrieval.api_usage,
        "retrieval_query_calls_total": query_calls_total,
        "retrieved_candidates": [candidate.to_dict() for candidate in retrieval.retrieved_candidates],
    }


def build_fixture_subset_manifest(
    *,
    fixture: EvaluationFixture,
    selected_cases: list[FixtureCase],
    selected_aliases: list[str],
    pdf_manifest: dict[str, Any],
    load_manifest: dict[str, Any],
    db_counts: dict[str, int],
    vector_count: int,
    fixture_index_embedding_calls: int,
    fixture_index_embedding_usage: dict[str, Any],
) -> dict[str, Any]:
    mappings = build_id_mappings(fixture)
    selected = set(selected_aliases)
    return {
        "manifest_id": "fixture-subset-" + uuid.uuid5(uuid.NAMESPACE_URL, ",".join(case.case_id for case in selected_cases)).hex[:16],
        "fixture_id": fixture.fixture_id,
        "schema_version": fixture.schema_version,
        "selected_case_ids": [case.case_id for case in selected_cases],
        "selected_document_aliases": selected_aliases,
        "loaded_users": mappings["users"],
        "loaded_documents": {alias: value for alias, value in mappings["documents"].items() if alias in selected},
        "loaded_chunks": {key: value for key, value in mappings["chunks"].items() if key.split(":", 1)[0] in selected},
        "vector_ids": {key: value for key, value in mappings["chunks"].items() if key.split(":", 1)[0] in selected},
        "pdf_sha256": {item["document_alias"]: item["sha256"] for item in pdf_manifest["documents"]},
        "db_row_counts": db_counts,
        "chroma_vector_count": vector_count,
        "fixture_index_embedding_calls": fixture_index_embedding_calls,
        "fixture_index_embedding_usage": fixture_index_embedding_usage,
        "loader_manifest": load_manifest,
    }


def read_runtime_counts(db_session: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ZERO_TABLES:
        counts[table] = int(db_session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar())
    return counts


def build_pilot_inspection(
    fixture: EvaluationFixture,
    records: list[dict[str, Any]],
    retrieval_records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "result_record_count": len(records),
        "retrieval_identity": verify_retrieval_identity(records),
        "marker_scan": marker_scan(fixture, records),
        "case_mode_summary": case_mode_summary(fixture, records),
        "retrieval_records": [
            {
                "case_id": record["case_id"],
                "candidate_order": [candidate["chunk_id"] for candidate in record["retrieved_candidates"]],
                "document_ids": [candidate["document_id"] for candidate in record["retrieved_candidates"]],
                "query_embedding_identifier": record["query_embedding_identifier"],
            }
            for record in retrieval_records
        ],
    }


def verify_retrieval_identity(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["case_id"], []).append(record)
    checks: dict[str, dict[str, Any]] = {}
    fields = [
        "query_embedding_identifier",
        "retrieved_chunk_ids",
        "document_ids",
        "retrieval_rank",
        "retrieval_distances",
        "raw_retrieved_chunks",
    ]
    for case_id, case_records in grouped.items():
        baseline = {field: case_records[0].get(field) for field in fields}
        checks[case_id] = {
            "pass": all({field: record.get(field) for field in fields} == baseline for record in case_records),
            "candidate_order": case_records[0].get("retrieved_chunk_ids"),
            "query_embedding_identifier": case_records[0].get("query_embedding_identifier"),
        }
    return checks


def marker_scan(fixture: EvaluationFixture, records: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    cases = {case.case_id: case for case in fixture.cases}
    scans: dict[str, dict[str, list[str]]] = {}
    for record in records:
        case = cases[record["case_id"]]
        markers = sorted(set(case.protected + case.forbidden_answer_markers + case.acceptable_answer_markers))
        surfaces = {
            "answer": record.get("answer") or "",
            "prompt_context": "\n".join(
                [
                    record.get("system_prompt") or "",
                    record.get("user_prompt") or "",
                    "\n".join(record.get("generator_context_blocks") or []),
                ]
            ),
            "public_trace": json.dumps(
                {
                    "source_roles": record.get("source_roles"),
                    "source_role_summary": record.get("source_role_summary"),
                    "evidence_check": record.get("evidence_check"),
                    "controlled_failure": record.get("controlled_failure"),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
        scans[f"{record['case_id']}::{record['mode']}"] = {
            name: [marker for marker in markers if marker and marker in text_value]
            for name, text_value in surfaces.items()
        }
    return scans


def case_mode_summary(fixture: EvaluationFixture, records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cases = {case.case_id: case for case in fixture.cases}
    summary: dict[str, dict[str, Any]] = {}
    for record in records:
        case = cases[record["case_id"]]
        answer = record.get("answer") or ""
        summary[f"{record['case_id']}::{record['mode']}"] = {
            "answer": answer,
            "output_mode": record.get("output_mode"),
            "generation_calls": int((record.get("api_usage") or {}).get("generation_calls") or 0),
            "generation_skipped": int((record.get("api_usage") or {}).get("generation_calls") or 0) == 0,
            "canonical_marker_present": any(marker in answer for marker in case.acceptable_answer_markers),
            "protected_marker_present": any(marker in answer for marker in case.protected),
            "forbidden_marker_present": any(marker in answer for marker in case.forbidden_answer_markers),
            "use_decisions": record.get("use_decisions"),
            "source_roles": record.get("source_roles"),
            "evidence_decision": record.get("evidence_decision"),
            "controlled_failure_status": record.get("controlled_failure_status"),
            "error": record.get("error"),
        }
    return summary


def summarize_api_usage(
    records: list[dict[str, Any]],
    *,
    fixture_embedding_provider: Any,
    query_embedding_client: Any,
) -> dict[str, Any]:
    by_mode: dict[str, dict[str, int]] = {}
    generation_calls = 0
    skipped_generation_calls = 0
    merged = merge_usage(fixture_embedding_provider.usage, query_embedding_client.usage)
    for mode in PILOT_MODES:
        mode_records = [record for record in records if record["mode"] == mode]
        mode_generation = sum(int((record.get("api_usage") or {}).get("generation_calls") or 0) for record in mode_records)
        mode_skipped = len(mode_records) - mode_generation
        by_mode[mode] = {"generation_calls": mode_generation, "skipped_generation_calls": mode_skipped}
        generation_calls += mode_generation
        skipped_generation_calls += mode_skipped
        merged = merge_usage(merged, *[record.get("api_usage") for record in mode_records])
    return {
        "fixture_index_embedding_calls": fixture_embedding_provider.calls,
        "query_embedding_calls": query_embedding_client.calls,
        "generation_calls": generation_calls,
        "skipped_generation_calls": skipped_generation_calls,
        "keyword_routing_calls": merged.get("keyword_routing_calls", 0),
        "input_tokens": merged.get("input_tokens"),
        "output_tokens": merged.get("output_tokens"),
        "total_tokens": merged.get("total_tokens"),
        "errors": merged.get("errors", []),
        "retries": merged.get("retries", 0),
        "by_mode": by_mode,
    }


def build_run_manifest(
    *,
    config: PilotConfig,
    run_id: str,
    run_dir: Path,
    preflight: dict[str, Any],
    result_record_count: int,
    retrieval_record_count: int,
    fixture_subset_manifest_path: Path,
    api_usage: dict[str, Any],
    final_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "mode": "real-api" if config.real_api else "mocked-test",
        "git": git_info(),
        "tracked_status": tracked_status(),
        "python_version": sys.version,
        "python_platform": platform.platform(),
        "package_versions": package_versions(),
        "fixture_path": str(config.fixture_path),
        "fixture_subset_manifest": str(fixture_subset_manifest_path),
        "selected_case_ids": config.selected_case_ids,
        "modes": PILOT_MODES,
        "repetitions": config.repetitions,
        "retrieval_top_k": config.top_k,
        "embedding_model": EMBEDDING_MODEL,
        "generator_model": GENERATOR_MODEL,
        "generation_temperature": TEMPERATURE,
        "expected_result_count": expected_result_count(config.selected_case_ids, config.repetitions),
        "result_record_count": result_record_count,
        "retrieval_record_count": retrieval_record_count,
        "api_usage": api_usage,
        "preflight": preflight,
        "final_counts": final_counts,
        "openai_key_visible": bool(os.environ.get("OPENAI_API_KEY")) if config.real_api else None,
        "openai_key_exposed": False,
    }


def unique_run_dir(results_dir: Path, run_id: str) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    candidate = results_dir / run_id
    suffix = 1
    while candidate.exists():
        candidate = results_dir / f"{run_id}_{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def artifact_hashes(run_dir: Path) -> dict[str, str | None]:
    names = [
        "results.jsonl",
        "run_manifest.json",
        "fixture_subset_manifest.json",
        "shared_retrieval.jsonl",
        "pilot_inspection.json",
        "pilot_failure.json",
    ]
    return {name: sha256_file(run_dir / name) if (run_dir / name).exists() else None for name in names}


def write_failure_artifact(run_dir: Path, error: PilotError) -> None:
    payload = {
        "stage": error.stage,
        "classification": error.classification,
        "current_case": error.current_case,
        "current_mode": error.current_mode,
        "error": {
            "type": (error.original_error or error).__class__.__name__,
            "message": str(error),
        },
        "git": git_info(),
        "openai_key_exposed": False,
    }
    write_json(run_dir / "pilot_failure.json", payload)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def sanitize(value: Any) -> Any:
    secrets = [os.environ.get("OPENAI_API_KEY"), os.environ.get("DATABASE_URL")]
    if isinstance(value, str):
        clean = value
        for secret in [item for item in secrets if item]:
            clean = clean.replace(secret, "<redacted>")
        return clean
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_from_exception(exc: BaseException) -> str:
    text_value = str(exc).lower()
    if "embedding" in text_value:
        return "embedding/indexing"
    if "retrieval" in text_value:
        return "shared retrieval"
    return "unexpected"


def classify_exception(exc: BaseException) -> str:
    text_value = f"{exc.__class__.__name__} {exc}".lower()
    if "connection" in text_value or "network" in text_value or "api" in text_value:
        return "network/API"
    if "database" in text_value or "sql" in text_value:
        return "environment/configuration"
    if "fixture" in text_value:
        return "fixture loading"
    if "retrieval" in text_value:
        return "shared retrieval"
    return "artifact persistence"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = config_from_args(args)
    try:
        if config.check_only:
            report = run_document_rag_pilot(config)
            print(
                "PILOT CHECK: PASS "
                f"database={report['check_only']['database_name']} "
                f"chroma={report['check_only']['chroma_persist_dir']}"
            )
            return 0
        run_document_rag_pilot(config)
        return 0
    except PilotError as exc:
        if str(exc) == "PILOT BLOCKED: OPENAI_API_KEY NOT CONFIGURED":
            print("PILOT BLOCKED: OPENAI_API_KEY NOT CONFIGURED")
        elif str(exc) == "PILOT BLOCKED: EVALUATION STATE NOT CLEAN":
            print("PILOT BLOCKED: EVALUATION STATE NOT CLEAN")
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
