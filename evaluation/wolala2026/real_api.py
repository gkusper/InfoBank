from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


OPENAI_API_BASE = "https://api.openai.com/v1"


@dataclass
class ProviderCallResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    retry_count: int = 0
    response_id: str | None = None
    retry_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EmbeddingCallResult:
    model: str
    latency_ms: float
    input_tokens: int = 0
    retry_count: int = 0
    response_id: str | None = None
    retry_events: list[dict[str, Any]] = field(default_factory=list)


class RealApiProvider(Protocol):
    provider_name: str
    embedding_model: str
    generator_model: str
    is_mock: bool

    def embed_query(self, query: str) -> EmbeddingCallResult:
        ...

    def generate_json(self, *, mode_name: str, system_prompt: str, user_payload: dict[str, Any], max_output_tokens: int) -> ProviderCallResult:
        ...


class OpenAIProvider:
    provider_name = "openai"
    is_mock = False

    def __init__(
        self,
        *,
        embedding_model: str = "text-embedding-3-small",
        generator_model: str = "gpt-4o-mini",
        timeout_seconds: int = 60,
    ) -> None:
        self.embedding_model = embedding_model
        self.generator_model = generator_model
        self.timeout_seconds = timeout_seconds
        self._api_key = os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is required for --allow-real-api and is not visible in the environment.")

    def embed_query(self, query: str) -> EmbeddingCallResult:
        start_ns = time.perf_counter_ns()
        payload = {"model": self.embedding_model, "input": query}
        response = self._post_json("/embeddings", payload)
        latency_ms = _elapsed_ms(start_ns)
        usage = response.get("usage") or {}
        return EmbeddingCallResult(
            model=str(response.get("model") or self.embedding_model),
            latency_ms=latency_ms,
            input_tokens=int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0),
            response_id=response.get("id"),
        )

    def generate_json(self, *, mode_name: str, system_prompt: str, user_payload: dict[str, Any], max_output_tokens: int) -> ProviderCallResult:
        start_ns = time.perf_counter_ns()
        payload = {
            "model": self.generator_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True, sort_keys=True)},
            ],
            "temperature": 0,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        response = self._post_json("/chat/completions", payload)
        latency_ms = _elapsed_ms(start_ns)
        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = response.get("usage") or {}
        return ProviderCallResult(
            content=str(message.get("content") or ""),
            model=str(response.get("model") or self.generator_model),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency_ms,
            response_id=response.get("id"),
        )

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            OPENAI_API_BASE + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"OpenAI API HTTP {exc.code}: {_sanitize_error(body)}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI API network error: {_sanitize_error(str(exc.reason))}") from exc
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError("OpenAI API returned a non-object JSON response.")
        return parsed


def _elapsed_ms(start_ns: int) -> float:
    return max(0.0, (time.perf_counter_ns() - start_ns) / 1_000_000)


def _sanitize_error(value: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY") or ""
    if api_key:
        value = value.replace(api_key, "<OPENAI_API_KEY>")
    return value.replace("Authorization", "<authorization-header>")
