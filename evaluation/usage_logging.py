from __future__ import annotations

from pathlib import Path
from typing import Any

from .manifest import ensure_not_frozen
from .schemas import RunRecord, canonical_json


def empty_usage() -> dict[str, Any]:
    return {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "latency_ms": None,
        "errors": [],
        "retries": 0,
    }


def merge_usage(*items: dict[str, Any] | None) -> dict[str, Any]:
    merged = empty_usage()
    for item in items:
        if not item:
            continue
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
