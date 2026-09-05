from __future__ import annotations

from pathlib import Path
from typing import Any

from .manifest import ensure_not_frozen
from .schemas import RunRecord, canonical_json


CALL_COUNT_KEYS = ("embedding_calls", "generation_calls", "keyword_routing_calls")


def empty_usage(*, include_call_counts: bool = True) -> dict[str, Any]:
    usage: dict[str, Any] = {
        "embedding_calls": 0,
        "generation_calls": 0,
        "keyword_routing_calls": 0,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "latency_ms": None,
        "errors": [],
        "retries": 0,
    }
    if not include_call_counts:
        for key in CALL_COUNT_KEYS:
            usage.pop(key)
    return usage


def merge_usage(*items: dict[str, Any] | None) -> dict[str, Any]:
    present = [item for item in items if item]
    include_call_counts = any(any(key in item for key in CALL_COUNT_KEYS) for item in present)
    merged = empty_usage(include_call_counts=include_call_counts)
    for item in present:
        if include_call_counts:
            for key in CALL_COUNT_KEYS:
                merged[key] += int(item.get(key) or 0)
        for token_key in ("input_tokens", "output_tokens", "total_tokens"):
            value = item.get(token_key)
            if value is not None:
                merged[token_key] = (merged[token_key] or 0) + int(value)
        latency = item.get("latency_ms")
        if latency is not None:
            merged["latency_ms"] = (merged["latency_ms"] or 0.0) + float(latency)
        merged["errors"].extend(str(error) for error in (item.get("errors") or []))
        merged["retries"] += int(item.get("retries") or 0)
    return merged


def append_run_record(path: str | Path, record: RunRecord, *, include_protected_content: bool = False) -> None:
    destination = Path(path)
    ensure_not_frozen(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(record.to_dict(include_protected_content=include_protected_content)) + "\n")


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
