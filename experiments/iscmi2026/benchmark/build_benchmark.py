#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import posixpath
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


ANNOTATED = "ANNOTATED"
ALLOWED_TRANSITIONS = {
    "CREATE",
    "CONFIRM",
    "MODIFY",
    "COMPLETE",
    "CANCEL",
    "REJECT",
    "NONE",
}
ALLOWED_STATES = {"OPEN", "CLOSED", "UNCERTAIN"}
MIN_PRIMARY_CONFIDENCE = 3
EXPECTED_PILOTS = [f"P{index:03d}" for index in range(1, 51)]
PILOT_FILE_RE = re.compile(r"^P\d{3}\.md$")
TASK_ID_RE = re.compile(r"^T(\d+)$")
CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")
TURN_RE = re.compile(r"::turn_(\d+)$")
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DATE_FIELDS = {"created_at", "deadline", "completed_at"}
REQUIRED_COLUMNS = [
    "annotator_id",
    "pilot_id",
    "thread_id",
    "task_id",
    "message_id",
    "chronological_rank",
    "sender",
    "recipients",
    "subject",
    "requester",
    "actor",
    "created_at",
    "deadline",
    "completed_at",
    "transition",
    "resulting_state",
    "closure_reason",
    "waiting_for",
    "blocked_by",
    "confidence",
    "notes",
    "annotation_status",
]
OUTPUT_FILES = [
    "message_evidence_index.jsonl",
    "task_histories.jsonl",
    "task_snapshots.jsonl",
    "questions.jsonl",
    "questions.csv",
    "benchmark_statistics.json",
]
CSV_COLUMNS = [
    "question_id",
    "question_family",
    "pilot_id",
    "thread_id",
    "task_id",
    "scope",
    "question",
    "gold_answer",
    "gold_structured",
    "evidence_message_ids",
    "difficulty_or_scope",
    "negative_control",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic ISCMI 2026 MailEx benchmark fixtures without an LLM."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        required=True,
        help="Path to MailEx_annotation_v1.6.xlsx.",
    )
    parser.add_argument(
        "--pilot-packet",
        type=Path,
        required=True,
        help="Path containing corrected P001.md through P050.md files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory for generated benchmark fixtures.",
    )
    parser.add_argument(
        "--generation-timestamp",
        help=(
            "ISO-8601 UTC timestamp for the manifest. When omitted, current UTC is used; "
            "pass a fixed value for byte-identical rebuilds."
        ),
    )
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_text(value: Any, *, compact: bool = False) -> str:
    if compact:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.write_text(json_text(value), encoding="utf-8", newline="\n")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    text = "".join(json_text(record, compact=True) + "\n" for record in records)
    path.write_text(text, encoding="utf-8", newline="\n")


def null_if_blank(value: Any) -> Any:
    if value is None or value == "":
        return None
    return value


def value_present(value: Any) -> bool:
    return null_if_blank(value) is not None


def normalize_timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def column_index(cell_reference: str) -> int:
    match = CELL_REF_RE.match(cell_reference)
    if not match:
        raise ValueError(f"Invalid XLSX cell reference: {cell_reference}")
    result = 0
    for character in match.group(1):
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def parse_numeric(value: str) -> int | float | str:
    if not value:
        return ""
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number


def read_xlsx_annotations(path: Path) -> tuple[list[str], list[dict[str, Any]], str]:
    if not path.exists():
        raise FileNotFoundError(f"Annotation workbook not found: {path}")
    if not zipfile.is_zipfile(path):
        raise ValueError(f"Annotation workbook is not a valid XLSX ZIP archive: {path}")

    main = f"{{{MAIN_NS}}}"
    rel_id_name = f"{{{DOC_REL_NS}}}id"
    relationship_name = f"{{{PKG_REL_NS}}}Relationship"

    with zipfile.ZipFile(path) as archive:
        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships_root = ET.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        relationships = {
            element.attrib["Id"]: element.attrib["Target"]
            for element in relationships_root.findall(relationship_name)
        }
        annotation_sheet = None
        for sheet in workbook_root.findall(f"{main}sheets/{main}sheet"):
            if sheet.attrib.get("name") == "Annotations":
                annotation_sheet = sheet
                break
        if annotation_sheet is None:
            raise ValueError("Workbook does not contain an 'Annotations' worksheet")

        relationship_id = annotation_sheet.attrib[rel_id_name]
        target = relationships[relationship_id].replace("\\", "/")
        if target.startswith("/"):
            worksheet_entry = target.lstrip("/")
        else:
            worksheet_entry = posixpath.normpath(posixpath.join("xl", target))

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall(f"{main}si"):
                shared_strings.append(
                    "".join(node.text or "" for node in item.iter(f"{main}t"))
                )

        worksheet_root = ET.fromstring(archive.read(worksheet_entry))
        parsed_rows: list[tuple[int, list[Any]]] = []
        for row_element in worksheet_root.findall(
            f"{main}sheetData/{main}row"
        ):
            row_number = int(row_element.attrib.get("r", len(parsed_rows) + 1))
            cell_values: dict[int, Any] = {}
            for cell in row_element.findall(f"{main}c"):
                reference = cell.attrib.get("r")
                if not reference:
                    continue
                index = column_index(reference)
                cell_type = cell.attrib.get("t", "")
                value_element = cell.find(f"{main}v")
                raw_value = value_element.text if value_element is not None else ""
                if cell_type == "inlineStr":
                    value = "".join(
                        node.text or "" for node in cell.iter(f"{main}t")
                    )
                elif cell_type == "s":
                    value = shared_strings[int(raw_value)] if raw_value else ""
                elif cell_type == "b":
                    value = raw_value == "1"
                elif cell_type in {"str", "e"}:
                    value = raw_value
                else:
                    value = parse_numeric(raw_value)
                cell_values[index] = value

            if not cell_values:
                continue
            width = max(cell_values) + 1
            row = [""] * width
            for index, value in cell_values.items():
                row[index] = value
            parsed_rows.append((row_number, row))

    if not parsed_rows:
        raise ValueError("Annotations worksheet is empty")
    header_row_number, header_values = parsed_rows[0]
    if header_row_number != 1:
        raise ValueError("Expected the annotation header in workbook row 1")
    headers = [str(value).strip() for value in header_values]
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing_columns:
        raise ValueError(f"Annotation workbook is missing columns: {missing_columns}")

    records: list[dict[str, Any]] = []
    for row_number, values in parsed_rows[1:]:
        padded = values + [""] * (len(headers) - len(values))
        if not any(value_present(value) for value in padded[: len(headers)]):
            continue
        record = {
            header: padded[index] if index < len(padded) else ""
            for index, header in enumerate(headers)
        }
        record["_source_workbook_row"] = row_number
        for field in headers:
            value = record[field]
            if isinstance(value, str):
                record[field] = value.strip()
        for field in DATE_FIELDS:
            value = record.get(field, "")
            if isinstance(value, (int, float)):
                date_value = datetime(1899, 12, 30) + timedelta(days=float(value))
                record[field] = date_value.date().isoformat()
        for field in ("chronological_rank", "confidence"):
            value = record.get(field, "")
            if value_present(value):
                number = float(value)
                if not number.is_integer():
                    raise ValueError(
                        f"{field} must be an integer in workbook row {row_number}"
                    )
                record[field] = int(number)
        records.append(record)
    return headers, records, "Annotations"


def read_markdown_field(block: str, label: str, *, code: bool = False) -> str:
    escaped = re.escape(label)
    value_pattern = r"`([^`]*)`" if code else r"(.*)"
    match = re.search(rf"^- {escaped}: {value_pattern}\r?$", block, re.MULTILINE)
    if not match:
        raise ValueError(f"Pilot packet field is missing: {label}")
    return match.group(1).strip()


def read_pilot_packet(
    packet_path: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, str],
    str,
    dict[str, str],
    list[str],
]:
    threads_dir = packet_path / "threads" if (packet_path / "threads").is_dir() else packet_path
    if not threads_dir.is_dir():
        raise FileNotFoundError(f"Pilot packet directory not found: {packet_path}")
    files = sorted(
        path for path in threads_dir.iterdir() if path.is_file() and PILOT_FILE_RE.match(path.name)
    )
    if [path.stem for path in files] != EXPECTED_PILOTS:
        raise ValueError("Pilot packet must contain exactly P001.md through P050.md")

    message_index: list[dict[str, Any]] = []
    thread_by_pilot: dict[str, str] = {}
    individual_hashes: dict[str, str] = {}
    packet_hash = hashlib.sha256()
    body_snippets: list[str] = []

    for path in files:
        content_bytes = path.read_bytes()
        content = content_bytes.decode("utf-8")
        individual_hashes[path.name] = sha256_bytes(content_bytes)
        packet_hash.update(path.name.encode("utf-8"))
        packet_hash.update(b"\0")
        packet_hash.update(content_bytes)
        packet_hash.update(b"\0")

        pilot_id = read_markdown_field(content, "Pilot ID", code=True)
        thread_id = read_markdown_field(content, "MailEx thread ID", code=True)
        if pilot_id != path.stem:
            raise ValueError(f"Pilot ID/file mismatch in {path.name}")
        thread_by_pilot[pilot_id] = thread_id

        blocks = re.split(r"^## Message \d+\s*$", content, flags=re.MULTILINE)[1:]
        if not blocks:
            raise ValueError(f"No messages found in {path.name}")
        for block in blocks:
            message_id = read_markdown_field(block, "Message ID", code=True)
            chronological_rank = int(read_markdown_field(block, "Chronological rank"))
            turn_match = TURN_RE.search(message_id)
            if not turn_match or int(turn_match.group(1)) + 1 != chronological_rank:
                raise ValueError(
                    f"Message order mismatch in {path.name}: {message_id} / {chronological_rank}"
                )
            if not message_id.startswith(f"{thread_id}::"):
                raise ValueError(f"Thread/message ID mismatch in {path.name}: {message_id}")
            message_index.append(
                {
                    "information_level": "original_email_evidence_reference",
                    "pilot_id": pilot_id,
                    "thread_id": thread_id,
                    "message_id": message_id,
                    "chronological_rank": chronological_rank,
                    "source_file": path.name,
                }
            )
            body_match = re.search(
                r"### Body\s*(.*?)\s*### Original MailEx annotations",
                block,
                flags=re.DOTALL,
            )
            if body_match:
                normalized = " ".join(body_match.group(1).split())
                if len(normalized) >= 120:
                    body_snippets.append(normalized[:120])

    message_index.sort(key=lambda item: (item["pilot_id"], item["chronological_rank"]))
    if len(message_index) != 195:
        raise ValueError(f"Expected 195 pilot messages, found {len(message_index)}")
    if len({item["message_id"] for item in message_index}) != len(message_index):
        raise ValueError("Pilot packet contains duplicate message IDs")
    for pilot_id in EXPECTED_PILOTS:
        ranks = [
            item["chronological_rank"]
            for item in message_index
            if item["pilot_id"] == pilot_id
        ]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError(f"Non-contiguous chronological ranks for {pilot_id}")
    return (
        message_index,
        thread_by_pilot,
        packet_hash.hexdigest(),
        individual_hashes,
        body_snippets,
    )


def counter_dict(values: Iterable[Any]) -> dict[str, int]:
    counter = Counter(str(value) for value in values)
    return dict(sorted(counter.items()))


def task_sort_key(task_id: str) -> tuple[int, str]:
    match = TASK_ID_RE.match(task_id)
    return (int(match.group(1)), task_id) if match else (10**9, task_id)


def ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def coverage(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    populated = sum(value_present(record.get(field)) for record in records)
    return {
        "populated": populated,
        "total": len(records),
        "ratio": round(populated / len(records), 6) if records else 0.0,
    }


def validate_annotation_rows(
    headers: list[str],
    rows: list[dict[str, Any]],
    message_by_id: dict[str, dict[str, Any]],
    thread_by_pilot: dict[str, str],
) -> None:
    observed_pilots = sorted({str(row["pilot_id"]) for row in rows})
    if observed_pilots != EXPECTED_PILOTS:
        raise ValueError("Annotation workbook pilot IDs do not cover P001-P050 exactly")
    qc_present = "qc_status" in headers
    duplicate_keys: set[tuple[str, str, str]] = set()

    for row in rows:
        workbook_row = row["_source_workbook_row"]
        pilot_id = str(row["pilot_id"])
        thread_id = str(row["thread_id"])
        message_id = str(row["message_id"])
        status = str(row["annotation_status"])
        evidence = message_by_id.get(message_id)
        if evidence is None:
            raise ValueError(
                f"Unknown message_id in annotation workbook row {workbook_row}: {message_id}"
            )
        if evidence["pilot_id"] != pilot_id or evidence["thread_id"] != thread_id:
            raise ValueError(f"Pilot/thread mismatch in workbook row {workbook_row}")
        if thread_by_pilot[pilot_id] != thread_id:
            raise ValueError(f"Unexpected thread ID in workbook row {workbook_row}")
        if int(row["chronological_rank"]) != evidence["chronological_rank"]:
            raise ValueError(f"Chronological rank mismatch in workbook row {workbook_row}")

        if status == ANNOTATED:
            task_id = str(row["task_id"])
            if not TASK_ID_RE.match(task_id):
                raise ValueError(f"Invalid task_id in workbook row {workbook_row}: {task_id}")
            if row["transition"] not in ALLOWED_TRANSITIONS:
                raise ValueError(f"Invalid transition in workbook row {workbook_row}")
            if row["resulting_state"] not in ALLOWED_STATES:
                raise ValueError(f"Invalid resulting_state in workbook row {workbook_row}")
            confidence = row["confidence"]
            if not isinstance(confidence, int) or not 1 <= confidence <= 5:
                raise ValueError(f"Invalid confidence in workbook row {workbook_row}")
            key = (pilot_id, task_id, message_id)
            if key in duplicate_keys:
                raise ValueError(f"Duplicate task/message annotation: {key}")
            duplicate_keys.add(key)
            if qc_present and not value_present(row.get("qc_status")):
                raise ValueError(f"Missing qc_status in annotated workbook row {workbook_row}")
        elif status in {"NO_TASK", "SKIP_UNCERTAIN", "PENDING"}:
            if value_present(row.get("task_id")):
                raise ValueError(
                    f"Excluded status {status} has task_id in workbook row {workbook_row}"
                )
        else:
            raise ValueError(
                f"Unknown annotation_status in workbook row {workbook_row}: {status}"
            )


def select_usable_rows(
    headers: list[str], rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], Counter[str]]:
    qc_present = "qc_status" in headers
    usable: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    for row in rows:
        status = str(row["annotation_status"])
        if status != ANNOTATED:
            exclusions[f"annotation_status:{status}"] += 1
            continue
        confidence = row.get("confidence")
        if not isinstance(confidence, int):
            exclusions["missing_confidence"] += 1
            continue
        if confidence < MIN_PRIMARY_CONFIDENCE:
            exclusions[f"confidence_below_{MIN_PRIMARY_CONFIDENCE}"] += 1
            continue
        if qc_present and row.get("qc_status") != "PASS":
            exclusions[f"qc_status:{row.get('qc_status') or '<blank>'}"] += 1
            continue
        usable.append(row)
    return usable, exclusions


def build_tasks(
    usable_rows: list[dict[str, Any]], qc_present: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in usable_rows:
        grouped[(str(row["pilot_id"]), str(row["task_id"]))].append(row)

    histories: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    for pilot_id, task_id in sorted(
        grouped, key=lambda key: (key[0], task_sort_key(key[1]))
    ):
        rows = sorted(
            grouped[(pilot_id, task_id)],
            key=lambda row: (
                int(row["chronological_rank"]),
                int(row["_source_workbook_row"]),
            ),
        )
        ranks = [int(row["chronological_rank"]) for row in rows]
        if len(set(ranks)) != len(ranks):
            raise ValueError(f"Duplicate chronological rank within {pilot_id}/{task_id}")
        thread_ids = {str(row["thread_id"]) for row in rows}
        if len(thread_ids) != 1:
            raise ValueError(f"Task spans multiple threads: {pilot_id}/{task_id}")

        events = []
        for row in rows:
            events.append(
                {
                    "message_id": row["message_id"],
                    "chronological_rank": int(row["chronological_rank"]),
                    "transition": row["transition"],
                    "resulting_state": row["resulting_state"],
                    "requester": null_if_blank(row.get("requester")),
                    "actor": null_if_blank(row.get("actor")),
                    "created_at": null_if_blank(row.get("created_at")),
                    "deadline": null_if_blank(row.get("deadline")),
                    "completed_at": null_if_blank(row.get("completed_at")),
                    "closure_reason": null_if_blank(row.get("closure_reason")),
                    "waiting_for": null_if_blank(row.get("waiting_for")),
                    "blocked_by": null_if_blank(row.get("blocked_by")),
                    "confidence": int(row["confidence"]),
                    "annotator_id": null_if_blank(row.get("annotator_id")),
                    "annotation_status": row["annotation_status"],
                    "qc_status": null_if_blank(row.get("qc_status"))
                    if qc_present
                    else None,
                    "annotation_notes": null_if_blank(row.get("notes")),
                    "source_workbook_row": int(row["_source_workbook_row"]),
                }
            )
        evidence_message_ids = ordered_unique(
            event["message_id"] for event in events
        )
        history = {
            "information_level": "human_annotation",
            "pilot_id": pilot_id,
            "thread_id": rows[0]["thread_id"],
            "task_id": task_id,
            "history": events,
            "evidence_message_ids": evidence_message_ids,
            "annotation_metadata": {
                "source_workbook": "MailEx_annotation_v1.6.xlsx",
                "annotation_statuses": ordered_unique(
                    event["annotation_status"] for event in events
                ),
                "confidence_values": [event["confidence"] for event in events],
                "qc_field_present": qc_present,
                "qc_statuses": ordered_unique(
                    str(event["qc_status"])
                    for event in events
                    if event["qc_status"] is not None
                ),
            },
        }
        final_event = events[-1]
        snapshot = {
            "information_level": "derived_benchmark_ground_truth",
            "pilot_id": pilot_id,
            "thread_id": rows[0]["thread_id"],
            "task_id": task_id,
            "final_state": final_event["resulting_state"],
            "last_transition": final_event["transition"],
            "requester": final_event["requester"],
            "actor": final_event["actor"],
            "created_at": final_event["created_at"],
            "deadline": final_event["deadline"],
            "completed_at": final_event["completed_at"],
            "closure_reason": final_event["closure_reason"],
            "waiting_for": final_event["waiting_for"],
            "blocked_by": final_event["blocked_by"],
            "confidence": final_event["confidence"],
            "last_message_id": final_event["message_id"],
            "evidence_message_ids": evidence_message_ids,
            "annotation_status": final_event["annotation_status"],
            "qc_status": final_event["qc_status"],
            "derivation": {
                "rule": "last_usable_chronological_annotation",
                "auxiliary_attribute_propagation": "none",
                "missing_value_policy": "null",
            },
        }
        histories.append(history)
        snapshots.append(snapshot)
    return histories, snapshots


def evidence_union(
    tasks: Iterable[dict[str, Any]], message_by_id: dict[str, dict[str, Any]]
) -> list[str]:
    message_ids = ordered_unique(
        message_id
        for task in tasks
        for message_id in task["evidence_message_ids"]
    )
    return sorted(
        message_ids,
        key=lambda message_id: (
            message_by_id[message_id]["pilot_id"],
            message_by_id[message_id]["chronological_rank"],
        ),
    )


def build_questions(
    snapshots: list[dict[str, Any]],
    histories: list[dict[str, Any]],
    annotation_rows: list[dict[str, Any]],
    message_index: list[dict[str, Any]],
    thread_by_pilot: dict[str, str],
) -> list[dict[str, Any]]:
    snapshots_by_pilot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    histories_by_pilot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    messages_by_pilot: dict[str, list[str]] = defaultdict(list)
    message_by_id = {item["message_id"]: item for item in message_index}
    for snapshot in snapshots:
        snapshots_by_pilot[snapshot["pilot_id"]].append(snapshot)
    for history in histories:
        histories_by_pilot[history["pilot_id"]].append(history)
    for message in message_index:
        messages_by_pilot[message["pilot_id"]].append(message["message_id"])
    for pilot_id in EXPECTED_PILOTS:
        snapshots_by_pilot[pilot_id].sort(key=lambda item: task_sort_key(item["task_id"]))
        histories_by_pilot[pilot_id].sort(key=lambda item: task_sort_key(item["task_id"]))

    questions: list[dict[str, Any]] = []

    def append_question(
        *,
        family: str,
        pilot_id: str,
        scope: str,
        question: str,
        gold_answer: str,
        gold_structured: dict[str, Any],
        evidence_message_ids: list[str],
        difficulty_or_scope: str,
        negative_control: bool = False,
        task_id: str | None = None,
    ) -> None:
        questions.append(
            {
                "question_id": "",
                "question_family": family,
                "pilot_id": pilot_id,
                "thread_id": thread_by_pilot[pilot_id],
                "task_id": task_id,
                "scope": scope,
                "question": question,
                "gold_answer": gold_answer,
                "gold_structured": gold_structured,
                "evidence_message_ids": evidence_message_ids,
                "difficulty_or_scope": difficulty_or_scope,
                "negative_control": negative_control,
            }
        )

    for pilot_id in EXPECTED_PILOTS:
        tasks = [
            task
            for task in snapshots_by_pilot[pilot_id]
            if task["final_state"] == "OPEN"
        ]
        task_refs = [
            {
                "task_id": task["task_id"],
                "final_state": task["final_state"],
                "last_transition": task["last_transition"],
            }
            for task in tasks
        ]
        append_question(
            family="OPEN_TASKS",
            pilot_id=pilot_id,
            scope="thread",
            question="What tasks are still open in this conversation?",
            gold_answer="NONE"
            if not tasks
            else "OPEN: " + ", ".join(task["task_id"] for task in tasks),
            gold_structured={
                "answer_type": "task_set",
                "state": "OPEN",
                "tasks": task_refs,
                "none": not tasks,
            },
            evidence_message_ids=evidence_union(tasks, message_by_id)
            if tasks
            else messages_by_pilot[pilot_id],
            difficulty_or_scope="thread_state_set",
            negative_control=not tasks,
        )

    for pilot_id in EXPECTED_PILOTS:
        tasks = [
            task
            for task in snapshots_by_pilot[pilot_id]
            if task["final_state"] == "CLOSED"
        ]
        task_refs = [
            {
                "task_id": task["task_id"],
                "final_state": task["final_state"],
                "last_transition": task["last_transition"],
                "closure_reason": task["closure_reason"],
            }
            for task in tasks
        ]
        labels = [
            f"{task['task_id']} ({task['closure_reason'] or 'CLOSED'})"
            for task in tasks
        ]
        append_question(
            family="CLOSED_TASKS",
            pilot_id=pilot_id,
            scope="thread",
            question="Which tasks are no longer actionable in this conversation?",
            gold_answer="NONE" if not labels else "CLOSED: " + ", ".join(labels),
            gold_structured={
                "answer_type": "task_set",
                "state": "CLOSED",
                "tasks": task_refs,
                "none": not tasks,
            },
            evidence_message_ids=evidence_union(tasks, message_by_id)
            if tasks
            else messages_by_pilot[pilot_id],
            difficulty_or_scope="thread_state_set",
            negative_control=not tasks,
        )

    for pilot_id in EXPECTED_PILOTS:
        tasks = [
            task
            for task in snapshots_by_pilot[pilot_id]
            if task["final_state"] == "OPEN" and task["actor"] is not None
        ]
        if not tasks:
            continue
        append_question(
            family="ACTOR_RESPONSIBILITY",
            pilot_id=pilot_id,
            scope="thread",
            question=(
                "For the currently open tasks with a known responsible party, "
                "who is responsible for each one?"
            ),
            gold_answer="; ".join(
                f"{task['task_id']}: {task['actor']}" for task in tasks
            ),
            gold_structured={
                "answer_type": "task_actor_map",
                "tasks": [
                    {"task_id": task["task_id"], "actor": task["actor"]}
                    for task in tasks
                ],
            },
            evidence_message_ids=evidence_union(tasks, message_by_id),
            difficulty_or_scope="thread_participant_mapping",
        )

    for pilot_id in EXPECTED_PILOTS:
        tasks = [
            task
            for task in snapshots_by_pilot[pilot_id]
            if task["requester"] is not None
        ]
        if not tasks:
            continue
        append_question(
            family="REQUESTER",
            pilot_id=pilot_id,
            scope="thread",
            question=(
                "For the tracked tasks with a known requester, who requested each one?"
            ),
            gold_answer="; ".join(
                f"{task['task_id']}: {task['requester']}" for task in tasks
            ),
            gold_structured={
                "answer_type": "task_requester_map",
                "tasks": [
                    {
                        "task_id": task["task_id"],
                        "requester": task["requester"],
                        "final_state": task["final_state"],
                    }
                    for task in tasks
                ],
            },
            evidence_message_ids=evidence_union(tasks, message_by_id),
            difficulty_or_scope="thread_participant_mapping",
        )

    for pilot_id in EXPECTED_PILOTS:
        task_histories = []
        related_tasks = []
        snapshots_by_task = {
            task["task_id"]: task for task in snapshots_by_pilot[pilot_id]
        }
        for history in histories_by_pilot[pilot_id]:
            meaningful = [
                event for event in history["history"] if event["transition"] != "NONE"
            ]
            if len(meaningful) < 2 or len(
                {event["chronological_rank"] for event in meaningful}
            ) < 2:
                continue
            task_histories.append(
                {
                    "task_id": history["task_id"],
                    "events": [
                        {
                            "message_id": event["message_id"],
                            "chronological_rank": event["chronological_rank"],
                            "transition": event["transition"],
                            "resulting_state": event["resulting_state"],
                        }
                        for event in history["history"]
                    ],
                    "meaningful_transition_count": len(meaningful),
                    "final_state": snapshots_by_task[history["task_id"]]["final_state"],
                }
            )
            related_tasks.append(snapshots_by_task[history["task_id"]])
        if not task_histories:
            continue
        append_question(
            family="TASK_HISTORY",
            pilot_id=pilot_id,
            scope="thread",
            question=(
                "Which tasks changed over multiple messages in this conversation, "
                "and what transition sequence did each follow?"
            ),
            gold_answer="; ".join(
                f"{item['task_id']}: "
                + " -> ".join(
                    f"{event['transition']}/{event['resulting_state']}"
                    for event in item["events"]
                )
                for item in task_histories
            ),
            gold_structured={
                "answer_type": "task_history_set",
                "tasks": task_histories,
            },
            evidence_message_ids=evidence_union(related_tasks, message_by_id),
            difficulty_or_scope="thread_multi_transition_history",
        )

    for pilot_id in EXPECTED_PILOTS:
        tasks = [
            task
            for task in snapshots_by_pilot[pilot_id]
            if task["final_state"] == "OPEN" and task["deadline"] is not None
        ]
        if not tasks:
            continue
        append_question(
            family="DEADLINE",
            pilot_id=pilot_id,
            scope="thread",
            question="Which open tasks have a known deadline, and what are the deadlines?",
            gold_answer="; ".join(
                f"{task['task_id']}: {task['deadline']}" for task in tasks
            ),
            gold_structured={
                "answer_type": "task_deadline_map",
                "tasks": [
                    {"task_id": task["task_id"], "deadline": task["deadline"]}
                    for task in tasks
                ],
            },
            evidence_message_ids=evidence_union(tasks, message_by_id),
            difficulty_or_scope="thread_auxiliary_attribute",
        )

    for pilot_id in EXPECTED_PILOTS:
        tasks = [
            task
            for task in snapshots_by_pilot[pilot_id]
            if task["final_state"] == "OPEN" and task["waiting_for"] is not None
        ]
        if not tasks:
            continue
        append_question(
            family="WAITING_FOR",
            pilot_id=pilot_id,
            scope="thread",
            question="Which open tasks are waiting for another person or input?",
            gold_answer="; ".join(
                f"{task['task_id']}: {task['waiting_for']}" for task in tasks
            ),
            gold_structured={
                "answer_type": "task_waiting_for_map",
                "tasks": [
                    {
                        "task_id": task["task_id"],
                        "waiting_for": task["waiting_for"],
                    }
                    for task in tasks
                ],
            },
            evidence_message_ids=evidence_union(tasks, message_by_id),
            difficulty_or_scope="thread_auxiliary_attribute",
        )

    for pilot_id in EXPECTED_PILOTS:
        tasks = [
            task
            for task in snapshots_by_pilot[pilot_id]
            if task["final_state"] == "OPEN" and task["blocked_by"] is not None
        ]
        if not tasks:
            continue
        append_question(
            family="BLOCKED_BY",
            pilot_id=pilot_id,
            scope="thread",
            question="Which open tasks are blocked, and what is blocking them?",
            gold_answer="; ".join(
                f"{task['task_id']}: {task['blocked_by']}" for task in tasks
            ),
            gold_structured={
                "answer_type": "task_blocker_map",
                "tasks": [
                    {"task_id": task["task_id"], "blocked_by": task["blocked_by"]}
                    for task in tasks
                ],
            },
            evidence_message_ids=evidence_union(tasks, message_by_id),
            difficulty_or_scope="thread_auxiliary_attribute",
        )

    no_task_rows = sorted(
        (
            row
            for row in annotation_rows
            if row["annotation_status"] == "NO_TASK"
        ),
        key=lambda row: (row["pilot_id"], int(row["chronological_rank"])),
    )
    for row in no_task_rows:
        pilot_id = str(row["pilot_id"])
        rank = int(row["chronological_rank"])
        append_question(
            family="NO_TASK_CONTROL",
            pilot_id=pilot_id,
            scope="message",
            question=(
                f"Does the message at chronological position {rank} in this "
                "conversation create or update a tracked task?"
            ),
            gold_answer="NONE",
            gold_structured={
                "answer_type": "no_task",
                "message_id": row["message_id"],
                "annotation_status": "NO_TASK",
                "none": True,
            },
            evidence_message_ids=[row["message_id"]],
            difficulty_or_scope="message_negative_control",
            negative_control=True,
        )

    for index, question in enumerate(questions, start=1):
        question["question_id"] = f"ISCMI-Q{index:04d}"
    return questions


def collect_task_ids(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "task_id" and isinstance(item, str):
                result.append(item)
            else:
                result.extend(collect_task_ids(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(collect_task_ids(item))
    return result


def validate_benchmark(
    histories: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    message_index: list[dict[str, Any]],
    annotation_rows: list[dict[str, Any]],
) -> None:
    message_by_id = {item["message_id"]: item for item in message_index}
    task_keys = {(item["pilot_id"], item["task_id"]) for item in snapshots}
    if len(task_keys) != len(snapshots) or len(histories) != len(snapshots):
        raise ValueError("Task histories and snapshots are not one-to-one")
    no_task_message_ids = {
        row["message_id"]
        for row in annotation_rows
        if row["annotation_status"] == "NO_TASK"
    }

    for history in histories:
        key = (history["pilot_id"], history["task_id"])
        if key not in task_keys:
            raise ValueError(f"Unresolved task history: {key}")
        for event in history["history"]:
            if event["message_id"] not in message_by_id:
                raise ValueError(f"Unknown task evidence: {event['message_id']}")
            if event["annotation_status"] != ANNOTATED:
                raise ValueError("Excluded annotation entered a positive task history")

    for snapshot in snapshots:
        if snapshot["final_state"] not in ALLOWED_STATES:
            raise ValueError(f"Invalid final state in snapshot: {snapshot}")
        blocker = snapshot.get("blocked_by")
        if blocker:
            for task_id in re.findall(r"\bT\d+\b", str(blocker)):
                if (snapshot["pilot_id"], task_id) not in task_keys:
                    raise ValueError(
                        f"Unresolved blocked_by task reference: {snapshot['pilot_id']}/{task_id}"
                    )

    question_ids = [question["question_id"] for question in questions]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("Question IDs are not unique")
    for question in questions:
        pilot_id = question["pilot_id"]
        for message_id in question["evidence_message_ids"]:
            evidence = message_by_id.get(message_id)
            if evidence is None or evidence["pilot_id"] != pilot_id:
                raise ValueError(
                    f"Invalid question evidence in {question['question_id']}: {message_id}"
                )
        for task_id in collect_task_ids(question["gold_structured"]):
            if (pilot_id, task_id) not in task_keys:
                raise ValueError(
                    f"Unresolved question task reference: {pilot_id}/{task_id}"
                )
        family = question["question_family"]
        task_records = question["gold_structured"].get("tasks", [])
        if family == "OPEN_TASKS" and any(
            task["final_state"] != "OPEN" for task in task_records
        ):
            raise ValueError("OPEN_TASKS includes a non-open task")
        if family == "CLOSED_TASKS" and any(
            task["final_state"] != "CLOSED" for task in task_records
        ):
            raise ValueError("CLOSED_TASKS includes a non-closed task")
        if family == "ACTOR_RESPONSIBILITY" and any(
            not value_present(task.get("actor")) for task in task_records
        ):
            raise ValueError("Actor question lacks actor ground truth")
        if family == "REQUESTER" and any(
            not value_present(task.get("requester")) for task in task_records
        ):
            raise ValueError("Requester question lacks requester ground truth")
        if family == "DEADLINE" and any(
            not value_present(task.get("deadline")) for task in task_records
        ):
            raise ValueError("Deadline question lacks deadline ground truth")
        if family == "WAITING_FOR" and any(
            not value_present(task.get("waiting_for")) for task in task_records
        ):
            raise ValueError("Waiting question lacks waiting_for ground truth")
        if family == "BLOCKED_BY" and any(
            not value_present(task.get("blocked_by")) for task in task_records
        ):
            raise ValueError("Blocking question lacks blocked_by ground truth")
        if family == "TASK_HISTORY" and any(
            task.get("meaningful_transition_count", 0) < 2
            or len(task.get("events", [])) < 2
            for task in task_records
        ):
            raise ValueError("Task-history question lacks multiple transitions")
        if family == "NO_TASK_CONTROL":
            message_id = question["gold_structured"].get("message_id")
            if message_id not in no_task_message_ids:
                raise ValueError("NO_TASK control is not supported by NO_TASK annotation")


def write_questions_csv(path: Path, questions: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for question in questions:
            row = dict(question)
            row["gold_structured"] = json_text(
                question["gold_structured"], compact=True
            )
            row["evidence_message_ids"] = json_text(
                question["evidence_message_ids"], compact=True
            )
            writer.writerow(row)


def main() -> int:
    args = parse_args()
    generation_timestamp = normalize_timestamp(args.generation_timestamp)
    headers, annotation_rows, sheet_name = read_xlsx_annotations(args.annotations)
    (
        message_index,
        thread_by_pilot,
        packet_sha256,
        pilot_hashes,
        body_snippets,
    ) = read_pilot_packet(args.pilot_packet)
    message_by_id = {item["message_id"]: item for item in message_index}
    validate_annotation_rows(
        headers, annotation_rows, message_by_id, thread_by_pilot
    )
    usable_rows, exclusions = select_usable_rows(headers, annotation_rows)
    qc_present = "qc_status" in headers
    histories, snapshots = build_tasks(usable_rows, qc_present)
    questions = build_questions(
        snapshots,
        histories,
        annotation_rows,
        message_index,
        thread_by_pilot,
    )
    validate_benchmark(
        histories, snapshots, questions, message_index, annotation_rows
    )

    task_snapshot_coverage = {
        field: coverage(snapshots, field)
        for field in (
            "requester",
            "actor",
            "deadline",
            "waiting_for",
            "blocked_by",
            "closure_reason",
        )
    }
    usable_row_coverage = {
        field: coverage(usable_rows, field)
        for field in (
            "requester",
            "actor",
            "deadline",
            "waiting_for",
            "blocked_by",
            "closure_reason",
        )
    }
    annotation_status_distribution = counter_dict(
        row["annotation_status"] for row in annotation_rows
    )
    qc_distribution = (
        counter_dict(
            row.get("qc_status") or "<blank>" for row in annotation_rows
        )
        if qc_present
        else {}
    )
    statistics = {
        "schema_version": "1.0",
        "threads": len(thread_by_pilot),
        "messages": len(message_index),
        "annotation_rows_total": len(annotation_rows),
        "usable_annotated_rows": len(usable_rows),
        "unique_tasks": len(snapshots),
        "tasks_by_final_state": counter_dict(
            snapshot["final_state"] for snapshot in snapshots
        ),
        "tasks_by_closure_reason": counter_dict(
            snapshot["closure_reason"]
            for snapshot in snapshots
            if snapshot["closure_reason"] is not None
        ),
        "transition_distribution": counter_dict(
            row["transition"] for row in usable_rows
        ),
        "usable_row_coverage": usable_row_coverage,
        "task_snapshot_coverage": task_snapshot_coverage,
        "questions_total": len(questions),
        "questions_by_family": counter_dict(
            question["question_family"] for question in questions
        ),
        "negative_control_questions": sum(
            bool(question["negative_control"]) for question in questions
        ),
        "annotation_status_distribution": annotation_status_distribution,
        "excluded_annotations": dict(sorted(exclusions.items())),
        "excluded_annotations_total": sum(exclusions.values()),
        "confidence_distribution_usable": counter_dict(
            row["confidence"] for row in usable_rows
        ),
        "qc": {
            "field_present": qc_present,
            "distribution": qc_distribution,
            "primary_filter": "PASS" if qc_present else None,
        },
        "rare_transition_policy": {
            "CANCEL": "secondary_descriptive_only",
            "REJECT": "secondary_descriptive_only",
        },
    }

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "message_evidence_index.jsonl", message_index)
    write_jsonl(output / "task_histories.jsonl", histories)
    write_jsonl(output / "task_snapshots.jsonl", snapshots)
    write_jsonl(output / "questions.jsonl", questions)
    write_questions_csv(output / "questions.csv", questions)
    write_json(output / "benchmark_statistics.json", statistics)

    generated_content = "\n".join(
        (output / name).read_text(encoding="utf-8") for name in OUTPUT_FILES
    )
    if "### Body" in generated_content:
        raise ValueError("Generated fixtures contain a raw body section marker")
    for snippet in body_snippets:
        if snippet in " ".join(generated_content.split()):
            raise ValueError("Generated fixtures contain a raw email body snippet")
    allowed_evidence_keys = {
        "information_level",
        "pilot_id",
        "thread_id",
        "message_id",
        "chronological_rank",
        "source_file",
    }
    if any(set(item) != allowed_evidence_keys for item in message_index):
        raise ValueError("Evidence index contains annotation or gold fields")

    generated_hashes = {
        name: sha256_file(output / name) for name in OUTPUT_FILES
    }
    manifest = {
        "schema_version": "1.0",
        "source_dataset": {
            "name": "MailEx",
            "pilot_threads": len(thread_by_pilot),
            "pilot_messages": len(message_index),
            "corrected_json_raw_message_alignment": True,
            "raw_email_bodies_committed": False,
        },
        "annotation_workbook": {
            "name": "MailEx_annotation_v1.6.xlsx",
            "worksheet": sheet_name,
            "columns": headers,
            "rows": len(annotation_rows),
            "sha256": sha256_file(args.annotations),
            "qc_field_present": qc_present,
        },
        "pilot_packet": {
            "description": "Corrected external P001.md-P050.md MailEx pilot packet",
            "file_count": len(pilot_hashes),
            "aggregate_sha256": packet_sha256,
            "file_sha256": dict(sorted(pilot_hashes.items())),
        },
        "benchmark_generation": {
            "script": "build_benchmark.py",
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "generation_timestamp_utc": generation_timestamp,
            "no_llm_or_paid_api_used": True,
            "deterministic_ordering": True,
            "timestamp_reproducibility": (
                "Pass --generation-timestamp with the recorded value for a byte-identical manifest."
            ),
        },
        "counts": {
            "usable_annotation_rows": len(usable_rows),
            "tasks": len(snapshots),
            "questions": len(questions),
        },
        "inclusion_rules": {
            "annotation_status_included": ["ANNOTATED"],
            "annotation_status_excluded": ["PENDING", "NO_TASK", "SKIP_UNCERTAIN"],
            "minimum_confidence": MIN_PRIMARY_CONFIDENCE,
            "qc_filter": "PASS" if qc_present else None,
            "no_qc_status_invented": not qc_present,
        },
        "snapshot_derivation": {
            "rule": "Use the last usable annotation in chronological order.",
            "auxiliary_attribute_propagation": "none",
            "missing_values": "null",
        },
        "information_separation": {
            "input_corpus": (
                "Corrected external original MailEx email evidence only; not copied into committed fixtures."
            ),
            "human_annotation": "task_histories.jsonl",
            "derived_ground_truth": "task_snapshots.jsonl and question gold fields",
            "gold_labels_in_retrieval_corpus": False,
        },
        "evaluation_partition": {
            "type": "fixed_evaluation_set",
            "pilot_ids": EXPECTED_PILOTS,
            "thread_level_split_required_if_partitioned_later": True,
            "row_level_split_used": False,
        },
        "generated_files_sha256": generated_hashes,
    }
    write_json(output / "benchmark_manifest.json", manifest)

    print(
        json_text(
            {
                "output": str(output),
                "threads": len(thread_by_pilot),
                "messages": len(message_index),
                "usable_rows": len(usable_rows),
                "tasks": len(snapshots),
                "tasks_by_final_state": statistics["tasks_by_final_state"],
                "questions": len(questions),
                "questions_by_family": statistics["questions_by_family"],
                "negative_controls": statistics["negative_control_questions"],
                "excluded_annotations": statistics["excluded_annotations"],
            },
            compact=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
