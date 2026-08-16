from __future__ import annotations

from typing import Any


def empty_usage() -> dict[str, Any]:
    return {
        "embedding_calls": 0,
        "generation_calls": 0,
        "keyword_routing_calls": 0,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "errors": [],
        "retries": 0,
    }


def merge_usage(*items: dict[str, Any] | None) -> dict[str, Any]:
    merged = empty_usage()
    for item in items:
        if not item:
            continue
        for key in ["embedding_calls", "generation_calls", "keyword_routing_calls", "retries"]:
            merged[key] += int(item.get(key) or 0)
        for token_key in ["input_tokens", "output_tokens", "total_tokens"]:
            value = item.get(token_key)
            if value is not None:
                merged[token_key] = (merged[token_key] or 0) + int(value)
        merged["errors"].extend(item.get("errors") or [])
    return merged


def usage_from_openai_response(response: Any, *, generation_calls: int = 0, embedding_calls: int = 0) -> dict[str, Any]:
    usage = empty_usage()
    usage["generation_calls"] = generation_calls
    usage["embedding_calls"] = embedding_calls
    raw = getattr(response, "usage", None)
    if not raw:
        return usage
    usage["input_tokens"] = getattr(raw, "prompt_tokens", None) or getattr(raw, "input_tokens", None)
    usage["output_tokens"] = getattr(raw, "completion_tokens", None) or getattr(raw, "output_tokens", None)
    usage["total_tokens"] = getattr(raw, "total_tokens", None)
    return usage
