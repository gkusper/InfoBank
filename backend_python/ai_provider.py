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


PROVIDER_CONFIG_VERSION = "infocom-provider-v2"
KEYWORD_SELECTION_STRATEGY_VERSION = "infocom-keyword-selector-v2"
OPENAI_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def _keyword_tokens(value: str) -> tuple[str, ...]:
    """Return stable lexical tokens used only against an allowed vocabulary."""

    return tuple(re.findall(r"[^\W_]+", str(value).casefold(), flags=re.UNICODE))


def deterministic_allowed_keyword_matches(
    text: str,
    available_keywords: Sequence[str] | None,
    *,
    limit: int = 5,
) -> list[str]:
    """Select explicit question/keyword overlaps without expanding governance.

    The caller supplies the already permitted vocabulary. A keyword matches
    only when all of its lexical tokens occur in the question; contiguous
    phrase matches rank first, followed by more specific (multi-token) values
    and a stable lexical tie-break. No synonym inference is attempted here --
    that remains the provider's optional contribution.
    """

    if limit <= 0 or not available_keywords:
        return []
    question_tokens = _keyword_tokens(text)
    if not question_tokens:
        return []
    question_token_set = set(question_tokens)
    canonical_by_key: dict[str, str] = {}
    for value in sorted((str(item).strip() for item in available_keywords), key=lambda item: (item.casefold(), item)):
        if value:
            canonical_by_key.setdefault(value.casefold(), value)

    ranked: list[tuple[int, int, str, str]] = []
    for key, canonical in canonical_by_key.items():
        tokens = _keyword_tokens(canonical)
        if not tokens or not set(tokens).issubset(question_token_set):
            continue
        phrase_match = any(
            question_tokens[index:index + len(tokens)] == tokens
            for index in range(len(question_tokens) - len(tokens) + 1)
        )
        ranked.append((0 if phrase_match else 1, -len(tokens), key, canonical))
    return [item[3] for item in sorted(ranked)[:limit]]


def reconcile_keyword_selection(
    text: str,
    *,
    available_keywords: Sequence[str] | None,
    provider_keywords: Sequence[str],
    provider_trace: dict[str, Any],
    limit: int = 5,
) -> tuple[list[str], dict[str, Any]]:
    """Merge deterministic allowed-vocabulary anchors with provider output."""

    anchors = deterministic_allowed_keyword_matches(text, available_keywords, limit=limit)
    allowed_lookup = {
        str(item).strip().casefold(): str(item).strip()
        for item in available_keywords or ()
        if str(item).strip()
    }
    provider_values: list[str] = []
    for value in provider_keywords:
        normalized = str(value).strip()
        if available_keywords is not None:
            normalized = allowed_lookup.get(normalized.casefold(), "")
        if normalized and normalized not in provider_values:
            provider_values.append(normalized)

    selected: list[str] = []
    for value in [*anchors, *provider_values]:
        if value not in selected:
            selected.append(value)
        if len(selected) >= limit:
            break

    trace = dict(provider_trace)
    provider_outcome = str(trace.get("outcome") or "no_selection_unclassified")
    if anchors and provider_values:
        outcome = "selected_with_deterministic_anchor"
    elif anchors:
        outcome = "deterministic_recovery"
    else:
        outcome = provider_outcome
    trace.update({
        "selection_strategy_version": KEYWORD_SELECTION_STRATEGY_VERSION,
        "provider_outcome": provider_outcome,
        "provider_selected_keyword_count": len(provider_values),
        "deterministic_match_count": len(anchors),
        "selected_keyword_count": len(selected),
        "outcome": outcome,
    })
    return selected, trace


def keyword_provider_error_fallback(
    text: str,
    *,
    available_keywords: Sequence[str] | None,
    limit: int,
    provider: str,
    adapter: str,
    prompt_version: str,
) -> tuple[list[str], dict[str, Any]]:
    """Recover deterministically after a routing-keyword provider failure."""

    available_count = None if available_keywords is None else len({
        str(item).strip().casefold() for item in available_keywords if str(item).strip()
    })
    base_trace = {
        "provider": provider,
        "adapter": adapter,
        "prompt_version": prompt_version,
        "available_keyword_count": available_count,
        "parsed_item_count": 0,
        "selected_keyword_count": 0,
        "rejected_item_count": 0,
        "outcome": "provider_error",
    }
    return reconcile_keyword_selection(
        text,
        available_keywords=available_keywords,
        provider_keywords=(),
        provider_trace=base_trace,
        limit=limit,
    )


def canonical_provider_name(name: str) -> str:
    normalized = name.strip().lower()
    if normalized == "openai":
        return "openai"
    if normalized in {"deterministic", "deterministic-mock", "mock"}:
        return "deterministic-mock"
    if normalized in {"local", "local-compatible"}:
        return "local-compatible"
    raise RuntimeError(
        f"Unsupported AI_PROVIDER={name!r}. Expected one of: openai, deterministic-mock, local-compatible."
    )


def _embedding_dimension_override() -> int | None:
    raw_value = os.getenv("AI_EMBEDDING_DIMENSIONS", "").strip()
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("AI_EMBEDDING_DIMENSIONS must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError("AI_EMBEDDING_DIMENSIONS must be a positive integer")
    return value


def embedding_dimensions(provider_name: str, model: str) -> int:
    """Return the configured vector size without making a provider request."""

    provider = canonical_provider_name(provider_name)
    if provider in {"deterministic-mock", "local-compatible"}:
        return 24
    override = _embedding_dimension_override()
    if override is not None:
        if not model.startswith("text-embedding-3-"):
            raise RuntimeError(
                "AI_EMBEDDING_DIMENSIONS is supported only for OpenAI text-embedding-3 models"
            )
        return override
    try:
        return OPENAI_EMBEDDING_DIMENSIONS[model]
    except KeyError as exc:
        raise RuntimeError(
            f"Unknown OpenAI embedding dimensions for model {model!r}; "
            "use a supported model or set AI_EMBEDDING_DIMENSIONS for a text-embedding-3 model"
        ) from exc


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

    def extract_keywords_with_trace(
        self,
        text: str,
        *,
        model: str,
        prompt: str,
        prompt_version: str,
        available_keywords: Sequence[str] | None = None,
        limit: int = 5,
    ) -> tuple[list[str], dict[str, Any]]:
        """Return keywords plus a content-free selection outcome trace.

        The default keeps third-party/provider wrappers compatible while
        allowing adapters with access to the raw response to report a more
        precise outcome.  Traces contain counts and classifications only;
        source text, provider output, and keyword values are deliberately
        excluded.
        """

        values = self.extract_keywords(
            text,
            model=model,
            prompt=prompt,
            prompt_version=prompt_version,
            available_keywords=available_keywords,
            limit=limit,
        )
        return values, self._keyword_selection_trace(
            prompt_version=prompt_version,
            available_keywords=available_keywords,
            selected_count=len(values),
            parsed_item_count=len(values),
            rejected_item_count=0,
            outcome="selected" if values else "no_selection_unclassified",
        )

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

    def _keyword_selection_trace(
        self,
        *,
        prompt_version: str,
        available_keywords: Sequence[str] | None,
        selected_count: int,
        parsed_item_count: int,
        rejected_item_count: int,
        outcome: str,
    ) -> dict[str, Any]:
        available_count = None
        if available_keywords is not None:
            available_count = len({str(item).strip().casefold() for item in available_keywords if str(item).strip()})
        return {
            "provider": self.provider_name,
            "adapter": self.adapter_name,
            "prompt_version": prompt_version,
            "available_keyword_count": available_count,
            "parsed_item_count": int(parsed_item_count),
            "selected_keyword_count": int(selected_count),
            "rejected_item_count": int(rejected_item_count),
            "outcome": outcome,
        }


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
        values, _ = self.extract_keywords_with_trace(
            text,
            model=model,
            prompt=prompt,
            prompt_version=prompt_version,
            available_keywords=available_keywords,
            limit=limit,
        )
        return values

    def extract_keywords_with_trace(
        self,
        text: str,
        *,
        model: str,
        prompt: str,
        prompt_version: str,
        available_keywords: Sequence[str] | None = None,
        limit: int = 5,
    ) -> tuple[list[str], dict[str, Any]]:
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
        allowed_lookup = {item.casefold(): item for item in available_keywords or ()}
        values: list[str] = []
        parsed_items = [] if raw.upper() == "NONE" else [item.strip() for item in raw.split(",") if item.strip()]
        rejected_item_count = 0
        for normalized in parsed_items:
            if available_keywords is not None:
                matched = allowed_lookup.get(normalized.casefold(), "")
                if not matched:
                    rejected_item_count += 1
                normalized = matched
            if normalized and normalized not in values:
                values.append(normalized)
        values = values[:limit]
        if raw.upper() == "NONE":
            outcome = "provider_none"
        elif values:
            outcome = "selected"
        elif not parsed_items:
            outcome = "empty_response"
        elif available_keywords is not None:
            outcome = "parser_rejected"
        else:
            outcome = "no_selection_unclassified"
        provider_trace = self._keyword_selection_trace(
            prompt_version=prompt_version,
            available_keywords=available_keywords,
            selected_count=len(values),
            parsed_item_count=len(parsed_items),
            rejected_item_count=rejected_item_count,
            outcome=outcome,
        )
        return reconcile_keyword_selection(
            text,
            available_keywords=available_keywords,
            provider_keywords=values,
            provider_trace=provider_trace,
            limit=limit,
        )

    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        request: dict[str, Any] = {"input": list(texts), "model": model}
        dimensions = _embedding_dimension_override()
        if dimensions is not None:
            if not model.startswith("text-embedding-3-"):
                raise RuntimeError(
                    "AI_EMBEDDING_DIMENSIONS is supported only for OpenAI text-embedding-3 models"
                )
            request["dimensions"] = dimensions
        response = self._get_client().embeddings.create(**request)
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

    def extract_keywords_with_trace(
        self,
        text: str,
        *,
        model: str,
        prompt: str,
        prompt_version: str,
        available_keywords: Sequence[str] | None = None,
        limit: int = 5,
    ) -> tuple[list[str], dict[str, Any]]:
        values = self.extract_keywords(
            text,
            model=model,
            prompt=prompt,
            prompt_version=prompt_version,
            available_keywords=available_keywords,
            limit=limit,
        )
        if values:
            outcome = "selected"
        elif available_keywords is not None and not available_keywords:
            outcome = "no_available_keywords"
        elif available_keywords is not None:
            outcome = "no_overlap"
        elif not self._tokens(text):
            outcome = "empty_input"
        else:
            outcome = "no_selection_unclassified"
        return values, self._keyword_selection_trace(
            prompt_version=prompt_version,
            available_keywords=available_keywords,
            selected_count=len(values),
            parsed_item_count=len(values),
            rejected_item_count=0,
            outcome=outcome,
        )

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
        system_text = "\n".join(message.get("content", "") for message in messages if message.get("role") == "system")
        user_text = "\n".join(message.get("content", "") for message in messages if message.get("role") == "user")
        if "prompt-only governance baseline" in system_text.lower():
            source_text = re.search(r"Retrieved sources:\s*(.+)", user_text, flags=re.DOTALL)
            source_body = source_text.group(1).strip() if source_text else ""
            question_match = re.search(r"Question:\s*(.+?)(?:\n|$)", user_text)
            question = question_match.group(1) if question_match else ""
            non_denied_source_available = any(
                f"policy_label: {label}" in source_body
                for label in ("Full", "Aggregate", "Metadata")
            )
            facts: list[str] = []
            for block in re.split(r"\n\s*---\s*\n", source_body):
                text_match = re.search(r"text:\s*(.+)", block, flags=re.DOTALL)
                if text_match:
                    facts.append(re.sub(r"\s+", " ", text_match.group(1)).strip())
            question_tokens = set(self._tokens(question))
            ranked = sorted(
                facts,
                key=lambda fact: (
                    -len(question_tokens.intersection(self._tokens(fact))),
                    facts.index(fact),
                ),
            )
            if not non_denied_source_available:
                return json.dumps(
                    {
                        "output_class": "REFUSE_PERMISSION",
                        "reason_code": "permission_refusal",
                        "answer": "The request cannot be answered from the sources available for this purpose.",
                    },
                    sort_keys=True,
                )
            return json.dumps(
                {
                    "output_class": "FULL_ANSWER",
                    "reason_code": "supported",
                    "answer": (ranked[0] if ranked else "The answer cannot be found in the document.")[:640],
                },
                sort_keys=True,
            )
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
    normalized = canonical_provider_name(name)
    if normalized == "openai":
        return OpenAIProvider(client_factory=openai_client_factory)
    if normalized == "deterministic-mock":
        return DeterministicMockProvider()
    if normalized == "local-compatible":
        return LocalCompatibleProvider()
    raise AssertionError(f"Unhandled canonical provider: {normalized}")
