from __future__ import annotations

from pathlib import Path

import chromadb
import pytest

import ai_service
from ai_provider import OpenAIProvider, embedding_dimensions


def test_known_embedding_dimensions_and_collection_identities_are_explicit() -> None:
    assert embedding_dimensions("openai", "text-embedding-3-small") == 1536
    assert embedding_dimensions("openai", "text-embedding-3-large") == 3072
    assert embedding_dimensions("deterministic-mock", "any-model") == 24

    openai_manifest = ai_service.build_vector_collection_manifest("openai", "text-embedding-3-small", 1536)
    mock_manifest = ai_service.build_vector_collection_manifest("deterministic-mock", "test-model", 24)
    assert openai_manifest == ai_service.build_vector_collection_manifest(
        "openai", "text-embedding-3-small", 1536
    )
    assert openai_manifest["collection_name"] != mock_manifest["collection_name"]
    assert openai_manifest["identity_hash"] != mock_manifest["identity_hash"]


def test_openai_dimension_override_is_validated_and_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class Embeddings:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            item = type("Embedding", (), {"embedding": [0.0] * kwargs["dimensions"]})()
            return type("Response", (), {"data": [item]})()

    client = type("Client", (), {"embeddings": Embeddings()})()
    monkeypatch.setenv("AI_EMBEDDING_DIMENSIONS", "256")
    provider = OpenAIProvider(client_factory=lambda: client)

    assert len(provider.embed(["synthetic"], model="text-embedding-3-small")[0]) == 256
    assert calls == [{"input": ["synthetic"], "model": "text-embedding-3-small", "dimensions": 256}]
    assert embedding_dimensions("openai", "text-embedding-3-small") == 256


def test_embedding_response_dimension_is_rejected_before_chroma(monkeypatch: pytest.MonkeyPatch) -> None:
    class WrongDimensionProvider:
        provider_name = "openai"

        @staticmethod
        def embed(texts, *, model):
            del model
            return [[0.0] * 24 for _ in texts]

    monkeypatch.delenv("AI_EMBEDDING_DIMENSIONS", raising=False)
    monkeypatch.setattr(ai_service, "get_embedding_provider", lambda: WrongDimensionProvider())
    with pytest.raises(RuntimeError, match="dimension 24.*expected 1536"):
        ai_service.embed_texts(["synthetic"], model="text-embedding-3-small")


def test_provider_specific_collection_does_not_reuse_legacy_24_dimension_index(tmp_path: Path) -> None:
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    legacy = client.get_or_create_collection("infobank_vectors")
    legacy.add(ids=["legacy"], embeddings=[[0.0] * 24], documents=["legacy mock vector"])

    manifest = ai_service.build_vector_collection_manifest("openai", "text-embedding-3-small", 1536)
    active = ai_service.get_or_create_vector_collection(client, manifest)
    active.add(ids=["openai"], embeddings=[[0.0] * 1536], documents=["openai vector"])
    result = active.query(query_embeddings=[[0.0] * 1536], n_results=1)

    assert active.name != legacy.name
    assert legacy.count() == 1
    assert active.count() == 1
    assert result["ids"] == [["openai"]]
    assert active.metadata["dimensions"] == 1536
