from __future__ import annotations

import json

from evaluation.a_gate_phase2 import DOCUMENTS, QUERIES
from evaluation.c_gate import (
    SCALE_SIZES,
    build_candidate_cases,
    build_scale_documents,
    candidate_manifest,
    run_c_gate,
    run_scale_stress,
    run_w3,
    scale_manifest,
)


def test_scale_builder_preserves_gold_sources_and_is_deterministic() -> None:
    base = {document.id: document for document in DOCUMENTS}
    for size in SCALE_SIZES:
        first = build_scale_documents(size)
        second = build_scale_documents(size)
        assert first == second
        assert len(first) == size
        by_id = {document.id: document for document in first}
        assert all(by_id[document_id] == document for document_id, document in base.items())
        assert scale_manifest(size) == scale_manifest(size)
        assert len(scale_manifest(size)["corpus_hash"]) == 64


def test_scale_stress_runs_same_gold_queries_and_reports_all_metrics(tmp_path) -> None:
    summaries = run_scale_stress(tmp_path / "scale")
    assert len(summaries) == len(SCALE_SIZES) * 2
    required = {
        "recall_at_k", "precision_at_k", "target_found_rate", "mean_target_rank",
        "mean_candidate_set_size", "hard_negative_inclusion", "false_exclusions",
        "routing_p50_ms", "routing_p95_ms", "retrieval_p50_ms", "retrieval_p95_ms",
        "gold_document_retrieval_completeness", "unsupported_answer_rate",
        "gold_page_retrieval_correctness", "gold_document_retrieval_coverage",
        "total_p50_ms", "total_p95_ms",
    }
    for summary in summaries:
        assert required <= set(summary)
        assert summary["false_exclusions"] == 0
        assert summary["unsupported_answer_rate"] == "NOT_EVALUATED"
        assert "answer_correctness" not in summary
        assert "citation_correctness" not in summary
    for size in SCALE_SIZES:
        raw = (tmp_path / "scale" / str(size) / "raw_results.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(raw) == len(QUERIES) * 2


def test_w3_is_executable_and_all_safety_metrics_are_zero(tmp_path) -> None:
    trace = run_w3(tmp_path / "w3")
    assert trace["status"] == "PASS"
    assert set(trace["safety"].values()) == {0}
    assert all(trace["assertions"].values())
    serialized = json.dumps(trace)
    assert "contributor-" not in serialized
    transfer = next(stage for stage in trace["stages"] if stage["stage"] == "ownership_transfer")
    assert transfer["old_owner_decision"] == "deny"
    assert transfer["new_owner_decision"] == "full"


def test_candidate_v2_split_is_disjoint_nonfrozen_and_no_health() -> None:
    cases = build_candidate_cases()
    manifest = candidate_manifest(cases)
    assert manifest["case_count"] == 54
    assert all(manifest["split_disjoint"].values())
    assert manifest["near_duplicate_exact_matches"] == []
    assert manifest["no_health_hits"] == []
    assert manifest["final"] is False
    assert manifest["frozen"] is False
    assert {case.query_class for case in cases} >= {
        "direct_answer", "multi_document", "no_answer", "conflict", "citation",
        "aggregate_threshold", "purpose_expiry", "stale_index", "hard_negative",
    }


def test_c_gate_orchestration_writes_only_declared_development_outputs(tmp_path) -> None:
    result = run_c_gate(tmp_path / "c-gate")
    assert result["status"] == "PASS"
    assert result["final_e1_run"] is False
    assert (tmp_path / "c-gate" / "summary.json").exists()
