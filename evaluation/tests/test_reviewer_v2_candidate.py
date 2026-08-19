from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from evaluation.reviewer_v2_candidate import (
    DOCUMENT_TYPES,
    PACKAGES,
    QUERY_CLASSES,
    build_browser_counterfactuals,
    build_candidate,
    build_gold_queries,
    build_permission_counterfactuals,
    build_synthetic_mail_candidate,
    validate_candidate,
)
from scripts.build_mailex_candidate import NO_HEALTH_TERMS as MAILEX_NO_HEALTH_TERMS
from scripts.build_mailex_candidate import build as build_mailex_candidate


def test_package_and_query_candidate_meets_declared_minimums() -> None:
    assert len(PACKAGES) == 6
    assert len(DOCUMENT_TYPES) == 5
    assert Counter(package.category for package in PACKAGES) == {
        "television": 2, "router": 2, "printer": 2,
    }
    queries = build_gold_queries()
    assert len(queries) == 90
    assert set(Counter(item["query_class"] for item in queries).values()) == {6}
    assert set(Counter(item["query_class"] for item in queries)) == set(QUERY_CLASSES)


def test_every_gold_query_has_required_fields_and_answer_or_refusal() -> None:
    required = {
        "query_id", "query_class", "expected_output_class", "gold_document_ids",
        "gold_page_or_message_ranges", "reference_answer", "refusal_reason", "reason_code",
        "evidence_role", "split", "template_family", "object_family",
    }
    for query in build_gold_queries():
        assert required <= set(query)
        assert bool(query["reference_answer"] or query["refusal_reason"])
        if query["expected_output_class"].startswith("REFUSE_"):
            assert query["reference_answer"] is None
            assert query["refusal_reason"]


def test_counterfactuals_hold_facts_constant_and_browser_never_creates_action() -> None:
    groups = build_permission_counterfactuals()
    assert len(groups) == 60
    for group in groups:
        facts = {
            json.dumps({key: variant[key] for key in ("document_ids", "retrieved_ids", "query")}, sort_keys=True)
            for variant in group["variants"]
        }
        assert len(facts) == 1
        assert {variant["policy"] for variant in group["variants"]} == {"Full", "Aggregate", "Metadata", "Deny"}
    browser = build_browser_counterfactuals()
    assert len(browser) == 60
    assert all(item["expected_action_count"] == 0 for item in browser)


def test_synthetic_mail_candidate_preserves_threads_and_marks_human_work_pending() -> None:
    threads, assignments = build_synthetic_mail_candidate()
    assert len(threads) == 120
    assert len(assignments) == 120
    assert sum(item["second_annotation_required"] for item in assignments) == 24
    assert all(item["source"] == "generated_synthetic_not_mailex" for item in threads)
    assert all(item["preannotation"]["requires_human_validation"] for item in threads)
    assert all(item["action_candidate"]["request_message_id"] == item["messages"][0]["message_id"] for item in threads)


def test_candidate_build_is_deterministic_complete_and_nonfrozen(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = build_candidate(first)
    second_manifest = build_candidate(second)
    assert first_manifest == second_manifest
    assert validate_candidate(first)["status"] == "PASS"
    assert validate_candidate(second)["status"] == "PASS"
    assert (first / "checksums.csv").read_bytes() == (second / "checksums.csv").read_bytes()
    assert first_manifest["status"] == "READY_FOR_HUMAN_QA"
    assert first_manifest["final"] is False
    assert first_manifest["frozen"] is False
    source_rows = json.loads((first / "source_manifest.json").read_text(encoding="utf-8"))["files"]
    assert len(source_rows) == 30
    assert all((first / item["relative_path"]).is_file() for item in source_rows)
    checksums = list(csv.DictReader((first / "checksums.csv").open(encoding="utf-8", newline="")))
    assert any(item["relative_path"] == "automated_qa_report.json" for item in checksums)


def test_manifest_schema_requires_nonfrozen_human_pending_candidate() -> None:
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "reviewer_v2_candidate.schema.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["final"]["const"] is False
    assert schema["properties"]["frozen"]["const"] is False
    assert schema["properties"]["human_annotation_complete"]["const"] is False
    assert schema["properties"]["gold_query_count"]["minimum"] == 90


def test_mailex_tool_preserves_threads_pseudonymizes_and_excludes_health(tmp_path) -> None:
    threads = []
    exclusion_sentinel = sorted(MAILEX_NO_HEALTH_TERMS)[0]
    for index in range(101):
        body = "Please complete the device review." if index else exclusion_sentinel
        threads.append({
            "thread_id": f"mail-{index:03d}",
            "messages": [{
                "message_id": f"message-{index:03d}", "timestamp": "2026-08-01T09:00:00Z",
                "sender": "person@example.com", "recipients": ["worker@example.com"],
                "subject": "Device review", "body": body,
            }],
        })
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"threads": threads}), encoding="utf-8")
    output = tmp_path / "derived"
    manifest = build_mailex_candidate(source, output, "test-licence-pending", 100)
    assert manifest["selected_thread_count"] == 100
    assert manifest["excluded_thread_count"] == 1
    assert manifest["raw_source_committed"] is False
    derived = json.loads((output / "threads.json").read_text(encoding="utf-8"))["threads"]
    assert all(item["messages"][0]["sender"].endswith("@example.invalid") for item in derived)
    exclusion = json.loads((output / "no_health_exclusion_log.json").read_text(encoding="utf-8"))["excluded"]
    assert exclusion == [{"reason": "NO_HEALTH_EXCLUSION", "terms": [exclusion_sentinel], "thread_id": "mail-000"}]
