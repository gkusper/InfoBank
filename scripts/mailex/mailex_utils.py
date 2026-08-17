from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


SPLITS = ("train", "dev", "test")
EVENT_REQUEST_ACTION = "Request_Action"
EVENT_DELIVER_ACTION_DATA = "Deliver_Action_Data"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "have",
    "has",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "please",
    "that",
    "the",
    "this",
    "to",
    "we",
    "with",
    "you",
    "your",
}

REQUEST_SIGNAL = re.compile(
    r"\b(please|need to|needs to|must|send|review|prepare|provide|forward|verify|"
    r"confirm|draft|file|submit|complete|return|call|contact|check|update|pay|"
    r"redistribute|run|calculate|distribute|give|apply|move)\b",
    re.IGNORECASE,
)

REQUEST_EXCLUSION = re.compile(
    r"\b(let me know|r\.s\.v\.p|wedding|spouse|vacation|feel free|ignore the first|"
    r"invite anyone else|virus|quarantined)\b",
    re.IGNORECASE,
)

CLOSURE_PATTERNS = {
    "cancelled": re.compile(r"\b(cancelled|canceled|disregard|withdrawn|no longer needed)\b", re.IGNORECASE),
    "superseded": re.compile(r"\b(replaced|superseded|new version|instead|revised)\b", re.IGNORECASE),
    "completed": re.compile(
        r"\b(done|completed|finished|sent|provided|attached|resolved|submitted|"
        r"forwarded|reviewed|drafted|prepared|paid|filed|delivered)\b",
        re.IGNORECASE,
    ),
}

NONCLOSING_PATTERN = re.compile(
    r"\b(will|working on|started|start|continue|plan|going to|intend|expect|"
    r"should be able|would)\b",
    re.IGNORECASE,
)

PERSON_NAME_TOKENS = (
    "Andy",
    "Carol",
    "Gossett",
    "Jay",
    "Jeff",
    "Mary",
    "Rabon",
    "Tom",
    "Vernon",
)
PERSON_NAME_RE = re.compile(r"\b(" + "|".join(re.escape(name) for name in PERSON_NAME_TOKENS) + r")\b")
PERSON_NAME_ALIASES = {name.lower(): f"person_{index:02d}" for index, name in enumerate(PERSON_NAME_TOKENS, start=1)}


def resolve_data_root(source: str | Path) -> Path:
    path = Path(source)
    candidates = [
        path,
        path / "data",
        path / "extracted" / "data",
        path / "Email-Event-Extraction" / "data",
    ]
    for candidate in candidates:
        if all((candidate / split).is_dir() for split in SPLITS):
            return candidate
    raise FileNotFoundError(f"Could not find MailEx train/dev/test directories under {path}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iter_split_files(data_root: Path):
    for split in SPLITS:
        for path in sorted((data_root / split).glob("*.json")):
            yield split, path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def turn_index(turn_id: str) -> int:
    match = re.search(r"(\d+)$", turn_id)
    return int(match.group(1)) if match else 0


def turn_timestamp(turn_id: str) -> str:
    # MailEx split JSON does not expose original message timestamps. Use a
    # deterministic synthetic thread-local clock for temporal benchmark checks.
    base = datetime(2001, 1, 1, 9, 0, 0)
    return (base + timedelta(days=turn_index(turn_id))).isoformat()


def detokenize(tokens: list[str]) -> str:
    text = " ".join(tokens)
    text = re.sub(r"\s+([,.;?!:)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_label_spans(sentence: list[str], labels: list[str]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for index, label in enumerate(labels):
        if label == "O":
            if current:
                spans.append(current)
                current = None
            continue
        tail = label.split(":")[-1].strip()
        match = re.match(r"([BI])-\s*(.+)", tail)
        prefix = match.group(1) if match else "B"
        role = match.group(2).strip() if match else tail
        if prefix == "B" or current is None or current["role"] != role:
            if current:
                spans.append(current)
            current = {"role": role, "tokens": [sentence[index]], "indices": [index]}
        else:
            current["tokens"].append(sentence[index])
            current["indices"].append(index)
    if current:
        spans.append(current)
    return spans


def event_argument_spans(data: dict[str, Any], turn_id: str, event_type: str) -> dict[str, list[str]]:
    event = data["events"][turn_id][event_type]
    sentence = data["sentences"][turn_index(turn_id)]
    roles: dict[str, list[str]] = {}
    for labels in event.get("labels") or []:
        for span in parse_label_spans(sentence, labels):
            roles.setdefault(span["role"], []).append(detokenize(span["tokens"]))
    return roles


def extract_turn_text(data: dict[str, Any], turn_id: str, max_tokens: int = 90) -> str:
    sentence = data["sentences"][turn_index(turn_id)]
    return detokenize(sentence[:max_tokens])


def sanitize_excerpt(value: str) -> str:
    value = re.sub(r"[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "email@example.test", value)
    value = re.sub(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b", "phone-number", value)
    value = re.sub(r"\bx\d{4,6}\b", "extension", value, flags=re.IGNORECASE)
    value = PERSON_NAME_RE.sub(lambda match: PERSON_NAME_ALIASES[match.group(0).lower()], value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def action_topic(action_description: str, limit: int = 6) -> str:
    terms = [term for term in re.findall(r"[A-Za-z][A-Za-z0-9]+", action_description.lower()) if term not in STOPWORDS]
    if not terms:
        return "current task"
    return " ".join(terms[:limit])


def is_good_request(description: str) -> bool:
    words = description.split()
    if not (3 <= len(words) <= 32):
        return False
    return bool(REQUEST_SIGNAL.search(description)) and not REQUEST_EXCLUSION.search(description)


def classify_closure(text: str) -> str | None:
    for label in ("cancelled", "superseded", "completed"):
        if CLOSURE_PATTERNS[label].search(text):
            return label
    return None


def is_nonclosing(text: str) -> bool:
    return bool(NONCLOSING_PATTERN.search(text)) and classify_closure(text) is None


def jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def jsonl_read(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
