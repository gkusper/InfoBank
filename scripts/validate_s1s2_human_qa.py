"""Validate the S1/S2 human-QA scorer package without reading gold at runtime."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_CASE_IDS = tuple([f"S1-Q{index}" for index in range(1, 7)] + [f"S2-Q{index}" for index in range(1, 7)])
RUNTIME_FORBIDDEN_KEYS = {
    "expected_output_class",
    "expected_output",
    "reason_code",
    "negative_reason",
    "gold_document_ids",
    "gold_page_or_message_ranges",
    "required_sources",
    "reference_answer",
    "reference_citations",
    "manual_validation_state",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSONL object row: {path}")
            rows.append(value)
    return rows


def validate_human_qa(*, benchmark_dir: Path, notes_path: Path) -> dict[str, Any]:
    queries = _load_jsonl(benchmark_dir / "query_inputs.jsonl")
    gold = _load_jsonl(benchmark_dir / "gold_annotations.jsonl")
    corpus = _load_json(benchmark_dir / "corpus_fixture.json")
    manifest = _load_json(benchmark_dir / "binding_manifest.json")
    notes = notes_path.read_text(encoding="utf-8")

    query_ids = tuple(row["case_id"] for row in queries)
    gold_ids = tuple(row["case_id"] for row in gold)
    if query_ids != EXPECTED_CASE_IDS or gold_ids != EXPECTED_CASE_IDS:
        raise ValueError("Runtime query and gold case IDs must match the approved S1/S2 order")

    for row in queries:
        leaked = RUNTIME_FORBIDDEN_KEYS.intersection(row)
        if leaked:
            raise ValueError(f"Runtime query leaks gold-only fields for {row['case_id']}: {sorted(leaked)}")

    if notes.count("Status: HUMAN_VALIDATED") != 12:
        raise ValueError("Human QA notes must mark all 12 cases HUMAN_VALIDATED")
    if "Overall status: HUMAN_QA_STATUS: APPROVED" not in notes:
        raise ValueError("Human QA notes must record HUMAN_QA_STATUS: APPROVED")
    if "Benchmark status: BENCHMARK_STATUS: NOT_YET_FROZEN" not in notes:
        raise ValueError("Human QA notes must record BENCHMARK_STATUS: NOT_YET_FROZEN")
    for case_id in EXPECTED_CASE_IDS:
        if not re.search(rf"^## {re.escape(case_id)}$", notes, flags=re.MULTILINE):
            raise ValueError(f"Human QA notes missing case section: {case_id}")

    documents = {item["document_id"]: item for item in corpus["documents"]}
    for row in gold:
        if row.get("manual_validation_state") != "HUMAN_VALIDATED":
            raise ValueError(f"Gold row is not human validated: {row['case_id']}")
        required = row.get("required_sources", [])
        if len(required) != len(set(required)):
            raise ValueError(f"Duplicate required source in {row['case_id']}")
        for source_id in required:
            if source_id not in documents:
                raise ValueError(f"Required source does not resolve in corpus: {row['case_id']} {source_id}")
        for source_id, pages in row.get("gold_page_or_message_ranges", {}).items():
            if source_id not in documents:
                raise ValueError(f"Gold page source does not resolve in corpus: {row['case_id']} {source_id}")
            document = documents[source_id]
            page_count = int(document.get("page_count") or len(document.get("pages") or ()))
            for page in pages:
                if not isinstance(page, int) or isinstance(page, bool) or page < 1 or page > page_count:
                    raise ValueError(f"Invalid acceptable page for {row['case_id']} {source_id}: {page}")

    by_case = {row["case_id"]: row for row in gold}
    if len(by_case["S1-Q6"]["required_sources"]) != 2:
        raise ValueError("S1-Q6 must retain two required documents")
    if len(by_case["S2-Q2"]["required_sources"]) != 2:
        raise ValueError("S2-Q2 must retain two required documents")
    if len(by_case["S2-Q5"]["required_sources"]) != 2:
        raise ValueError("S2-Q5 must retain two required documents")
    s2_q6_pages = sorted(next(iter(by_case["S2-Q6"]["gold_page_or_message_ranges"].values())))
    if s2_q6_pages != [17, 20]:
        raise ValueError("S2-Q6 must accept exactly pages 17 and 20")

    verification = manifest.get("verification") or {}
    if manifest.get("runtime_gold_separated", verification.get("runtime_gold_separated")) is not True:
        raise ValueError("Binding manifest must record runtime/gold separation")
    if manifest.get("gold_manual_validation_state") != "HUMAN_VALIDATED":
        raise ValueError("Binding manifest must record HUMAN_VALIDATED gold")

    return {
        "status": "PASS",
        "case_count": len(gold),
        "runtime_gold_separated": True,
        "human_qa_status": "APPROVED",
        "benchmark_status": "NOT_YET_FROZEN",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-dir", type=Path, required=True)
    parser.add_argument("--notes", type=Path, default=Path("docs/integration/human_qa_review_notes.md"))
    args = parser.parse_args()
    print(json.dumps(validate_human_qa(benchmark_dir=args.benchmark_dir, notes_path=args.notes), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
