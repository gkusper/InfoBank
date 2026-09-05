#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
import statistics
import subprocess
import sys
import tarfile
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable


SPLITS = ("train", "dev", "test")
PROJECT_URL = "https://github.com/salokr/Email-Event-Extraction"
DATASET_DRIVE_URL = "https://drive.google.com/file/d/1a336g4-wlEwsVbXLPB9wPQnBDRE933mb/view"
HF_DATASET_URL = "https://huggingface.co/datasets/salokr/MailEx"

ACTION_EVENT_TYPES = {
    "Request_Action",
    "Request_Action_Data",
    "Deliver_Action_Data",
    "Amend_Action_Data",
}

REQUEST_PAT = re.compile(
    r"\b(please|need(?:ed)?|needs to|must|send|review|prepare|provide|forward|verify|"
    r"confirm|draft|file|submit|complete|return|call|contact|check|update|approve)\b",
    re.IGNORECASE,
)
COMMITMENT_PAT = re.compile(
    r"\b(i will|we will|i'll|we'll|will send|will provide|will review|will follow|"
    r"going to|plan to|can send|can provide|let me)\b",
    re.IGNORECASE,
)
DEADLINE_PAT = re.compile(
    r"\b(today|tomorrow|tonight|eod|cob|asap|by (?:monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday|noon|close|end)|next week|this week|\d{1,2}/\d{1,2})\b",
    re.IGNORECASE,
)
COMPLETION_PAT = re.compile(
    r"\b(done|completed|finished|sent|provided|attached|resolved|submitted|delivered|"
    r"forwarded|reviewed|drafted|prepared|filed)\b",
    re.IGNORECASE,
)
CANCEL_PAT = re.compile(
    r"\b(cancel(?:ed|led)?|disregard|withdrawn|withdraw|no longer needed|delete|remove)\b",
    re.IGNORECASE,
)
MODIFY_PAT = re.compile(
    r"\b(update(?:d)?|revised|revision|change(?:d)?|modify|modified|instead|replace(?:d)?|"
    r"add(?:ed)?|delete(?:d)?)\b",
    re.IGNORECASE,
)
REJECT_PAT = re.compile(
    r"\b(unable|cannot|can't|decline|rejected|negative|not possible|won't|will not|"
    r"no thanks|do not)\b",
    re.IGNORECASE,
)
CONFIRM_PAT = re.compile(
    r"\b(confirm(?:ed)?|yes|approved|ok|okay|agreed|positive|correct|sounds good)\b",
    re.IGNORECASE,
)

EMAIL_PAT = re.compile(r"[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PAT = re.compile(r"\b(?:\+?\d[\d .()/-]{6,}\d|x\d{3,6})\b", re.IGNORECASE)


@dataclass
class DatasetSource:
    kind: str
    root: Path
    files: dict[str, bytes]
    source_revision: str | None = None
    checksum_sha256: str | None = None

    def names(self) -> list[str]:
        return sorted(self.files)

    def read_bytes(self, name: str) -> bytes:
        return self.files[name]

    def read_text(self, name: str) -> str:
        return self.read_bytes(name).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run_git(repo: Path, args: list[str], *, binary: bool = False) -> bytes | str:
    cmd = ["git", "-C", str(repo), *args]
    out = subprocess.check_output(cmd)
    if binary:
        return out
    return out.decode("utf-8", errors="replace").strip()


def load_dataset(path: Path) -> DatasetSource:
    if not path.exists():
        raise FileNotFoundError(f"MailEx dataset path does not exist: {path}")
    if path.is_file() and zipfile.is_zipfile(path):
        data = path.read_bytes()
        files: dict[str, bytes] = {}
        with zipfile.ZipFile(BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                files[info.filename.replace("\\", "/")] = archive.read(info)
        return DatasetSource(
            kind="zip",
            root=path,
            files=files,
            checksum_sha256=sha256_bytes(data),
        )
    if path.is_dir() and (path / ".git").exists():
        revision = run_git(path, ["rev-parse", "HEAD"])
        archive_bytes = run_git(path, ["archive", "--format=tar", "HEAD"], binary=True)
        files = {}
        with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                handle = archive.extractfile(member)
                if handle is None:
                    continue
                files[member.name.replace("\\", "/")] = handle.read()
        return DatasetSource(
            kind="git-archive",
            root=path,
            files=files,
            source_revision=revision,
            checksum_sha256=sha256_bytes(archive_bytes),
        )
    if path.is_dir():
        files = {}
        for file_path in path.rglob("*"):
            if file_path.is_file():
                rel = file_path.relative_to(path).as_posix()
                files[rel] = file_path.read_bytes()
        return DatasetSource(kind="directory", root=path, files=files)
    raise ValueError(f"Unsupported dataset path: {path}")


def normalize_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        for item in value:
            tokens.extend(normalize_tokens(item))
    return tokens


def detokenize(tokens: list[str]) -> str:
    text = " ".join(token for token in tokens if token is not None)
    text = re.sub(r"\s+([,.;?!:)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sanitize(value: str, max_words: int = 18) -> str:
    value = EMAIL_PAT.sub("email@example.test", value)
    value = PHONE_PAT.sub("phone-number", value)
    value = re.sub(r"\s+", " ", value).strip()
    words = value.split()
    if len(words) > max_words:
        value = " ".join(words[:max_words]) + "..."
    return value


def percentile(values: list[int], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * pct
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    weight = pos - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def split_thread_paths(names: Iterable[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for split in SPLITS:
        prefix = f"data/{split}/"
        result[split] = sorted(
            name
            for name in names
            if name.startswith(prefix)
            and name.endswith(".json")
            and "/._" not in name
            and not Path(name).name.startswith(".")
        )
    return result


def thread_id_from_path(path: str) -> str:
    return Path(path).name.removesuffix(".json")


def raw_id_from_path(path: str) -> str:
    base = Path(path).name
    return base[:-1] if base.endswith(".") else base


def turn_index(turn_id: str) -> int:
    match = re.search(r"(\d+)$", turn_id)
    return int(match.group(1)) if match else 0


def parse_trigger(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return sanitize(value), ""
    if isinstance(parsed, dict):
        return sanitize(str(parsed.get("words", ""))), str(parsed.get("indices", ""))
    return sanitize(str(parsed)), ""


def parse_label(label: str) -> tuple[str, str, str] | None:
    if label == "O":
        return None
    tail = label.split(":", 1)[1] if ":" in label else label
    match = re.search(r"\b([BI])-\s*(.+)$", tail)
    if not match:
        return "", "", tail.strip()
    prefix = match.group(1)
    role = match.group(2).strip()
    modifier = tail[: match.start()].strip(" :")
    return prefix, modifier, role


def extract_label_spans(tokens: list[str], labels: list[str]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for index, label in enumerate(labels):
        parsed = parse_label(label)
        if parsed is None:
            if current:
                spans.append(current)
                current = None
            continue
        _prefix, modifier, role = parsed
        begins = label.split(":")[-1].lstrip().startswith("B-")
        if begins or current is None or current["role"] != role or current["modifier"] != modifier:
            if current:
                spans.append(current)
            current = {
                "role": role,
                "modifier": modifier,
                "tokens": [tokens[index] if index < len(tokens) else ""],
                "indices": [index],
            }
        else:
            current["tokens"].append(tokens[index] if index < len(tokens) else "")
            current["indices"].append(index)
    if current:
        spans.append(current)
    return spans


def parse_meta_extra(extra: str) -> tuple[str, str]:
    if not extra or ":" not in extra:
        return extra.strip(), ""
    left, right = extra.split(":", 1)
    return left.strip(), right.strip()


def raw_header_stats(raw_text: str) -> dict[str, Any]:
    segments = [part.strip() for part in re.split(r"\n-{5,}\n", raw_text) if part.strip()]
    fields = Counter()
    date_values = []
    participants = set()
    for segment in segments:
        for line in segment.splitlines()[:30]:
            match = re.match(r"^([A-Za-z-]+)\s*:\s*(.*)$", line)
            if not match:
                continue
            key = match.group(1).upper()
            value = match.group(2).strip()
            fields[key] += 1
            if key in {"FROM", "TO", "CC", "BCC"} and value:
                for part in re.split(r"[,;]", value):
                    if part.strip():
                        participants.add(part.strip().lower())
            if key == "DATE" and value:
                date_values.append(value)
    parsed_dates = 0
    malformed_dates = 0
    for value in date_values:
        try:
            parsedate_to_datetime(value)
            parsed_dates += 1
        except (TypeError, ValueError, IndexError, OverflowError):
            malformed_dates += 1
    return {
        "segments": len(segments),
        "fields": dict(fields),
        "participant_count": len(participants),
        "date_values": len(date_values),
        "parsed_dates": parsed_dates,
        "malformed_dates": malformed_dates,
    }


def lexical_flags(text: str) -> dict[str, int]:
    patterns = {
        "request": REQUEST_PAT,
        "commitment": COMMITMENT_PAT,
        "deadline": DEADLINE_PAT,
        "completion": COMPLETION_PAT,
        "cancel": CANCEL_PAT,
        "modify": MODIFY_PAT,
        "reject": REJECT_PAT,
        "confirm": CONFIRM_PAT,
    }
    return {name: int(bool(pattern.search(text))) for name, pattern in patterns.items()}


def source_commit(path: Path | None) -> str | None:
    if not path or not path.exists() or not (path / ".git").exists():
        return None
    try:
        return str(run_git(path, ["rev-parse", "HEAD"]))
    except subprocess.CalledProcessError:
        return None


def read_repo_file(repo: Path | None, rel: str) -> str | None:
    if not repo or not repo.exists():
        return None
    path = repo / rel
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    if (repo / ".git").exists():
        try:
            return str(run_git(repo, ["show", f"HEAD:{rel}"]))
        except subprocess.CalledProcessError:
            return None
    return None


def inspect_license(dataset: DatasetSource, project_repo: Path | None, hf_repo: Path | None) -> dict[str, Any]:
    project_readme = read_repo_file(project_repo, "README.md") or ""
    hf_readme = read_repo_file(hf_repo, "README.md") or ""
    dataset_license_files = [
        name
        for name in dataset.names()
        if Path(name).name.lower() in {"license", "license.md", "copying", "copying.md"}
    ]
    project_license_files = []
    if project_repo and project_repo.exists():
        for name in ("LICENSE", "LICENSE.md", "COPYING", "COPYING.md"):
            if (project_repo / name).exists():
                project_license_files.append(name)
    project_claim = "CC BY-SA 4.0" if "CC BY-SA 4.0" in project_readme else None
    hf_license = None
    match = re.search(r"(?m)^license:\s*([A-Za-z0-9_.-]+)\s*$", hf_readme)
    if match:
        hf_license = match.group(1)
    claims = [claim for claim in (project_claim, hf_license) if claim]
    normalized = {claim.lower().replace("_", "-") for claim in claims}
    ambiguous = len(normalized) > 1 or not claims or bool(dataset_license_files) is False
    return {
        "project_url": PROJECT_URL,
        "dataset_download_url": DATASET_DRIVE_URL,
        "huggingface_dataset_url": HF_DATASET_URL,
        "project_repo_commit": source_commit(project_repo),
        "hf_dataset_repo_commit": source_commit(hf_repo),
        "project_readme_claim": project_claim,
        "project_readme_evidence": "README.md Licensing Information states the dataset is distributed under CC BY-SA 4.0."
        if project_claim
        else "No CC BY-SA 4.0 claim found in project README.md.",
        "hf_dataset_card_license": hf_license,
        "hf_dataset_card_evidence": f"README.md metadata declares license: {hf_license}."
        if hf_license
        else "No HuggingFace license metadata found.",
        "dataset_internal_license_files": dataset_license_files,
        "project_license_files": project_license_files,
        "research_reuse_allowed": "Both cited Creative Commons variants allow reuse with attribution; public redistribution obligations differ.",
        "attribution_required": True,
        "share_alike_requirement": "Required under the project README CC BY-SA 4.0 claim; not required under the HuggingFace cc-by-4.0 metadata.",
        "applies_to_dataset_or_code": "The project README explicitly says the dataset is distributed under CC BY-SA 4.0; the HuggingFace dataset card license metadata applies to the dataset card/repository. No separate code LICENSE was found.",
        "ambiguous_or_incomplete": ambiguous,
        "blocker": "Exact public redistribution terms are ambiguous because project README says CC BY-SA 4.0 while HuggingFace metadata says cc-by-4.0 and no dataset-internal LICENSE file was observed.",
    }


def audit(dataset: DatasetSource, project_repo: Path | None, hf_repo: Path | None, candidate_limit: int) -> dict[str, Any]:
    names = dataset.names()
    split_paths = split_thread_paths(names)
    json_paths = [path for split in SPLITS for path in split_paths[split]]
    full_data_paths = sorted(
        name
        for name in names
        if name.startswith("data/full_data/")
        and name.endswith(".json")
        and "/._" not in name
        and not Path(name).name.startswith(".")
    )
    raw_paths = sorted(
        name
        for name in names
        if name.startswith("data/raw_threads/")
        and not name.endswith("/")
        and "/._" not in name
        and not Path(name).name.startswith(".")
    )
    raw_by_id: dict[str, list[str]] = defaultdict(list)
    for path in raw_paths:
        raw_by_id[raw_id_from_path(path)].append(path)

    file_exts = Counter(Path(name).suffix.lower() or "(none)" for name in names if "/._" not in name)
    top_dirs = Counter(name.split("/")[0] for name in names)
    data_dirs = Counter("/".join(name.split("/")[:2]) if name.startswith("data/") else name for name in names)

    event_instances = Counter()
    event_groups = Counter()
    event_threads = defaultdict(set)
    event_turns = Counter()
    event_label_sequences = Counter()
    event_nonempty_triggers = Counter()
    event_examples: dict[str, dict[str, str]] = {}
    role_tokens = Counter()
    role_spans = Counter()
    role_modifiers = Counter()
    meta_extras = Counter()
    meta_categories = Counter()
    quality = Counter()
    lexical_turn_counts = Counter()
    lexical_thread_counts = Counter()
    action_annotation_thread_counts = Counter()
    action_annotation_turn_counts = Counter()

    thread_rows: list[dict[str, Any]] = []
    candidate_pool: list[dict[str, Any]] = []
    thread_lengths: list[int] = []
    nonempty_lengths: list[int] = []
    raw_segment_counts: list[int] = []
    raw_field_presence = Counter()
    raw_date_values = 0
    raw_parsed_dates = 0
    raw_malformed_dates = 0
    raw_duplicate_ids = {key: value for key, value in raw_by_id.items() if len(value) > 1}
    seen_turn_hashes = Counter()

    for split in SPLITS:
        for path in split_paths[split]:
            thread_id = thread_id_from_path(path)
            data = json.loads(dataset.read_text(path))
            events_by_turn = data.get("events", {})
            sentence_values = data.get("sentences", [])
            tokens_by_turn = [normalize_tokens(value) for value in sentence_values]
            texts_by_turn = [detokenize(tokens) for tokens in tokens_by_turn]
            thread_len = len(sentence_values)
            nonempty_len = sum(1 for text in texts_by_turn if text)
            thread_lengths.append(thread_len)
            nonempty_lengths.append(nonempty_len)
            if len(events_by_turn) != thread_len:
                quality["events_sentences_length_mismatch"] += 1
            expected_turns = [f"turn_{index}" for index in range(thread_len)]
            if sorted(events_by_turn, key=turn_index) != expected_turns:
                quality["nonsequential_turn_ids"] += 1
            if nonempty_len < thread_len:
                quality["threads_with_empty_turns"] += 1
                quality["empty_turns"] += thread_len - nonempty_len

            thread_event_instances = 0
            thread_event_groups = 0
            thread_event_types = Counter()
            thread_roles = Counter()
            thread_meta = Counter()
            thread_lexical = Counter()
            action_turns = 0
            request_turn_indexes: list[int] = []
            later_action_after_request = False

            for turn_id, event_map in sorted(events_by_turn.items(), key=lambda item: turn_index(item[0])):
                idx = turn_index(turn_id)
                tokens = tokens_by_turn[idx] if idx < len(tokens_by_turn) else []
                turn_text = texts_by_turn[idx] if idx < len(texts_by_turn) else ""
                if turn_text:
                    seen_turn_hashes[hashlib.sha1(turn_text.lower().encode("utf-8")).hexdigest()] += 1
                flags = lexical_flags(turn_text)
                for flag, value in flags.items():
                    if value:
                        lexical_turn_counts[flag] += 1
                        thread_lexical[flag] += 1
                for event_type, event_data in event_map.items():
                    labels = event_data.get("labels") or []
                    triggers = event_data.get("triggers") or []
                    extras = event_data.get("extras") or []
                    count = max(len(labels), len(triggers), len(extras), 1)
                    event_groups[event_type] += 1
                    event_turns[event_type] += 1
                    if event_type in ACTION_EVENT_TYPES:
                        action_turns += 1
                        action_annotation_turn_counts[event_type] += 1
                    if event_type == "Request_Action":
                        request_turn_indexes.append(idx)
                    if event_type != "O":
                        event_instances[event_type] += count
                        event_label_sequences[event_type] += len(labels)
                        event_threads[event_type].add(thread_id)
                        thread_event_instances += count
                        thread_event_groups += 1
                        thread_event_types[event_type] += count
                        if triggers:
                            nonempty = [trigger for trigger in triggers if trigger]
                            event_nonempty_triggers[event_type] += len(nonempty)
                            if nonempty and event_type not in event_examples:
                                words, indices = parse_trigger(nonempty[0])
                                event_examples[event_type] = {"trigger": words, "indices": indices}
                        for extra in extras:
                            category, value = parse_meta_extra(extra)
                            if extra:
                                meta_extras[extra] += 1
                                meta_categories[category] += 1
                                thread_meta[extra] += 1
                        for label_sequence in labels:
                            spans = extract_label_spans(tokens, label_sequence)
                            for span in spans:
                                role = str(span["role"])
                                modifier = str(span["modifier"])
                                role_spans[role] += 1
                                role_tokens[role] += len(span["tokens"])
                                if modifier:
                                    role_modifiers[modifier] += 1
                                thread_roles[role] += 1
                    else:
                        event_threads[event_type].add(thread_id)

            if request_turn_indexes:
                for later_idx in range(max(request_turn_indexes) + 1, thread_len):
                    later_key = f"turn_{later_idx}"
                    later_events = set(events_by_turn.get(later_key, {}))
                    if later_events & {"Deliver_Action_Data", "Request_Action", "Amend_Action_Data", "Amend_Data"}:
                        later_action_after_request = True
                        break
            for event_type in ACTION_EVENT_TYPES:
                if thread_event_types.get(event_type):
                    action_annotation_thread_counts[event_type] += 1
            for flag, count in thread_lexical.items():
                if count:
                    lexical_thread_counts[flag] += 1

            raw_stats = None
            raw_paths_for_thread = raw_by_id.get(thread_id, [])
            if raw_paths_for_thread:
                raw_text = dataset.read_bytes(raw_paths_for_thread[0]).decode("utf-8", errors="replace")
                raw_stats = raw_header_stats(raw_text)
                raw_segment_counts.append(int(raw_stats["segments"]))
                for key, count in raw_stats["fields"].items():
                    raw_field_presence[key] += int(count)
                raw_date_values += int(raw_stats["date_values"])
                raw_parsed_dates += int(raw_stats["parsed_dates"])
                raw_malformed_dates += int(raw_stats["malformed_dates"])
            else:
                quality["missing_raw_thread_for_split_thread"] += 1

            duplicate_turns = sum(count - 1 for count in seen_turn_hashes.values() if count > 1)
            row = {
                "split": split,
                "thread_id": thread_id,
                "source_path": path,
                "thread_length": thread_len,
                "nonempty_turns": nonempty_len,
                "empty_turns": thread_len - nonempty_len,
                "event_instances": thread_event_instances,
                "event_groups": thread_event_groups,
                "event_types": ";".join(sorted(thread_event_types)),
                "request_action_instances": thread_event_types.get("Request_Action", 0),
                "deliver_action_data_instances": thread_event_types.get("Deliver_Action_Data", 0),
                "amend_instances": sum(value for key, value in thread_event_types.items() if key.startswith("Amend")),
                "has_later_action_after_request": int(later_action_after_request),
                "lexical_request_turns": thread_lexical.get("request", 0),
                "lexical_commitment_turns": thread_lexical.get("commitment", 0),
                "lexical_deadline_turns": thread_lexical.get("deadline", 0),
                "lexical_completion_turns": thread_lexical.get("completion", 0),
                "lexical_cancel_turns": thread_lexical.get("cancel", 0),
                "lexical_modify_turns": thread_lexical.get("modify", 0),
                "lexical_reject_turns": thread_lexical.get("reject", 0),
                "lexical_confirm_turns": thread_lexical.get("confirm", 0),
                "raw_segments": raw_stats["segments"] if raw_stats else "",
                "raw_participant_count": raw_stats["participant_count"] if raw_stats else "",
                "raw_has_date": int(bool(raw_stats and raw_stats["date_values"])),
            }
            thread_rows.append(row)

            score = (
                (thread_len >= 2) * 3
                + min(thread_event_instances, 10)
                + thread_event_types.get("Request_Action", 0) * 3
                + thread_event_types.get("Deliver_Action_Data", 0) * 2
                + int(later_action_after_request) * 5
                + sum(thread_lexical.values())
                + min(thread_len, 6)
            )
            if thread_len >= 2 and (thread_event_instances or sum(thread_lexical.values())):
                reasons = []
                if later_action_after_request:
                    reasons.append("request followed by later action-related MailEx event")
                if thread_event_types.get("Request_Action"):
                    reasons.append("contains Request_Action")
                if thread_event_types.get("Deliver_Action_Data"):
                    reasons.append("contains Deliver_Action_Data")
                amend_total = sum(value for key, value in thread_event_types.items() if key.startswith("Amend"))
                if amend_total:
                    reasons.append("contains Amend event")
                for flag in ("deadline", "completion", "cancel", "modify", "reject", "confirm"):
                    if thread_lexical.get(flag):
                        reasons.append(f"has deterministic {flag} lexical signal")
                candidate_pool.append(
                    {
                        "score": score,
                        "split": split,
                        "thread_id": thread_id,
                        "source_path": path,
                        "thread_length": thread_len,
                        "nonempty_turns": nonempty_len,
                        "event_instances": thread_event_instances,
                        "event_types": ";".join(sorted(thread_event_types)),
                        "request_action_instances": thread_event_types.get("Request_Action", 0),
                        "deliver_action_data_instances": thread_event_types.get("Deliver_Action_Data", 0),
                        "amend_instances": amend_total,
                        "lexical_indicators": ";".join(sorted(flag for flag, count in thread_lexical.items() if count)),
                        "raw_participant_count": raw_stats["participant_count"] if raw_stats else "",
                        "selection_reasons": "; ".join(reasons[:6]) if reasons else "multi-message event-annotated thread",
                    }
                )

    duplicate_text_turns = sum(count - 1 for count in seen_turn_hashes.values() if count > 1)
    if duplicate_text_turns:
        quality["duplicate_turn_text_hashes"] = duplicate_text_turns

    selected_candidates = select_candidates(candidate_pool, candidate_limit)

    event_rows = []
    for event_type in sorted(event_instances):
        example = event_examples.get(event_type, {})
        roles_for_event = sorted(
            {
                row_role
                for thread_row in thread_rows
                if event_type in str(thread_row["event_types"]).split(";")
                for row_role in []
            }
        )
        del roles_for_event
        event_rows.append(
            {
                "event_type": event_type,
                "event_instances": event_instances[event_type],
                "event_groups": event_groups[event_type],
                "threads_with_event": len(event_threads[event_type]),
                "turns_with_event_group": event_turns[event_type],
                "label_sequences": event_label_sequences[event_type],
                "nonempty_triggers": event_nonempty_triggers[event_type],
                "example_trigger": example.get("trigger", ""),
                "example_trigger_indices": example.get("indices", ""),
                "iscmi_relevance_note": relevance_note(event_type),
            }
        )

    lengths_summary = length_summary(thread_lengths)
    nonempty_lengths_summary = length_summary(nonempty_lengths)
    raw_lengths_summary = length_summary(raw_segment_counts)

    annotations = {
        "event_instance_total_excluding_O": sum(event_instances.values()),
        "event_group_total_including_O": sum(event_groups.values()),
        "event_group_total_excluding_O": sum(value for key, value in event_groups.items() if key != "O"),
        "event_types_observed_excluding_O": sorted(event_instances),
        "event_type_frequencies": dict(sorted(event_instances.items())),
        "event_group_frequencies": dict(sorted(event_groups.items())),
        "argument_role_span_frequencies": dict(role_spans.most_common()),
        "argument_role_token_frequencies": dict(role_tokens.most_common()),
        "label_modifiers_observed": dict(role_modifiers.most_common()),
        "meta_semantic_role_frequencies": dict(meta_extras.most_common()),
        "meta_semantic_categories": dict(meta_categories.most_common()),
        "trigger_annotations": {
            "nonempty_triggers": sum(event_nonempty_triggers.values()),
            "format": "serialized dictionaries with words and token indices",
        },
        "cross_message_relationships": "not explicitly annotated",
        "event_dependencies": "not explicitly annotated",
    }

    messages = {
        "annotated_turns_total": sum(thread_lengths),
        "nonempty_annotated_turns": sum(nonempty_lengths),
        "empty_or_placeholder_turns": quality.get("empty_turns", 0),
        "message_identifier": "No explicit per-message ID in split JSON; thread file and turn_N index can form a local ID.",
        "thread_identifier": "Recoverable from JSON file name.",
        "sender": "Not in split JSON; partially recoverable from raw_threads FROM headers.",
        "recipients": "Not in split JSON; partially recoverable from raw_threads TO headers.",
        "cc_bcc": "Rare/mostly absent in raw_threads; not in split JSON.",
        "timestamp_date": "Not in split JSON; only rare DATE-like raw headers observed.",
        "subject": "Not in split JSON; recoverable from raw_threads SUBJECT headers.",
        "body": "Tokenized body text is available in split JSON sentences.",
        "quoted_previous_messages": "No explicit quote structure in split JSON; raw_threads preserve concatenated history-like text.",
        "ordering_within_thread": "Recoverable from turn_0, turn_1, ... order.",
        "reply_relationships": "No Message-ID/In-Reply-To/References graph observed.",
    }

    raw_threads = {
        "raw_thread_files": len(raw_paths),
        "raw_thread_ids": len(raw_by_id),
        "raw_duplicate_ids": len(raw_duplicate_ids),
        "raw_files_not_matched_to_split_threads": len(set(raw_by_id) - {thread_id_from_path(path) for path in json_paths}),
        "raw_segments_summary": raw_lengths_summary,
        "raw_header_field_occurrences": dict(raw_field_presence.most_common()),
        "raw_date_values": raw_date_values,
        "raw_parsed_dates": raw_parsed_dates,
        "raw_malformed_dates": raw_malformed_dates,
        "windows_problematic_raw_filenames": sum(1 for path in raw_paths if Path(path).name.endswith(".")),
    }

    threads = {
        "thread_count": len(json_paths),
        "split_thread_counts": {split: len(split_paths[split]) for split in SPLITS},
        "thread_length_distribution": lengths_summary,
        "nonempty_thread_length_distribution": nonempty_lengths_summary,
        "single_message_threads": sum(1 for value in thread_lengths if value == 1),
        "threads_with_at_least_2_messages": sum(1 for value in thread_lengths if value >= 2),
        "threads_with_at_least_3_messages": sum(1 for value in thread_lengths if value >= 3),
        "threads_with_at_least_4_messages": sum(1 for value in thread_lengths if value >= 4),
        "threads_with_at_least_5_messages": sum(1 for value in thread_lengths if value >= 5),
        "ordering_basis": "turn_N order in each JSON file",
    }

    candidate_counts = {
        "annotation_based": dict(sorted(action_annotation_thread_counts.items())),
        "annotation_based_turn_groups": dict(sorted(action_annotation_turn_counts.items())),
        "lexical_thread_counts": dict(sorted(lexical_thread_counts.items())),
        "lexical_turn_counts": dict(sorted(lexical_turn_counts.items())),
        "request_then_later_action_threads": sum(int(row["has_later_action_after_request"]) for row in thread_rows),
        "candidate_pool_size": len(candidate_pool),
        "pilot_candidates_selected": len(selected_candidates),
    }

    files = {
        "total_files_in_input": len(names),
        "top_level_counts": dict(sorted(top_dirs.items())),
        "data_directory_counts": {key: data_dirs[key] for key in sorted(data_dirs) if key.startswith("data/")},
        "extension_counts": dict(sorted(file_exts.items())),
        "split_json_files": {split: len(split_paths[split]) for split in SPLITS},
        "full_data_json_files": len(full_data_paths),
        "raw_thread_files": len(raw_paths),
        "encoding": "UTF-8 for JSON files; raw thread files decoded as UTF-8 with replacement fallback for audit.",
        "annotation_format": "JSON dictionaries: events[turn_N][event_type] contains labels, triggers, extras; sentences contains tokenized turns.",
    }

    summary = {
        "dataset": {
            "name": "MailEx / Email Event and Argument Extraction",
            "source_project_url": PROJECT_URL,
            "dataset_drive_url": DATASET_DRIVE_URL,
            "huggingface_dataset_url": HF_DATASET_URL,
            "input_path": str(dataset.root),
            "input_kind": dataset.kind,
            "input_sha256": dataset.checksum_sha256,
            "source_revision": dataset.source_revision,
        },
        "license": inspect_license(dataset, project_repo, hf_repo),
        "files": files,
        "messages": messages,
        "threads": threads,
        "annotations": annotations,
        "quality_issues": dict(sorted(quality.items())),
        "raw_threads": raw_threads,
        "candidate_analysis": candidate_counts,
        "iscmi_suitability": suitability(candidate_counts, annotations, messages, threads),
    }

    return {
        "summary": summary,
        "event_rows": event_rows,
        "thread_rows": thread_rows,
        "candidate_rows": selected_candidates,
    }


def length_summary(values: list[int]) -> dict[str, Any]:
    if not values:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
            "p90": None,
        }
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.mean(values), 3),
        "median": round(statistics.median(values), 3),
        "p25": round(percentile(values, 0.25), 3),
        "p75": round(percentile(values, 0.75), 3),
        "p90": round(percentile(values, 0.90), 3),
    }


def relevance_note(event_type: str) -> str:
    notes = {
        "Request_Action": "Strong CREATE/open-action candidate, but not final ISCMI ground truth.",
        "Request_Action_Data": "Potential CREATE or MODIFY candidate involving action plus data request.",
        "Deliver_Action_Data": "Potential COMPLETE/CONFIRM evidence candidate depending on context.",
        "Amend_Action_Data": "Potential MODIFY or CANCEL candidate, very sparse.",
        "Amend_Data": "Potential MODIFY candidate for data-centric tasks.",
        "Deliver_Data": "Contextual or completion evidence for data delivery.",
        "Request_Data": "Possible contextual data request, not necessarily an action item.",
        "Request_Meeting": "Possible CREATE candidate for meeting-related task.",
        "Deliver_Meeting_Data": "Possible confirmation/context for meeting state.",
        "Request_Meting_Data": "Possible contextual meeting data request.",
        "Request_Meeting_Data": "Possible contextual meeting data request.",
        "Amend_Meeting_Data": "Potential MODIFY candidate for meeting state.",
    }
    return notes.get(event_type, "Observed MailEx event type; mapping requires manual inspection.")


def suitability(
    candidate_counts: dict[str, Any],
    annotations: dict[str, Any],
    messages: dict[str, Any],
    threads: dict[str, Any],
) -> dict[str, Any]:
    return {
        "classification": "SUITABLE WITH ADDITIONAL MANUAL ANNOTATION",
        "rationale": (
            "MailEx provides ordered multi-message threads and explicit event/action annotations "
            "such as Request_Action and Deliver_Action_Data, so it can support a later manual "
            "pilot for action-item evolution. It does not provide final ISCMI transition labels, "
            "evidence roles, task-state labels, reliable timestamps, reply graphs, or explicit "
            "cross-message event dependencies."
        ),
        "create_candidate_basis": "Request_Action, Request_Action_Data, Request_Meeting and request lexical indicators.",
        "confirm_candidate_basis": "Deliver_Action_Data extras such as Deliver Confirmation : Positive plus confirm lexical indicators.",
        "modify_candidate_basis": "Amend_* event types, Amend Action extras and modify lexical indicators.",
        "complete_candidate_basis": "Deliver_Action_Data/Deliver_Data and completion lexical indicators.",
        "cancel_candidate_basis": "Sparse Amend Action : Delete and cancel/delete lexical indicators; manual confirmation needed.",
        "reject_candidate_basis": "Deliver Confirmation : Negative and reject lexical indicators; sparse and ambiguous.",
        "none_candidate_basis": "O event groups and turns without action-related event annotations.",
        "evidence_roles_present": False,
        "task_state_present": False,
        "future_annotation_required": True,
        "candidate_pilot_threads": candidate_counts.get("pilot_candidates_selected"),
        "message_turns": messages.get("annotated_turns_total"),
        "threads": threads.get("thread_count"),
        "annotated_events": annotations.get("event_instance_total_excluding_O"),
    }


def select_candidates(pool: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ordered = sorted(
        pool,
        key=lambda row: (
            -int(row["score"]),
            -int(row["thread_length"]),
            str(row["split"]),
            str(row["thread_id"]),
        ),
    )
    selected: list[dict[str, Any]] = []
    seen_splits = Counter()
    seen_lengths = Counter()
    for row in ordered:
        if len(selected) >= limit:
            break
        length_bucket = "5+" if int(row["thread_length"]) >= 5 else str(row["thread_length"])
        if seen_splits[row["split"]] > max(20, limit // 2) and len(selected) < limit - 5:
            continue
        if seen_lengths[length_bucket] > max(12, limit // 3) and len(selected) < limit - 5:
            continue
        selected.append(row)
        seen_splits[row["split"]] += 1
        seen_lengths[length_bucket] += 1
    if len(selected) < limit:
        selected_ids = {row["thread_id"] for row in selected}
        for row in ordered:
            if len(selected) >= limit:
                break
            if row["thread_id"] not in selected_ids:
                selected.append(row)
                selected_ids.add(row["thread_id"])
    result = []
    for index, row in enumerate(selected, start=1):
        row = dict(row)
        row.pop("score", None)
        row["candidate_id"] = f"MAILEX_CAND_{index:03d}"
        result.append(row)
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def render_report(summary: dict[str, Any], event_rows: list[dict[str, Any]]) -> str:
    dataset = summary["dataset"]
    license_info = summary["license"]
    files = summary["files"]
    messages = summary["messages"]
    threads = summary["threads"]
    annotations = summary["annotations"]
    quality = summary["quality_issues"]
    raw = summary["raw_threads"]
    candidate = summary["candidate_analysis"]
    suitability_info = summary["iscmi_suitability"]
    length = threads["thread_length_distribution"]
    raw_length = raw["raw_segments_summary"]
    raw_header_top = dict(list(raw["raw_header_field_occurrences"].items())[:20])
    event_table = "\n".join(
        f"| {row['event_type']} | {row['event_instances']} | {row['event_groups']} | "
        f"{row['threads_with_event']} | {row['example_trigger']} |"
        for row in event_rows
    )
    role_top = "\n".join(
        f"- {role}: {count}"
        for role, count in list(annotations["argument_role_span_frequencies"].items())[:20]
    )
    meta_top = "\n".join(
        f"- {extra or '(blank)'}: {count}"
        for extra, count in list(annotations["meta_semantic_role_frequencies"].items())[:20]
    )
    quality_lines = "\n".join(f"- {key}: {value}" for key, value in quality.items()) or "- None detected by the audit script."

    return f"""# MailEx Technical Audit for ISCMI 2026

## 1. Dataset Identification

Dataset: MailEx / Email Event and Argument Extraction.

Project URL: {dataset['source_project_url']}

Dataset URL: {dataset['dataset_drive_url']}

HuggingFace mirror inspected for metadata comparison: {dataset['huggingface_dataset_url']}

Input kind: `{dataset['input_kind']}`

Input SHA-256: `{dataset['input_sha256']}`

## 2. Licence and Research-use Status

- Project README evidence: {license_info['project_readme_evidence']}
- HuggingFace dataset-card evidence: {license_info['hf_dataset_card_evidence']}
- Dataset-internal licence files observed: {license_info['dataset_internal_license_files']}
- Attribution required: {license_info['attribution_required']}
- Share-alike status: {license_info['share_alike_requirement']}
- Scope: {license_info['applies_to_dataset_or_code']}

Licensing note: {license_info['blocker']}

For internal research auditing, both cited Creative Commons variants permit reuse with attribution. For public redistribution of derived materials, the exact CC BY versus CC BY-SA obligation should be resolved before release.

## 3. Actual Dataset Structure

Observed file counts:

- Total files in ZIP/object tree: {files['total_files_in_input']}
- Split JSON files: {files['split_json_files']}
- Full-data JSON files: {files['full_data_json_files']}
- Raw thread files: {files['raw_thread_files']}
- Extension counts: {files['extension_counts']}

The primary annotated split data lives under `data/train`, `data/dev`, and `data/test`. Each split file is a JSON document with `events` and `sentences` top-level keys. `data/raw_threads` contains concatenated raw-ish thread text files, many with trailing-dot filenames. `data/full_data` contains 1500 JSON files parallel to the split data in the downloaded ZIP.

The HuggingFace Git mirror was also inspected and currently exposes only 100 train JSON files while the Google Drive ZIP exposes 1200 train JSON files. The audit therefore treats the Google Drive ZIP as the complete dataset source for measured annotation statistics.

## 4. Message Structure

- Annotated turns/messages: {messages['annotated_turns_total']}
- Nonempty annotated turns: {messages['nonempty_annotated_turns']}
- Empty or placeholder turns: {messages['empty_or_placeholder_turns']}
- Message identifier: {messages['message_identifier']}
- Thread identifier: {messages['thread_identifier']}
- Sender: {messages['sender']}
- Recipients: {messages['recipients']}
- CC/BCC: {messages['cc_bcc']}
- Timestamp/date: {messages['timestamp_date']}
- Subject: {messages['subject']}
- Body: {messages['body']}
- Quoted previous messages: {messages['quoted_previous_messages']}
- Ordering: {messages['ordering_within_thread']}
- Reply relationships: {messages['reply_relationships']}

Raw header evidence:

- Raw segments: min {raw_length['min']}, median {raw_length['median']}, max {raw_length['max']}
- Raw header field occurrences, top 20: {raw_header_top}
- Raw DATE values observed: {raw['raw_date_values']}
- Parsed DATE values: {raw['raw_parsed_dates']}
- Malformed DATE values: {raw['raw_malformed_dates']}

## 5. Thread Reconstruction

- Distinct annotated threads: {threads['thread_count']}
- Split thread counts: {threads['split_thread_counts']}
- Thread length min/mean/median/max: {length['min']} / {length['mean']} / {length['median']} / {length['max']}
- P25/P75/P90: {length['p25']} / {length['p75']} / {length['p90']}
- Single-message threads: {threads['single_message_threads']}
- Threads with at least 2 messages: {threads['threads_with_at_least_2_messages']}
- Threads with at least 3 messages: {threads['threads_with_at_least_3_messages']}
- Threads with at least 4 messages: {threads['threads_with_at_least_4_messages']}
- Threads with at least 5 messages: {threads['threads_with_at_least_5_messages']}

MailEx supports a local sequence equivalent to `turn_0 -> turn_1 -> ...` within each JSON file. It does not expose a reliable absolute timestamp sequence or Message-ID/In-Reply-To graph in the annotated split JSON.

## 6. MailEx Annotation Model

Observed top-level annotation shape:

- `events[turn_N][event_type].labels`: BIO argument labels over the tokenized turn.
- `events[turn_N][event_type].triggers`: serialized trigger dictionaries with words and indices.
- `events[turn_N][event_type].extras`: meta-semantic strings such as deliver confirmation or amend action.

Annotated event instances excluding `O`: {annotations['event_instance_total_excluding_O']}

Event types:

| Event type | Instances | Event groups | Threads | Example trigger |
|---|---:|---:|---:|---|
{event_table}

Top argument roles by span count:

{role_top}

Top meta-semantic extras:

{meta_top}

Event dependencies and cross-message event relations are not explicitly annotated. Events can be associated with a specific thread file and `turn_N` email.

## 7. Quantitative Statistics

Annotation-based action-related thread counts:

```json
{json.dumps(candidate['annotation_based'], indent=2, sort_keys=True)}
```

Deterministic lexical candidate counts by thread:

```json
{json.dumps(candidate['lexical_thread_counts'], indent=2, sort_keys=True)}
```

These lexical counts are transparent candidate indicators only. They are not ground truth labels.

## 8. Data Quality Issues

{quality_lines}

Additional issues:

- Raw thread files: {raw['raw_thread_files']} files but {raw['raw_thread_ids']} normalized raw IDs.
- Raw duplicate IDs: {raw['raw_duplicate_ids']}.
- Raw files not matched to split threads: {raw['raw_files_not_matched_to_split_threads']}.
- Windows-problematic trailing-dot raw filenames: {raw['windows_problematic_raw_filenames']}.
- HuggingFace mirror train split count differs from the Google Drive ZIP count.

## 9. Suitability for ISCMI 2026

Classification: **{suitability_info['classification']}**

{suitability_info['rationale']}

The dataset is useful for a later manual pilot because it contains ordered email turns, action/request/delivery/amendment event types, trigger spans, argument spans, and meta-semantic extras. It is not sufficient by itself as final ISCMI ground truth because communication transitions, evidence roles, and task states are not MailEx labels.

## 10. Candidate Mapping to ISCMI Transitions

- CREATE: {suitability_info['create_candidate_basis']}
- CONFIRM: {suitability_info['confirm_candidate_basis']}
- MODIFY: {suitability_info['modify_candidate_basis']}
- COMPLETE: {suitability_info['complete_candidate_basis']}
- CANCEL: {suitability_info['cancel_candidate_basis']}
- REJECT: {suitability_info['reject_candidate_basis']}

These mappings are feasibility notes only. No CREATE/CONFIRM/MODIFY/COMPLETE/CANCEL/REJECT labels were assigned.

## 11. Limitations

- Licence metadata is inconsistent across source locations.
- Split JSON lacks structured sender, recipient, date, CC/BCC, Message-ID, and reply-reference fields.
- Raw headers are partial and sparse for dates.
- Some turns are empty placeholders.
- Cross-message event dependencies are absent.
- Lexical candidate counts are heuristics, not labels.

## 12. Recommendation

**{suitability_info['classification']}**

MailEx is appropriate for a follow-up manual pilot shortlist and later carefully documented annotation work. It should not be treated as ready-made ISCMI transition/state ground truth, and public redistribution terms should be clarified before releasing derived examples or benchmark subsets.
"""


def write_outputs(out_dir: Path, results: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = results["summary"]
    (out_dir / "mailex_audit_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_csv(out_dir / "mailex_event_statistics.csv", results["event_rows"])
    write_csv(out_dir / "mailex_thread_statistics.csv", results["thread_rows"])
    write_csv(out_dir / "mailex_pilot_candidates.csv", results["candidate_rows"])
    (out_dir / "mailex_audit_report.md").write_text(
        render_report(summary, results["event_rows"]), encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministically audit the MailEx dataset for ISCMI 2026 suitability.")
    parser.add_argument("--dataset-path", required=True, help="Path to MailEx data.zip, extracted dataset directory, or Git repo.")
    parser.add_argument("--project-repo", default="", help="Optional local clone of salokr/Email-Event-Extraction for license evidence.")
    parser.add_argument("--hf-dataset-repo", default="", help="Optional local HuggingFace dataset repo for metadata comparison.")
    parser.add_argument("--out-dir", default=str(Path(__file__).resolve().parent), help="Directory for audit outputs.")
    parser.add_argument("--candidate-limit", type=int, default=50, help="Number of pilot candidate threads to list.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_dataset(Path(args.dataset_path))
    project_repo = Path(args.project_repo) if args.project_repo else None
    hf_repo = Path(args.hf_dataset_repo) if args.hf_dataset_repo else None
    results = audit(dataset, project_repo, hf_repo, args.candidate_limit)
    write_outputs(Path(args.out_dir), results)
    summary = results["summary"]
    print(json.dumps({
        "threads": summary["threads"]["thread_count"],
        "messages": summary["messages"]["annotated_turns_total"],
        "events": summary["annotations"]["event_instance_total_excluding_O"],
        "candidates": summary["candidate_analysis"]["pilot_candidates_selected"],
        "classification": summary["iscmi_suitability"]["classification"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
