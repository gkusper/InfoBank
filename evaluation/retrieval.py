from __future__ import annotations

import hashlib
from typing import Any

from .backend import ensure_backend_path
from .schemas import RetrievedCandidate, SharedRetrievalResult
from .usage_logging import empty_usage, usage_from_openai_response


def build_query_profile(question: str) -> dict[str, Any]:
    ensure_backend_path()
    import relevance

    return relevance.build_query_profile(question, [])


def query_embedding_identifier(question: str, model: str) -> str:
    digest = hashlib.sha256(f"{model}\n{question}".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _score_from_distance(distance: float | None) -> float | None:
    if distance is None:
        return None
    try:
        return 1.0 / (1.0 + float(distance))
    except Exception:
        return None


def run_shared_retrieval(
    *,
    question: str,
    top_k: int = 4,
    collection: Any | None = None,
    embedding_client: Any | None = None,
    embedding_model: str | None = None,
    db: Any | None = None,
    query_profile: dict[str, Any] | None = None,
    document_ids: list[str] | None = None,
) -> SharedRetrievalResult:
    ai_service = None
    if embedding_model is None or embedding_client is None or collection is None:
        ensure_backend_path()
        import ai_service as backend_ai_service

        ai_service = backend_ai_service
    model = embedding_model or ai_service.EMBEDDING_MODEL
    query_profile = query_profile or build_query_profile(question)
    client = embedding_client or ai_service.openai_client
    response = client.embeddings.create(input=question, model=model)
    embedding = response.data[0].embedding
    usage = usage_from_openai_response(response, embedding_calls=1)
    coll = collection or ai_service.collection
    query_args: dict[str, Any] = {
        "query_embeddings": [embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if document_ids:
        query_args["where"] = _document_where_clause(document_ids)
    results = coll.query(**query_args)
    ids = (results.get("ids") or [[]])[0]
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]
    candidates: list[RetrievedCandidate] = []
    for index, chunk_id in enumerate(ids):
        metadata = dict(metadatas[index] or {})
        doc_id = metadata.get("document_id") or ""
        file_name = metadata.get("file_name") or _lookup_file_name(db, doc_id) or "Unknown document"
        distance = distances[index] if index < len(distances) else None
        candidates.append(
            RetrievedCandidate(
                rank=index + 1,
                chunk_id=str(chunk_id),
                document_id=str(doc_id),
                file_name=str(file_name),
                raw_text=documents[index] if index < len(documents) else "",
                metadata=metadata,
                distance=distance,
                score=_score_from_distance(distance),
            )
        )
    return SharedRetrievalResult(
        question=question,
        query_profile=query_profile,
        query_embedding_identifier=query_embedding_identifier(question, model),
        retrieved_candidates=candidates,
        retrieval_top_k=top_k,
        embedding_model=model,
        api_usage=usage or empty_usage(),
    )


def _lookup_file_name(db: Any | None, document_id: str) -> str | None:
    if not db or not document_id:
        return None
    try:
        ensure_backend_path()
        import models

        doc = db.query(models.Document).filter(models.Document.id == document_id).first()
        return doc.file_path if doc else None
    except Exception:
        return None


def _document_where_clause(document_ids: list[str]) -> dict[str, Any]:
    unique_ids = list(dict.fromkeys(document_ids))
    if len(unique_ids) == 1:
        return {"document_id": unique_ids[0]}
    return {"document_id": {"$in": unique_ids}}
