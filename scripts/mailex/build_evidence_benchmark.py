#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
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
    write_json,
)


def git_commit(path: Path) -> str | None:
    git_dir = path / ".git"
    if not git_dir.exists():
        return None
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except Exception:
        pass
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref: "):
            return head
        ref = head.removeprefix("ref: ").strip()
        ref_path = git_dir / ref
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8").strip()
        packed_refs = git_dir / "packed-refs"
        if packed_refs.exists():
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                commit, packed_ref = line.split(" ", 1)
                if packed_ref == ref:
                    return commit
    except Exception:
        return None
    return None


def collect_candidates(data_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    closure_candidates: list[dict[str, Any]] = []
    nonclosing_candidates: list[dict[str, Any]] = []
    for split, path in iter_split_files(data_root):
        data = load_json(path)
        for turn_id, events in sorted(data.get("events", {}).items(), key=lambda item: turn_index(item[0])):
            if EVENT_REQUEST_ACTION not in events:
                continue
            request_args = event_argument_spans(data, turn_id, EVENT_REQUEST_ACTION)
            description = sanitize_excerpt("; ".join(request_args.get("Action Description", [])))
            if not is_good_request(description):
                continue
            base = {
                "split": split,
                "source_filename": path.name,
                "source_path": str(path),
                "turn_id": turn_id,
                "action_description": description,
                "action_members": [sanitize_excerpt(value) for value in request_args.get("Action Members", [])],
                "action_date": sanitize_excerpt("; ".join(request_args.get("Action Date", []))),
                "request_excerpt": sanitize_excerpt(extract_turn_text(data, turn_id)),
                "source_hash": sha256_text(path.read_text(encoding="utf-8")),
            }
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
                        "closure_members": [sanitize_excerpt(value) for value in deliver_args.get("Action Members", [])],
                        "closure_excerpt": sanitize_excerpt(extract_turn_text(data, later_turn)),
                        "closure_type": classify_closure(closure_text),
                    }
                )
            for later_event in later_events:
                if later_event["closure_type"]:
                    closure_candidates.append({**base, "later": later_event})
                    break
            for later_event in later_events:
                if is_nonclosing(later_event["closure_text"]):
                    nonclosing_candidates.append({**base, "later": later_event})
                    break
    return closure_candidates, nonclosing_candidates


def evidence_unit(seed_id: str, case_id: str, source_type: str, title: str, content: str, timestamp: str, relation_key: str, provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": stable_id("EU", case_id, source_type, title, timestamp, content),
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


def build_case_family(seed_number: int, candidate: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    seed_id = f"MAILEX_SEED_{seed_number:03d}"
    action_id = f"ACTION_{seed_number:03d}"
    relation_key = stable_id("REL", seed_id, candidate["source_filename"], candidate["turn_id"])
    topic = action_topic(candidate["action_description"])
    request_time = turn_timestamp(candidate["turn_id"])
    query_time = (date.fromisoformat(request_time[:10]) + timedelta(days=1)).isoformat() + "T12:00:00"
    closure_time = turn_timestamp(candidate["later"]["turn_id"])

    base_provenance = {
        "source_dataset": "MailEx",
        "source_reference": f"{candidate['split']}:{candidate['source_filename']}:{candidate['turn_id']}",
        "mailex_split": candidate["split"],
        "mailex_source_filename": candidate["source_filename"],
        "thread_identifier": candidate["source_filename"].removesuffix(".json"),
        "turn_identifier": candidate["turn_id"],
        "source_hash": candidate["source_hash"],
        "excerpted": True,
        "pseudonymized": True,
        "modified": True,
    }
    request_content = (
        "Email message. Direction: inbound. "
        f"Body excerpt: {candidate['action_description']}."
    )
    request_unit = evidence_unit(
        seed_id,
        f"D6_{seed_number:03d}",
        "Email",
        f"MailEx email about {topic}",
        request_content,
        request_time,
        relation_key,
        {**base_provenance, "transformation_type": "mailex_request_action_excerpt"},
    )

    d6_case_id = f"D6_{seed_number:03d}"
    d7_case_id = f"D7_{seed_number:03d}"
    d8_case_id = f"D8_{seed_number:03d}"

    d6_case = {
        "case_id": d6_case_id,
        "scenario": "D6",
        "seed_id": seed_id,
        "benchmark_user": "benchmark_user",
        "query": "What is my current action list?",
        "query_time": query_time,
        "evidence_units": [request_unit],
        "matched_family": {"seed_id": seed_id, "d6_case": d6_case_id, "d7_case": d7_case_id, "d8_case": d8_case_id},
    }
    browser_units = []
    for index, text in enumerate(
        [
            f"Search query: {topic}",
            f"Visited page: {topic.title()} reference page",
            f"Search query: {topic} examples",
        ],
        start=1,
    ):
        browser_units.append(
            evidence_unit(
                seed_id,
                d7_case_id,
                "BrowserHistory",
                text,
                text,
                (date.fromisoformat(request_time[:10]) + timedelta(hours=index)).isoformat() + "T10:00:00",
                relation_key,
                {
                    "source_dataset": "InfoBank synthetic counterfactual derived from MailEx",
                    "source_reference": f"derived_from:{seed_id}",
                    "derived_from_seed_id": seed_id,
                    "transformation_type": "deterministic_browser_trace",
                    "transformation_rule": "deterministic_topic_trace_v1",
                    "synthetic": True,
                    "excerpted": False,
                    "pseudonymized": True,
                    "modified": True,
                },
            )
        )
    d7_case = {
        "case_id": d7_case_id,
        "scenario": "D7",
        "seed_id": seed_id,
        "benchmark_user": "benchmark_user",
        "query": "What is my current action list?",
        "query_time": query_time,
        "evidence_units": browser_units,
        "matched_family": {"seed_id": seed_id, "d6_case": d6_case_id, "d7_case": d7_case_id, "d8_case": d8_case_id},
    }
    closure_unit = evidence_unit(
        seed_id,
        d8_case_id,
        "Email",
        f"Later MailEx reply about {topic}",
        f"Email message. Direction: inbound. Later body excerpt: {candidate['later']['closure_text']}.",
        closure_time,
        relation_key,
        {
            **base_provenance,
            "source_reference": f"{candidate['split']}:{candidate['source_filename']}:{candidate['later']['turn_id']}",
            "turn_identifier": candidate["later"]["turn_id"],
            "transformation_type": "mailex_later_action_related_excerpt",
            "closure_source_turn": candidate["later"]["turn_id"],
            "closure_type": candidate["later"]["closure_type"],
            "natural_or_synthetic": "natural",
            "curation_required": False,
        },
    )
    d8_case = {
        "case_id": d8_case_id,
        "scenario": "D8",
        "seed_id": seed_id,
        "benchmark_user": "benchmark_user",
        "query": "What is my current action list?",
        "query_time": (date.fromisoformat(closure_time[:10]) + timedelta(days=1)).isoformat() + "T12:00:00",
        "evidence_units": [{**request_unit, "evidence_id": stable_id("EU", d8_case_id, "request", request_unit["content"])}, closure_unit],
        "matched_family": {"seed_id": seed_id, "d6_case": d6_case_id, "d7_case": d7_case_id, "d8_case": d8_case_id},
    }

    d6_primary = d6_case["evidence_units"][0]["evidence_id"]
    d8_primary = d8_case["evidence_units"][0]["evidence_id"]
    d8_contrastive = d8_case["evidence_units"][1]["evidence_id"]
    gold = [
        {
            "case_id": d6_case_id,
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
            "primary_evidence_ids": [d6_primary],
            "contextual_evidence_ids": [],
            "contrastive_evidence_ids": [],
            "closure_type": None,
        },
        {
            "case_id": d7_case_id,
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
        },
        {
            "case_id": d8_case_id,
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
            "primary_evidence_ids": [d8_primary],
            "contextual_evidence_ids": [],
            "contrastive_evidence_ids": [d8_contrastive],
            "closure_type": candidate["later"]["closure_type"],
        },
    ]
    curation = [
        {
            "source_mailex_identifier": f"{candidate['split']}:{candidate['source_filename']}:{candidate['later']['turn_id']}",
            "decision": candidate["later"]["closure_type"],
            "reason": "Selected as later MailEx Deliver_Action_Data with an explicit completion/cancellation/supersession lexical signal; this is an InfoBank benchmark-level status interpretation.",
            "affected_benchmark_case": d8_case_id,
        }
    ]
    relation = {"seed_id": seed_id, "d6_case": d6_case_id, "d7_case": d7_case_id, "d8_case": d8_case_id}
    return [d6_case, d7_case, d8_case], gold, relation, curation


def build(source: str | Path, output: str | Path, pilot_size: int, nonclosing_size: int, archive: str | Path | None, source_repo: str | Path | None) -> dict[str, Any]:
    data_root = resolve_data_root(source)
    output_root = Path(output)
    closure_candidates, nonclosing_candidates = collect_candidates(data_root)
    selected = closure_candidates[:pilot_size]
    cases: list[dict[str, Any]] = []
    gold: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    curation: list[dict[str, Any]] = []
    for index, candidate in enumerate(selected, start=1):
        family_cases, family_gold, relation, decisions = build_case_family(index, candidate)
        cases.extend(family_cases)
        gold.extend(family_gold)
        relations.append(relation)
        curation.extend(decisions)

    used_sources = {candidate["source_filename"] for candidate in selected}
    for offset, candidate in enumerate([c for c in nonclosing_candidates if c["source_filename"] not in used_sources][:nonclosing_size], start=1):
        seed_number = pilot_size + offset
        seed_id = f"MAILEX_SEED_NONCLOSING_{offset:03d}"
        relation_key = stable_id("REL", seed_id, candidate["source_filename"], candidate["turn_id"])
        topic = action_topic(candidate["action_description"])
        case_id = f"D8_NONCLOSING_{offset:03d}"
        request_time = turn_timestamp(candidate["turn_id"])
        later_time = turn_timestamp(candidate["later"]["turn_id"])
        primary = evidence_unit(
            seed_id,
            case_id,
            "Email",
            f"MailEx email about {topic}",
            f"Email message. Direction: inbound. Body excerpt: {candidate['action_description']}.",
            request_time,
            relation_key,
            {
                "source_dataset": "MailEx",
                "source_reference": f"{candidate['split']}:{candidate['source_filename']}:{candidate['turn_id']}",
                "mailex_split": candidate["split"],
                "mailex_source_filename": candidate["source_filename"],
                "thread_identifier": candidate["source_filename"].removesuffix(".json"),
                "turn_identifier": candidate["turn_id"],
                "source_hash": candidate["source_hash"],
                "transformation_type": "mailex_request_action_excerpt",
                "excerpted": True,
                "pseudonymized": True,
                "modified": True,
            },
        )
        progress = evidence_unit(
            seed_id,
            case_id,
            "Email",
            f"Later non-closing MailEx reply about {topic}",
            f"Email message. Direction: inbound. Later body excerpt: {candidate['later']['closure_text']}.",
            later_time,
            relation_key,
            {
                "source_dataset": "MailEx",
                "source_reference": f"{candidate['split']}:{candidate['source_filename']}:{candidate['later']['turn_id']}",
                "mailex_split": candidate["split"],
                "mailex_source_filename": candidate["source_filename"],
                "thread_identifier": candidate["source_filename"].removesuffix(".json"),
                "turn_identifier": candidate["later"]["turn_id"],
                "source_hash": candidate["source_hash"],
                "transformation_type": "mailex_later_nonclosing_excerpt",
                "closure_source_turn": candidate["later"]["turn_id"],
                "closure_type": "non_closing_progress",
                "natural_or_synthetic": "natural",
                "curation_required": False,
                "excerpted": True,
                "pseudonymized": True,
                "modified": True,
            },
        )
        cases.append(
            {
                "case_id": case_id,
                "scenario": "D8_NONCLOSING",
                "seed_id": seed_id,
                "benchmark_user": "benchmark_user",
                "query": "What is my current action list?",
                "query_time": (date.fromisoformat(later_time[:10]) + timedelta(days=1)).isoformat() + "T12:00:00",
                "evidence_units": [primary, progress],
            }
        )
        gold.append(
            {
                "case_id": case_id,
                "seed_id": seed_id,
                "scenario": "D8_NONCLOSING",
                "action_id": f"ACTION_NONCLOSING_{offset:03d}",
                "actor": "benchmark_user",
                "action_description": candidate["action_description"],
                "object": topic,
                "due_date": candidate.get("action_date") or None,
                "expected_status": "OPEN",
                "expected_presence": True,
                "gold_role": "primary_with_nonclosing_context",
                "primary_evidence_ids": [primary["evidence_id"]],
                "contextual_evidence_ids": [progress["evidence_id"]],
                "contrastive_evidence_ids": [],
                "closure_type": "non_closing_progress",
            }
        )
        curation.append(
            {
                "source_mailex_identifier": f"{candidate['split']}:{candidate['source_filename']}:{candidate['later']['turn_id']}",
                "decision": "non_closing_progress",
                "reason": "Selected as later MailEx action-related material with future/progress wording and no closure lexical signal.",
                "affected_benchmark_case": case_id,
            }
        )

    jsonl_write(output_root / "cases.jsonl", cases)
    jsonl_write(output_root / "gold.jsonl", gold)
    source_manifest = {
        "benchmark_id": "evidence_unit_v1",
        "created_date": date.today().isoformat(),
        "source_dataset": "MailEx",
        "source_repository_url": "https://github.com/salokr/Email-Event-Extraction",
        "source_repository_commit": git_commit(Path(source_repo)) if source_repo else None,
        "dataset_download_url": "https://drive.google.com/file/d/1a336g4-wlEwsVbXLPB9wPQnBDRE933mb/view",
        "downloaded_archive_file": str(archive) if archive else None,
        "downloaded_archive_sha256": sha256_file(Path(archive)) if archive and Path(archive).exists() else None,
        "download_date": date.today().isoformat(),
        "mail_ex_observed_statistics": inspect(data_root),
        "candidate_counts": {
            "closure_candidates": len(closure_candidates),
            "nonclosing_candidates": len(nonclosing_candidates),
            "selected_d6_seeds": len(selected),
            "selected_d7_cases": len(selected),
            "selected_d8_closure_cases": len(selected),
            "selected_d8_nonclosing_cases": nonclosing_size,
        },
        "matched_relations": relations,
        "privacy_transformations": [
            "Only action-related excerpts are redistributed, not full raw threads.",
            "E-mail addresses, phone-like strings, participant fields, and selected person-name tokens are pseudonymized.",
            "D7 browser/search records are deterministic synthetic counterfactuals.",
        ],
    }
    write_json(output_root / "source_manifest.json", source_manifest)
    write_json(output_root / "curation_overrides.json", {"decisions": curation})
    return source_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the InfoBank EvidenceUnit D6-D8 pilot benchmark from MailEx.")
    parser.add_argument("--source", default="data/external/mailex/extracted/data")
    parser.add_argument("--output", default="data/benchmarks/evidence_unit_v1")
    parser.add_argument("--pilot-size", type=int, default=10)
    parser.add_argument("--nonclosing-size", type=int, default=2)
    parser.add_argument("--archive", default="data/external/mailex/mailex_dataset_download")
    parser.add_argument("--source-repo", default="data/external/mailex/Email-Event-Extraction")
    args = parser.parse_args()
    manifest = build(args.source, args.output, args.pilot_size, args.nonclosing_size, args.archive, args.source_repo)
    print(
        "BUILD: PASS "
        f"d6={manifest['candidate_counts']['selected_d6_seeds']} "
        f"d7={manifest['candidate_counts']['selected_d7_cases']} "
        f"d8_closed={manifest['candidate_counts']['selected_d8_closure_cases']} "
        f"d8_nonclosing={manifest['candidate_counts']['selected_d8_nonclosing_cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
