#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INDEX = SCRIPT_DIR / "mailex_pilot_index.csv"


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


def parse_raw_messages(raw_text: str) -> list[dict[str, str]]:
    parts = [part.strip() for part in re.split(r"\n-{5,}\n", raw_text) if part.strip()]
    messages = []
    for part in parts:
        headers: dict[str, str] = {}
        body_lines: list[str] = []
        in_header = True
        for line in part.splitlines():
            match = re.match(r"^([A-Za-z-]+)\s*:\s*(.*)$", line)
            if in_header and match:
                headers[match.group(1).upper()] = match.group(2).strip()
            else:
                in_header = False
                body_lines.append(line)
        messages.append(
            {
                "from": headers.get("FROM", ""),
                "to": headers.get("TO", ""),
                "cc": headers.get("CC", ""),
                "bcc": headers.get("BCC", ""),
                "date": headers.get("DATE", ""),
                "subject": headers.get("SUBJECT", ""),
                "body": "\n".join(body_lines).strip(),
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
        "",
    ]
    for index, sentence in enumerate(sentences):
        turn_id = f"turn_{index}"
        message_id = f"{row['thread_id']}::{turn_id}"
        tokens = normalize_tokens(sentence)
        raw = raw_messages[index] if index < len(raw_messages) else {}
        body = raw.get("body") or detokenize(tokens)
        lines.extend(
            [
                f"## Message {index + 1}",
                "",
                f"- Message ID: `{message_id}`",
                f"- Message order: {index + 1}",
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
