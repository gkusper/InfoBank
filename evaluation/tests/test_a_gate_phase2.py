from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import controlled_failure
import relevance
from evaluation.a_gate_phase2 import (
    DOCUMENTS,
    QUERIES,
    generate_corpus,
    run_evaluation,
)


def test_current_status_detection_does_not_match_short_term_inside_other_words() -> None:
    question = "Summarize initial HDMI setup and firmware support."
    profile = relevance.build_query_profile(question, ["television"])
    source = {
        "role": relevance.SOURCE_ROLE_PRIMARY,
        "usable_relevance": {
            "role": relevance.SOURCE_ROLE_PRIMARY,
            "levels": {level: 1.0 for level in relevance.RELEVANCE_LEVELS},
            "evidence_warnings": [],
            "temporal_status": [],
        },
    }
    decision = controlled_failure.select_rag_output_mode(
        question,
        [source],
        profile,
        {
            "usable_doc_ids": ["synthetic-doc"],
            "content_doc_ids": ["synthetic-doc"],
            "metadata_only_doc_ids": [],
            "denied_doc_ids": [],
            "has_primary_evidence": True,
        },
        True,
    )
    assert decision["output_mode"] == controlled_failure.STATUS_FULL_ANSWER


def test_a2_corpus_meets_size_family_and_case_contract() -> None:
    assert len(DOCUMENTS) >= 12
    assert len(QUERIES) >= 24
    assert {item.object_family for item in DOCUMENTS} == {"television", "router", "printer"}
    assert {item.case_type for item in QUERIES} >= {
        "answerable", "multi_document", "no_answer", "conflict", "hard_negative",
    }
    assert all(item.gold_pages or item.refusal_reason for item in QUERIES)
    assert all(item.hard_negative_document_ids for item in QUERIES)


def test_a2_corpus_contains_no_health_terms_or_machine_paths() -> None:
    serialized = json.dumps({
        "documents": [item.__dict__ for item in DOCUMENTS],
        "queries": [item.__dict__ for item in QUERIES],
    }).lower()
    assert not re.search(r"\b(patient|diagnosis|treatment|medication|clinical|hospital|healthcare)\b", serialized)
    assert not re.search(r"[a-z]:\\\\|/home/|/users/", serialized)


def test_corpus_pdf_hashes_and_manifest_are_deterministic(tmp_path: Path) -> None:
    first = generate_corpus(tmp_path / "first")
    second = generate_corpus(tmp_path / "second")
    assert first == second
    assert [item["sha256"] for item in first["files"]] == [item["sha256"] for item in second["files"]]
    assert first["synthetic"] is True
    assert first["privacy_safe"] is True
    assert first["final_reviewer_dataset"] is False


def test_runner_emits_both_modes_metrics_decision_and_workflow_traces(tmp_path: Path) -> None:
    summary = run_evaluation(tmp_path / "run")
    assert summary["result_count"] == len(QUERIES) * 2
    assert set(summary["summaries"]) == {"ROUTING_OFF", "KEYWORD_ROUTING"}
    routed = summary["summaries"]["KEYWORD_ROUTING"]
    off = summary["summaries"]["ROUTING_OFF"]
    assert routed["false_exclusion_count"] == 0
    assert routed["mean_recall_at_k"] >= off["mean_recall_at_k"]
    assert routed["mean_candidate_set_size"] < off["mean_candidate_set_size"]
    assert summary["routing_scope_decision"]["production_claim"] is False
    assert summary["w1_status"] == "PASS"
    assert summary["w2_status"] == "PASS"
    for filename in (
        "raw_results.jsonl", "summary.csv", "summary.json", "summary.md",
        "w1_owned_object_trace.json", "w2_warranty_support_trace.json",
        "semantic_cooccurrence_graph.json", "manifest.json", "queries.json",
    ):
        assert (tmp_path / "run" / filename).is_file()

    raw_records = [
        json.loads(line)
        for line in (tmp_path / "run" / "raw_results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    paired = Counter((item["query_id"], item["routing_mode"]) for item in raw_records)
    assert len(paired) == len(QUERIES) * 2
    assert set(paired.values()) == {1}

    w2 = json.loads((tmp_path / "run" / "w2_warranty_support_trace.json").read_text(encoding="utf-8"))
    assert {item["case"] for item in w2["cases"]} == {
        "answerable_multi_document", "insufficient_evidence", "conflicting_evidence", "wrong_object_hard_negative",
    }
    assert all(item["status"] == "PASS" for item in w2["cases"])
    cases = {item["case"]: item for item in w2["cases"]}
    assert cases["insufficient_evidence"]["policy_gate"] == "evidence_sufficiency_checking"
    assert cases["insufficient_evidence"]["policy_reason"] == "evidential"
    assert cases["conflicting_evidence"]["policy_gate"] == "conflict_defeat_check"
    assert cases["conflicting_evidence"]["policy_reason"] == "conflict_defeat"
    assert cases["wrong_object_hard_negative"]["policy_gate"] == "evidence_sufficiency_checking"
    assert cases["wrong_object_hard_negative"]["wrong_object_evidence_rejected"] is True
    for case_name in ("answerable_multi_document", "conflicting_evidence"):
        query = next(item for item in QUERIES if item.id == cases[case_name]["query_id"])
        for citation in cases[case_name]["citations"]:
            assert citation["page_number"] in query.gold_pages[citation["document_id"]]
            assert citation["chunk_id"]
