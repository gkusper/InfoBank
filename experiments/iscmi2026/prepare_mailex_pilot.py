#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import itertools
import json
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INDEX = SCRIPT_DIR / "mailex_pilot_index.csv"
WORD_RE = re.compile(r"[a-z0-9]+")
HEADER_RE = re.compile(r"^([A-Za-z-]+)\s*:\s*(.*)$")
ALIGNMENT_SCORE_MIN = 70.0
ALIGNMENT_MARGIN_MIN = 3.0


@dataclass
class Dataset:
    root: Path
    files: dict[str, bytes]

    def has(self, name: str) -> bool:
        return name in self.files

    def read_text(self, name: str) -> str:
        return self.files[name].decode("utf-8", errors="replace")


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("/")


def load_dataset(path: Path) -> Dataset:
    if not path.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {path}")
    if path.is_file():
        if not zipfile.is_zipfile(path):
            raise ValueError(f"Dataset file is not a ZIP archive: {path}")
        files: dict[str, bytes] = {}
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                files[normalize_path(info.filename)] = archive.read(info)
        return Dataset(path, files)
    if path.is_dir():
        files = {}
        for file_path in path.rglob("*"):
            if file_path.is_file():
                files[file_path.relative_to(path).as_posix()] = file_path.read_bytes()
        return Dataset(path, files)
    raise ValueError(f"Unsupported dataset path: {path}")


def load_index(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Pilot index not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = [f"P{index:03d}" for index in range(1, 51)]
    observed = [row.get("pilot_id", "") for row in rows]
    if observed != expected:
        raise ValueError("Pilot index must contain exactly P001 through P050 in order")
    return rows


def normalize_tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        tokens: list[str] = []
        for item in value:
            tokens.extend(normalize_tokens(item))
        return tokens
    return []


def detokenize(tokens: list[str]) -> str:
    text = " ".join(tokens)
    text = re.sub(r"\s+([,.;?!:)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalized_words(value: str) -> list[str]:
    return WORD_RE.findall(value.lower())


def normalized_text(value: str) -> str:
    return " ".join(normalized_words(value))


def token_f1(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    right_set = set(right)
    overlap = sum(1 for token in left if token in right_set)
    precision = overlap / len(right)
    recall = overlap / len(left)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def parse_raw_messages(raw_text: str) -> list[dict[str, str]]:
    parts = [part.strip() for part in re.split(r"\n-{5,}\n", raw_text) if part.strip()]
    messages = []
    for raw_index, part in enumerate(parts):
        headers: dict[str, str] = {}
        body_lines: list[str] = []
        in_header = True
        for line in part.splitlines():
            match = HEADER_RE.match(line)
            if in_header and match:
                headers[match.group(1).upper()] = match.group(2).strip()
            else:
                in_header = False
                body_lines.append(line)
        messages.append(
            {
                "raw_index": str(raw_index),
                "from": headers.get("FROM", ""),
                "to": headers.get("TO", ""),
                "cc": headers.get("CC", ""),
                "bcc": headers.get("BCC", ""),
                "date": headers.get("DATE", ""),
                "subject": headers.get("SUBJECT", ""),
                "body": "\n".join(body_lines).strip(),
                "raw_text": part,
            }
        )
    return messages


def raw_thread_candidates(thread_id: str) -> list[str]:
    return [
        f"data/raw_threads/{thread_id}",
        f"data/raw_threads/{thread_id}.",
    ]


def load_thread(dataset: Dataset, row: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    source_path = normalize_path(row.get("source_path", ""))
    if not dataset.has(source_path):
        raise FileNotFoundError(f"Selected thread not found in dataset: {source_path}")
    thread = json.loads(dataset.read_text(source_path))
    raw_messages: list[dict[str, str]] = []
    for raw_path in raw_thread_candidates(row["thread_id"]):
        if dataset.has(raw_path):
            raw_messages = parse_raw_messages(dataset.read_text(raw_path))
            break
    return thread, raw_messages


def trigger_words(event_map: dict[str, Any]) -> list[str]:
    words = []
    for event_data in event_map.values():
        for trigger in event_data.get("triggers", []) or []:
            if not trigger:
                continue
            try:
                parsed = ast.literal_eval(trigger)
                value = parsed.get("words", "") if isinstance(parsed, dict) else parsed
            except (SyntaxError, ValueError):
                value = trigger
            value = str(value).strip()
            if value:
                words.append(value)
    return words


def trigger_hit_ratio(triggers: list[str], raw_body: str, raw_text: str) -> float | None:
    normalized_raw = f"{normalized_text(raw_body)} {normalized_text(raw_text)}"
    normalized_triggers = [normalized_text(trigger) for trigger in triggers if normalized_text(trigger)]
    if not normalized_triggers:
        return None
    hits = sum(1 for trigger in normalized_triggers if trigger in normalized_raw)
    return hits / len(normalized_triggers)


def alignment_score(json_text: str, raw_message: dict[str, str], triggers: list[str]) -> float:
    json_norm = normalized_text(json_text)
    body_norm = normalized_text(raw_message.get("body", ""))
    raw_norm = normalized_text(raw_message.get("raw_text", ""))
    json_words = normalized_words(json_text)
    body_words = normalized_words(raw_message.get("body", ""))
    raw_words = normalized_words(raw_message.get("raw_text", ""))

    if not json_norm and not body_norm:
        text_score = 100.0
    elif not json_norm:
        text_score = 0.0
    else:
        body_exact = json_norm == body_norm and bool(body_norm)
        body_contains = bool(body_norm) and (json_norm in body_norm or body_norm in json_norm)
        raw_contains = bool(raw_norm) and (json_norm in raw_norm or raw_norm in json_norm)
        body_f1 = token_f1(json_words, body_words)
        raw_f1 = token_f1(json_words, raw_words)
        body_seq = SequenceMatcher(None, json_norm, body_norm).ratio() if body_norm else 0.0
        raw_seq = SequenceMatcher(None, json_norm, raw_norm).ratio() if raw_norm else 0.0
        text_score = max(
            100.0 if body_exact else 0.0,
            95.0 if body_contains else 0.0,
            85.0 if raw_contains else 0.0,
            90.0 * body_f1,
            75.0 * raw_f1,
            70.0 * body_seq,
            55.0 * raw_seq,
        )

    length_bonus = 0.0
    if json_norm and body_norm:
        length_bonus = 5.0 * min(len(json_norm), len(body_norm)) / max(len(json_norm), len(body_norm))
    trigger_ratio = trigger_hit_ratio(triggers, raw_message.get("body", ""), raw_message.get("raw_text", ""))
    trigger_bonus = 0.0 if trigger_ratio is None else 10.0 * trigger_ratio
    return text_score + length_bonus + trigger_bonus


def best_one_to_one_alignment(score_matrix: list[list[float]]) -> tuple[dict[int, int], float]:
    turn_count = len(score_matrix)
    raw_count = len(score_matrix[0]) if score_matrix else 0
    if turn_count == 0 or raw_count == 0:
        return {}, 0.0
    if raw_count < turn_count:
        return {}, 0.0
    if raw_count <= 9:
        best_score = -1.0
        best_mapping: dict[int, int] = {}
        for permutation in itertools.permutations(range(raw_count), turn_count):
            score = sum(score_matrix[turn_index][raw_index] for turn_index, raw_index in enumerate(permutation))
            if score > best_score:
                best_score = score
                best_mapping = {turn_index: raw_index for turn_index, raw_index in enumerate(permutation)}
        return best_mapping, best_score

    # This is not expected for the 50-thread pilot, but keeps the script usable
    # for larger local checks without duplicating raw messages.
    remaining = set(range(raw_count))
    mapping = {}
    total = 0.0
    for turn_index, scores in enumerate(score_matrix):
        raw_index = max(remaining, key=lambda candidate: scores[candidate])
        mapping[turn_index] = raw_index
        total += scores[raw_index]
        remaining.remove(raw_index)
    return mapping, total


def align_raw_messages(thread: dict[str, Any], raw_messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    sentences = thread.get("sentences", [])
    events = thread.get("events", {})
    json_texts = [detokenize(normalize_tokens(sentence)) for sentence in sentences]
    score_matrix = []
    for turn_index, json_text in enumerate(json_texts):
        triggers = trigger_words(events.get(f"turn_{turn_index}", {}))
        score_matrix.append([alignment_score(json_text, raw_message, triggers) for raw_message in raw_messages])

    mapping, _total_score = best_one_to_one_alignment(score_matrix)
    aligned = []
    for turn_index, json_text in enumerate(json_texts):
        raw_index = mapping.get(turn_index)
        scores = score_matrix[turn_index] if turn_index < len(score_matrix) else []
        if raw_index is None or raw_index >= len(raw_messages):
            aligned.append(
                {
                    "raw": {},
                    "raw_index": None,
                    "alignment_status": "unresolved",
                    "alignment_score": 0.0,
                    "alignment_margin": 0.0,
                }
            )
            continue
        assigned_score = scores[raw_index]
        competing_scores = [score for index, score in enumerate(scores) if index != raw_index]
        next_best = max(competing_scores) if competing_scores else 0.0
        margin = assigned_score - next_best
        status = (
            "aligned"
            if assigned_score >= ALIGNMENT_SCORE_MIN and margin >= ALIGNMENT_MARGIN_MIN
            else "ambiguous"
        )
        aligned.append(
            {
                "raw": raw_messages[raw_index],
                "raw_index": raw_index,
                "alignment_status": status,
                "alignment_score": assigned_score,
                "alignment_margin": margin,
                "json_text": json_text,
            }
        )
    return aligned


def event_summary(event_map: dict[str, Any]) -> list[str]:
    lines = []
    for event_type in sorted(event_map):
        event = event_map[event_type]
        triggers = [trigger for trigger in event.get("triggers", []) if trigger]
        extras = [extra for extra in event.get("extras", []) if extra]
        label_count = len(event.get("labels", []) or [])
        lines.append(f"- Event type: `{event_type}`")
        lines.append(f"  - Label sequences: {label_count}")
        if triggers:
            lines.append("  - Triggers:")
            for trigger in triggers:
                lines.append(f"    - `{trigger}`")
        if extras:
            lines.append("  - Extras:")
            for extra in extras:
                lines.append(f"    - `{extra}`")
    return lines or ["- None"]


def render_thread(row: dict[str, str], thread: dict[str, Any], raw_messages: list[dict[str, str]]) -> str:
    sentences = thread.get("sentences", [])
    events = thread.get("events", {})
    aligned_raw = align_raw_messages(thread, raw_messages)
    lines = [
        f"# {row['pilot_id']} - {row['thread_id']}",
        "",
        f"- Pilot ID: `{row['pilot_id']}`",
        f"- MailEx thread ID: `{row['thread_id']}`",
        f"- Source path: `{row.get('source_path', '')}`",
        f"- Candidate ID: `{row.get('candidate_id', '')}`",
        f"- Candidate event types: `{row.get('event_types', '')}`",
        "",
        "Do not treat Original MailEx annotations as ISCMI labels.",
        "Chronological rank is the MailEx JSON conversational order, not an independently recovered send-time order.",
        "",
    ]
    for index, sentence in enumerate(sentences):
        turn_id = f"turn_{index}"
        message_id = f"{row['thread_id']}::{turn_id}"
        tokens = normalize_tokens(sentence)
        alignment = aligned_raw[index] if index < len(aligned_raw) else {}
        raw = alignment.get("raw", {}) if isinstance(alignment, dict) else {}
        body = raw.get("body") or detokenize(tokens)
        lines.extend(
            [
                f"## Message {index + 1}",
                "",
                f"- Message ID: `{message_id}`",
                f"- Chronological rank: {index + 1}",
                f"- Raw message index: {int(raw.get('raw_index', -1)) + 1 if raw.get('raw_index', '').isdigit() else ''}",
                f"- Alignment status: {alignment.get('alignment_status', 'unresolved')}",
                f"- Date: {raw.get('date', '')}",
                f"- Sender: {raw.get('from', '')}",
                f"- Recipients: {raw.get('to', '')}",
                f"- CC: {raw.get('cc', '')}",
                f"- BCC: {raw.get('bcc', '')}",
                f"- Subject: {raw.get('subject', '')}",
                "",
                "### Body",
                "",
                body or "(empty message body)",
                "",
                "### Original MailEx annotations",
                "",
                *event_summary(events.get(turn_id, {})),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def ensure_external_output(output: Path) -> None:
    repo_root = SCRIPT_DIR.parents[1].resolve()
    resolved = output.resolve()
    if resolved == repo_root or repo_root in resolved.parents:
        raise ValueError(f"Output directory must be outside the repository: {output}")


def write_packet(dataset: Dataset, rows: list[dict[str, str]], output: Path) -> None:
    ensure_external_output(output)
    if output.exists():
        shutil.rmtree(output)
    threads_dir = output / "threads"
    threads_dir.mkdir(parents=True, exist_ok=True)
    with (output / "pilot_index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    resolved = 0
    for row in rows:
        thread, raw_messages = load_thread(dataset, row)
        rendered = render_thread(row, thread, raw_messages)
        (threads_dir / f"{row['pilot_id']}.md").write_text(rendered, encoding="utf-8")
        resolved += 1
    if resolved != 50:
        raise RuntimeError(f"Expected 50 resolved threads, got {resolved}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare an external full-text MailEx packet for manual ISCMI pilot annotation."
    )
    parser.add_argument("--dataset", required=True, help="Path to MailEx data.zip or extracted dataset directory.")
    parser.add_argument("--output", required=True, help="External output directory for the annotation packet.")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="Pilot index CSV; defaults to mailex_pilot_index.csv.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_index(Path(args.index))
    dataset = load_dataset(Path(args.dataset))
    write_packet(dataset, rows, Path(args.output))
    print(f"Generated {len(rows)} pilot thread files in {Path(args.output) / 'threads'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
