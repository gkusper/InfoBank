import os
from pathlib import Path
from typing import Any, List, Sequence
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

from ai_provider import AIProvider, create_provider

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

MODEL_NAME = os.getenv("AI_GENERATION_MODEL", "gpt-4o-mini")
KEYWORD_MODEL = os.getenv("AI_KEYWORD_MODEL", MODEL_NAME)
EMBEDDING_MODEL = os.getenv("AI_EMBEDDING_MODEL", "text-embedding-3-small")
AI_PROVIDER_NAME = os.getenv("AI_PROVIDER", "openai")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = chroma_client.get_or_create_collection(name="infobank_vectors")

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


def embed_texts(texts: Sequence[str], *, model: str = EMBEDDING_MODEL) -> list[list[float]]:
    return get_ai_provider().embed(list(texts), model=model)


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
