"""Deterministic, content-based accounting of the local MailEx ZIP.

Generated tables contain paths, hashes, counts, and relationship evidence but
never raw subjects, message bodies, participant mappings, or annotation text.
"""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from .mailex_local import (
    LICENCE_STATUS,
    SOURCE_ZIP_BASENAME,
    _normalized_stem,
    _parsed_message,
    _split_messages,
    _topic_hits,
)


RECONCILIATION_VERSION = "infobank-mailex-reconciliation-v1"
ALLOWED_CATEGORIES = {
    "MATCHED_ONE_TO_ONE",
    "MATCHED_ALIAS",
    "DUPLICATE_JSON",
    "DUPLICATE_RAW",
    "UNMATCHED_JSON",
    "UNMATCHED_RAW",
    "NON_THREAD_LOGICAL_FILE",
    "MACOS_METADATA",
    "EXCLUDED_NO_HEALTH",
    "MALFORMED",
    "OTHER_EXPLAINED",
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record_id(path: str, content_sha256: str) -> str:
    return hashlib.sha256(f"{RECONCILIATION_VERSION}|{path}|{content_sha256}".encode("utf-8")).hexdigest()[:24]


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", text.lower()))


def _json_tokens(value: bytes) -> tuple[str, ...]:
    parsed = json.loads(value)
    sentences = parsed.get("sentences") or []
    return _tokens(" ".join(" ".join(map(str, row)) if isinstance(row, list) else str(row) for row in sentences))


def _raw_tokens(value: bytes) -> tuple[str, ...]:
    sections = _split_messages(value.decode("utf-8", errors="replace"))
    messages = [_parsed_message(section) for section in sections]
    return _tokens(" ".join(message["body"] for message in messages))


def _token_set_hash(tokens: tuple[str, ...]) -> str:
    return _sha256("\n".join(sorted(set(tokens))).encode("utf-8"))


def _similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _logical_basename(path: str, *, json_record: bool) -> str:
    name = PurePosixPath(path).name
    return name.removesuffix(".json") if json_record else name.rstrip(".")


def _best_bipartite_pairs(
    json_names: list[str],
    raw_names: list[str],
    json_meta: dict[str, dict[str, Any]],
    raw_meta: dict[str, dict[str, Any]],
) -> list[tuple[str, str, float]]:
    candidates: list[tuple[float, int, int, str, str]] = []
    raw_by_set: dict[str, list[str]] = defaultdict(list)
    raw_stems = defaultdict(list)
    for raw_name in raw_names:
        raw_by_set[raw_meta[raw_name]["token_set_hash"]].append(raw_name)
        raw_stems[raw_meta[raw_name]["normalized_stem"]].append(raw_name)

    for json_name in json_names:
        meta = json_meta[json_name]
        candidate_names = set(raw_stems.get(meta["normalized_stem"], []))
        candidate_names.update(raw_by_set.get(meta["token_set_hash"], []))
        if not candidate_names:
            for raw_name in raw_names:
                score = _similarity(meta["tokens"], raw_meta[raw_name]["tokens"])
                if score >= 0.75:
                    candidate_names.add(raw_name)
        for raw_name in candidate_names:
            raw = raw_meta[raw_name]
            score = _similarity(meta["tokens"], raw["tokens"])
            same_stem = int(meta["normalized_stem"] == raw["normalized_stem"])
            exact_basename = int(
                _logical_basename(json_name, json_record=True)
                == _logical_basename(raw_name, json_record=False)
            )
            candidates.append((score, same_stem, exact_basename, json_name, raw_name))

    used_json: set[str] = set()
    used_raw: set[str] = set()
    pairs: list[tuple[str, str, float]] = []
    for score, same_stem, exact_basename, json_name, raw_name in sorted(
        candidates,
        key=lambda row: (-row[0], -row[1], -row[2], row[3], row[4]),
    ):
        if json_name in used_json or raw_name in used_raw:
            continue
        used_json.add(json_name)
        used_raw.add(raw_name)
        pairs.append((json_name, raw_name, score))
    return pairs


def build_match_plan(
    archive: zipfile.ZipFile,
    full_names: list[str],
    raw_names: list[str],
) -> dict[str, Any]:
    json_meta: dict[str, dict[str, Any]] = {}
    raw_meta: dict[str, dict[str, Any]] = {}
    malformed_json: list[str] = []
    malformed_raw: list[str] = []

    for name in full_names:
        value = archive.read(name)
        try:
            tokens = _json_tokens(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            malformed_json.append(name)
            continue
        json_meta[name] = {
            "tokens": tokens,
            "token_set_hash": _token_set_hash(tokens),
            "normalized_stem": _normalized_stem(name),
            "sha256": _sha256(value),
        }
    for name in raw_names:
        value = archive.read(name)
        try:
            tokens = _raw_tokens(value)
        except (TypeError, ValueError):
            malformed_raw.append(name)
            continue
        raw_meta[name] = {
            "tokens": tokens,
            "token_set_hash": _token_set_hash(tokens),
            "normalized_stem": _normalized_stem(name),
            "sha256": _sha256(value),
        }

    primary_pairs = _best_bipartite_pairs(list(json_meta), list(raw_meta), json_meta, raw_meta)
    json_to_raw = {json_name: raw_name for json_name, raw_name, _ in primary_pairs}
    used_raw = set(json_to_raw.values())
    relations: list[dict[str, Any]] = []

    for json_name, raw_name, score in primary_pairs:
        same_stem = json_meta[json_name]["normalized_stem"] == raw_meta[raw_name]["normalized_stem"]
        relations.append({
            "category": "MATCHED_ONE_TO_ONE" if same_stem else "MATCHED_ALIAS",
            "json_record_id": _record_id(json_name, json_meta[json_name]["sha256"]),
            "json_logical_path": json_name,
            "json_sha256": json_meta[json_name]["sha256"],
            "raw_record_id": _record_id(raw_name, raw_meta[raw_name]["sha256"]),
            "raw_logical_path": raw_name,
            "raw_sha256": raw_meta[raw_name]["sha256"],
            "content_token_set_similarity": round(score, 9),
            "explanation": "normalized stem plus content evidence" if same_stem else "content match under a different logical filename",
        })

    unmatched_json_names = [name for name in json_meta if name not in json_to_raw]
    for json_name in sorted(unmatched_json_names):
        best = max(
            (
                (_similarity(json_meta[json_name]["tokens"], raw_meta[raw_name]["tokens"]), raw_name)
                for raw_name in used_raw
            ),
            default=(0.0, ""),
        )
        score, raw_name = best
        if raw_name and score >= 0.85:
            json_to_raw[json_name] = raw_name
            relations.append({
                "category": "MATCHED_ALIAS",
                "json_record_id": _record_id(json_name, json_meta[json_name]["sha256"]),
                "json_logical_path": json_name,
                "json_sha256": json_meta[json_name]["sha256"],
                "raw_record_id": _record_id(raw_name, raw_meta[raw_name]["sha256"]),
                "raw_logical_path": raw_name,
                "raw_sha256": raw_meta[raw_name]["sha256"],
                "content_token_set_similarity": round(score, 9),
                "explanation": "additional JSON annotation aliases an already matched raw thread by content",
            })

    relation_by_json = {row["json_logical_path"]: row for row in relations}
    relation_by_raw = {
        row["raw_logical_path"]: row
        for row in relations
        if row["raw_logical_path"] in used_raw
    }
    raw_categories: dict[str, dict[str, str]] = {}
    for raw_name in raw_meta:
        if raw_name in relation_by_raw:
            relation = relation_by_raw[raw_name]
            raw_categories[raw_name] = {
                "category": relation["category"],
                "explanation": relation["explanation"],
            }
            continue
        best = max(
            (
                (_similarity(raw_meta[raw_name]["tokens"], json_meta[json_name]["tokens"]), json_name)
                for json_name in json_to_raw
            ),
            default=(0.0, ""),
        )
        score, json_name = best
        same_stem = bool(json_name) and raw_meta[raw_name]["normalized_stem"] == json_meta[json_name]["normalized_stem"]
        if json_name and (score >= 0.98 or (same_stem and score >= 0.75)):
            raw_categories[raw_name] = {
                "category": "DUPLICATE_RAW",
                "explanation": f"alternate raw record for a matched JSON record; token-set similarity={score:.9f}",
            }
        else:
            raw_categories[raw_name] = {
                "category": "UNMATCHED_RAW",
                "explanation": "no JSON record has sufficient content evidence for a match",
            }

    json_categories = {
        name: {
            "category": relation_by_json[name]["category"] if name in relation_by_json else "UNMATCHED_JSON",
            "explanation": relation_by_json[name]["explanation"] if name in relation_by_json else "no raw record has sufficient content evidence for a match",
        }
        for name in json_meta
    }
    for name in malformed_json:
        json_categories[name] = {"category": "MALFORMED", "explanation": "JSON record could not be parsed"}
    for name in malformed_raw:
        raw_categories[name] = {"category": "MALFORMED", "explanation": "raw thread could not be parsed"}

    unexplained_count = sum(
        item["category"] == "OTHER_EXPLAINED" and not item.get("explanation")
        for item in itertools.chain(json_categories.values(), raw_categories.values())
    )
    return {
        "version": RECONCILIATION_VERSION,
        "json_to_raw": json_to_raw,
        "relations": sorted(relations, key=lambda row: row["json_logical_path"]),
        "json_categories": json_categories,
        "raw_categories": raw_categories,
        "unexplained_count": unexplained_count,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="")


def build_mailex_reconciliation(source_zip: Path, output_dir: Path, candidate_dir: Path | None = None) -> dict[str, Any]:
    if source_zip.name != SOURCE_ZIP_BASENAME:
        raise ValueError(f"Expected local source basename {SOURCE_ZIP_BASENAME!r}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to mix reconciliation output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_bytes = source_zip.read_bytes()
    with zipfile.ZipFile(source_zip) as archive:
        non_directory = [item for item in archive.infolist() if not item.is_dir()]
        macos_names = {
            item.filename
            for item in non_directory
            if item.filename.startswith("__MACOSX/") or PurePosixPath(item.filename).name == ".DS_Store"
        }
        logical = [item for item in non_directory if item.filename not in macos_names]
        logical_names = [item.filename for item in logical]
        json_by_split: dict[str, list[str]] = defaultdict(list)
        for name in logical_names:
            match = re.search(r"/data/(train|dev|test|full_data)/([^/]+\.json)$", f"/{name}")
            if match:
                json_by_split[match.group(1)].append(name)
        full_names = sorted(json_by_split.get("full_data", []))
        raw_names = sorted(name for name in logical_names if "/raw_threads/" in f"/{name}")
        plan = build_match_plan(archive, full_names, raw_names)

        excluded_record_hashes: set[str] = set()
        selected_count = 0
        exclusion_count = 0
        if candidate_dir:
            manifest = json.loads((candidate_dir / "candidate_manifest.json").read_text(encoding="utf-8"))
            if manifest.get("source_zip_sha256") != _sha256(zip_bytes):
                raise ValueError("Candidate manifest source hash does not match reconciliation source")
            selected_count = int(manifest.get("selected_thread_count", 0))
            exclusion_log = json.loads((candidate_dir / "no_health_exclusion_log.json").read_text(encoding="utf-8"))
            excluded_record_hashes = {row["source_thread_hash"] for row in exclusion_log.get("excluded", [])}
            exclusion_count = len(excluded_record_hashes)

        inventory: list[dict[str, Any]] = []
        full_set = set(full_names)
        raw_set = set(raw_names)
        split_sets = {key: set(value) for key, value in json_by_split.items()}
        for item in non_directory:
            value = archive.read(item.filename)
            content_sha = _sha256(value)
            category = "OTHER_EXPLAINED"
            explanation = "dataset split projection accounted for by full_data and split membership"
            record_type = "split_json"
            if item.filename in macos_names:
                category = "MACOS_METADATA"
                explanation = "AppleDouble resource metadata or Finder metadata"
                record_type = "macos_metadata"
            elif item.filename in full_set:
                category = plan["json_categories"][item.filename]["category"]
                explanation = plan["json_categories"][item.filename]["explanation"]
                record_type = "full_data_json"
            elif item.filename in raw_set:
                category = plan["raw_categories"][item.filename]["category"]
                explanation = plan["raw_categories"][item.filename]["explanation"]
                record_type = "raw_thread"
            elif not any(item.filename in values for values in split_sets.values()):
                category = "NON_THREAD_LOGICAL_FILE"
                explanation = "logical dataset support file; not a thread record"
                record_type = "non_thread_logical"
            if category not in ALLOWED_CATEGORIES:
                raise AssertionError(f"Unknown reconciliation category: {category}")
            inventory.append({
                "record_id": _record_id(item.filename, content_sha),
                "logical_path": item.filename,
                "record_type": record_type,
                "category": category,
                "explanation": explanation,
                "sha256": content_sha,
                "byte_size": len(value),
            })

        unmatched_json = [row for row in inventory if row["category"] == "UNMATCHED_JSON"]
        unmatched_raw = [row for row in inventory if row["category"] == "UNMATCHED_RAW"]
        duplicate_alias = [
            row for row in plan["relations"] if row["category"] == "MATCHED_ALIAS"
        ] + [
            {
                "category": row["category"],
                "json_record_id": "",
                "json_logical_path": "",
                "json_sha256": "",
                "raw_record_id": row["record_id"],
                "raw_logical_path": row["logical_path"],
                "raw_sha256": row["sha256"],
                "content_token_set_similarity": "",
                "explanation": row["explanation"],
            }
            for row in inventory if row["category"] in {"DUPLICATE_RAW", "DUPLICATE_JSON"}
        ]
        category_counts = Counter(row["category"] for row in inventory)
        relationship_counts = Counter(row["category"] for row in plan["relations"])
        summary = {
            "reconciliation_version": RECONCILIATION_VERSION,
            "status": "PASS" if not unmatched_json and plan["unexplained_count"] == 0 else "PARTIAL",
            "source_zip_basename": source_zip.name,
            "source_zip_sha256": _sha256(zip_bytes),
            "source_zip_size": len(zip_bytes),
            "non_directory_entry_count": len(non_directory),
            "macos_metadata_entry_count": len(macos_names),
            "logical_entry_count_after_all_macos_metadata": len(logical),
            "legacy_entry_count_excluding_macosx_directory_only": sum(
                not item.filename.startswith("__MACOSX/") for item in non_directory
            ),
            "json_record_counts": {key: len(value) for key, value in sorted(json_by_split.items())},
            "raw_record_count": len(raw_names),
            "primary_match_count": len({row["raw_logical_path"] for row in plan["relations"]}),
            "one_to_one_relationship_count": relationship_counts["MATCHED_ONE_TO_ONE"],
            "alias_relationship_count": relationship_counts["MATCHED_ALIAS"],
            "duplicate_raw_count": category_counts["DUPLICATE_RAW"],
            "duplicate_json_count": category_counts["DUPLICATE_JSON"],
            "unmatched_raw_count": len(unmatched_raw),
            "unmatched_json_count": len(unmatched_json),
            "non_thread_logical_file_count": category_counts["NON_THREAD_LOGICAL_FILE"],
            "malformed_count": category_counts["MALFORMED"],
            "candidate_selected_thread_count": selected_count,
            "no_health_exclusion_count": exclusion_count,
            "unexplained_count": plan["unexplained_count"],
            "licence_status": LICENCE_STATUS,
            "raw_content_written": False,
        }

    inventory_path = output_dir / "source_entry_inventory.jsonl"
    match_path = output_dir / "json_raw_match_table.csv"
    unmatched_json_path = output_dir / "unmatched_json_records.csv"
    unmatched_raw_path = output_dir / "unmatched_raw_records.csv"
    duplicate_path = output_dir / "duplicate_or_alias_records.csv"
    summary_path = output_dir / "reconciliation_summary.json"
    _write_jsonl(inventory_path, inventory)
    relation_fields = [
        "category", "json_record_id", "json_logical_path", "json_sha256",
        "raw_record_id", "raw_logical_path", "raw_sha256",
        "content_token_set_similarity", "explanation",
    ]
    _write_csv(match_path, plan["relations"], relation_fields)
    inventory_fields = ["record_id", "logical_path", "record_type", "category", "explanation", "sha256", "byte_size"]
    _write_csv(unmatched_json_path, unmatched_json, inventory_fields)
    _write_csv(unmatched_raw_path, unmatched_raw, inventory_fields)
    _write_csv(duplicate_path, duplicate_alias, relation_fields)
    summary_path.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    checksum_rows = []
    for path in (inventory_path, match_path, unmatched_json_path, unmatched_raw_path, duplicate_path, summary_path):
        value = path.read_bytes()
        checksum_rows.append({"filename": path.name, "sha256": _sha256(value), "byte_size": len(value)})
    _write_csv(output_dir / "reconciliation_checksums.csv", checksum_rows, ["filename", "sha256", "byte_size"])
    return summary
