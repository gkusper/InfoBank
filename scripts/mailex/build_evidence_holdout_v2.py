#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from inspect_mailex import inspect
from mailex_utils import (
    EVENT_DELIVER_ACTION_DATA,
    EVENT_REQUEST_ACTION,
    action_topic,
    classify_closure,
    event_argument_spans,
    extract_turn_text,
    is_good_request,
    is_nonclosing,
    iter_split_files,
    jsonl_write,
    load_json,
    resolve_data_root,
    sanitize_excerpt,
    sha256_file,
    sha256_text,
    stable_id,
    turn_index,
    turn_timestamp,
)


DEFAULT_SOURCE = "data/external/mailex/extracted/data"
DEFAULT_OUTPUT = "data/benchmarks/evidence_unit_v2_holdout"
DEFAULT_EXCLUDE = "data/benchmarks/evidence_unit_v1"


def git_commit(path: Path) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except Exception:
        return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def excluded_threads(root: Path) -> set[str]:
    threads: set[str] = set()
    if not (root / "cases.jsonl").exists():
        return threads
    for case in read_jsonl(root / "cases.jsonl"):
        for unit in case.get("evidence_units") or []:
            provenance = unit.get("provenance") or {}
            value = provenance.get("thread_identifier") or provenance.get("mailex_source_filename")
            if value:
                threads.add(str(value).removesuffix(".json"))
    return threads


def collect_requests(data_root: Path, excluded: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requests: list[dict[str, Any]] = []
    nonclosing: list[dict[str, Any]] = []
    for split, path in iter_split_files(data_root):
        thread = path.name.removesuffix(".json")
        if thread in excluded:
            continue
        data = load_json(path)
        source_hash = sha256_text(path.read_text(encoding="utf-8"))
        for turn_id, events in sorted(data.get("events", {}).items(), key=lambda item: turn_index(item[0])):
            if EVENT_REQUEST_ACTION not in events:
                continue
            request_args = event_argument_spans(data, turn_id, EVENT_REQUEST_ACTION)
            description = sanitize_excerpt("; ".join(request_args.get("Action Description", [])))
            if not is_good_request(description):
                continue
            later_events: list[dict[str, Any]] = []
            for later_turn, later in sorted(data.get("events", {}).items(), key=lambda item: turn_index(item[0])):
                if turn_index(later_turn) <= turn_index(turn_id):
                    continue
                if EVENT_DELIVER_ACTION_DATA not in later:
                    continue
                deliver_args = event_argument_spans(data, later_turn, EVENT_DELIVER_ACTION_DATA)
                closure_text = sanitize_excerpt("; ".join(deliver_args.get("Action Description", [])))
                if not closure_text:
                    continue
                later_events.append(
                    {
                        "turn_id": later_turn,
                        "closure_text": closure_text,
                        "closure_excerpt": sanitize_excerpt(extract_turn_text(data, later_turn)),
                        "closure_type": classify_closure(closure_text),
                        "nonclosing": is_nonclosing(closure_text),
                    }
                )
            candidate = {
                "split": split,
                "source_filename": path.name,
                "thread_identifier": thread,
                "turn_id": turn_id,
                "action_description": description,
                "action_members": [sanitize_excerpt(value) for value in request_args.get("Action Members", [])],
                "action_date": sanitize_excerpt("; ".join(request_args.get("Action Date", []))),
                "request_excerpt": sanitize_excerpt(extract_turn_text(data, turn_id)),
                "source_hash": source_hash,
                "later_events": later_events,
            }
            requests.append(candidate)
            for later in later_events:
                if later["nonclosing"]:
                    nonclosing.append({**candidate, "later": later})
                    break
    unique: list[dict[str, Any]] = []
    seen_threads: set[str] = set()
    seen_actions: set[str] = set()
    for candidate in requests:
        action_key = candidate["action_description"].lower()
        if candidate["thread_identifier"] in seen_threads or action_key in seen_actions:
            continue
        seen_threads.add(candidate["thread_identifier"])
        seen_actions.add(action_key)
        unique.append(candidate)
    return unique, nonclosing


def evidence_unit(case_id: str, seed_id: str, source_type: str, title: str, content: str, timestamp: str, relation_key: str, provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": stable_id("EUH", case_id, source_type, timestamp, content),
        "source_type": source_type,
        "title": title,
        "content": content,
        "timestamp": timestamp,
        "thread_id": seed_id,
        "relation_key": relation_key,
        "sender": "person_1@example.test",
        "recipients": ["benchmark_user@example.test"],
        "owner": "benchmark_user",
        "access_mode": "full",
        "provenance": provenance,
    }


def d7_texts(topic: str, index: int) -> tuple[str, list[str]]:
    patterns = [
        ("topic_only_browsing", [f"Visited page: {topic.title()} overview", f"Search query: {topic} background", f"Visited page: {topic.title()} archive"]),
        ("task_like_search_phrase", [f"Search query: how to {topic}", f"Search query: {topic} checklist", f"Visited page: {topic.title()} examples"]),
        ("deadline_related_research", [f"Search query: {topic} deadline rules", f"Visited page: calendar notes for {topic}", f"Search query: {topic} timing example"]),
        ("reference_document_visit", [f"Visited page: reference guide for {topic}", f"Search query: {topic} policy reference", f"Visited page: sample document about {topic}"]),
        ("example_search", [f"Search query: {topic} sample wording", f"Visited page: example library for {topic}", f"Search query: {topic} previous examples"]),
        ("preparation_like_activity", [f"Search query: preparing for {topic}", f"Visited page: preparation notes for {topic}", f"Search query: {topic} planning worksheet"]),
    ]
    return patterns[(index - 1) % len(patterns)]


def synthetic_closure(topic: str, closure_type: str) -> str:
    if closure_type == "completed":
        return f"I have completed {topic} and sent the final package."
    if closure_type == "cancelled":
        return f"The request is no longer needed; please disregard the request for {topic}."
    return f"This has been replaced by a new version instead for {topic}."


def synthetic_nonclosing(topic: str, subtype: str) -> str:
    templates = {
        "acknowledgement": f"I received the note about {topic} and will review the details.",
        "future_commitment": f"I will do {topic} tomorrow after checking the schedule.",
        "progress_update": f"I am working on {topic} and will send an update later.",
        "partial_completion": f"I have started reviewing {topic}, but the final work is not finished.",
        "clarification_request": f"Can you clarify the preferred format before I finish {topic}?",
        "intention_without_completion": f"I plan to handle {topic} after the next review meeting.",
    }
    return templates[subtype]


def base_provenance(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_dataset": "MailEx",
        "source_reference": f"{candidate['split']}:{candidate['source_filename']}:{candidate['turn_id']}",
        "mailex_split": candidate["split"],
        "mailex_source_filename": candidate["source_filename"],
        "thread_identifier": candidate["thread_identifier"],
        "turn_identifier": candidate["turn_id"],
        "source_hash": candidate["source_hash"],
        "excerpted": True,
        "pseudonymized": True,
        "modified": True,
    }


def build_family(index: int, candidate: dict[str, Any], closure_type: str, natural_later: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    seed_id = f"HOLDOUT_SEED_{index:04d}"
    d6_id = f"D6_H_{index:04d}"
    d7_id = f"D7_H_{index:04d}"
    d8_id = f"D8_H_{index:04d}"
    action_id = f"HOLDOUT_ACTION_{index:04d}"
    topic = action_topic(candidate["action_description"])
    relation_key = stable_id("RELH", seed_id, candidate["thread_identifier"], candidate["turn_id"])
    request_time = turn_timestamp(candidate["turn_id"])
    request_content = f"Email message. Direction: inbound. Body excerpt: {candidate['action_description']}."
    request = evidence_unit(
        d6_id,
        seed_id,
        "Email",
        f"Holdout email about {topic}",
        request_content,
        request_time,
        relation_key,
        base_provenance(candidate) | {"transformation_type": "mailex_request_action_excerpt"},
    )
    query_time = (date.fromisoformat(request_time[:10]) + timedelta(days=1)).isoformat() + "T12:00:00"
    d6 = {
        "case_id": d6_id,
        "scenario": "D6",
        "seed_id": seed_id,
        "benchmark_user": "benchmark_user",
        "query": "What is my current action list?",
        "query_time": query_time,
        "evidence_units": [request],
        "matched_family": {"seed_id": seed_id, "d6_case": d6_id, "d7_case": d7_id, "d8_case": d8_id},
    }
    pattern, browser_texts = d7_texts(topic, index)
    browser_units = [
        evidence_unit(
            d7_id,
            seed_id,
            "BrowserHistory",
            text,
            text,
            (date.fromisoformat(request_time[:10]) + timedelta(hours=offset)).isoformat() + "T10:00:00",
            relation_key,
            {
                "source_dataset": "InfoBank synthetic counterfactual derived from MailEx",
                "source_reference": f"derived_from:{seed_id}",
                "derived_from_seed_id": seed_id,
                "transformation_type": "deterministic_browser_trace",
                "transformation_rule": f"deterministic_{pattern}_v2",
                "synthetic": True,
                "excerpted": False,
                "pseudonymized": True,
                "modified": True,
            },
        )
        for offset, text in enumerate(browser_texts, start=1)
    ]
    d7 = {
        "case_id": d7_id,
        "scenario": "D7",
        "seed_id": seed_id,
        "benchmark_user": "benchmark_user",
        "query": "What is my current action list?",
        "query_time": query_time,
        "evidence_units": browser_units,
        "matched_family": {"seed_id": seed_id, "d6_case": d6_id, "d7_case": d7_id, "d8_case": d8_id},
    }
    if natural_later:
        closure_text = natural_later["closure_text"]
        later_time = turn_timestamp(natural_later["turn_id"])
        closure_provenance = base_provenance(candidate) | {
            "source_reference": f"{candidate['split']}:{candidate['source_filename']}:{natural_later['turn_id']}",
            "turn_identifier": natural_later["turn_id"],
            "transformation_type": "mailex_later_action_related_excerpt",
            "closure_source_turn": natural_later["turn_id"],
            "natural_or_synthetic": "natural",
            "synthetic": False,
        }
        natural_or_synthetic = "natural"
    else:
        closure_text = synthetic_closure(topic, closure_type)
        later_time = (date.fromisoformat(request_time[:10]) + timedelta(days=1)).isoformat() + "T09:00:00"
        closure_provenance = {
            "source_dataset": "InfoBank synthetic closure derived from MailEx request seed",
            "source_reference": f"derived_from:{seed_id}",
            "derived_from_seed_id": seed_id,
            "transformation_type": "deterministic_synthetic_closure_v2",
            "synthetic": True,
            "excerpted": False,
            "pseudonymized": True,
            "modified": True,
            "natural_or_synthetic": "synthetic",
        }
        natural_or_synthetic = "synthetic"
    d8_request = {**request, "evidence_id": stable_id("EUH", d8_id, "request", request_content)}
    closure = evidence_unit(
        d8_id,
        seed_id,
        "Email",
        f"Later holdout reply about {topic}",
        f"Email message. Direction: inbound. Later body excerpt: {closure_text}",
        later_time,
        relation_key,
        closure_provenance,
    )
    d8 = {
        "case_id": d8_id,
        "scenario": "D8",
        "seed_id": seed_id,
        "benchmark_user": "benchmark_user",
        "query": "What is my current action list?",
        "query_time": (date.fromisoformat(later_time[:10]) + timedelta(days=1)).isoformat() + "T12:00:00",
        "evidence_units": [d8_request, closure],
        "matched_family": {"seed_id": seed_id, "d6_case": d6_id, "d7_case": d7_id, "d8_case": d8_id},
    }
    gold = [
        {
            "case_id": d6_id,
            "seed_id": seed_id,
            "scenario": "D6",
            "action_id": action_id,
            "actor": "benchmark_user",
            "action_description": candidate["action_description"],
            "object": topic,
            "due_date": candidate.get("action_date") or None,
            "expected_status": "OPEN",
            "expected_presence": True,
            "gold_role": "primary",
            "primary_evidence_ids": [request["evidence_id"]],
            "contextual_evidence_ids": [],
            "contrastive_evidence_ids": [],
            "closure_type": None,
            "natural_or_synthetic": "natural",
        },
        {
            "case_id": d7_id,
            "seed_id": seed_id,
            "scenario": "D7",
            "action_id": action_id,
            "actor": "benchmark_user",
            "action_description": candidate["action_description"],
            "object": topic,
            "due_date": candidate.get("action_date") or None,
            "expected_status": "ABSENT",
            "expected_presence": False,
            "gold_role": "contextual",
            "primary_evidence_ids": [],
            "contextual_evidence_ids": [unit["evidence_id"] for unit in browser_units],
            "contrastive_evidence_ids": [],
            "closure_type": None,
            "natural_or_synthetic": "synthetic",
        },
        {
            "case_id": d8_id,
            "seed_id": seed_id,
            "scenario": "D8",
            "action_id": action_id,
            "actor": "benchmark_user",
            "action_description": candidate["action_description"],
            "object": topic,
            "due_date": candidate.get("action_date") or None,
            "expected_status": "CLOSED",
            "expected_presence": False,
            "gold_role": "contrastive",
            "primary_evidence_ids": [d8_request["evidence_id"]],
            "contextual_evidence_ids": [],
            "contrastive_evidence_ids": [closure["evidence_id"]],
            "closure_type": closure_type,
            "natural_or_synthetic": natural_or_synthetic,
        },
    ]
    triplet = {"seed_id": seed_id, "d6_case_id": d6_id, "d7_case_id": d7_id, "d8_case_id": d8_id}
    curation = {
        "seed_id": seed_id,
        "source_thread": candidate["thread_identifier"],
        "source_message": f"{candidate['split']}:{candidate['source_filename']}:{candidate['turn_id']}",
        "action": candidate["action_description"],
        "responsible_actor": "benchmark_user",
        "query_time": d8["query_time"],
        "relation_key": relation_key,
        "closure_decision": closure_type,
        "closure_subtype": closure_type,
        "natural_or_synthetic": natural_or_synthetic,
        "confidence": "high" if natural_later else "controlled_synthetic",
        "rationale": "Natural lexical closure selected before synthetic fallback." if natural_later else "Controlled synthetic closure used to meet preregistered subtype quota.",
        "modification": "Pseudonymized action excerpt; no raw thread redistributed.",
    }
    return [d6, d7, d8], gold, triplet, curation


def build(source: str | Path, output: str | Path, exclude: str | Path, archive: str | Path | None, source_repo: str | Path | None) -> dict[str, Any]:
    data_root = resolve_data_root(source)
    output_root = Path(output)
    excluded = excluded_threads(Path(exclude))
    request_candidates, nonclosing_candidates = collect_requests(data_root, excluded)
    if len(request_candidates) < 100:
        raise RuntimeError(f"Need at least 100 disjoint request candidates, found {len(request_candidates)}")
    selected = request_candidates[:100]
    selected_threads = {candidate["thread_identifier"] for candidate in selected}
    natural_by_thread = {
        candidate["thread_identifier"]: next((later for later in candidate["later_events"] if later["closure_type"]), None)
        for candidate in selected
    }
    closure_plan = ["completed"] * 40 + ["cancelled"] * 30 + ["superseded"] * 30
    cases: list[dict[str, Any]] = []
    gold: list[dict[str, Any]] = []
    triplets: list[dict[str, Any]] = []
    curation_rows: list[dict[str, Any]] = []
    for index, (candidate, closure_type) in enumerate(zip(selected, closure_plan), start=1):
        natural = natural_by_thread.get(candidate["thread_identifier"])
        if natural and natural["closure_type"] != closure_type:
            natural = None
        family_cases, family_gold, triplet, curation = build_family(index, candidate, closure_type, natural)
        cases.extend(family_cases)
        gold.extend(family_gold)
        triplets.append(triplet)
        curation_rows.append(curation)

    nonclosing_pool = [item for item in nonclosing_candidates if item["thread_identifier"] not in selected_threads]
    nonclosing_subtypes = ["acknowledgement", "future_commitment", "progress_update", "partial_completion", "clarification_request", "intention_without_completion"]
    for offset in range(1, 41):
        natural = nonclosing_pool[offset - 1] if offset <= len(nonclosing_pool) else None
        candidate = natural or selected[(offset - 1) % len(selected)]
        seed_id = f"HOLDOUT_NONCLOSING_{offset:04d}"
        case_id = f"D8_NONCLOSING_H_{offset:04d}"
        topic = action_topic(candidate["action_description"])
        relation_key = stable_id("RELH", seed_id, candidate["thread_identifier"], candidate["turn_id"])
        request_time = turn_timestamp(candidate["turn_id"])
        later_time = (date.fromisoformat(request_time[:10]) + timedelta(days=1)).isoformat() + "T09:00:00"
        primary = evidence_unit(
            case_id,
            seed_id,
            "Email",
            f"Holdout non-closing email about {topic}",
            f"Email message. Direction: inbound. Body excerpt: {candidate['action_description']}.",
            request_time,
            relation_key,
            base_provenance(candidate) | {"transformation_type": "mailex_request_action_excerpt"},
        )
        subtype = nonclosing_subtypes[(offset - 1) % len(nonclosing_subtypes)]
        if natural:
            text = natural["later"]["closure_text"]
            later_time = turn_timestamp(natural["later"]["turn_id"])
            provenance = base_provenance(natural) | {
                "source_reference": f"{natural['split']}:{natural['source_filename']}:{natural['later']['turn_id']}",
                "turn_identifier": natural["later"]["turn_id"],
                "transformation_type": "mailex_later_nonclosing_excerpt",
                "natural_or_synthetic": "natural",
                "synthetic": False,
            }
            natural_or_synthetic = "natural"
        else:
            text = synthetic_nonclosing(topic, subtype)
            provenance = {
                "source_dataset": "InfoBank synthetic non-closing control derived from MailEx request seed",
                "source_reference": f"derived_from:{seed_id}",
                "derived_from_seed_id": seed_id,
                "transformation_type": "deterministic_synthetic_nonclosing_v2",
                "synthetic": True,
                "excerpted": False,
                "pseudonymized": True,
                "modified": True,
                "natural_or_synthetic": "synthetic",
            }
            natural_or_synthetic = "synthetic"
        later = evidence_unit(
            case_id,
            seed_id,
            "Email",
            f"Later non-closing holdout reply about {topic}",
            f"Email message. Direction: inbound. Later body excerpt: {text}",
            later_time,
            relation_key,
            provenance,
        )
        cases.append(
            {
                "case_id": case_id,
                "scenario": "D8_NONCLOSING",
                "seed_id": seed_id,
                "benchmark_user": "benchmark_user",
                "query": "What is my current action list?",
                "query_time": (date.fromisoformat(later_time[:10]) + timedelta(days=1)).isoformat() + "T12:00:00",
                "evidence_units": [primary, later],
            }
        )
        gold.append(
            {
                "case_id": case_id,
                "seed_id": seed_id,
                "scenario": "D8_NONCLOSING",
                "action_id": f"HOLDOUT_NONCLOSING_ACTION_{offset:04d}",
                "actor": "benchmark_user",
                "action_description": candidate["action_description"],
                "object": topic,
                "due_date": candidate.get("action_date") or None,
                "expected_status": "OPEN",
                "expected_presence": True,
                "gold_role": "primary_with_nonclosing_context",
                "primary_evidence_ids": [primary["evidence_id"]],
                "contextual_evidence_ids": [later["evidence_id"]],
                "contrastive_evidence_ids": [],
                "closure_type": f"non_closing_{subtype}",
                "natural_or_synthetic": natural_or_synthetic,
            }
        )
        curation_rows.append(
            {
                "seed_id": seed_id,
                "source_thread": candidate["thread_identifier"],
                "source_message": f"{candidate['split']}:{candidate['source_filename']}:{candidate['turn_id']}",
                "action": candidate["action_description"],
                "responsible_actor": "benchmark_user",
                "query_time": cases[-1]["query_time"],
                "relation_key": relation_key,
                "closure_decision": "non_closing",
                "closure_subtype": subtype,
                "natural_or_synthetic": natural_or_synthetic,
                "confidence": "high" if natural else "controlled_synthetic",
                "rationale": "Later evidence does not express completion, cancellation, or supersession.",
                "modification": "Pseudonymized excerpt or controlled synthetic non-closing message.",
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    jsonl_write(output_root / "cases.jsonl", cases)
    jsonl_write(output_root / "gold.jsonl", gold)
    jsonl_write(output_root / "triplets.jsonl", triplets)
    write_json(output_root / "curation_overrides.json", {"decisions": curation_rows})
    statistics = {
        "benchmark_id": "evidence_unit_v2_holdout",
        "case_count": len(cases),
        "scenario_counts": dict(Counter(row["scenario"] for row in cases)),
        "closure_type_counts": dict(Counter(row.get("closure_type") for row in gold if row["scenario"] == "D8")),
        "d8_natural_synthetic_counts": dict(Counter(row.get("natural_or_synthetic") for row in gold if row["scenario"] == "D8")),
        "nonclosing_natural_synthetic_counts": dict(Counter(row.get("natural_or_synthetic") for row in gold if row["scenario"] == "D8_NONCLOSING")),
        "excluded_v1_thread_count": len(excluded),
        "selected_thread_count": len({row["source_thread"] for row in curation_rows}),
    }
    write_json(output_root / "benchmark_statistics.json", statistics)
    manifest = {
        "benchmark_id": "evidence_unit_v2_holdout",
        "created_date": date.today().isoformat(),
        "source_dataset": "MailEx",
        "source_repository_url": "https://github.com/salokr/Email-Event-Extraction",
        "source_repository_commit": (git_commit(Path(source_repo)) or "unknown-local-copy") if source_repo else "unknown-local-copy",
        "dataset_download_url": "https://drive.google.com/file/d/1a336g4-wlEwsVbXLPB9wPQnBDRE933mb/view",
        "downloaded_archive_file": str(archive) if archive else None,
        "downloaded_archive_sha256": sha256_file(Path(archive)) if archive and Path(archive).exists() else None,
        "download_date": date.today().isoformat(),
        "mail_ex_observed_statistics": inspect(data_root),
        "source_exclusion_manifest": {
            "excluded_benchmark": str(Path(exclude)),
            "excluded_thread_count": len(excluded),
            "excluded_threads": sorted(excluded),
        },
        "candidate_counts": {
            "request_candidates_after_thread_and_action_dedup": len(request_candidates),
            "nonclosing_candidates": len(nonclosing_candidates),
            "selected_triplet_seeds": 100,
            "selected_nonclosing_cases": 40,
        },
        "privacy_transformations": [
            "Only action-related excerpts or controlled synthetic messages are redistributed.",
            "D7 browser/search records are deterministic synthetic counterfactuals.",
            "Synthetic D8 closure and non-closing records are marked in gold/statistics and do not alter source MailEx threads.",
        ],
    }
    write_json(output_root / "source_manifest.json", manifest)
    for name, text in static_docs().items():
        (output_root / name).write_text(text, encoding="utf-8")
    return statistics


def static_docs() -> dict[str, str]:
    return {
        "README.md": "# EvidenceUnit v2 Holdout\n\nFrozen 340-case D6-D8 holdout benchmark for InfoBank action reconstruction.\n",
        "LICENSE_DATA.md": "MailEx-derived material is handled as CC BY-SA 4.0-derived benchmark data. Synthetic records are InfoBank benchmark material. This is not legal advice.\n",
        "ATTRIBUTION.md": "Includes selected, modified, pseudonymized excerpts derived from MailEx: Joshua Poore and Ziyu Yao, 2023, MailEx: Email Event and Argument Extraction.\n",
        "SOURCE_PROVENANCE.md": "Raw MailEx data are not redistributed. Runtime cases contain only pseudonymized excerpts or synthetic counterfactual/control messages.\n",
        "curation_report.md": "# Curation Report\n\nThe machine-readable curation decisions are in `curation_overrides.json`. Raw personal e-mail text is intentionally omitted from this report.\n",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 340-case EvidenceUnit v2 holdout benchmark.")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--exclude", default=DEFAULT_EXCLUDE)
    parser.add_argument("--archive", default="data/external/mailex/mailex_dataset_download")
    parser.add_argument("--source-repo", default="data/external/mailex/Email-Event-Extraction")
    args = parser.parse_args()
    stats = build(args.source, args.output, args.exclude, args.archive, args.source_repo)
    print(
        "EVIDENCE_V2 BUILD: PASS "
        f"cases={stats['case_count']} "
        f"scenarios={stats['scenario_counts']} "
        f"closures={stats['closure_type_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
