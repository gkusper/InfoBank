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


@dataclass(frozen=True)
class ProviderGenerationResult:
    """Provider-neutral generated text plus auditable usage metadata."""

    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    retries: int
    cost: float | None
    usage_source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def generate_with_usage(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.0,
    ) -> ProviderGenerationResult:
        """Generate through the provider interface and return explicit usage.

        Adapters without native usage reporting use a labelled deterministic
        whitespace-token estimate.  They must never present that estimate as
        provider-billed usage.
        """

        text = self.generate(messages, model=model, temperature=temperature)
        input_tokens = sum(len(self._usage_tokens(item.get("content", ""))) for item in messages)
        output_tokens = len(self._usage_tokens(text))
        return ProviderGenerationResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            retries=0,
            cost=0.0,
            usage_source="deterministic_local_estimate",
        )

    @staticmethod
    def _usage_tokens(text: str) -> list[str]:
        return re.findall(r"\S+", text or "")


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

    def generate_with_usage(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.0,
    ) -> ProviderGenerationResult:
        """Return provider-reported tokens and explicit adapter retry count.

        Monetary cost remains ``None`` here because the adapter has no
        authoritative local pricing table.  Evaluation tooling may calculate
        it only from a caller-supplied pricing configuration.
        """

        retries = 0
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._get_client().chat.completions.create(
                    model=model,
                    messages=list(messages),
                    temperature=temperature,
                )
                usage = getattr(response, "usage", None)
                input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
                return ProviderGenerationResult(
                    text=str(response.choices[0].message.content or ""),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    retries=retries,
                    cost=None,
                    usage_source="provider_reported",
                )
            except Exception as exc:
                last_error = exc
                if attempt == 2:
                    raise
                retries += 1
        raise RuntimeError("OpenAI generation retry loop ended unexpectedly") from last_error


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
        context = re.search(r"Context from the document\(s\):\s*(.+)", user_text, flags=re.DOTALL)
        if context:
            context_text = context.group(1).strip()
            question_match = re.search(r"Question:\s*(.+?)(?:\n|$)", user_text)
            question_tokens = set(self._tokens(question_match.group(1) if question_match else ""))
            # Context blocks contain trace labels followed by wrapped source
            # text. Drop labels, rejoin wrapped lines, and rank factual
            # sentences only by query/context overlap.
            content_lines: list[str] = []
            for block in re.split(r"\n\s*---\s*\n", context_text):
                text_lines = [
                    re.sub(r"\s+", " ", line).strip()
                    for line in block.splitlines()
                    if line.strip() and not line.lstrip().startswith("[")
                ]
                if text_lines:
                    content_lines.append(" ".join(text_lines))
            facts = list(dict.fromkeys(content_lines))
            ranked = sorted(
                facts,
                key=lambda fact: (
                    -len(question_tokens.intersection(self._tokens(fact))),
                    facts.index(fact),
                ),
            )
            multi_fact = bool(re.search(r"\b(and|both|conflict|compare|multi-source)\b", question_match.group(1) if question_match else "", re.IGNORECASE))
            if facts:
                return " ".join(ranked[: 2 if multi_fact else 1])[:640]
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
