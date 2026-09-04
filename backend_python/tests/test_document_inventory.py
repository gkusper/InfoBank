from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import BackgroundTasks

import ai_service
import models
import relevance
from ai_provider import ProviderGenerationResult
from routers import chat
from routers import documents as documents_router


USER_ID = "00000000-0000-0000-0000-000000000071"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000072"


def _add_user(db, user_id: str, username: str) -> None:
    db.add(models.User(
        id=user_id,
        email=f"{username}@example.invalid",
        username=username,
        password_hash="not-used",
    ))


def _add_document(
    db,
    *,
    document_id: str,
    file_path: str,
    original_filename: str | None,
    user_id: str,
    permission: models.PermissionType,
    source_status: str = "ACTIVE",
) -> None:
    db.add(models.Document(
        id=document_id,
        file_path=file_path,
        original_filename=original_filename,
        visibility="Private",
        source_status=source_status,
        processing_status="READY",
        page_count=3,
    ))
    db.add(models.UserDocumentPermission(
        id=f"permission-{document_id}-{user_id}",
        document_id=document_id,
        user_id=user_id,
        permission_type=permission,
    ))


@pytest.mark.parametrize(
    "question",
    [
        "what are my documents?",
        "Which documents are uploaded?",
        "Mik vannak feltöltve?",
        "Milyen dokumentumaim vannak?",
        "Mit töltöttem fel?",
    ],
)
def test_document_inventory_questions_have_explicit_intent(question: str) -> None:
    assert relevance.infer_task_intent(question) == "document_inventory"


def test_content_question_about_an_uploaded_document_is_not_inventory() -> None:
    assert relevance.infer_task_intent(
        "What does my uploaded router document say about warranty?"
    ) != "document_inventory"


@pytest.mark.parametrize(
    ("question", "expected_lead"),
    [
        ("what are my documents?", "Your account has 2 uploaded document(s)"),
        ("Mik vannak feltöltve?", "A fiókodhoz 2 feltöltött dokumentum"),
    ],
)
def test_inventory_is_audited_metadata_only_and_never_calls_provider(
    db_session,
    monkeypatch,
    question: str,
    expected_lead: str,
) -> None:
    _add_user(db_session, USER_ID, "inventory-user")
    _add_user(db_session, OTHER_USER_ID, "other-user")
    _add_document(
        db_session,
        document_id="owned-document",
        file_path=r"C:\private\storage\owned-document.pdf",
        original_filename="My TV manual.pdf",
        user_id=USER_ID,
        permission=models.PermissionType.Owner,
    )
    _add_document(
        db_session,
        document_id="shared-document",
        file_path=r"C:\private\storage\shared-router.pdf",
        original_filename=None,
        user_id=USER_ID,
        permission=models.PermissionType.Reader,
        source_status="ARCHIVED",
    )
    _add_document(
        db_session,
        document_id="other-private-document",
        file_path=r"C:\private\storage\secret.pdf",
        original_filename="Other user's secret.pdf",
        user_id=OTHER_USER_ID,
        permission=models.PermissionType.Owner,
    )
    db_session.commit()

    def forbidden_provider_call(*_args, **_kwargs):
        raise AssertionError("Document inventory must not call an AI provider")

    monkeypatch.setattr(ai_service, "extract_provider_keywords_with_trace", forbidden_provider_call)
    monkeypatch.setattr(ai_service, "embed_text", forbidden_provider_call)
    monkeypatch.setattr(ai_service, "generate_answer", forbidden_provider_call)

    result = asyncio.run(chat.ask_infobank(
        BackgroundTasks(),
        question=question,
        user_id=USER_ID,
        db=db_session,
    ))

    assert result["status"] == "success"
    assert result["output_mode"] == "METADATA_ONLY"
    assert result["query_profile"]["task_intent"] == "document_inventory"
    assert result["query_profile"]["retrieval_strategy"] == "authorized_document_metadata_inventory"
    assert result["query_profile"]["provider_called"] is False
    assert result["evidence_check"]["generator_called"] is False
    assert result["evidence_check"]["counts"] == {"documents": 2, "owned": 1, "shared": 1}
    assert expected_lead in result["answer"]
    assert "My TV manual.pdf" in result["answer"]
    assert "shared-router.pdf" in result["answer"]
    assert "Other user's secret.pdf" not in result["answer"]
    assert "C:\\private\\storage" not in result["answer"]
    assert {source["document_id"] for source in result["sources"]} == {
        "owned-document",
        "shared-document",
    }
    assert all(source["use_decision"] == "metadata" for source in result["sources"])
    assert all(source["citation"]["available"] is False for source in result["sources"])

    audit = db_session.query(models.AuditLog).filter(models.AuditLog.id == result["audit_id"]).one()
    audit_payload = json.loads(audit.details)
    assert audit_payload["status"] == "document_inventory"
    assert audit_payload["output_mode"] == "METADATA_ONLY"
    assert "Other user's secret.pdf" not in audit.details
    assert "C:\\private\\storage" not in audit.details


def test_empty_inventory_returns_successful_metadata_answer_without_enumeration(db_session) -> None:
    _add_user(db_session, USER_ID, "empty-inventory-user")
    db_session.commit()
    result = asyncio.run(chat.ask_infobank(
        BackgroundTasks(),
        question="Mik vannak feltöltve?",
        user_id=USER_ID,
        db=db_session,
    ))
    assert result["status"] == "success"
    assert result["output_mode"] == "METADATA_ONLY"
    assert result["sources"] == []
    assert result["evidence_check"]["counts"] == {"documents": 0, "owned": 0, "shared": 0}
    assert result["answer"] == "Jelenleg nincs a fiókodhoz rendelt feltöltött dokumentum."


def test_normal_query_with_anthropic_llm_reuses_existing_chunks_and_vectors(db_session, monkeypatch) -> None:
    _add_user(db_session, USER_ID, "normal-query-user")
    document_id = "normal-query-document"
    chunk_id = "normal-query-chunk"
    chunk_text = "Warranty period for TV-TEST-1 is 24 months from the purchase date."
    _add_document(
        db_session,
        document_id=document_id,
        file_path="normal-query.pdf",
        original_filename="normal-query.pdf",
        user_id=USER_ID,
        permission=models.PermissionType.Reader,
    )
    db_session.add(
        models.DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            chunk_index=0,
            page_number=1,
            block_index=0,
            char_start=0,
            char_end=len(chunk_text),
            text_content=chunk_text,
            content_sha256=chat.sha256_text(chunk_text),
            source_sha256=None,
            chunk_config_version="test",
            chunk_config_hash="test-config",
            vector_id=chunk_id,
        )
    )
    keyword = models.Keyword(word="warranty")
    db_session.add(keyword)
    db_session.flush()
    db_session.add(
        models.DocumentKeyword(
            document_id=document_id,
            keyword_id=keyword.id,
            provenance_type=models.ProvenanceType.Rule,
            extraction_method="test",
            user_edited=False,
        )
    )
    db_session.commit()

    def forbidden_ingestion(*_args, **_kwargs):
        raise AssertionError("normal query must not invoke ingestion, chunking, or document embedding")

    monkeypatch.setattr(documents_router, "process_document_source", forbidden_ingestion)
    monkeypatch.setattr(documents_router, "_embed_chunks", forbidden_ingestion)
    monkeypatch.setattr(documents_router, "extract_pdf_pages", forbidden_ingestion)
    monkeypatch.setattr(documents_router, "chunk_pages", forbidden_ingestion)
    monkeypatch.setattr(ai_service, "embed_texts", forbidden_ingestion)

    keyword_calls = []
    query_embedding_calls = []
    generation_calls = []

    def fake_keywords(*_args, **_kwargs):
        keyword_calls.append(_kwargs)
        return ["warranty"], {
            "provider": "anthropic",
            "adapter": "anthropic-python",
            "model": "claude-haiku-4-5-20251001",
            "prompt_version": "routing-keyword-v1",
            "available_keyword_count": 1,
            "parsed_item_count": 1,
            "selected_keyword_count": 1,
            "rejected_item_count": 0,
            "selection_strategy_version": "infocom-keyword-selector-v2",
            "provider_outcome": "selected",
            "provider_selected_keyword_count": 1,
            "deterministic_match_count": 0,
            "outcome": "selected",
        }

    def fake_embed_text(text: str, *, model: str):
        query_embedding_calls.append({"text": text, "model": model})
        return [0.0]

    def fake_generation(messages, *, model: str, temperature: float):
        generation_calls.append({"messages": messages, "model": model, "temperature": temperature})
        return ProviderGenerationResult(
            text="Warranty period is 24 months.",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            retries=0,
            cost=None,
            usage_source="provider_reported",
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            latency_ms=1.25,
            provider_request_id="msg_smoke",
            stop_reason="end_turn",
            configured_max_retries=1,
        )

    class FakeCollection:
        @staticmethod
        def query(**_kwargs):
            return {
                "ids": [[chunk_id]],
                "documents": [[chunk_text]],
                "metadatas": [[{"document_id": document_id, "chunk_id": chunk_id, "page_number": 1}]],
            }

    monkeypatch.setattr(ai_service, "extract_provider_keywords_with_trace", fake_keywords)
    monkeypatch.setattr(ai_service, "embed_text", fake_embed_text)
    monkeypatch.setattr(ai_service, "generate_answer_with_usage", fake_generation)
    monkeypatch.setattr(ai_service, "collection", FakeCollection())
    monkeypatch.setattr(
        ai_service,
        "effective_provider_configuration",
        lambda: {
            "llm_provider": "anthropic",
            "llm_model": "claude-haiku-4-5-20251001",
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "hybrid_configuration": True,
        },
    )

    result = asyncio.run(chat.ask_infobank(
        BackgroundTasks(),
        question="What is the warranty period for TV-TEST-1?",
        user_id=USER_ID,
        db=db_session,
    ))

    assert result["status"] == "success"
    assert result["answer"] == "Warranty period is 24 months."
    assert result["sources"][0]["document_id"] == document_id
    assert result["query_profile"]["keyword_selection_trace"]["provider"] == "anthropic"
    assert result["query_profile"]["generation_trace"]["provider"] == "anthropic"
    assert result["query_profile"]["generation_trace"]["model"] == "claude-haiku-4-5-20251001"
    assert keyword_calls and query_embedding_calls and generation_calls
