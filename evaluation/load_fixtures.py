from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.orm import Session

from .backend import ensure_backend_path
from .clean_state import check_clean_state
from .fixture_schema import EvaluationFixture, FixtureCase, FixtureDocument, load_fixture
from .schemas import RetrievedCandidate, SharedRetrievalResult
from .validate_fixtures import validate_fixture


FIXTURE_NAMESPACE = uuid.UUID("2f79de7a-7b53-5d22-a5a3-d0c000000001")


class MockEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [round(byte / 255.0, 6) for byte in digest[:16]]


@dataclass
class LoadManifest:
    fixture_id: str
    schema_version: str | None
    case_count: int
    document_count: int
    chunk_count: int
    vector_count: int
    id_mappings: dict[str, dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "schema_version": self.schema_version,
            "case_count": self.case_count,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "vector_count": self.vector_count,
            "id_mappings": self.id_mappings,
        }


def deterministic_uuid(alias: str) -> str:
    return str(uuid.uuid5(FIXTURE_NAMESPACE, alias))


def deterministic_chunk_id(document_alias: str, chunk_index: int) -> str:
    return deterministic_uuid(f"chunk:{document_alias}:{chunk_index}")


def chunk_text_equivalent(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks or [""]


def build_id_mappings(fixture: EvaluationFixture) -> dict[str, dict[str, str]]:
    return {
        "users": {user.alias: user.user_id or deterministic_uuid(f"user:{user.alias}") for user in fixture.users},
        "documents": {document.alias: document.document_id or deterministic_uuid(f"document:{document.alias}") for document in fixture.documents},
        "permissions": {},
        "chunks": {
            f"{document.alias}:{index}": deterministic_chunk_id(document.alias, index)
            for document in fixture.documents
            for index, _ in enumerate(chunk_text_equivalent(document.content))
        },
    }


def load_fixture_data(
    *,
    fixture: EvaluationFixture,
    db: Session,
    collection: Any,
    embedding_provider: Any | None = None,
    clean_checker: Any | None = check_clean_state,
    case_ids: Iterable[str] | None = None,
) -> LoadManifest:
    validate_fixture(fixture)
    if clean_checker:
        clean_checker()
    ensure_backend_path()
    import models

    selected_aliases = selected_document_aliases(fixture, case_ids)
    mappings = build_id_mappings(fixture)
    embedding_provider = embedding_provider or MockEmbeddingProvider()

    for user in fixture.users:
        db.add(
            models.User(
                id=mappings["users"][user.alias],
                email=user.email,
                username=user.username,
                password_hash="fixture-password-hash-not-a-secret",
            )
        )

    chunk_count = 0
    for document in fixture.documents:
        if document.alias not in selected_aliases:
            continue
        doc_id = mappings["documents"][document.alias]
        db.add(models.Document(id=doc_id, file_path=document.file_name, visibility=document.visibility))
        owner_alias = document.owner_user_alias or (fixture.users[0].alias if fixture.users else None)
        if owner_alias:
            perm_id = deterministic_uuid(f"permission:{owner_alias}:{document.alias}:Owner")
            mappings["permissions"][f"{owner_alias}:{document.alias}:Owner"] = perm_id
            db.add(
                models.UserDocumentPermission(
                    id=perm_id,
                    user_id=mappings["users"][owner_alias],
                    document_id=doc_id,
                    permission_type=models.PermissionType.Owner,
                )
            )
        for keyword in document.keywords:
            db_kw = db.query(models.Keyword).filter(models.Keyword.word == keyword).first()
            if not db_kw:
                db_kw = models.Keyword(word=keyword)
                db.add(db_kw)
                db.flush()
            db.add(models.DocumentKeyword(document_id=doc_id, keyword_id=db_kw.id))
        for index, chunk in enumerate(chunk_text_equivalent(document.content)):
            chunk_id = deterministic_chunk_id(document.alias, index)
            embedding = embedding_provider.embed(chunk)
            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                metadatas=[{"document_id": doc_id, "document_alias": document.alias, "file_name": document.file_name}],
                documents=[chunk],
            )
            db.add(
                models.DocumentChunk(
                    id=chunk_id,
                    document_id=doc_id,
                    chunk_index=index,
                    text_content=chunk,
                    vector_id=chunk_id,
                )
            )
            chunk_count += 1
    db.commit()
    return LoadManifest(
        fixture_id=fixture.fixture_id,
        schema_version=fixture.schema_version,
        case_count=len(fixture.cases),
        document_count=len(selected_aliases),
        chunk_count=chunk_count,
        vector_count=chunk_count,
        id_mappings=mappings,
    )


def selected_document_aliases(fixture: EvaluationFixture, case_ids: Iterable[str] | None = None) -> set[str]:
    allowed_cases = set(case_ids or [])
    aliases: set[str] = set()
    for case in fixture.cases:
        if allowed_cases and case.case_id not in allowed_cases:
            continue
        aliases.update(case.scope)
    return aliases


def case_to_harness_inputs(
    fixture: EvaluationFixture,
    case_id: str,
    *,
    top_k: int = 4,
    embedding_model: str = "text-embedding-3-small",
) -> tuple[SharedRetrievalResult, dict[str, Any]]:
    docs = fixture.document_by_alias()
    case = next(item for item in fixture.cases if item.case_id == case_id)
    candidates: list[RetrievedCandidate] = []
    for rank, alias in enumerate(case.scope[:top_k], start=1):
        document = docs[alias]
        candidates.append(
            RetrievedCandidate(
                rank=rank,
                chunk_id=deterministic_chunk_id(alias, 0),
                document_id=deterministic_uuid(f"document:{alias}"),
                file_name=document.file_name,
                raw_text=chunk_text_equivalent(document.content)[0],
                metadata={"document_alias": alias, "document_id": deterministic_uuid(f"document:{alias}")},
                distance=round(rank / 10.0, 4),
                score=round(1.0 / (1.0 + rank / 10.0), 6),
            )
        )
    retrieval = SharedRetrievalResult(
        question=case.question,
        query_profile={"purpose": "grounded_question_answering", "required_evidence_strength": "primary_or_aggregate_with_role_label"},
        query_embedding_identifier=f"fixture:{fixture.fixture_id}:{case.case_id}",
        retrieved_candidates=candidates,
        retrieval_top_k=top_k,
        embedding_model=embedding_model,
        api_usage={"embedding_calls": 0, "keyword_routing_calls": 0},
    )
    policy_context = policy_context_for_case(fixture, case)
    return retrieval, policy_context


def policy_context_for_case(fixture: EvaluationFixture, case: FixtureCase) -> dict[str, Any]:
    decisions: dict[str, str] = {}
    roles: dict[str, str] = {}
    for alias in case.scope:
        doc_id = deterministic_uuid(f"document:{alias}")
        access = case.document_access.get(alias, {})
        decisions[doc_id] = access.get("use_decision", case.expected_policy_decision or "deny")
        roles[doc_id] = access.get("source_role", "governance-excluded")
    content_doc_ids = [doc_id for doc_id, decision in decisions.items() if decision in {"full", "aggregate"}]
    metadata_only_doc_ids = [doc_id for doc_id, decision in decisions.items() if decision == "metadata"]
    denied_doc_ids = [doc_id for doc_id, decision in decisions.items() if decision == "deny"]
    return {
        "use_decisions": decisions,
        "source_roles": roles,
        "policy_reasons": {doc_id: "fixture_case_policy" for doc_id in decisions},
        "policy_rule_ids": {doc_id: None for doc_id in decisions},
        "usable_doc_ids": [doc_id for doc_id, decision in decisions.items() if decision in {"full", "aggregate", "metadata"}],
        "content_doc_ids": content_doc_ids,
        "metadata_only_doc_ids": metadata_only_doc_ids,
        "denied_doc_ids": denied_doc_ids,
        "has_primary_evidence": any(roles.get(doc_id) == "primary" for doc_id in content_doc_ids),
        "has_aggregate_evidence": any(roles.get(doc_id) == "aggregate-only" for doc_id in content_doc_ids),
        "has_metadata_only": bool(metadata_only_doc_ids),
    }


def write_load_manifest(path: str | Path, manifest: LoadManifest) -> None:
    Path(path).write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load evaluation fixtures into an isolated DB/Chroma store")
    parser.add_argument("fixture")
    parser.add_argument("--manifest", default="evaluation/generated_fixtures/load_manifest.json")
    parser.add_argument("--mock-embeddings", action="store_true", help="Use deterministic mock embeddings instead of OpenAI.")
    parser.add_argument("--case-id", action="append", help="Optional case ID to load. Can be repeated.")
    args = parser.parse_args(argv)
    if not args.mock_embeddings:
        raise SystemExit("Real embedding loading is intentionally disabled in this fixture-construction task; use --mock-embeddings.")
    fixture = load_fixture(args.fixture)
    validate_fixture(fixture)
    ensure_backend_path()
    from database import SessionLocal

    import chromadb

    chroma_path = os.getenv("CHROMA_PERSIST_DIR")
    if not chroma_path:
        raise SystemExit("CHROMA_PERSIST_DIR is required for fixture loading.")
    collection = chromadb.PersistentClient(path=chroma_path).get_or_create_collection("infobank_vectors")
    db = SessionLocal()
    try:
        manifest = load_fixture_data(
            fixture=fixture,
            db=db,
            collection=collection,
            embedding_provider=MockEmbeddingProvider(),
            clean_checker=check_clean_state,
            case_ids=args.case_id,
        )
        write_load_manifest(args.manifest, manifest)
    finally:
        db.close()
    print(f"LOADED: fixture={manifest.fixture_id} documents={manifest.document_count} chunks={manifest.chunk_count} vectors={manifest.vector_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
