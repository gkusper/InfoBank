#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCORER_ONLY_FIELDS = {
    "gold_role",
    "gold_status",
    "expected_status",
    "expected_presence",
    "primary_evidence_ids",
    "contextual_evidence_ids",
    "contrastive_evidence_ids",
    "closure_type",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
    return rows


def parse_ts(value: str, label: str, errors: list[str]) -> None:
    try:
        dt.datetime.fromisoformat(value)
    except Exception:
        errors.append(f"{label}: invalid timestamp {value!r}")


def validate(root: str | Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    cases_path = root / "cases.jsonl"
    gold_path = root / "gold.jsonl"
    manifest_path = root / "source_manifest.json"
    for path in [cases_path, gold_path, manifest_path, root / "README.md", root / "LICENSE_DATA.md", root / "ATTRIBUTION.md"]:
        if not path.exists():
            errors.append(f"missing required file: {path}")
    if errors:
        return errors

    cases = read_jsonl(cases_path)
    gold = read_jsonl(gold_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    case_ids = [case.get("case_id") for case in cases]
    if len(case_ids) != len(set(case_ids)):
        errors.append("case IDs must be unique")
    gold_ids = [row.get("case_id") for row in gold]
    if set(case_ids) != set(gold_ids):
        errors.append("cases.jsonl and gold.jsonl case_id sets differ")

    evidence_by_case: dict[str, dict[str, dict[str, Any]]] = {}
    all_evidence_ids = []
    for case in cases:
        case_id = case.get("case_id")
        if SCORER_ONLY_FIELDS & set(case):
            errors.append(f"{case_id}: scorer-only fields appear at case top level")
        if not case.get("seed_id"):
            errors.append(f"{case_id}: missing seed_id")
        if not case.get("query_time"):
            errors.append(f"{case_id}: missing query_time")
        else:
            parse_ts(case["query_time"], f"{case_id}.query_time", errors)
        units = case.get("evidence_units") or []
        evidence_by_case[case_id] = {}
        if not units:
            errors.append(f"{case_id}: no evidence units")
        for unit in units:
            unit_id = unit.get("evidence_id")
            all_evidence_ids.append((case_id, unit_id))
            if SCORER_ONLY_FIELDS & set(unit):
                errors.append(f"{case_id}/{unit_id}: scorer-only fields appear in runtime evidence")
            if not unit_id:
                errors.append(f"{case_id}: evidence unit missing evidence_id")
                continue
            if unit_id in evidence_by_case[case_id]:
                errors.append(f"{case_id}: duplicate evidence_id {unit_id}")
            evidence_by_case[case_id][unit_id] = unit
            if not unit.get("thread_id") and not unit.get("relation_key"):
                errors.append(f"{case_id}/{unit_id}: missing thread_id/relation_key")
            if not unit.get("timestamp"):
                errors.append(f"{case_id}/{unit_id}: missing timestamp")
            else:
                parse_ts(unit["timestamp"], f"{case_id}/{unit_id}.timestamp", errors)
            if not unit.get("provenance", {}).get("source_dataset"):
                errors.append(f"{case_id}/{unit_id}: missing provenance.source_dataset")

    by_case = {row["case_id"]: row for row in gold}
    scenario_counts = Counter(row.get("scenario") for row in gold)
    expected_counts = {"D6": 10, "D7": 10, "D8": 10, "D8_NONCLOSING": 2}
    for scenario, expected in expected_counts.items():
        if scenario_counts.get(scenario, 0) != expected:
            errors.append(f"{scenario}: expected {expected} cases, found {scenario_counts.get(scenario, 0)}")

    for row in gold:
        case_id = row["case_id"]
        scenario = row.get("scenario")
        evidence = evidence_by_case.get(case_id, {})
        unit_types = Counter(unit.get("source_type") for unit in evidence.values())
        for ref_list in ["primary_evidence_ids", "contextual_evidence_ids", "contrastive_evidence_ids"]:
            for evidence_id in row.get(ref_list) or []:
                if evidence_id not in evidence:
                    errors.append(f"{case_id}: {ref_list} references missing evidence_id {evidence_id}")
        if scenario == "D6":
            if not unit_types.get("Email"):
                errors.append(f"{case_id}: D6 must contain e-mail evidence")
            if row.get("expected_status") != "OPEN" or row.get("expected_presence") is not True:
                errors.append(f"{case_id}: D6 expected gold must be OPEN/present")
            primary_times = [evidence[eid]["timestamp"] for eid in row.get("primary_evidence_ids", []) if eid in evidence]
            if primary_times and case_id in evidence_by_case and cases:
                query_time = next(case["query_time"] for case in cases if case["case_id"] == case_id)
                if max(primary_times) >= query_time:
                    errors.append(f"{case_id}: query_time must follow obligation creation")
        elif scenario == "D7":
            if set(unit_types) != {"BrowserHistory"}:
                errors.append(f"{case_id}: D7 must contain browser/search-history evidence only")
            if row.get("expected_status") != "ABSENT" or row.get("expected_presence") is not False:
                errors.append(f"{case_id}: D7 expected gold must be ABSENT/not present")
            for unit in evidence.values():
                if unit.get("provenance", {}).get("transformation_rule") != "deterministic_topic_trace_v1":
                    errors.append(f"{case_id}/{unit.get('evidence_id')}: missing deterministic D7 transformation rule")
        elif scenario == "D8":
            if not row.get("primary_evidence_ids") or not row.get("contrastive_evidence_ids"):
                errors.append(f"{case_id}: D8 must reference original and contrastive evidence")
            if row.get("expected_status") != "CLOSED":
                errors.append(f"{case_id}: D8 closure case must expect CLOSED")
            if row.get("closure_type") not in {"completed", "cancelled", "superseded"}:
                errors.append(f"{case_id}: invalid D8 closure_type {row.get('closure_type')}")
            primary_ts = [evidence[eid]["timestamp"] for eid in row.get("primary_evidence_ids", []) if eid in evidence]
            contrastive_ts = [evidence[eid]["timestamp"] for eid in row.get("contrastive_evidence_ids", []) if eid in evidence]
            if primary_ts and contrastive_ts and min(contrastive_ts) <= max(primary_ts):
                errors.append(f"{case_id}: closure evidence timestamp must be later than obligation")
        elif scenario == "D8_NONCLOSING":
            if row.get("expected_status") != "OPEN" or row.get("expected_presence") is not True:
                errors.append(f"{case_id}: non-closing D8 must remain OPEN")
            if row.get("closure_type") != "non_closing_progress":
                errors.append(f"{case_id}: non-closing D8 closure_type must be non_closing_progress")

    by_seed = defaultdict(dict)
    for row in gold:
        if row.get("scenario") in {"D6", "D7", "D8"}:
            by_seed[row["seed_id"]][row["scenario"]] = row
    for seed_id, group in by_seed.items():
        if set(group) != {"D6", "D7", "D8"}:
            errors.append(f"{seed_id}: incomplete D6/D7/D8 triplet")
            continue
        if group["D6"]["expected_status"] != "OPEN" or group["D7"]["expected_status"] != "ABSENT" or group["D8"]["expected_status"] != "CLOSED":
            errors.append(f"{seed_id}: triplet status must be D6 OPEN, D7 ABSENT, D8 CLOSED")

    if not manifest.get("downloaded_archive_sha256"):
        errors.append("source_manifest.json must record downloaded_archive_sha256")
    if not manifest.get("source_repository_commit"):
        errors.append("source_manifest.json must record source_repository_commit")

    repo_gitignore = Path(".gitignore")
    if repo_gitignore.exists() and "data/external/" not in repo_gitignore.read_text(encoding="utf-8"):
        errors.append(".gitignore must exclude data/external/")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the InfoBank EvidenceUnit D6-D8 benchmark.")
    parser.add_argument("--benchmark", default="data/benchmarks/evidence_unit_v1")
    args = parser.parse_args()
    errors = validate(args.benchmark)
    if errors:
        print("VALIDATION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
