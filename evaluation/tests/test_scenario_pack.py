from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evaluation.scenario_pack import (
    PACK_FIELDS,
    QUERY_FIELDS,
    SCENARIO_IDS,
    SOURCE_FIELDS,
    project_scenario_pack,
    roadmap_scenario_packs,
    validate_scenario_catalog,
    validate_scenario_pack,
    write_scenario_pack_bundle,
    write_scenario_pack_projection,
)


def _by_id() -> dict[str, dict]:
    return {pack["scenario_id"]: pack for pack in roadmap_scenario_packs()}


def _complete_s1_pack() -> dict:
    pack = copy.deepcopy(roadmap_scenario_packs()[0])
    for query in pack["queries"]:
        if query["required_sources"]:
            query["reference_answer"] = query["reference_answer"] or f"Reviewed reference for {query['query_id']}."
            query["reference_citations"] = [
                {"source_id": source_id, "page": 1, "message_id": None, "record_id": None}
                for source_id in query["required_sources"]
            ]
    return pack


def test_catalog_contains_the_six_roadmap_stories_with_only_contract_fields() -> None:
    packs = roadmap_scenario_packs()
    assert tuple(pack["scenario_id"] for pack in packs) == SCENARIO_IDS
    for pack in packs:
        assert set(pack) == PACK_FIELDS
        assert all(set(source) == SOURCE_FIELDS for source in pack["sources"])
        assert all(set(query) == QUERY_FIELDS for query in pack["queries"])


def test_catalog_is_structurally_valid_and_reports_unfinished_evidence_honestly() -> None:
    report = validate_scenario_catalog(roadmap_scenario_packs())
    assert report["status"] == "STRUCTURALLY_VALID_WITH_READINESS_GAPS"
    assert report["scenario_count"] == 6
    assert report["query_count"] == 28
    assert report["error_count"] == 0
    codes = {issue["code"] for pack in report["packs"] for issue in pack["issues"]}
    assert "QUERY_TARGET_GAP" in codes
    assert "REFERENCE_CITATIONS_PENDING" in codes


def test_required_sources_match_the_key_multi_source_roadmap_cases() -> None:
    packs = _by_id()
    s2 = {query["query_id"]: query for query in packs["S2_TV_WARRANTY_01"]["queries"]}
    assert s2["S2-Q2"]["required_sources"] == ["s2-tv-purchase-receipt", "s2-tv-warranty-terms"]

    s4 = packs["S4_TESCO_BANK_01"]
    order_ids = [source["source_id"] for source in s4["sources"] if source["source_type"] == "order_confirmation_pdf"]
    bank_ids = [source["source_id"] for source in s4["sources"] if source["source_type"] == "bank_statement_pdf"]
    queries = {query["query_id"]: query for query in s4["queries"]}
    assert set(queries["S4-Q1"]["required_sources"]) == set(order_ids + bank_ids)
    assert queries["S4-Q4"]["required_sources"] == bank_ids


def test_s1_uses_english_queries_natural_source_ids_and_document_relation_keys() -> None:
    s1 = _by_id()["S1_SOFA_01"]
    assert s1["object_id"] == "LUN-S3-2401"
    assert [source["source_id"] for source in s1["sources"]] == [
        "lunara-s3-care-guide",
        "lunara-s3-purchase-receipt",
        "vellum-l2-armchair-care-notes",
        "polarweave-p9-rug-care-guide",
    ]
    assert [source["relation_key"] for source in s1["sources"]] == [
        "LUN-S3-2401",
        "LUN-S3-2401",
        "ARM-L2-880",
        "RUG-P9-009",
    ]
    assert s1["sources"][1]["date"] == "2025-11-14"
    assert [query["query"] for query in s1["queries"]] == [
        "I spilled coffee on my sofa. How should I clean it?",
        "When did I buy this sofa?",
        "Can I use chlorine bleach?",
        "How long is the manufacturer's warranty?",
        "How much did I pay for the sofa?",
        "Do the care guide and purchase receipt refer to the same sofa?",
    ]
    assert all("distractor" not in source["source_id"] for source in s1["sources"])
    assert all(query["reference_answer"] for query in s1["queries"])
    queries = {query["query_id"]: query for query in s1["queries"]}
    assert queries["S1-Q5"]["required_sources"] == ["lunara-s3-purchase-receipt"]
    assert queries["S1-Q6"]["required_sources"] == [
        "lunara-s3-care-guide",
        "lunara-s3-purchase-receipt",
    ]
    assert [citation["source_id"] for citation in queries["S1-Q6"]["reference_citations"]] == [
        "lunara-s3-care-guide",
        "lunara-s3-purchase-receipt",
    ]


def test_s2_matches_the_six_live_english_queries_and_reviewed_gold() -> None:
    s2 = _by_id()["S2_TV_WARRANTY_01"]
    assert [source["source_id"] for source in s2["sources"]] == [
        "s2-tv-manual",
        "s2-tv-purchase-receipt",
        "s2-tv-warranty-terms",
        "s2-tv-product-sheet",
        "s2-tv-regional-service-notice",
        "s2-wrong-device-manual",
    ]
    assert [source["relation_key"] for source in s2["sources"]] == [
        "TV-001",
        "TV-001",
        "TV-001",
        "TV-001",
        "TV-001",
        "DISPLAY-OTHER-001",
    ]
    queries = {query["query_id"]: query for query in s2["queries"]}
    assert list(queries) == [f"S2-Q{number}" for number in range(1, 7)]
    assert all(query["expected_output"] == "FULL_ANSWER" for query in queries.values())
    assert all(query["reference_answer"] for query in queries.values())
    assert all(query["reference_citations"] for query in queries.values())
    assert all(query["negative_reason"] is None for query in queries.values())
    assert queries["S2-Q2"]["required_sources"] == [
        "s2-tv-purchase-receipt",
        "s2-tv-warranty-terms",
    ]
    assert queries["S2-Q5"]["required_sources"] == [
        "s2-tv-warranty-terms",
        "s2-tv-regional-service-notice",
    ]
    assert queries["S2-Q6"]["required_sources"] == ["s2-tv-manual"]
    assert queries["S2-Q6"]["supporting_sources"] == ["s2-wrong-device-manual"]
    assert [citation["source_id"] for citation in queries["S2-Q6"]["reference_citations"]] == [
        "s2-tv-manual",
        "s2-tv-manual",
    ]
    assert [citation["page"] for citation in queries["S2-Q6"]["reference_citations"]] == [17, 20]


def test_human_qa_notes_record_all_s1_s2_cases_as_author_validated() -> None:
    notes = (Path(__file__).parents[2] / "docs" / "integration" / "human_qa_review_notes.md").read_text(encoding="utf-8")
    case_ids = [f"S1-Q{number}" for number in range(1, 7)] + [f"S2-Q{number}" for number in range(1, 7)]
    assert "Overall status: HUMAN_QA_STATUS: APPROVED" in notes
    assert "Benchmark status: BENCHMARK_STATUS: NOT_YET_FROZEN" in notes
    assert notes.count("Status: HUMAN_VALIDATED") == 12
    for case_id in case_ids:
        assert f"## {case_id}" in notes


def test_no_evidence_questions_do_not_claim_required_sources() -> None:
    packs = _by_id()
    assert next(query for query in packs["S1_SOFA_01"]["queries"] if query["query_id"] == "S1-Q4")["required_sources"] == []
    assert next(query for query in packs["S3_TESCO_ORDERS_01"]["queries"] if query["query_id"] == "S3-Q4")["required_sources"] == []


def test_validator_rejects_unknown_required_source_and_reversed_validity() -> None:
    pack = copy.deepcopy(roadmap_scenario_packs()[0])
    pack["queries"][0]["required_sources"] = ["does-not-exist"]
    pack["sources"][0]["valid_from"] = "2026-08-22"
    pack["sources"][0]["valid_to"] = "2026-08-21"
    error_codes = {issue["code"] for issue in validate_scenario_pack(pack) if issue["severity"] == "ERROR"}
    assert {"UNKNOWN_SOURCE_REFERENCE", "INVALID_VALIDITY_RANGE"} <= error_codes


def test_validator_rejects_empty_reason_and_invalid_citation_locator() -> None:
    pack = copy.deepcopy(roadmap_scenario_packs()[0])
    pack["queries"][3]["negative_reason"] = ""
    pack["queries"][0]["reference_citations"] = [
        {"source_id": "lunara-s3-care-guide", "page": 0, "message_id": None, "record_id": None}
    ]
    error_codes = {issue["code"] for issue in validate_scenario_pack(pack) if issue["severity"] == "ERROR"}
    assert {"MISSING_NEGATIVE_REASON", "INVALID_CITATION_PAGE"} <= error_codes


def test_validator_allows_constrained_answer_without_negative_reason() -> None:
    pack = _complete_s1_pack()
    pack["queries"][0]["expected_output"] = "CONSTRAINED_ANSWER"
    pack["queries"][0]["negative_reason"] = None

    error_codes = {issue["code"] for issue in validate_scenario_pack(pack) if issue["severity"] == "ERROR"}

    assert "MISSING_NEGATIVE_REASON" not in error_codes
    assert "UNEXPECTED_NEGATIVE_REASON" not in error_codes


def test_bundle_writer_is_deterministic_and_keeps_gold_outside_query_runtime_contract(tmp_path: Path) -> None:
    first = write_scenario_pack_bundle(tmp_path)
    second = write_scenario_pack_bundle(tmp_path)
    assert first == second
    assert first["scenario_count"] == 6
    assert first["query_count"] == 28
    index = json.loads((tmp_path / "scenario_pack_index.json").read_text(encoding="utf-8"))
    assert index == {key: first[key] for key in ("schema_id", "scenario_count", "source_count", "query_count", "scenarios")}
    assert (tmp_path / "validation_reports" / "scenario_pack_validation.json").is_file()
    assert all((tmp_path / "scenario_packs" / scenario_id / "source_documents").is_dir() for scenario_id in SCENARIO_IDS)

    query_input_source = (Path(__file__).parents[1] / "actual_pipeline_inputs.py").read_text(encoding="utf-8")
    for gold_field in ("required_sources", "reference_answer", "reference_citations", "negative_reason"):
        assert gold_field not in query_input_source


def test_incomplete_pack_cannot_be_projected_as_evaluation_input() -> None:
    pack = copy.deepcopy(roadmap_scenario_packs()[1])
    pack["queries"][0]["reference_answer"] = None
    pack["queries"][0]["reference_citations"] = []
    with pytest.raises(ValueError, match="evidence is incomplete"):
        project_scenario_pack(pack)


def test_projection_separates_runtime_query_and_scorer_gold() -> None:
    runtime, gold = project_scenario_pack(_complete_s1_pack())
    assert len(runtime) == len(gold) == 6
    runtime_values = [item.to_dict() for item in runtime]
    gold_values = [item.to_dict() for item in gold]
    for value in runtime_values:
        assert not {
            "expected_output_class",
            "required_sources",
            "reference_answer",
            "reference_citations",
            "negative_reason",
        }.intersection(value)
    first = next(item for item in gold_values if item["case_id"] == "S1-Q1")
    assert first["required_sources"] == ["lunara-s3-care-guide"]
    assert first["reference_citations"] == [
        {"source_id": "lunara-s3-care-guide", "page": 1, "message_id": None, "record_id": None}
    ]
    refusal = next(item for item in gold_values if item["case_id"] == "S1-Q4")
    assert refusal["required_sources"] == []


def test_projection_writer_is_deterministic_and_physically_separates_gold(tmp_path: Path) -> None:
    pack = _complete_s1_pack()
    first = write_scenario_pack_projection(pack, tmp_path)
    second = write_scenario_pack_projection(pack, tmp_path)
    assert first == second
    runtime_path = tmp_path / first["runtime_query_path"]
    gold_path = tmp_path / first["scorer_gold_path"]
    assert runtime_path.parent.name == "runtime"
    assert gold_path.parent.name == "scorer"
    assert first["gold_blind_runtime"] is True
    assert first["status"] == "READY_FOR_CORPUS_BINDING"
    assert b"required_sources" not in runtime_path.read_bytes()
    assert b"reference_citations" not in runtime_path.read_bytes()
    assert b"required_sources" in gold_path.read_bytes()
