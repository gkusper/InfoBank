"""Provider-neutral AI operations used by InfoBank domain code.

The adapters in this module own provider-specific client calls.  Governance is
deliberately absent: callers must resolve authorization before sending text to
any provider.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable, Sequence

from openai import OpenAI


PROVIDER_CONFIG_VERSION = "infocom-provider-v1"


@dataclass(frozen=True)
class ProviderManifest:
    provider: str
    adapter: str
    model: str
    config_version: str = PROVIDER_CONFIG_VERSION
    external_network_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["config_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload


class AIProvider(ABC):
    """Small interface for keywording, embeddings, and answer generation."""

    provider_name: str
    adapter_name: str
    external_network_required: bool

    @abstractmethod
    def extract_keywords(
        self,
        text: str,
        *,
        model: str,
        prompt: str,
        prompt_version: str,
        available_keywords: Sequence[str] | None = None,
        limit: int = 5,
    ) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def generate(self, messages: Sequence[dict[str, str]], *, model: str, temperature: float = 0.0) -> str:
        raise NotImplementedError

    def manifest(self, model: str) -> dict[str, Any]:
        return ProviderManifest(
            provider=self.provider_name,
            adapter=self.adapter_name,
            model=model,
            external_network_required=self.external_network_required,
        ).to_dict()


class OpenAIProvider(AIProvider):
    provider_name = "openai"
    adapter_name = "openai-python"
    external_network_required = True

    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self._client_factory = client_factory
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is required when AI_PROVIDER=openai for keyword extraction, embeddings, and generation."
                )
            self._client = OpenAI(api_key=api_key)
        return self._client

    def extract_keywords(
        self,
        text: str,
        *,
        model: str,
        prompt: str,
        prompt_version: str,
        available_keywords: Sequence[str] | None = None,
        limit: int = 5,
    ) -> list[str]:
        if available_keywords is None:
            instruction = prompt
        else:
            allowed = ", ".join(sorted(set(available_keywords), key=str.lower))
            instruction = (
                f"{prompt}\nSelect at most {limit} exact items from this allowed list: [{allowed}]. "
                "Return a comma-separated list or NONE."
            )
        response = self._get_client().chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": instruction}, {"role": "user", "content": text[:10000]}],
            temperature=0.0,
        )
        raw = str(response.choices[0].message.content or "").strip()
        if raw.upper() == "NONE":
            return []
        allowed_lookup = {item.lower(): item for item in available_keywords or ()}
        values: list[str] = []
        for item in raw.split(","):
            normalized = item.strip()
            if not normalized:
                continue
            if allowed_lookup:
                normalized = allowed_lookup.get(normalized.lower(), "")
            if normalized and normalized not in values:
                values.append(normalized)
        return values[:limit]

    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        response = self._get_client().embeddings.create(input=list(texts), model=model)
        return [list(item.embedding) for item in response.data]

    def generate(self, messages: Sequence[dict[str, str]], *, model: str, temperature: float = 0.0) -> str:
        response = self._get_client().chat.completions.create(
            model=model,
            messages=list(messages),
            temperature=temperature,
        )
        return str(response.choices[0].message.content or "")


class DeterministicMockProvider(AIProvider):
    """Network-free adapter with stable behavior for tests and development runs."""

    provider_name = "deterministic-mock"
    adapter_name = "infobank-deterministic"
    external_network_required = False
    dimensions = 24

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower())

    def extract_keywords(
        self,
        text: str,
        *,
        model: str,
        prompt: str,
        prompt_version: str,
        available_keywords: Sequence[str] | None = None,
        limit: int = 5,
    ) -> list[str]:
        del model, prompt, prompt_version
        tokens = self._tokens(text)
        if available_keywords is not None:
            token_set = set(tokens)
            ranked = []
            for keyword in sorted(set(available_keywords), key=str.lower):
                keyword_tokens = set(self._tokens(keyword))
                score = len(token_set & keyword_tokens)
                if keyword.lower() in text.lower():
                    score += 2
                if score:
                    ranked.append((-score, keyword.lower(), keyword))
            return [item[2] for item in sorted(ranked)[:limit]]
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        return sorted(counts, key=lambda token: (-counts[token], token))[:limit]

    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in self._tokens(f"{model} {text}"):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:2], "big") % self.dimensions
                vector[index] += -1.0 if digest[2] & 1 else 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([round(value / norm, 9) for value in vector])
        return vectors

    def generate(self, messages: Sequence[dict[str, str]], *, model: str, temperature: float = 0.0) -> str:
        del model, temperature
        user_text = "\n".join(message.get("content", "") for message in messages if message.get("role") == "user")
        reference = re.search(r"REFERENCE_ANSWER:\s*(.+)", user_text)
        if reference:
            return reference.group(1).strip().splitlines()[0]
        context = re.search(r"Context from the document\(s\):\s*(.+)", user_text, flags=re.DOTALL)
        if context:
            candidate = re.sub(r"\s+", " ", context.group(1)).strip()
            if candidate:
                return candidate[:320]
        return "The answer cannot be found in the document."


class LocalCompatibleProvider(DeterministicMockProvider):
    """Provider-neutral local-compatible smoke adapter; it never uses a network."""

    provider_name = "local-compatible"
    adapter_name = "openai-compatible-local-contract"


def create_provider(name: str, *, openai_client_factory: Callable[[], Any] | None = None) -> AIProvider:
    normalized = name.strip().lower()
    if normalized == "openai":
        return OpenAIProvider(client_factory=openai_client_factory)
    if normalized in {"deterministic", "deterministic-mock", "mock"}:
        return DeterministicMockProvider()
    if normalized in {"local", "local-compatible"}:
        return LocalCompatibleProvider()
    raise RuntimeError(
        f"Unsupported AI_PROVIDER={name!r}. Expected one of: openai, deterministic-mock, local-compatible."
    )
