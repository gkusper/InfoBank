"""Gold-blind actual InfoBank B0-B3 execution harness.

This module intentionally imports only query/corpus input schemas.  Scoring and
annotation loading live in a separate post-run module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .actual_pipeline_inputs import (
    CorpusDocument,
    PolicyFixture,
    QueryInput,
    load_corpus_fixture,
    load_query_inputs,
)
from .backend import BACKEND_DIR, REPO_ROOT, ensure_backend_path
from .schemas import EvaluationMode, utc_timestamp


RUNNER_VERSION = "infobank-actual-pipeline-runner-v1"
RAW_SCHEMA_VERSION = "infobank-actual-raw-record-v1"
SEAL_SCHEMA_VERSION = "infobank-raw-run-seal-v1"
DEFAULT_MODEL = "infobank-deterministic-extractive-v1"
MODES = tuple(item.value for item in EvaluationMode)


@dataclass(frozen=True)
class ActualPipelineConfig:
    top_k: int = 6
    minimum_support_score: float = 0.45
    minimum_primary_sources: int = 1
    minimum_source_diversity: int = 1
    conflict_policy: str = "query_sensitive"
    routing_mode: str = "KEYWORD_ROUTING"
    embedding_model: str = "infobank-deterministic-embedding-v1"
    generation_model: str = DEFAULT_MODEL
    config_version: str = "actual-pipeline-development-config-v1"

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be positive")
        if not 0.0 <= self.minimum_support_score <= 1.0:
            raise ValueError("minimum_support_score must be within [0, 1]")
        if self.conflict_policy not in {"query_sensitive", "bounded_summary", "authority_required"}:
            raise ValueError("Unsupported conflict policy")

    @property
    def config_hash(self) -> str:
        value = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _pdf_bytes(document: CorpusDocument) -> bytes:
    import fitz

    pdf = fitz.open()
    pdf.set_metadata(
        {
            "title": f"{document.object_id} {document.document_type}",
            "author": "InfoBank deterministic actual-pipeline builder",
            "subject": "Generated synthetic development fixture",
            "keywords": ",".join(document.keywords),
            "creationDate": "D:20260819000000Z",
            "modDate": "D:20260819000000Z",
        }
    )
    for text in document.pages:
        page = pdf.new_page(width=595, height=842)
        page.insert_textbox(fitz.Rect(72, 72, 523, 770), text, fontsize=11, fontname="helv")
    try:
        payload = pdf.tobytes(garbage=4, deflate=True, no_new_id=True)
    except TypeError:
        payload = pdf.tobytes(garbage=4, deflate=True)
    pdf.close()
    return payload


def _elapsed_ms(start_ns: int) -> float:
    return round((time.perf_counter_ns() - start_ns) / 1_000_000, 6)


def _support_score(question: str, text: str) -> float:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", question.lower())
        if token
        not in {
            "what",
            "which",
            "where",
            "when",
            "does",
            "stated",
            "specified",
            "available",
            "across",
            "permitted",
            "governed",
            "source",
            "this",
            "that",
            "give",
        }
        and not re.fullmatch(r"(?:tv|router|printer|device)-[a-z0-9-]+", token)
    }
    if not tokens:
        return 0.0
    lowered = text.lower()
    aliases = {"authority": "authoritative", "authoritative": "authority"}
    return round(
        sum(token in lowered or aliases.get(token, "\0") in lowered for token in tokens) / len(tokens),
        6,
    )


def _page_aware_score(question: str, text: str, vector_distance: float) -> float:
    lexical = _support_score(question, text)
    semantic = max(0.0, 1.0 - float(vector_distance))
    authority_bonus = 0.15 if "conflict" in question.lower() and "authoritative" in text.lower() else 0.0
    return round(0.7 * lexical + 0.3 * semantic + authority_bonus, 9)


def _known_object_reference(question: str) -> list[str]:
    return re.findall(r"\b(?:TV|ROUTER|PRINTER|DEVICE)-[A-Z0-9-]+\b", question.upper())


class PipelineRuntime:
    """Isolated SQL/Chroma/source-store runtime backed by production modules."""

    def __init__(
        self,
        *,
        documents: list[CorpusDocument],
        fixtures: dict[str, PolicyFixture],
        database_url: str,
        chroma_dir: Path,
        source_storage_dir: Path,
        config: ActualPipelineConfig,
    ) -> None:
        ensure_backend_path()
        os.environ["DATABASE_URL"] = database_url
        os.environ["AI_PROVIDER"] = "deterministic-mock"
        os.environ.pop("OPENAI_API_KEY", None)

        import chromadb
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker

        import aggregate_executor
        import ai_provider
        import citation_service
        import controlled_failure
        import database
        import document_processing
        import models
        import policy_engine
        import relevance
        import routing
        import source_storage

        self.aggregate_executor = aggregate_executor
        self.citation_service = citation_service
        self.controlled_failure = controlled_failure
        self.document_processing = document_processing
        self.models = models
        self.policy_engine = policy_engine
        self.relevance = relevance
        self.routing = routing
        self.documents = documents
        self.document_by_id = {item.document_id: item for item in documents}
        self.fixtures = fixtures
        self.config = config
        self.provider = ai_provider.DeterministicMockProvider()
        self.engine = create_engine(database_url, pool_pre_ping=True)
        if self.engine.dialect.name == "mysql":
            database_name = self.engine.url.database or ""
            if not database_name.startswith("infobank_eval_"):
                raise ValueError("Refusing to reset a non-evaluation MySQL database")
            with self.engine.begin() as connection:
                connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                for table in reversed(database.Base.metadata.sorted_tables):
                    connection.execute(text(f"DELETE FROM `{table.name}`"))
                connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        else:
            database.Base.metadata.drop_all(self.engine)
            database.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self.chroma = chromadb.PersistentClient(path=str(chroma_dir))
        self.collection = self.chroma.get_or_create_collection(
            name=f"actual_{config.config_hash[:16]}",
            metadata={"hnsw:space": "cosine"},
        )
        self.source_storage = source_storage.SourceStorage(source_storage_dir)
        self._seed()

    @staticmethod
    def _user_id(identity: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:actual-user:{identity}"))

    def _seed(self) -> None:
        models = self.models
        with self.Session() as db:
            fixture_users = sorted({f"eval-{name}" for name in self.fixtures})
            owner_id = self._user_id("source-owner")
            for identity in ["source-owner", *fixture_users]:
                db.add(
                    models.User(
                        id=self._user_id(identity),
                        email=f"{identity}@example.invalid",
                        username=identity,
                        password_hash="not-a-login-credential",
                    )
                )
            all_chunk_ids: list[str] = []
            all_chunk_texts: list[str] = []
            all_chunk_metadata: list[dict[str, Any]] = []
            for fixture_doc in self.documents:
                payload = _pdf_bytes(fixture_doc)
                stored = self.source_storage.save(fixture_doc.document_id, payload)
                extracted = self.document_processing.extract_pdf_pages(payload)
                chunks = self.document_processing.chunk_pages(fixture_doc.document_id, extracted.pages)
                db.add(
                    models.Document(
                        id=fixture_doc.document_id,
                        file_path=fixture_doc.original_filename,
                        original_filename=fixture_doc.original_filename,
                        source_storage_path=stored.relative_path,
                        source_sha256=stored.sha256,
                        source_mime_type=stored.mime_type,
                        source_byte_size=stored.byte_size,
                        page_count=extracted.page_count,
                        source_status="ARCHIVED" if fixture_doc.archived else "ACTIVE",
                        processing_status="READY",
                        processing_config_version=self.document_processing.DEFAULT_PROCESSING_CONFIG.config_version,
                        processing_config_hash=self.document_processing.DEFAULT_PROCESSING_CONFIG.config_hash,
                        visibility="Private",
                    )
                )
                db.add(
                    models.UserDocumentPermission(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"owner:{fixture_doc.document_id}")),
                        user_id=owner_id,
                        document_id=fixture_doc.document_id,
                        permission_type=models.PermissionType.Owner,
                    )
                )
                for chunk in chunks:
                    db.add(
                        models.DocumentChunk(
                            id=chunk.id,
                            document_id=fixture_doc.document_id,
                            chunk_index=chunk.chunk_index,
                            page_number=chunk.page_number,
                            block_index=chunk.block_index,
                            char_start=chunk.char_start,
                            char_end=chunk.char_end,
                            text_content=chunk.text,
                            content_sha256=chunk.content_hash,
                            source_sha256=stored.sha256,
                            chunk_config_version=chunk.config_version,
                            chunk_config_hash=chunk.config_hash,
                            vector_id=chunk.id,
                        )
                    )
                    all_chunk_ids.append(chunk.id)
                    all_chunk_texts.append(chunk.text)
                    all_chunk_metadata.append(chunk.chroma_metadata())
                for keyword_value in fixture_doc.keywords:
                    keyword = db.query(models.Keyword).filter(models.Keyword.word == keyword_value).first()
                    if keyword is None:
                        keyword = models.Keyword(word=keyword_value)
                        db.add(keyword)
                        db.flush()
                    db.add(
                        models.DocumentKeyword(
                            document_id=fixture_doc.document_id,
                            keyword_id=keyword.id,
                            provenance_type=models.ProvenanceType.Rule,
                            provenance_json=json.dumps({"method": "actual-pipeline-fixture-v1"}, sort_keys=True),
                            extraction_method="actual-pipeline-fixture-v1",
                            user_edited=False,
                        )
                    )
            for fixture_id, fixture in self.fixtures.items():
                user_id = self._user_id(f"eval-{fixture_id}")
                for doc_id, access in fixture.access_by_document.items():
                    permission = {
                        "Full": models.PermissionType.Reader,
                        "Aggregate": models.PermissionType.Aggregate,
                        "Metadata": models.PermissionType.Metadata,
                    }.get(access)
                    if permission is None:
                        continue
                    db.add(
                        models.UserDocumentPermission(
                            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"fixture:{fixture_id}:{doc_id}")),
                            user_id=user_id,
                            document_id=doc_id,
                            permission_type=permission,
                        )
                    )
            db.commit()
            embeddings = self.provider.embed(all_chunk_texts, model=self.config.embedding_model)
            self.collection.add(
                ids=all_chunk_ids,
                documents=all_chunk_texts,
                metadatas=all_chunk_metadata,
                embeddings=embeddings,
            )

    def _routing(
        self,
        question: str,
        permitted_ids: list[str],
        *,
        enabled: bool,
    ) -> tuple[list[str], list[str], dict[str, Any]]:
        referenced_objects = set(_known_object_reference(question))
        object_scoped = [
            item.document_id
            for item in self.documents
            if item.document_id in permitted_ids and item.object_id.upper() in referenced_objects
        ]
        routing_input = object_scoped or permitted_ids
        document_keywords = {item.document_id: item.keywords for item in self.documents if item.document_id in routing_input}
        scoped_families = {
            item.package_ref.split("-")[1]
            for item in self.documents
            if item.document_id in object_scoped
        }
        available = sorted(
            {
                value
                for values in document_keywords.values()
                for value in values
                if value.upper() not in referenced_objects and value.lower() not in scoped_families
            }
        )
        selected = self.provider.extract_keywords(
            question,
            model=self.config.generation_model,
            prompt="Select governed routing tags.",
            prompt_version="routing-keyword-v1",
            available_keywords=available,
            limit=4,
        )
        mode = self.routing.RoutingMode.KEYWORD_ROUTING if enabled else self.routing.RoutingMode.ROUTING_OFF
        decision = self.routing.route_documents(routing_input, document_keywords, selected, mode)
        return list(decision.candidate_document_ids), selected, decision.to_trace()

    def _retrieve(self, question: str, candidate_ids: list[str], top_k: int) -> list[dict[str, Any]]:
        if not candidate_ids:
            return []
        question_vector = self.provider.embed([question], model=self.config.embedding_model)[0]
        where = {"document_id": candidate_ids[0]} if len(candidate_ids) == 1 else {"document_id": {"$in": candidate_ids}}
        chunk_count = sum(
            self.collection.count() for _ in [0]
        )
        results = self.collection.query(
            query_embeddings=[question_vector],
            n_results=min(max(top_k, 1), chunk_count),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        rows: list[dict[str, Any]] = []
        for vector_id, text, metadata, distance in zip(
            results.get("ids", [[]])[0],
            results.get("documents", [[]])[0],
            results.get("metadatas", [[]])[0],
            results.get("distances", [[]])[0],
        ):
            rows.append(
                {
                    "chunk_id": vector_id,
                    "document_id": metadata["document_id"],
                    "page_number": int(metadata["page_number"]),
                    "text": text,
                    "vector_distance": round(float(distance), 9),
                    "page_aware_score": _page_aware_score(question, text, float(distance)),
                }
            )
        return sorted(rows, key=lambda item: (-item["page_aware_score"], item["vector_distance"], item["chunk_id"]))

    def run_case(self, query: QueryInput, mode: str) -> tuple[dict[str, Any], dict[str, float]]:
        timings: dict[str, float] = {}
        total_start = time.perf_counter_ns()
        fixture = self.fixtures[query.policy_fixture_ref]
        models = self.models
        relevance = self.relevance
        cf = self.controlled_failure
        output_class = "FULL_ANSWER"
        reason_code = "supported"
        answer = ""
        citations: list[dict[str, Any]] = []
        generation_skipped = False
        provider_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "retries": 0,
            "cost": 0.0,
            "usage_source": "generation_skipped",
        }
        candidate_ids: list[str] = []
        selected_keywords: list[str] = []
        routing_trace: dict[str, Any] = {}
        retrieved: list[dict[str, Any]] = []
        generator_blocks: list[str] = []
        sources: list[dict[str, Any]] = []
        governance: dict[str, Any] = {}
        aggregate_trace: dict[str, Any] | None = None
        error: str | None = None

        try:
            with self.Session() as db:
                active_ids = sorted(item.document_id for item in self.documents if not item.archived)
                known_objects = {item.object_id.upper() for item in self.documents}
                referenced_objects = _known_object_reference(query.query_text)
                exact_object_missing = bool(referenced_objects and not set(referenced_objects).intersection(known_objects))

                stage = time.perf_counter_ns()
                if mode == EvaluationMode.B3_FULL_ROLE_AWARE.value:
                    pre_gate = cf.select_pre_generation_output_mode(
                        query.query_text,
                        relevance.build_query_profile(query.query_text, []),
                    )
                    if pre_gate.get("decision") == "controlled_failure":
                        controlled = pre_gate["controlled_failure"]
                        output_class = controlled["status"]
                        reason_code = controlled["reason"]
                        answer = controlled["safeOutput"]
                        generation_skipped = True
                timings["pre_generation_gate"] = _elapsed_ms(stage)

                stage = time.perf_counter_ns()
                if not generation_skipped:
                    if mode in {EvaluationMode.B0_VECTOR_ONLY.value, EvaluationMode.B1_VECTOR_ROUTING.value}:
                        permitted_ids = active_ids
                    else:
                        governance = self.policy_engine.resolve_document_access_bulk(
                            db,
                            self._user_id(query.evaluation_identity),
                            active_ids,
                            query.declared_purpose,
                        )
                        permitted_ids = list(governance["usable_doc_ids"])
                    if exact_object_missing and mode in {
                        EvaluationMode.B2_PERMISSION_FILTERED.value,
                        EvaluationMode.B3_FULL_ROLE_AWARE.value,
                    }:
                        permitted_ids = []
                        governance = {
                            "use_decisions": {},
                            "source_roles": {},
                            "usable_doc_ids": [],
                            "content_doc_ids": [],
                            "metadata_only_doc_ids": [],
                            "denied_doc_ids": [],
                            "has_primary_evidence": False,
                            "has_aggregate_evidence": False,
                            "has_metadata_only": False,
                            "exact_object_missing": True,
                        }
                else:
                    permitted_ids = []
                timings["policy_resolution"] = _elapsed_ms(stage)

                stage = time.perf_counter_ns()
                if not generation_skipped:
                    routing_enabled = mode in {
                        EvaluationMode.B1_VECTOR_ROUTING.value,
                        EvaluationMode.B3_FULL_ROLE_AWARE.value,
                    }
                    candidate_ids, selected_keywords, routing_trace = self._routing(
                        query.query_text,
                        permitted_ids,
                        enabled=routing_enabled,
                    )
                timings["routing"] = _elapsed_ms(stage)

                stage = time.perf_counter_ns()
                if not generation_skipped:
                    top_k = int(query.runtime_parameters.get("top_k", self.config.top_k))
                    retrieved = self._retrieve(query.query_text, candidate_ids, top_k)
                timings["retrieval"] = _elapsed_ms(stage)

                stage = time.perf_counter_ns()
                if not generation_skipped:
                    if mode in {EvaluationMode.B2_PERMISSION_FILTERED.value, EvaluationMode.B3_FULL_ROLE_AWARE.value}:
                        governance = self.policy_engine.resolve_document_access_bulk(
                            db,
                            self._user_id(query.evaluation_identity),
                            candidate_ids,
                            query.declared_purpose,
                        ) if candidate_ids else governance
                    else:
                        governance = {
                            "use_decisions": {doc_id: relevance.USE_FULL for doc_id in candidate_ids},
                            "source_roles": {doc_id: relevance.SOURCE_ROLE_PRIMARY for doc_id in candidate_ids},
                            "usable_doc_ids": list(candidate_ids),
                            "content_doc_ids": list(candidate_ids),
                            "metadata_only_doc_ids": [],
                            "denied_doc_ids": [],
                            "has_primary_evidence": bool(candidate_ids),
                            "has_aggregate_evidence": False,
                            "has_metadata_only": False,
                        }

                    if mode == EvaluationMode.B3_FULL_ROLE_AWARE.value:
                        profile = relevance.build_query_profile(query.query_text, selected_keywords)
                    else:
                        profile = {"task_intent": "baseline", "required_evidence_strength": "baseline"}
                    aggregate_contributions: list[Any] = []
                    for item in retrieved:
                        doc_id = item["document_id"]
                        use_decision = governance.get("use_decisions", {}).get(doc_id, relevance.USE_FULL)
                        if use_decision == relevance.USE_DENY:
                            continue
                        doc_row = db.query(models.Document).filter(models.Document.id == doc_id).first()
                        chunk_row = db.query(models.DocumentChunk).filter(models.DocumentChunk.id == item["chunk_id"]).first()
                        if not doc_row or not chunk_row or doc_row.source_status != "ACTIVE":
                            continue
                        if mode == EvaluationMode.B3_FULL_ROLE_AWARE.value:
                            source_profile = relevance.classify_chunk_profile(
                                query.query_text,
                                item["text"],
                                doc_row.original_filename or doc_row.file_path,
                                profile,
                                governance["source_roles"].get(doc_id, relevance.SOURCE_ROLE_CONTEXTUAL),
                                use_decision,
                            )
                            role = source_profile["role"]
                        elif use_decision == relevance.USE_AGGREGATE:
                            source_profile = {}
                            role = relevance.SOURCE_ROLE_AGGREGATE_ONLY
                        elif use_decision == relevance.USE_METADATA:
                            source_profile = {}
                            role = relevance.SOURCE_ROLE_CONTEXTUAL
                        else:
                            source_profile = {}
                            role = relevance.SOURCE_ROLE_PRIMARY
                        citation = self.citation_service.citation_from_chunk(doc_row, chunk_row, use_decision)
                        if citation.get("available"):
                            citation["evidence_role"] = role
                            citation["_selection_score"] = item["page_aware_score"]
                            citations.append(citation)
                        public_text = relevance.public_source_text(role, item["text"])
                        sources.append(
                            {
                                "document_id": doc_id,
                                "chunk_id": item["chunk_id"],
                                "page_number": item["page_number"],
                                "role": role,
                                "use_decision": use_decision,
                                "usable_relevance": source_profile,
                                "text": public_text,
                            }
                        )
                        if role == relevance.SOURCE_ROLE_AGGREGATE_ONLY:
                            numeric = re.search(r"approval time is\s+(\d+(?:\.\d+)?)", item["text"], re.IGNORECASE)
                            if numeric:
                                aggregate_contributions.append(
                                    self.aggregate_executor.AggregateContribution(
                                        source_id=doc_id,
                                        contributor_id=doc_id,
                                        value=float(numeric.group(1)),
                                    )
                                )
                        elif use_decision == relevance.USE_FULL:
                            block = (
                                relevance.make_context_block(source_profile, doc_row.original_filename, item["text"])
                                if mode == EvaluationMode.B3_FULL_ROLE_AWARE.value
                                else item["text"]
                            )
                            generator_blocks.append(block)

                    visible_text = "\n\n---\n\n".join(generator_blocks)
                    if citations:
                        if any(item.get("evidence_role") == relevance.SOURCE_ROLE_CONTRASTIVE for item in citations):
                            selected_citations = []
                            for role in (relevance.SOURCE_ROLE_PRIMARY, relevance.SOURCE_ROLE_CONTRASTIVE):
                                role_items = [item for item in citations if item.get("evidence_role") == role]
                                if role_items:
                                    selected_citations.append(max(role_items, key=lambda item: float(item["_selection_score"])))
                        else:
                            selected_citations = [max(citations, key=lambda item: float(item["_selection_score"]))]
                        citations = [
                            {key: value for key, value in item.items() if key != "_selection_score"}
                            for item in selected_citations
                        ]
                    support_score = _support_score(query.query_text, visible_text)
                    context_available = bool(generator_blocks) and support_score >= self.config.minimum_support_score
                    aggregate_request = any(term in query.query_text.lower() for term in ("average", "aggregate", "mean", "count"))

                    if mode == EvaluationMode.B3_FULL_ROLE_AWARE.value:
                        if aggregate_request and governance.get("has_aggregate_evidence") and not governance.get("has_primary_evidence"):
                            aggregate_result = self.aggregate_executor.execute_aggregate(
                                aggregate_contributions,
                                governance.get("use_decisions", {}),
                                self.aggregate_executor.AggregateConfig(k_threshold=fixture.aggregate_k),
                            )
                            output_class = aggregate_result["output_class"]
                            reason_code = aggregate_result["reason_code"]
                            answer = aggregate_result["safe_output"]
                            aggregate_trace = aggregate_result["public_trace"]
                            generation_skipped = True
                            citations = []
                            generator_blocks = [aggregate_result["generator_context"]] if aggregate_result.get("generator_context") else []
                        else:
                            gate = cf.select_rag_output_mode(
                                query.query_text,
                                sources,
                                profile,
                                governance,
                                context_available,
                                aggregate_request=aggregate_request,
                                conflict_policy=fixture.conflict_policy or self.config.conflict_policy,
                            )
                            output_class = gate["output_mode"]
                            if gate.get("controlled_failure"):
                                controlled = gate["controlled_failure"]
                                reason_code = controlled["reason"]
                                if gate.get("decision") == "controlled_failure":
                                    answer = controlled["safeOutput"]
                                    generation_skipped = True
                            else:
                                reason_code = "supported"
                    elif mode == EvaluationMode.B2_PERMISSION_FILTERED.value:
                        if governance.get("metadata_only_doc_ids") and not governance.get("content_doc_ids"):
                            output_class, reason_code = "METADATA_ONLY", "governance"
                            answer, generation_skipped = "Only metadata-level source information is available; content is withheld by policy.", True
                        elif not governance.get("content_doc_ids"):
                            output_class = "REFUSE_PERMISSION" if governance.get("denied_doc_ids") else "REFUSE_NO_MATCH"
                            reason_code = "governance" if governance.get("denied_doc_ids") else "epistemic"
                            answer, generation_skipped = "There is no permitted source that can be used for this question in the InfoBank.", True
                        elif aggregate_request and governance.get("has_aggregate_evidence"):
                            aggregate_result = self.aggregate_executor.execute_aggregate(
                                aggregate_contributions,
                                governance.get("use_decisions", {}),
                                self.aggregate_executor.AggregateConfig(k_threshold=fixture.aggregate_k),
                            )
                            output_class, reason_code = aggregate_result["output_class"], aggregate_result["reason_code"]
                            answer, generation_skipped = aggregate_result["safe_output"], True
                            aggregate_trace = aggregate_result["public_trace"]
                            citations = []
                        elif not context_available:
                            output_class, reason_code = "REFUSE_INSUFFICIENT_EVIDENCE", "evidential"
                            answer, generation_skipped = "The answer cannot be found in the document.", True
                        else:
                            output_class, reason_code = "FULL_ANSWER", "supported"
                    else:
                        output_class, reason_code = "FULL_ANSWER", "baseline_generation"
                    timings["evidence_and_output_gate"] = _elapsed_ms(stage)

                    stage = time.perf_counter_ns()
                    if not generation_skipped:
                        visible_text = "\n\n---\n\n".join(generator_blocks)
                        messages = [
                            {
                                "role": "system",
                                "content": "Answer only from generator-visible context. Extract supported factual sentences and do not add outside facts.",
                            },
                            {
                                "role": "user",
                                "content": f"Question: {query.query_text}\n\nContext from the document(s):\n{visible_text}",
                            },
                        ]
                        generated = self.provider.generate_with_usage(
                            messages,
                            model=self.config.generation_model,
                            temperature=0.0,
                        )
                        answer = generated.text
                        provider_usage = generated.to_dict()
                        if answer == "The answer cannot be found in the document.":
                            output_class, reason_code = "REFUSE_INSUFFICIENT_EVIDENCE", "evidential"
                    timings["generation"] = _elapsed_ms(stage)
                else:
                    support_score = 0.0

                if output_class in {
                    "CLARIFICATION",
                    "REFUSE_PERMISSION",
                    "REFUSE_INSUFFICIENT_EVIDENCE",
                    "REFUSE_NO_MATCH",
                    "REFUSE_AGGREGATION_THRESHOLD",
                }:
                    citations = []
                if generation_skipped:
                    generator_blocks = []

                generator_visible_text = "\n\n---\n\n".join(generator_blocks)
                generator_visible_ids = sorted(
                    {
                        item["document_id"]
                        for item in sources
                        if item.get("use_decision") == relevance.USE_FULL
                        and item.get("role") != relevance.SOURCE_ROLE_GOVERNANCE_EXCLUDED
                    }
                )
                audit_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"infobank:actual-audit:{query.case_id}:{mode}:{self.config.config_hash}",
                    )
                )
                prohibited_document_ids = sorted(
                    doc_id
                    for doc_id in active_ids
                    if fixture.access_by_document.get(doc_id) in {None, "Deny"}
                ) if mode in {EvaluationMode.B2_PERMISSION_FILTERED.value, EvaluationMode.B3_FULL_ROLE_AWARE.value} else []
                prohibited_markers = list(fixture.prohibited_markers)
                record = {
                    "schema_version": RAW_SCHEMA_VERSION,
                    "runner_version": RUNNER_VERSION,
                    "dataset_version": "actual-pipeline-development-v1",
                    "case_id": query.case_id,
                    "mode": mode,
                    "query_input_fingerprint": _sha256_bytes(_canonical(query.to_dict()).encode("utf-8")),
                    "candidate_ids": candidate_ids,
                    "selected_keywords": selected_keywords,
                    "routing_trace": routing_trace,
                    "retrieved_chunks": [
                        {key: item[key] for key in ("chunk_id", "document_id", "page_number", "vector_distance", "page_aware_score")}
                        for item in retrieved
                    ],
                    "retrieved_document_ids": sorted({item["document_id"] for item in retrieved}),
                    "generator_visible_text_hash": _sha256_bytes(generator_visible_text.encode("utf-8")),
                    "generator_visible_text": generator_visible_text,
                    "generator_visible_document_ids": generator_visible_ids,
                    "actual_output_text": answer,
                    "actual_output_class": output_class,
                    "actual_reason_code": reason_code,
                    "actual_citations": citations,
                    "support_score": support_score,
                    "provider_usage": provider_usage,
                    "generation_skipped": generation_skipped,
                    "audit_id": audit_id,
                    "aggregate_trace": aggregate_trace,
                    "policy_trace": {
                        "use_decisions": governance.get("use_decisions", {}),
                        "denied_document_count": len(governance.get("denied_doc_ids", [])),
                        "metadata_only_count": len(governance.get("metadata_only_doc_ids", [])),
                        "content_document_count": len(governance.get("content_doc_ids", [])),
                    },
                    "safety_constraints": {
                        "prohibited_document_ids": prohibited_document_ids,
                        "prohibited_markers": prohibited_markers,
                        "archived_document_ids": sorted(item.document_id for item in self.documents if item.archived),
                        "aggregate_individual_fragments": [
                            page
                            for item in self.documents
                            if fixture.access_by_document.get(item.document_id) == "Aggregate"
                            for page in item.pages
                            if "approval time is" in page.lower()
                        ],
                    },
                    "error": error,
                }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            record = {
                "schema_version": RAW_SCHEMA_VERSION,
                "runner_version": RUNNER_VERSION,
                "dataset_version": "actual-pipeline-development-v1",
                "case_id": query.case_id,
                "mode": mode,
                "query_input_fingerprint": _sha256_bytes(_canonical(query.to_dict()).encode("utf-8")),
                "candidate_ids": candidate_ids,
                "selected_keywords": selected_keywords,
                "routing_trace": routing_trace,
                "retrieved_chunks": [],
                "retrieved_document_ids": [],
                "generator_visible_text_hash": _sha256_bytes(b""),
                "generator_visible_text": "",
                "generator_visible_document_ids": [],
                "actual_output_text": "",
                "actual_output_class": "ERROR",
                "actual_reason_code": "runtime_error",
                "actual_citations": [],
                "support_score": 0.0,
                "provider_usage": provider_usage,
                "generation_skipped": True,
                "audit_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:actual-error:{query.case_id}:{mode}")),
                "aggregate_trace": None,
                "policy_trace": {},
                "safety_constraints": {"prohibited_document_ids": [], "prohibited_markers": [], "archived_document_ids": []},
                "error": error,
            }
        timings["total"] = _elapsed_ms(total_start)
        return record, timings


def _deterministic_projection(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in record.items() if key not in {"run_id", "stage_timings_ms"}} for record in records]


def run_actual_pipeline(
    *,
    query_input_path: str | Path,
    corpus_fixture_path: str | Path,
    output_dir: str | Path,
    database_url: str,
    chroma_dir: str | Path,
    source_storage_dir: str | Path,
    run_id: str,
    modes: Iterable[str] = MODES,
    config: ActualPipelineConfig = ActualPipelineConfig(),
) -> dict[str, Any]:
    """Run, write and seal raw results without opening any annotation file."""

    queries_path = Path(query_input_path)
    corpus_path = Path(corpus_fixture_path)
    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing to overwrite raw run output: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    queries = load_query_inputs(queries_path)
    documents, fixtures, corpus_metadata = load_corpus_fixture(corpus_path)
    resolved_modes = [EvaluationMode(mode).value for mode in modes]
    runtime = PipelineRuntime(
        documents=documents,
        fixtures=fixtures,
        database_url=database_url,
        chroma_dir=Path(chroma_dir),
        source_storage_dir=Path(source_storage_dir),
        config=config,
    )
    records: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []
    for mode in resolved_modes:
        for query in queries:
            record, timings = runtime.run_case(query, mode)
            record["run_id"] = run_id
            record["stage_timings_ms"] = timings
            records.append(record)
            timing_rows.append({"run_id": run_id, "case_id": query.case_id, "mode": mode, "stage_timings_ms": timings})
    raw_path = destination / "raw_records.jsonl"
    raw_path.write_text("".join(_canonical(record) + "\n" for record in records), encoding="utf-8")
    timing_path = destination / "wall_clock_timings.jsonl"
    timing_path.write_text("".join(_canonical(item) + "\n" for item in timing_rows), encoding="utf-8")
    deterministic_projection = _deterministic_projection(records)
    deterministic_path = destination / "deterministic_content.jsonl"
    deterministic_path.write_text("".join(_canonical(item) + "\n" for item in deterministic_projection), encoding="utf-8")
    seal = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp": utc_timestamp(),
        "raw_run_sha256": _sha256_file(raw_path),
        "deterministic_content_sha256": _sha256_file(deterministic_path),
        "timing_sidecar_sha256": _sha256_file(timing_path),
        "config_hash": config.config_hash,
        "config_version": config.config_version,
        "query_input_sha256": _sha256_file(queries_path),
        "corpus_sha256": _sha256_file(corpus_path),
        "commit_sha": _git_head(),
        "provider": runtime.provider.provider_name,
        "model": config.generation_model,
        "embedding_model": config.embedding_model,
        "runner_version": RUNNER_VERSION,
        "dataset_version": corpus_metadata["dataset_version"],
        "record_count": len(records),
        "modes": resolved_modes,
        "wall_clock_separated_from_deterministic_hash": True,
        "scoring_started": False,
    }
    seal_path = destination / "run_seal.json"
    seal_path.write_text(json.dumps(seal, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return seal
