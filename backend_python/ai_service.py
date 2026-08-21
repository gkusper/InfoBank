import os
import hashlib
import json
import re
from pathlib import Path
from typing import Any, List, Sequence
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

from ai_provider import AIProvider, canonical_provider_name, create_provider, embedding_dimensions

BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def resolve_backend_runtime_path(configured: str | Path | None, *, default_name: str) -> Path:
    """Resolve runtime state independently of the process working directory."""

    raw_value = str(configured).strip() if configured is not None else ""
    path = Path(raw_value or default_name).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()

MODEL_NAME = os.getenv("AI_GENERATION_MODEL", "gpt-4o-mini")
KEYWORD_MODEL = os.getenv("AI_KEYWORD_MODEL", MODEL_NAME)
EMBEDDING_MODEL = os.getenv("AI_EMBEDDING_MODEL", "text-embedding-3-small")
AI_PROVIDER_NAME = os.getenv("AI_PROVIDER", "openai")
EMBEDDING_DIMENSIONS = embedding_dimensions(AI_PROVIDER_NAME, EMBEDDING_MODEL)
CHROMA_PERSIST_PATH = resolve_backend_runtime_path(os.getenv("CHROMA_PERSIST_DIR"), default_name="chroma_data")
CHROMA_PERSIST_DIR = str(CHROMA_PERSIST_PATH)

VECTOR_COLLECTION_SCHEMA_VERSION = "infobank-vector-collection-v1"


def build_vector_collection_manifest(provider_name: str, model: str, dimensions: int) -> dict[str, str | int]:
    if dimensions <= 0:
        raise ValueError("Embedding dimensions must be positive")
    identity = {
        "schema_version": VECTOR_COLLECTION_SCHEMA_VERSION,
        "provider": canonical_provider_name(provider_name),
        "embedding_model": model,
        "dimensions": dimensions,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    identity_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    provider_slug = re.sub(r"[^a-z0-9]+", "-", str(identity["provider"]).lower()).strip("-") or "provider"
    identity["identity_hash"] = identity_hash
    identity["collection_name"] = f"infobank-{provider_slug[:18]}-d{dimensions}-{identity_hash[:12]}"
    return identity


VECTOR_COLLECTION_MANIFEST = build_vector_collection_manifest(
    AI_PROVIDER_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
)
CHROMA_COLLECTION_NAME = str(VECTOR_COLLECTION_MANIFEST["collection_name"])


def get_or_create_vector_collection(client, manifest: dict[str, str | int]):
    collection_name = str(manifest["collection_name"])
    metadata = {key: value for key, value in manifest.items() if key != "collection_name"}
    selected = client.get_or_create_collection(name=collection_name, metadata=metadata)
    actual_metadata = dict(selected.metadata or {})
    mismatches = {
        key: {"expected": value, "actual": actual_metadata.get(key)}
        for key, value in metadata.items()
        if actual_metadata.get(key) != value
    }
    if mismatches:
        raise RuntimeError(
            f"Chroma collection {collection_name!r} has incompatible embedding metadata: "
            f"{json.dumps(mismatches, sort_keys=True)}"
        )
    return selected

chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = get_or_create_vector_collection(chroma_client, VECTOR_COLLECTION_MANIFEST)

_openai_client = None
_ai_provider: AIProvider | None = None
_ai_provider_name: str | None = None


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI-backed document ingestion, retrieval, and generation.")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


class LazyOpenAIClient:
    def __getattr__(self, name):
        return getattr(get_openai_client(), name)


openai_client = LazyOpenAIClient()


def get_ai_provider() -> AIProvider:
    global _ai_provider, _ai_provider_name
    configured = os.getenv("AI_PROVIDER", AI_PROVIDER_NAME).strip().lower()
    if _ai_provider is None or _ai_provider_name != configured:
        _ai_provider = create_provider(configured, openai_client_factory=get_openai_client)
        _ai_provider_name = configured
    return _ai_provider


def reset_ai_provider() -> None:
    global _ai_provider, _ai_provider_name
    _ai_provider = None
    _ai_provider_name = None


def provider_manifest(*, operation: str, model: str) -> dict[str, Any]:
    manifest = get_ai_provider().manifest(model)
    manifest["operation"] = operation
    return manifest


def vector_store_manifest() -> dict[str, str | int]:
    return {
        **VECTOR_COLLECTION_MANIFEST,
        "persist_path": CHROMA_PERSIST_DIR,
    }


def extract_provider_keywords(
    text: str,
    *,
    available_keywords: Sequence[str] | None = None,
    limit: int = 5,
    model: str = KEYWORD_MODEL,
    prompt: str = "Extract important concepts.",
    prompt_version: str = "keyword-v1",
) -> list[str]:
    return get_ai_provider().extract_keywords(
        text,
        model=model,
        prompt=prompt,
        prompt_version=prompt_version,
        available_keywords=available_keywords,
        limit=limit,
    )


def extract_provider_keywords_with_trace(
    text: str,
    *,
    available_keywords: Sequence[str] | None = None,
    limit: int = 5,
    model: str = KEYWORD_MODEL,
    prompt: str = "Extract important concepts.",
    prompt_version: str = "keyword-v1",
) -> tuple[list[str], dict[str, Any]]:
    """Extract keywords and return privacy-safe provider-selection metadata."""

    return get_ai_provider().extract_keywords_with_trace(
        text,
        model=model,
        prompt=prompt,
        prompt_version=prompt_version,
        available_keywords=available_keywords,
        limit=limit,
    )


def embed_texts(texts: Sequence[str], *, model: str = EMBEDDING_MODEL) -> list[list[float]]:
    provider = get_ai_provider()
    expected_dimensions = embedding_dimensions(provider.provider_name, model)
    vectors = provider.embed(list(texts), model=model)
    if len(vectors) != len(texts):
        raise RuntimeError(
            f"AI provider returned {len(vectors)} embeddings for {len(texts)} inputs"
        )
    for index, vector in enumerate(vectors):
        if len(vector) != expected_dimensions:
            raise RuntimeError(
                f"AI provider returned embedding dimension {len(vector)} for item {index}; "
                f"expected {expected_dimensions} for {provider.provider_name}/{model}"
            )
    return vectors


def embed_text(text: str, *, model: str = EMBEDDING_MODEL) -> list[float]:
    vectors = embed_texts([text], model=model)
    if len(vectors) != 1:
        raise RuntimeError("AI provider returned an invalid embedding count")
    return vectors[0]


def generate_answer(
    messages: Sequence[dict[str, str]],
    *,
    model: str = MODEL_NAME,
    temperature: float = 0.0,
) -> str:
    return get_ai_provider().generate(messages, model=model, temperature=temperature)

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0:
        raise ValueError("overlap must not be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks
