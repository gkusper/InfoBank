"""Privacy-safe transformation of the locally supplied MailEx ZIP."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
import zipfile
from collections import Counter, defaultdict
from email import policy
from email.parser import Parser
from email.utils import getaddresses
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .backend import ensure_backend_path


TRANSFORMATION_VERSION = "infobank-mailex-local-transform-v1"
LICENCE_STATUS = "LICENCE_PENDING_HUMAN_CONFIRMATION"
ANNOTATION_STATUS = "MACHINE_SUGGESTION_NOT_GOLD"
MANUAL_STATUS = "PENDING_HUMAN_REVIEW"
SOURCE_ZIP_BASENAME = "data.zip"

PROHIBITED_TOPIC_TERMS = {
    "care_setting": {"clinic", "hospital", "pharmacy"},
    "condition": {"cancer", "diagnosis", "disease", "symptom"},
    "care_process": {"medication", "medicine", "surgery", "therapy", "treatment", "vaccine"},
    "health_context": {"clinical", "doctor", "health", "healthcare", "medical", "patient", "physician", "pregnancy"},
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable_id(namespace: str, value: str, length: int = 16) -> str:
    return hashlib.sha256(f"{TRANSFORMATION_VERSION}|{namespace}|{value}".encode("utf-8")).hexdigest()[:length]


def _normalized_stem(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", PurePosixPath(name).name.lower().removesuffix(".json"))


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    safe: list[zipfile.ZipInfo] = []
    for item in archive.infolist():
        path = PurePosixPath(item.filename)
        if item.is_dir() or item.filename.startswith("__MACOSX/"):
            continue
        if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", item.filename):
            raise ValueError(f"Unsafe ZIP member: {item.filename!r}")
        safe.append(item)
    return safe


def _split_messages(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?m)^-{20,}\s*$", text) if item.strip()]


def _parsed_message(section: str) -> dict[str, Any]:
    message = Parser(policy=policy.default).parsestr(section)
    headers = {name.lower(): str(message.get(name, "")).strip() for name in ("From", "To", "Cc", "Subject", "Date", "Sent", "Message-ID")}
    body = message.get_body(preferencelist=("plain",)) if message.is_multipart() else None
    content = body.get_content() if body is not None else message.get_payload()
    if not isinstance(content, str):
        content = str(content or "")
    if not headers["from"] and not headers["subject"]:
        header_block, _, fallback_body = section.partition("\n\n")
        for line in header_block.splitlines():
            match = re.match(r"(?i)^(from|to|cc|subject|date|sent|message-id)\s*:\s*(.*)$", line)
            if match:
                headers[match.group(1).lower()] = match.group(2).strip()
        if fallback_body:
            content = fallback_body
    return {"headers": headers, "body": content.strip()}


def _topic_hits(value: Any) -> list[str]:
    text = json.dumps(value, ensure_ascii=False).lower()
    hits: list[str] = []
    for category, terms in PROHIBITED_TOPIC_TERMS.items():
        if any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms):
            hits.append(category)
    return sorted(hits)


def _identity_alias(value: str) -> str:
    return f"participant-{_stable_id('participant', value.strip().lower(), 12)}@example.invalid"


def _extract_people(headers: Iterable[str]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for display_name, address in getaddresses(list(headers)):
        canonical = (address or display_name).strip().lower()
        if not canonical:
            continue
        alias = _identity_alias(canonical)
        if display_name and len(display_name.strip()) >= 4:
            aliases[display_name.strip()] = alias.split("@", 1)[0]
    return aliases


EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL_PATTERN = re.compile(r"(?i)\bhttps?://[^\s<>]+")
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")
LOCAL_PATH_PATTERN = re.compile(
    r"(?i)(?:[A-Z]:\\[^\r\n<>\"|?*]+|\\\\[^\r\n<>\"|?*]+|/(?:home|users|tmp|var)/[^\s<>\"|?*]+)"
)


def _pseudonymize(text: str, identities: dict[str, str]) -> str:
    result = str(text or "")
    for original, alias in sorted(identities.items(), key=lambda item: -len(item[0])):
        result = re.sub(rf"(?<!\w){re.escape(original)}(?!\w)", alias, result, flags=re.IGNORECASE)
    result = URL_PATTERN.sub(lambda match: f"https://link-{_stable_id('url', match.group(0), 12)}.example.invalid/", result)
    result = PHONE_PATTERN.sub(lambda match: f"phone-{_stable_id('phone', match.group(0), 12)}", result)
    result = LOCAL_PATH_PATTERN.sub(lambda match: f"local-path-{_stable_id('path', match.group(0), 12)}", result)
    result = EMAIL_PATTERN.sub(lambda match: _identity_alias(match.group(0)), result)
    return result


def _pseudonymize_value(value: Any, identities: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _pseudonymize(value, identities)
    if isinstance(value, list):
        return [_pseudonymize_value(item, identities) for item in value]
    if isinstance(value, dict):
        return {key: _pseudonymize_value(item, identities) for key, item in value.items()}
    return value


def _json_annotations(value: dict[str, Any], identities: dict[str, str]) -> dict[str, Any]:
    sentences = value.get("sentences") or []
    turns = [
        _pseudonymize(" ".join(str(token) for token in tokens), identities)
        if isinstance(tokens, list)
        else _pseudonymize(str(tokens), identities)
        for tokens in sentences
    ]
    return {"turn_text": turns, "events": _pseudonymize_value(value.get("events") or {}, identities)}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="")


def _action_preannotation(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ensure_backend_path()
    from action_closure import MessageEvidence, reconstruct_actions

    output = []
    for thread in threads:
        evidence = [
            MessageEvidence(
                evidence_id=message["message_id"],
                source_type="Email",
                timestamp=message.get("timestamp") or f"ORDER-{message['message_order']:06d}",
                sender=message["sender"],
                recipients=tuple(message["recipients"]),
                subject=message["subject"],
                body=message["body"],
                thread_id=thread["thread_id"],
                relation_key=thread["thread_id"],
            )
            for message in thread["messages"]
        ]
        result = reconstruct_actions(evidence)
        output.append({
            "thread_id": thread["thread_id"],
            "annotation_status": ANNOTATION_STATUS,
            "engine_version": result["engine_version"],
            "actions": result["actions"],
            "human_validation_state": MANUAL_STATUS,
        })
    return output


def build_local_mailex_candidate(source_zip: Path, output_dir: Path, limit: int = 120) -> dict[str, Any]:
    if source_zip.name != SOURCE_ZIP_BASENAME:
        raise ValueError(f"Expected local source basename {SOURCE_ZIP_BASENAME!r}")
    if limit < 100:
        raise ValueError("MailEx candidate limit must be at least 100")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to mix MailEx output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_bytes = source_zip.read_bytes()
    with zipfile.ZipFile(source_zip) as archive:
        members = _safe_members(archive)
        names = [item.filename for item in members]
        licence_names = [name for name in names if re.search(r"(?i)(^|/)(licen[cs]e|copying|readme)(\.|$)", PurePosixPath(name).name)]
        json_by_split: dict[str, list[str]] = defaultdict(list)
        for name in names:
            match = re.search(r"/data/(train|dev|test|full_data)/([^/]+\.json)$", f"/{name}")
            if match:
                json_by_split[match.group(1)].append(name)
        split_by_stem: dict[str, set[str]] = defaultdict(set)
        for split in ("train", "dev", "test"):
            for name in json_by_split.get(split, []):
                split_by_stem[_normalized_stem(name)].add(split)
        raw_names = [name for name in names if "/raw_threads/" in f"/{name}"]
        raw_by_stem = {_normalized_stem(name): name for name in raw_names}
        full_names = sorted(json_by_split.get("full_data", []))

        selected: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        unmatched = sum(_normalized_stem(name) not in raw_by_stem for name in full_names)
        for json_name in full_names:
            stem = _normalized_stem(json_name)
            raw_name = raw_by_stem.get(stem)
            if not raw_name:
                continue
            annotation_bytes = archive.read(json_name)
            annotation_value = json.loads(annotation_bytes)
            raw_bytes = archive.read(raw_name)
            raw_text = raw_bytes.decode("utf-8", errors="replace")
            parsed_messages = [_parsed_message(item) for item in _split_messages(raw_text)]
            pre_hits = _topic_hits({"messages": parsed_messages, "annotations": annotation_value})
            source_hash = _stable_id("source-thread", stem, 24)
            if pre_hits:
                excluded.append({"source_thread_hash": source_hash, "reason_category": "NO_HEALTH_THREAD_EXCLUSION", "matched_term_categories": pre_hits})
                continue
            identities = _extract_people(
                value
                for message in parsed_messages
                for value in (message["headers"].get("from", ""), message["headers"].get("to", ""), message["headers"].get("cc", ""))
            )
            thread_id = f"mailex-thread-{source_hash}"
            messages: list[dict[str, Any]] = []
            for order, parsed in enumerate(parsed_messages):
                headers = parsed["headers"]
                sender_addresses = getaddresses([headers.get("from", "")])
                recipient_addresses = getaddresses([headers.get("to", ""), headers.get("cc", "")])
                sender_value = (sender_addresses[0][1] or sender_addresses[0][0]) if sender_addresses else "unknown-sender"
                recipients = [address or name for name, address in recipient_addresses if address or name]
                source_message = headers.get("message-id") or f"{stem}:{order}"
                messages.append({
                    "message_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:mailex:{source_message}")),
                    "source_message_id_hash": _stable_id("message", source_message, 24),
                    "message_order": order,
                    "sender": _identity_alias(sender_value),
                    "recipients": sorted({_identity_alias(value) for value in recipients}),
                    "subject": _pseudonymize(headers.get("subject", ""), identities),
                    "timestamp": headers.get("date") or headers.get("sent") or None,
                    "body": _pseudonymize(parsed["body"], identities),
                })
            transformed = {
                "thread_id": thread_id,
                "source_record_id_hash": source_hash,
                "source_split": sorted(split_by_stem.get(stem, {"unassigned"})),
                "messages": messages,
                "annotations": _json_annotations(annotation_value, identities),
                "transformation_version": TRANSFORMATION_VERSION,
                "source_hashes": {
                    "raw_thread_sha256": _sha256(raw_bytes),
                    "annotation_json_sha256": _sha256(annotation_bytes),
                    "source_zip_sha256": _sha256(zip_bytes),
                },
                "human_validation_state": MANUAL_STATUS,
            }
            post_hits = _topic_hits(transformed)
            if post_hits:
                excluded.append({"source_thread_hash": source_hash, "reason_category": "NO_HEALTH_DERIVED_FIELD_EXCLUSION", "matched_term_categories": post_hits})
                continue
            selected.append(transformed)
            if len(selected) >= limit:
                break

        if len(selected) < 100:
            raise RuntimeError(f"Only {len(selected)} usable MailEx threads remained after exclusion")

        preannotations = _action_preannotation(selected)
        second_count = max(1, (len(selected) + 4) // 5)
        assignments = [
            {
                "thread_id": item["thread_id"],
                "primary_annotator": "PENDING_ASSIGNMENT",
                "primary_status": MANUAL_STATUS,
                "second_annotation_required": index < second_count,
                "second_annotator": "PENDING_ASSIGNMENT" if index < second_count else "NOT_ASSIGNED",
                "second_status": MANUAL_STATUS if index < second_count else "NOT_REQUIRED",
            }
            for index, item in enumerate(selected)
        ]
        adjudication = [
            {
                "thread_id": item["thread_id"],
                "annotator_a_label": "",
                "annotator_b_label": "",
                "disagreement_category": "",
                "adjudicator": "",
                "final_label": "",
                "status": "PENDING_HUMAN_ANNOTATION",
            }
            for item in selected
        ]
        split_counts = Counter(split for item in selected for split in item["source_split"])
        manifest = {
            "candidate_status": "READY_FOR_HUMAN_ANNOTATION_NOT_FREEZE",
            "transformation_version": TRANSFORMATION_VERSION,
            "source_zip_basename": source_zip.name,
            "source_zip_sha256": _sha256(zip_bytes),
            "source_zip_size": len(zip_bytes),
            "licence_status": LICENCE_STATUS,
            "licence_identifier": None,
            "selected_thread_count": len(selected),
            "excluded_thread_count": len(excluded),
            "unmatched_full_data_count": unmatched,
            "primary_annotation_count": len(assignments),
            "second_annotation_count": second_count,
            "split_counts": dict(sorted(split_counts.items())),
            "source_record_ids_are_irreversibly_hashed": True,
            "raw_source_committed": False,
            "derived_candidate_committed": False,
            "human_annotation_complete": False,
            "adjudication_complete": False,
            "manual_no_health_signoff_complete": False,
        }
        source_report = {
            "source_zip_basename": source_zip.name,
            "zip_sha256": _sha256(zip_bytes),
            "zip_size": len(zip_bytes),
            "logical_internal_file_count": len(members),
            "dataset_format": "ZIP containing token-list/event JSON plus delimiter-separated RFC-822-like raw threads",
            "split_files_found": {key: len(value) for key, value in sorted(json_by_split.items())},
            "raw_thread_files_found": len(raw_names),
            "licence_readme_files_found": licence_names,
            "licence_status": LICENCE_STATUS,
            "licence_identifier": None,
            "fields_found": [
                "events.turn_N.<event>.labels/triggers/extras",
                "sentences token lists",
                "From",
                "To",
                "Cc where present",
                "Subject",
                "Date/Sent where present",
                "Message-ID where present",
            ],
            "thread_identifier_strategy": "normalized source filename retained only as irreversible hash",
            "selected_parser": "zip-direct JSON parser plus delimiter/RFC-822-compatible raw-thread parser",
            "unresolved_issues": [
                "No licence/readme evidence was found locally; human licence and redistribution confirmation is required.",
                "Most raw messages lack a source Message-ID or timestamp; deterministic derived IDs and order are retained, with missing timestamps left null.",
                "Automated no-health exclusion requires manual sign-off before release.",
            ],
        }

    _write_jsonl(output_dir / "candidate_threads.jsonl", selected)
    _write_jsonl(output_dir / "action_closure_preannotations.jsonl", preannotations)
    _write_json(output_dir / "candidate_manifest.json", manifest)
    _write_json(output_dir / "source_report.json", source_report)
    _write_json(output_dir / "no_health_exclusion_log.json", {"excluded": excluded, "raw_text_included": False})
    _write_csv(output_dir / "annotation_assignments.csv", assignments, list(assignments[0]))
    _write_csv(output_dir / "adjudication_template.csv", adjudication, list(adjudication[0]))
    (output_dir / "manual_annotation_instructions.md").write_text(
        "# Mail action annotation instructions\n\nStatus: PENDING_HUMAN_REVIEW\n\n"
        "Review the pseudonymized thread in message order. Treat every machine preannotation as MACHINE_SUGGESTION_NOT_GOLD. "
        "Label request, acceptance, completion, cancellation, rejection, postponement, reminder, acknowledgement, status-update and supersession evidence. "
        "Assign OPEN, CLOSED_COMPLETED, CLOSED_CANCELLED or SUPERSEDED only from the thread evidence. "
        "Second annotators work independently; disagreements go to the adjudication template. Do not calculate agreement until human labels exist.\n",
        encoding="utf-8",
    )
    return {"manifest": manifest, "source_report": source_report}
