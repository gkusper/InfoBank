"""Explicit-network provider readiness, estimation, and deterministic caching."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Sequence

from .actual_pipeline_inputs import load_corpus_fixture, load_query_inputs
from .backend import ensure_backend_path


ensure_backend_path()
from ai_provider import AIProvider, ProviderGenerationResult  # noqa: E402


READINESS_STATUS = "PENDING_EXPLICIT_PROVIDER_RUN_APPROVAL"
GENERATION_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_TEMPERATURE = 0.0
GENERATION_PROMPT_VERSION = "actual-pipeline-answer-v1"
ROUTING_PROMPT_VERSION = "routing-keyword-v1"
READINESS_CONFIG_VERSION = "real-provider-readiness-v1"


def canonical_hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_provider_request(provider: str, allow_network_provider: bool) -> None:
    normalized = provider.strip().lower()
    if normalized == "openai" and not allow_network_provider:
        raise RuntimeError("OpenAI evaluation requires explicit --allow-network-provider approval; no mock fallback is permitted.")
    if normalized not in {"openai", "deterministic-mock"}:
        raise RuntimeError(f"Unsupported evaluation provider: {provider}")


@dataclass(frozen=True)
class ReadinessConfig:
    provider: str
    generation_model: str = GENERATION_MODEL
    embedding_model: str = EMBEDDING_MODEL
    temperature: float = GENERATION_TEMPERATURE
    generation_prompt_version: str = GENERATION_PROMPT_VERSION
    routing_prompt_version: str = ROUTING_PROMPT_VERSION
    config_version: str = READINESS_CONFIG_VERSION

    @property
    def config_hash(self) -> str:
        return canonical_hash(asdict(self))


def cache_key(*, input_value: Any, provider: str, model: str, prompt_version: str, config_hash: str) -> tuple[str, dict[str, str]]:
    identity = {
        "input_hash": canonical_hash(input_value),
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "config_hash": config_hash,
    }
    return canonical_hash(identity), identity


class CachedEvaluationProvider(AIProvider):
    """File cache for evaluator-only provider outputs with auditable keys."""

    def __init__(self, wrapped: AIProvider, root: Path, config_hash: str, pricing: dict[str, float] | None = None) -> None:
        self.wrapped = wrapped
        self.root = Path(root)
        self.config_hash = config_hash
        self.pricing = pricing
        self.provider_name = wrapped.provider_name
        self.adapter_name = f"cached:{wrapped.adapter_name}"
        self.external_network_required = wrapped.external_network_required

    def _path(self, operation: str, key: str) -> Path:
        return self.root / operation / f"{key}.json"

    def _read(self, operation: str, key: str) -> dict[str, Any] | None:
        path = self._path(operation, key)
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def _write(self, operation: str, key: str, identity: dict[str, str], value: Any) -> None:
        path = self._path(operation, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cache_identity": identity, "value": value}
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def extract_keywords(
        self, text: str, *, model: str, prompt: str, prompt_version: str,
        available_keywords: Sequence[str] | None = None, limit: int = 5,
    ) -> list[str]:
        input_value = {"text": text, "prompt": prompt, "available_keywords": list(available_keywords or []), "limit": limit}
        key, identity = cache_key(input_value=input_value, provider=self.provider_name, model=model, prompt_version=prompt_version, config_hash=self.config_hash)
        cached = self._read("keywords", key)
        if cached:
            return list(cached["value"])
        value = self.wrapped.extract_keywords(
            text, model=model, prompt=prompt, prompt_version=prompt_version,
            available_keywords=available_keywords, limit=limit,
        )
        self._write("keywords", key, identity, value)
        return value

    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        input_value = {"texts": list(texts)}
        key, identity = cache_key(input_value=input_value, provider=self.provider_name, model=model, prompt_version="embedding-v1", config_hash=self.config_hash)
        cached = self._read("embeddings", key)
        if cached:
            return [list(row) for row in cached["value"]]
        value = self.wrapped.embed(texts, model=model)
        self._write("embeddings", key, identity, value)
        return value

    def generate(self, messages: Sequence[dict[str, str]], *, model: str, temperature: float = 0.0) -> str:
        return self.generate_with_usage(messages, model=model, temperature=temperature).text

    def generate_with_usage(
        self, messages: Sequence[dict[str, str]], *, model: str, temperature: float = 0.0,
    ) -> ProviderGenerationResult:
        input_value = {"messages": list(messages), "temperature": temperature}
        key, identity = cache_key(
            input_value=input_value, provider=self.provider_name, model=model,
            prompt_version=GENERATION_PROMPT_VERSION, config_hash=self.config_hash,
        )
        cached = self._read("generation", key)
        if cached:
            value = dict(cached["value"])
            value["usage_source"] = f"cache:{value.get('usage_source', 'unknown')}"
            return self._apply_cost(ProviderGenerationResult(**value))
        value = self.wrapped.generate_with_usage(messages, model=model, temperature=temperature)
        value = self._apply_cost(value)
        self._write("generation", key, identity, value.to_dict())
        return value

    def _apply_cost(self, value: ProviderGenerationResult) -> ProviderGenerationResult:
        if not self.pricing:
            return value
        cost = (
            value.input_tokens / 1_000_000 * self.pricing["input_per_million"]
            + value.output_tokens / 1_000_000 * self.pricing["output_per_million"]
        )
        return replace(value, cost=round(cost, 10))


def load_pricing(path: Path | None, model: str) -> tuple[dict[str, float] | None, str]:
    if path is None:
        return None, "NO_LOCAL_PRICING_CONFIG"
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    row = value.get(model)
    if not isinstance(row, dict) or not {"input_per_million", "output_per_million"}.issubset(row):
        raise ValueError(f"Local pricing configuration has no complete entry for {model}")
    return {
        "input_per_million": float(row["input_per_million"]),
        "output_per_million": float(row["output_per_million"]),
    }, "LOCAL_PRICING_CONFIG"


def estimate_evaluation(
    *, query_input_path: Path, corpus_fixture_path: Path, max_cases: int | None,
    provider: str, pricing_config: Path | None,
) -> dict[str, Any]:
    queries = load_query_inputs(query_input_path)
    documents, _, _ = load_corpus_fixture(corpus_fixture_path)
    selected = queries[:max_cases] if max_cases is not None else queries
    corpus_text = " ".join(page for document in documents for page in document.pages)
    # A transparent local estimate, not provider-billed tokenizer output.
    corpus_tokens = max(1, (len(corpus_text) + 3) // 4)
    query_tokens = sum(max(1, (len(item.query_text) + 3) // 4) for item in selected)
    estimated_input = query_tokens + len(selected) * min(corpus_tokens, 4096)
    estimated_output = len(selected) * 512
    pricing, pricing_status = load_pricing(pricing_config, GENERATION_MODEL)
    projected_cost = None
    if pricing:
        projected_cost = round(
            estimated_input / 1_000_000 * pricing["input_per_million"]
            + estimated_output / 1_000_000 * pricing["output_per_million"],
            8,
        )
    config = ReadinessConfig(provider=provider)
    return {
        "status": READINESS_STATUS,
        "provider": provider,
        "network_called": False,
        "case_count": len(selected),
        "available_case_count": len(queries),
        "estimated_input_tokens": estimated_input,
        "estimated_output_tokens": estimated_output,
        "token_estimate_method": "UTF-8 character count divided by four plus fixed 512-token output budget per case",
        "projected_cost": projected_cost,
        "pricing_status": pricing_status,
        "fixed_config": asdict(config) | {"config_hash": config.config_hash},
    }
