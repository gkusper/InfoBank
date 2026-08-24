from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[2]
BENCHMARK_DIR = REPO_ROOT / "experiments" / "iscmi2026" / "benchmark"
DEFAULT_PACKET_DIR = REPO_ROOT.parent / "mailex_pilot_external_packet"
CONDITIONS = ("STANDARD_RAG", "THREAD_AWARE_RAG", "ORACLE_TASK_STATE_RAG")
ANSWER_TYPES = {
    "TASK_SET",
    "TASK_ATTRIBUTE_MAP",
    "TASK_HISTORY",
    "NO_TASK",
    "INSUFFICIENT_EVIDENCE",
}
FORBIDDEN_GOLD_FIELDS = {
    "gold_answer",
    "gold_structured",
    "expected_answer",
    "score",
    "is_correct",
}
BASELINE_DOCUMENT_KEYS = {
    "document_id",
    "document_type",
    "pilot_id",
    "thread_id",
    "message_id",
    "chronological_rank",
    "sender",
    "recipients",
    "cc",
    "bcc",
    "date",
    "subject",
    "text",
}
SHARED_GENERATION_KEYS = (
    "generator_model",
    "embedding_model",
    "temperature",
    "max_output_tokens",
    "top_p",
    "seed",
)


SYSTEM_PROMPT = """You answer todo-oriented questions using only the supplied knowledge blocks. Do not use outside knowledge or infer unsupported task facts. Return exactly one JSON object with this schema:
{
  "answer_type": "TASK_SET|TASK_ATTRIBUTE_MAP|TASK_HISTORY|NO_TASK|INSUFFICIENT_EVIDENCE",
  "tasks": [
    {
      "task_id": "internal identifier or null",
      "task_summary": "short source-grounded description or null",
      "final_state": "OPEN|CLOSED|UNCERTAIN|null",
      "actor": "string or null",
      "requester": "string or null",
      "deadline": "YYYY-MM-DD or null",
      "waiting_for": "string or null",
      "blocked_by": "string or null",
      "closure_reason": "string or null",
      "events": [
        {
          "transition": "CREATE|CONFIRM|MODIFY|COMPLETE|CANCEL|REJECT|NONE",
          "resulting_state": "OPEN|CLOSED|UNCERTAIN",
          "message_id": "source message ID"
        }
      ],
      "evidence_message_ids": ["source message ID"]
    }
  ],
  "none": false,
  "evidence_message_ids": ["source message ID"],
  "controlled_failure": false,
  "failure_reason": null
}
Use NO_TASK only when the evidence supports that the asked message/conversation has no tracked task. Use INSUFFICIENT_EVIDENCE with controlled_failure=true when the evidence cannot justify an answer. Keep internal task IDs in JSON only; do not invent IDs when they are absent from the supplied knowledge."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_packet_dir(value: str | Path | None = None) -> Path:
    candidate = Path(value) if value else Path(os.environ.get("MAILEX_PILOT_PACKET", DEFAULT_PACKET_DIR))
    candidate = candidate.expanduser().resolve()
    if not candidate.is_dir():
        raise FileNotFoundError(
            f"Corrected MailEx packet not found at {candidate}. "
            "Pass --packet-dir or set MAILEX_PILOT_PACKET."
        )
    return candidate


def load_benchmark() -> dict[str, Any]:
    questions = read_jsonl(BENCHMARK_DIR / "questions.jsonl")
    histories = read_jsonl(BENCHMARK_DIR / "task_histories.jsonl")
    snapshots = read_jsonl(BENCHMARK_DIR / "task_snapshots.jsonl")
    evidence = read_jsonl(BENCHMARK_DIR / "message_evidence_index.jsonl")
    manifest = read_json(BENCHMARK_DIR / "benchmark_manifest.json")
    question_ids = [row["question_id"] for row in questions]
    if len(questions) != 271:
        raise ValueError(f"Expected 271 benchmark questions, found {len(questions)}")
    if len(set(question_ids)) != len(question_ids):
        raise ValueError("Benchmark question IDs are not unique")
    return {
        "questions": questions,
        "histories": histories,
        "snapshots": snapshots,
        "evidence": evidence,
        "manifest": manifest,
    }


def load_configs(config_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    config_dir = config_dir or EXPERIMENT_DIR / "configs"
    configs: dict[str, dict[str, Any]] = {}
    for path in sorted(config_dir.glob("*.json")):
        config = read_json(path)
        condition = config.get("condition")
        if condition in configs:
            raise ValueError(f"Duplicate condition config: {condition}")
        configs[str(condition)] = config
    if set(configs) != set(CONDITIONS):
        raise ValueError(f"Expected configs for {CONDITIONS}, found {tuple(configs)}")
    first = configs[CONDITIONS[0]]
    for condition in CONDITIONS[1:]:
        for key in SHARED_GENERATION_KEYS:
            if configs[condition].get(key) != first.get(key):
                raise ValueError(f"Generator setting {key} differs for {condition}")
    return configs


def _metadata_value(block: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}:\s*(.*)$", block, flags=re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip().strip("`")


def parse_corrected_packet(packet_dir: Path, evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected = {row["message_id"]: row for row in evidence_rows}
    documents: list[dict[str, Any]] = []
    threads_dir = packet_dir / "threads"
    if not threads_dir.is_dir():
        raise FileNotFoundError(f"Packet threads directory not found: {threads_dir}")
    for source_file in sorted({row["source_file"] for row in evidence_rows}):
        path = threads_dir / source_file
        text = path.read_text(encoding="utf-8-sig")
        starts = list(re.finditer(r"^## Message\s+\d+\s*$", text, flags=re.MULTILINE))
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
            block = text[start.start() : end]
            if "### Body" not in block or "### Original MailEx annotations" not in block:
                raise ValueError(f"Malformed message block in {path.name}")
            metadata, remainder = block.split("### Body", 1)
            body, _ignored_annotations = remainder.split("### Original MailEx annotations", 1)
            message_id = _metadata_value(metadata, "Message ID")
            if message_id not in expected:
                raise ValueError(f"Unexpected message ID {message_id!r} in {path.name}")
            expected_row = expected[message_id]
            rank_text = _metadata_value(metadata, "Chronological rank")
            rank = int(rank_text)
            if rank != int(expected_row["chronological_rank"]):
                raise ValueError(f"Rank mismatch for {message_id}: {rank} != {expected_row['chronological_rank']}")
            document = {
                "document_id": message_id,
                "document_type": "original_email_message",
                "pilot_id": expected_row["pilot_id"],
                "thread_id": expected_row["thread_id"],
                "message_id": message_id,
                "chronological_rank": rank,
                "sender": _metadata_value(metadata, "Sender"),
                "recipients": _metadata_value(metadata, "Recipients"),
                "cc": _metadata_value(metadata, "CC"),
                "bcc": _metadata_value(metadata, "BCC"),
                "date": _metadata_value(metadata, "Date"),
                "subject": _metadata_value(metadata, "Subject"),
            }
            document["text"] = format_email_document(document, body.strip())
            if set(document) != BASELINE_DOCUMENT_KEYS:
                raise AssertionError("Baseline email document schema changed unexpectedly")
            documents.append(document)
    found = {doc["message_id"] for doc in documents}
    if found != set(expected):
        missing = sorted(set(expected) - found)
        extra = sorted(found - set(expected))
        raise ValueError(f"Corrected packet mismatch; missing={missing}, extra={extra}")
    if len(documents) != 195:
        raise ValueError(f"Expected 195 corrected messages, found {len(documents)}")
    return sorted(documents, key=lambda row: (row["pilot_id"], row["chronological_rank"]))


def format_email_document(document: dict[str, Any], body: str) -> str:
    lines = [
        "Original email message",
        f"Message ID: {document['message_id']}",
        f"Thread ID: {document['thread_id']}",
        f"Chronological rank: {document['chronological_rank']}",
        f"Date: {document['date'] or 'unknown'}",
        f"Sender: {document['sender'] or 'unknown'}",
        f"Recipients: {document['recipients'] or 'unknown'}",
        f"CC: {document['cc'] or 'none'}",
        f"BCC: {document['bcc'] or 'none'}",
        f"Subject: {document['subject'] or '(no subject)'}",
        "Body:",
        body,
    ]
    return "\n".join(lines)


def build_oracle_documents(
    histories: list[dict[str, Any]], snapshots: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    history_by_key = {(row["pilot_id"], row["task_id"]): row for row in histories}
    documents: list[dict[str, Any]] = []
    for snapshot in snapshots:
        key = (snapshot["pilot_id"], snapshot["task_id"])
        history = history_by_key[key]
        events = [
            {
                "message_id": event["message_id"],
                "chronological_rank": event["chronological_rank"],
                "transition": event["transition"],
                "resulting_state": event["resulting_state"],
                "requester": event.get("requester"),
                "actor": event.get("actor"),
                "created_at": event.get("created_at"),
                "deadline": event.get("deadline"),
                "completed_at": event.get("completed_at"),
                "closure_reason": event.get("closure_reason"),
                "waiting_for": event.get("waiting_for"),
                "blocked_by": event.get("blocked_by"),
            }
            for event in history["history"]
        ]
        oracle = {
            "document_id": f"oracle:{snapshot['pilot_id']}:{snapshot['task_id']}",
            "document_type": "oracle_task_state",
            "information_level": "human_derived_oracle_task_representation",
            "pilot_id": snapshot["pilot_id"],
            "thread_id": snapshot["thread_id"],
            "task_id": snapshot["task_id"],
            "final_state": snapshot["final_state"],
            "last_transition": snapshot["last_transition"],
            "requester": snapshot.get("requester"),
            "actor": snapshot.get("actor"),
            "created_at": snapshot.get("created_at"),
            "deadline": snapshot.get("deadline"),
            "completed_at": snapshot.get("completed_at"),
            "closure_reason": snapshot.get("closure_reason"),
            "waiting_for": snapshot.get("waiting_for"),
            "blocked_by": snapshot.get("blocked_by"),
            "evidence_message_ids": list(snapshot["evidence_message_ids"]),
            "history": events,
        }
        oracle["text"] = format_oracle_document(oracle)
        documents.append(oracle)
    return sorted(documents, key=lambda row: (row["pilot_id"], row["task_id"]))


def format_oracle_document(document: dict[str, Any]) -> str:
    def value(name: str) -> str:
        raw = document.get(name)
        return str(raw) if raw not in (None, "") else "unknown"

    lines = [
        "Oracle human-derived task-state record",
        f"Thread ID: {document['thread_id']}",
        f"Task ID (internal): {document['task_id']}",
        f"State: {document['final_state']}",
        f"Last transition: {document['last_transition']}",
        f"Requester: {value('requester')}",
        f"Actor: {value('actor')}",
        f"Created at: {value('created_at')}",
        f"Deadline: {value('deadline')}",
        f"Completed at: {value('completed_at')}",
        f"Closure reason: {value('closure_reason')}",
        f"Waiting for: {value('waiting_for')}",
        f"Blocked by: {value('blocked_by')}",
        "History:",
    ]
    for event in document["history"]:
        attributes = ", ".join(
            f"{key}={event[key]}"
            for key in (
                "requester",
                "actor",
                "created_at",
                "deadline",
                "completed_at",
                "closure_reason",
                "waiting_for",
                "blocked_by",
            )
            if event.get(key) not in (None, "")
        )
        suffix = f"; {attributes}" if attributes else ""
        lines.append(
            f"- rank {event['chronological_rank']}: {event['transition']} -> "
            f"{event['resulting_state']} [source {event['message_id']}]{suffix}"
        )
    lines.append("Evidence message IDs: " + ", ".join(document["evidence_message_ids"]))
    return "\n".join(lines)


def inference_question(question: dict[str, Any]) -> dict[str, str]:
    """Return only fields permitted before scoring."""
    return {
        "question_id": str(question["question_id"]),
        "question_family": str(question["question_family"]),
        "pilot_id": str(question["pilot_id"]),
        "thread_id": str(question["thread_id"]),
        "question": str(question["question"]),
    }


def build_prompt(question_text: str, context_documents: list[dict[str, Any]]) -> tuple[str, str]:
    blocks = []
    for index, document in enumerate(context_documents, start=1):
        blocks.append(f"[Knowledge block {index}: {document['document_id']}]\n{document['text']}")
    user_prompt = (
        f"Question:\n{question_text}\n\n"
        "Knowledge blocks:\n"
        + "\n\n---\n\n".join(blocks)
    )
    return SYSTEM_PROMPT, user_prompt


def deterministic_mock_embedding(text: str, dimensions: int = 128) -> list[float]:
    vector = [0.0] * dimensions
    for token in re.findall(r"[\w@.-]+", text.casefold()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def semantic_retrieve(
    *,
    question_embedding: list[float],
    candidates: list[dict[str, Any]],
    document_embeddings: dict[str, list[float]],
    top_k: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scored = [
        (cosine_similarity(question_embedding, document_embeddings[row["document_id"]]), row)
        for row in candidates
    ]
    scored.sort(key=lambda item: (-item[0], item[1]["document_id"]))
    selected = scored[:top_k]
    return [item[1] for item in selected], [
        {"context_id": item[1]["document_id"], "similarity": round(float(item[0]), 8)}
        for item in selected
    ]


def contexts_for_condition(
    *,
    condition: str,
    question: dict[str, str],
    email_documents: list[dict[str, Any]],
    oracle_documents: list[dict[str, Any]],
    question_embedding: list[float],
    document_embeddings: dict[str, list[float]],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    thread_emails = [
        row
        for row in email_documents
        if row["pilot_id"] == question["pilot_id"] and row["thread_id"] == question["thread_id"]
    ]
    seeds, scores = semantic_retrieve(
        question_embedding=question_embedding,
        candidates=thread_emails,
        document_embeddings=document_embeddings,
        top_k=int(config["retrieval_top_k"]),
    )
    if condition == "STANDARD_RAG":
        return apply_context_budget(seeds, int(config["context_character_budget"])), scores

    chronological = sorted(thread_emails, key=lambda row: (row["chronological_rank"], row["message_id"]))
    contexts = chronological
    if condition == "ORACLE_TASK_STATE_RAG":
        contexts = chronological + [
            row
            for row in oracle_documents
            if row["pilot_id"] == question["pilot_id"] and row["thread_id"] == question["thread_id"]
        ]
    selected = apply_context_budget(contexts, int(config["context_character_budget"]))
    seed_score_by_id = {row["context_id"]: row["similarity"] for row in scores}
    expanded_scores = [
        {"context_id": row["document_id"], "similarity": seed_score_by_id.get(row["document_id"])}
        for row in selected
    ]
    return selected, expanded_scores


def apply_context_budget(documents: list[dict[str, Any]], character_budget: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used = 0
    for document in documents:
        size = len(document["text"])
        if selected and used + size > character_budget:
            continue
        selected.append(document)
        used += size
    return selected


def parse_model_output(raw: str) -> tuple[dict[str, Any], str | None]:
    candidate = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    else:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        parsed = recover_truncated_json(candidate)
        if parsed is None:
            return controlled_failure_output(f"JSON parse error: {exc.msg}"), str(exc)
        parsed["_parser_recovery"] = "closed_at_last_complete_json_boundary"
    if not isinstance(parsed, dict):
        return controlled_failure_output("Top-level output is not an object"), "top_level_not_object"
    answer_type = str(parsed.get("answer_type", "")).upper()
    if answer_type not in ANSWER_TYPES:
        return controlled_failure_output(f"Unrecognized answer_type: {answer_type or 'missing'}"), "bad_answer_type"
    tasks = parsed.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
    normalized_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        events = task.get("events") if isinstance(task.get("events"), list) else []
        evidence_ids = task.get("evidence_message_ids")
        normalized_task = dict(task)
        normalized_task["events"] = [event for event in events if isinstance(event, dict)]
        normalized_task["evidence_message_ids"] = _string_list(evidence_ids)
        normalized_tasks.append(normalized_task)
    parsed["answer_type"] = answer_type
    parsed["tasks"] = normalized_tasks
    parsed["evidence_message_ids"] = _string_list(parsed.get("evidence_message_ids"))
    parsed["none"] = bool(parsed.get("none", False))
    parsed["controlled_failure"] = bool(
        parsed.get("controlled_failure", answer_type == "INSUFFICIENT_EVIDENCE")
    )
    parsed.setdefault("failure_reason", None)
    return parsed, None


def recover_truncated_json(candidate: str) -> dict[str, Any] | None:
    """Close containers after the latest complete JSON token boundary.

    The recovery never invents a value: it discards the incomplete suffix and
    retains only key/value pairs or array elements that the model fully emitted.
    """
    boundaries: list[int] = []
    in_string = False
    escaped = False
    for index, character in enumerate(candidate):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in ",}]":
            boundaries.append(index + 1)
    for boundary in reversed(boundaries):
        prefix = candidate[:boundary].rstrip()
        if prefix.endswith(","):
            prefix = prefix[:-1].rstrip()
        closers = json_container_closers(prefix)
        if closers is None:
            continue
        try:
            recovered = json.loads(prefix + closers)
        except json.JSONDecodeError:
            continue
        if isinstance(recovered, dict):
            return recovered
    return None


def json_container_closers(prefix: str) -> str | None:
    stack: list[str] = []
    in_string = False
    escaped = False
    for character in prefix:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "{[":
            stack.append(character)
        elif character in "}]":
            expected = "{" if character == "}" else "["
            if not stack or stack[-1] != expected:
                return None
            stack.pop()
    if in_string:
        return None
    return "".join("}" if character == "{" else "]" for character in reversed(stack))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item) for item in value if item not in (None, "")))


def controlled_failure_output(reason: str) -> dict[str, Any]:
    return {
        "answer_type": "INSUFFICIENT_EVIDENCE",
        "tasks": [],
        "none": False,
        "evidence_message_ids": [],
        "controlled_failure": True,
        "failure_reason": reason,
    }


def mock_model_output(question_text: str, context_documents: list[dict[str, Any]]) -> str:
    del question_text, context_documents
    return json.dumps(controlled_failure_output("mock dry-run; no semantic answer generated"), sort_keys=True)


def ensure_no_forbidden_fields(value: Any, location: str) -> None:
    violations: list[str] = []

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = str(key).casefold()
                if normalized in FORBIDDEN_GOLD_FIELDS:
                    violations.append(f"{path}.{key}")
                visit(child, f"{path}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")

    visit(value, location)
    if violations:
        raise ValueError("Forbidden benchmark target fields found: " + ", ".join(violations))


def group_by_thread(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["pilot_id"], row["thread_id"])].append(row)
    return grouped
