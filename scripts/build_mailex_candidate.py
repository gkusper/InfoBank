"""Select a thread-preserving MailEx candidate without committing raw mail.

The input is JSON or JSONL. Each thread must contain ``thread_id`` and a
``messages`` list; each message must contain ``message_id``, ``sender``,
``recipients``, ``subject``, ``body`` and ``timestamp``. The derived output is
intended for an ignored artifact directory and still requires licence review
and human annotation before any freeze.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


NO_HEALTH_TERMS = {
    "patient", "diagnosis", "diagnostic", "medical", "medicine", "medication",
    "treatment", "therapy", "hospital", "disease", "symptom", "clinical", "healthcare",
}


def _load(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    return value["threads"] if isinstance(value, dict) else value


def _alias(address: str) -> str:
    digest = hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()[:12]
    return f"mailbox-{digest}@example.invalid"


def _contains_excluded_term(value: Any) -> list[str]:
    text = json.dumps(value, ensure_ascii=False).lower()
    return sorted(term for term in NO_HEALTH_TERMS if re.search(rf"\b{re.escape(term)}\b", text))


def build(source: Path, output: Path, licence_id: str, limit: int) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing candidate output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    selected, excluded = [], []
    for thread in _load(source):
        hits = _contains_excluded_term(thread)
        if hits:
            excluded.append({"thread_id": thread.get("thread_id", "UNKNOWN"), "reason": "NO_HEALTH_EXCLUSION", "terms": hits})
            continue
        messages = []
        for message in thread["messages"]:
            messages.append({
                **message,
                "sender": _alias(message["sender"]),
                "recipients": [_alias(value) for value in message["recipients"]],
            })
        selected.append({
            "thread_id": str(thread["thread_id"]), "messages": messages,
            "source": "mailex-derived-candidate", "requires_human_annotation": True,
        })
        if len(selected) == limit:
            break
    (output / "threads.json").write_text(json.dumps({"threads": selected}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "no_health_exclusion_log.json").write_text(json.dumps({"excluded": excluded}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "source_path_committed": False, "raw_source_committed": False, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "licence_id": licence_id, "licence_review_status": "PENDING_HUMAN_CONFIRMATION",
        "thread_preserved": True, "selected_thread_count": len(selected), "excluded_thread_count": len(excluded),
        "human_annotation_complete": False, "adjudication_complete": False,
    }
    (output / "provenance_manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--licence-id", required=True)
    parser.add_argument("--limit", type=int, default=120)
    args = parser.parse_args()
    if args.limit < 100:
        parser.error("--limit must be at least 100 for the reviewer-v2 candidate")
    print(json.dumps(build(args.source, args.output, args.licence_id, args.limit), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
