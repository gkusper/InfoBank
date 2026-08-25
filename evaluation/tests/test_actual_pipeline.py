from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.actual_pipeline_dataset import OUTPUT_CLASSES, build_development_dataset, document_id
from evaluation.actual_pipeline_gold import HUMAN_VALIDATED, GoldAnnotation, load_gold_annotations
from evaluation.actual_pipeline_inputs import CORPUS_SCHEMA_VERSION, CorpusDocument, QueryInput, write_jsonl
from evaluation.actual_pipeline_runner import (
    ActualPipelineConfig,
    PipelineRuntime,
    _document_routing_keywords,
    _informative_routing_keyword,
    _select_answer_citations,
    _support_score,
    run_actual_pipeline,
)
from evaluation.actual_pipeline_scorer import _human_validation_state, _score_mode, scan_record_safety, score_sealed_run
from evaluation.reason_codes import canonical_reason_code


def _minimal_fixture(root: Path) -> tuple[Path, Path, Path]:
    dataset = root / "dataset"
    dataset.mkdir()
    doc_id = document_id("pkg-test", "manual")
    query = QueryInput(
        case_id="case-1",
        evaluation_identity="eval-full",
        query_text="What setup instruction is stated for TV-TEST-1?",
        declared_purpose="grounded_question_answering",
        corpus_package_ref="pkg-test",
        policy_fixture_ref="full",
        runtime_parameters={"top_k": 2},
    )
    write_jsonl(dataset / "query_inputs.jsonl", [query.to_dict()])
    corpus = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "metadata": {
            "dataset_version": "actual-pipeline-development-v1",
            "builder_version": "test",
            "synthetic": True,
        },
        "documents": [
            {
                "document_id": doc_id,
                "package_ref": "pkg-test",
                "object_id": "TV-TEST-1",
                "document_type": "manual",
                "original_filename": "tv-test-manual.pdf",
                "pages": ["Synthetic TV-TEST-1 setup instruction: connect test port 2."],
                "keywords": ["setup", "manual"],
                "archived": False,
            }
        ],
        "policy_fixtures": [
            {
                "fixture_id": "full",
                "access_by_document": {doc_id: "Full"},
                "purpose": "grounded_question_answering",
                "conflict_policy": "query_sensitive",
                "aggregate_k": 3,
                "prohibited_markers": [],
            }
        ],
    }
    (dataset / "corpus_fixture.json").write_text(json.dumps(corpus), encoding="utf-8")
    gold = {
        "case_id": "case-1",
        "expected_output_class": "FULL_ANSWER",
        "reason_code": "supported",
        "gold_document_ids": [doc_id],
        "gold_page_or_message_ranges": {doc_id: [1]},
        "required_sources": [doc_id],
        "reference_citations": [
            {"source_id": doc_id, "page": 1, "message_id": None, "record_id": None}
        ],
        "reference_answer": "connect test port 2",
        "factual_atoms": ["connect test port 2"],
        "required_evidence_roles": ["primary"],
        "action_status": "NOT_APPLICABLE",
        "manual_validation_state": "PENDING_HUMAN_REVIEW",
        "dataset_version": "actual-pipeline-development-v1",
        "schema_version": "infobank-gold-annotation-v1",
        "metadata": {},
    }
    write_jsonl(dataset / "gold_annotations.jsonl", [gold])
    return dataset / "query_inputs.jsonl", dataset / "corpus_fixture.json", dataset / "gold_annotations.jsonl"


def _write_test_pdf(path: Path, text: str) -> str:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(72, 72, 523, 770), text, fontsize=11, fontname="helv")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(pdf.tobytes(garbage=4, deflate=True, no_new_id=True))
    except TypeError:
        path.write_bytes(pdf.tobytes(garbage=4, deflate=True))
    finally:
        pdf.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_minimal(root: Path, query_path: Path, corpus_path: Path, label: str) -> dict:
    return run_actual_pipeline(
        query_input_path=query_path,
        corpus_fixture_path=corpus_path,
        output_dir=root / label / "raw",
        database_url=f"sqlite+pysqlite:///{(root / label / 'eval.db').as_posix()}",
        chroma_dir=root / label / "chroma",
        source_storage_dir=root / label / "sources",
        run_id=label,
        modes=["B3_FULL_ROLE_AWARE"],
        config=ActualPipelineConfig(),
    )


def test_support_score_handles_short_exact_factual_lookups() -> None:
    date_source = "Purchase record for DEVICE-A. Purchase date 3 May 2026."
    amount_source = "Invoice for DEVICE-B. Amount paid 42,500 HUF."
    identifier_source = "Inspection sheet. Reference identifier ZX-99-A7 is printed on the label."
    assert _support_score("When did I buy device A?", date_source) >= 0.45
    assert _support_score("How much did I pay?", amount_source) >= 0.45
    assert _support_score("What reference identifier is listed?", identifier_source) >= 0.45
    assert _support_score("How long is the manufacturer's warranty?", "Routine care notes only.") < 0.45


def test_low_information_keywords_are_not_used_for_routing() -> None:
    assert not _informative_routing_keyword("of")
    assert not _informative_routing_keyword("an")
    assert not _informative_routing_keyword("55")
    assert _informative_routing_keyword("purchase")
    assert _informative_routing_keyword("warranty")


def test_document_type_terms_are_available_for_routing() -> None:
    document = CorpusDocument(
        document_id="receipt-doc",
        package_ref="pkg-routing",
        object_id="DEVICE-A",
        document_type="purchase_receipt_pdf",
        original_filename="opaque-name.pdf",
        pages=("Receipt body.",),
        keywords=(),
    )

    assert {"purchase", "receipt", "purchase_receipt_pdf"} <= set(_document_routing_keywords(document))


def test_canonical_reason_codes_cover_refusal_taxonomy() -> None:
    assert canonical_reason_code("REFUSE_INSUFFICIENT_EVIDENCE", "evidential") == "insufficient_evidence"
    assert canonical_reason_code("REFUSE_PERMISSION", "governance") == "permission_refusal"
    assert canonical_reason_code("REFUSE_NO_MATCH", "epistemic") == "no_match"
    assert canonical_reason_code("REFUSE_CONFLICT", "conflict_defeat") == "conflict"
    assert canonical_reason_code("REFUSE_AGGREGATION_THRESHOLD", "aggregation_threshold_not_met") == "aggregation_threshold_not_met"
    assert canonical_reason_code("CLARIFICATION", "underspecified_question") == "clarification"


def test_citation_selection_prefers_supporting_page_in_multi_page_document() -> None:
    selected = _select_answer_citations(
        [
            {
                "available": True,
                "document_id": "doc-a",
                "page_number": 1,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.9,
                "_text": "Device overview and generic administration notes.",
            },
            {
                "available": True,
                "document_id": "doc-a",
                "page_number": 2,
                "chunk_index": 1,
                "evidence_role": "primary",
                "_selection_score": 0.4,
                "_text": "Reference identifier ZX-99-A7 is the approved service code.",
            },
        ],
        question="What reference identifier is listed?",
        answer="The reference identifier is ZX-99-A7.",
    )
    assert [item["page_number"] for item in selected] == [2]
    assert all(not any(key.startswith("_") for key in item) for item in selected)


def test_citation_selection_prunes_semantically_related_non_material_sources() -> None:
    selected = _select_answer_citations(
        [
            {
                "available": True,
                "document_id": "receipt",
                "page_number": 1,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.4,
                "_document_type": "purchase_receipt_pdf",
                "_text": "Purchase receipt. Purchase date 3 May 2026. Amount paid 42,500 HUF.",
            },
            {
                "available": True,
                "document_id": "care",
                "page_number": 1,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.9,
                "_document_type": "care_manual_pdf",
                "_text": "Device care manual. Wipe the exterior with a dry cloth.",
            },
            {
                "available": True,
                "document_id": "overview",
                "page_number": 1,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.8,
                "_document_type": "user_manual_pdf",
                "_text": "Device overview. Keep all records with the product packaging.",
            },
        ],
        question="How much did I pay for the device?",
        answer="The amount paid was 42,500 HUF.",
    )

    assert [(item["document_id"], item["page_number"]) for item in selected] == [("receipt", 1)]


def test_citation_selection_uses_document_type_for_purchase_fact() -> None:
    selected = _select_answer_citations(
        [
            {
                "available": True,
                "document_id": "manual",
                "page_number": 2,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.9,
                "_document_type": "user_manual_pdf",
                "_text": "Manual for DEVICE-A. Keep the purchase paperwork with this guide.",
            },
            {
                "available": True,
                "document_id": "receipt",
                "page_number": 1,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.4,
                "_document_type": "purchase_receipt_pdf",
                "_text": "Receipt for DEVICE-A. Purchase date 3 May 2026.",
            },
        ],
        question="When did I buy DEVICE-A?",
        answer="DEVICE-A was purchased on 3 May 2026.",
    )

    assert [(item["document_id"], item["page_number"]) for item in selected] == [("receipt", 1)]


def test_citation_selection_prefers_specification_for_technical_property() -> None:
    selected = _select_answer_citations(
        [
            {
                "available": True,
                "document_id": "manual",
                "page_number": 10,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.9,
                "_document_type": "user_manual_pdf",
                "_text": "Manual connection section. Use certified cables for HDMI and USB accessories.",
            },
            {
                "available": True,
                "document_id": "spec",
                "page_number": 3,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.5,
                "_document_type": "product_specification_pdf",
                "_text": "Product specification. HDMI 4 inputs. USB-A 2 ports. Ethernet and optical audio are listed wired connections.",
            },
        ],
        question="How many HDMI and USB-A ports are listed?",
        answer="The specification lists 4 HDMI inputs and 2 USB-A ports.",
    )

    assert [(item["document_id"], item["page_number"]) for item in selected] == [("spec", 3)]


def test_citation_selection_keeps_multiple_supporting_documents() -> None:
    selected = _select_answer_citations(
        [
            {
                "available": True,
                "document_id": "receipt",
                "page_number": 1,
                "chunk_index": 0,
                "evidence_role": "primary",
                "_selection_score": 0.5,
                "_document_type": "purchase_receipt_pdf",
                "_text": "Purchase date 4 April 2026. Amount paid 19,900 HUF.",
            },
            {
                "available": True,
                "document_id": "terms",
                "page_number": 2,
                "chunk_index": 1,
                "evidence_role": "primary",
                "_selection_score": 0.5,
                "_document_type": "warranty_terms_pdf",
                "_text": "Warranty period is 24 months from the purchase date.",
            },
        ],
        question="What purchase date and warranty period are stated?",
        answer="Purchase date is 4 April 2026 and the warranty period is 24 months.",
    )
    assert {item["document_id"] for item in selected} == {"receipt", "terms"}


def test_retrieval_overfetches_before_page_aware_truncation() -> None:
    class FakeProvider:
        def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
            return [[0.0]]

    class FakeCollection:
        def count(self) -> int:
            return 4

        def query(self, **kwargs):
            assert kwargs["n_results"] == 4
            return {
                "ids": [["generic", "purchase-date", "care", "setup"]],
                "documents": [[
                    "Generic device overview and setup summary.",
                    "Purchase date 3 May 2026. Amount paid 42,500 HUF.",
                    "Routine care instructions.",
                    "Setup checklist.",
                ]],
                "metadatas": [[
                    {"document_id": "manual", "page_number": 1},
                    {"document_id": "receipt", "page_number": 1},
                    {"document_id": "manual", "page_number": 2},
                    {"document_id": "manual", "page_number": 3},
                ]],
                "distances": [[0.01, 0.99, 0.4, 0.5]],
            }

    runtime = object.__new__(PipelineRuntime)
    runtime.provider = FakeProvider()
    runtime.collection = FakeCollection()
    runtime.config = ActualPipelineConfig()
    runtime.document_by_id = {
        "manual": CorpusDocument("manual", "pkg", "DEVICE-A", "user_manual_pdf", "manual.pdf", ("x",), ()),
        "receipt": CorpusDocument("receipt", "pkg", "DEVICE-A", "purchase_receipt_pdf", "receipt.pdf", ("x",), ()),
    }

    rows = PipelineRuntime._retrieve(
        runtime,
        "When did I buy it?",
        ["manual", "receipt"],
        top_k=1,
    )

    assert [(item["document_id"], item["page_number"]) for item in rows] == [("receipt", 1)]


def test_retrieval_diversifies_top_rows_across_documents() -> None:
    class FakeProvider:
        def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
            return [[0.0]]

    class FakeCollection:
        def count(self) -> int:
            return 4

        def query(self, **kwargs):
            assert kwargs["n_results"] == 4
            return {
                "ids": [["terms-a", "terms-b", "receipt-a", "manual-a"]],
                "documents": [[
                    "Warranty period is 24 months from the purchase date.",
                    "Warranty period begins on the retail purchase date.",
                    "Purchase date 3 May 2026. Amount paid 42,500 HUF.",
                    "Generic setup checklist.",
                ]],
                "metadatas": [[
                    {"document_id": "terms", "page_number": 2},
                    {"document_id": "terms", "page_number": 3},
                    {"document_id": "receipt", "page_number": 1},
                    {"document_id": "manual", "page_number": 1},
                ]],
                "distances": [[0.01, 0.02, 0.99, 0.5]],
            }

    runtime = object.__new__(PipelineRuntime)
    runtime.provider = FakeProvider()
    runtime.collection = FakeCollection()
    runtime.config = ActualPipelineConfig()
    runtime.document_by_id = {
        "terms": CorpusDocument("terms", "pkg", "DEVICE-A", "warranty_terms_pdf", "terms.pdf", ("x",), ()),
        "receipt": CorpusDocument("receipt", "pkg", "DEVICE-A", "purchase_receipt_pdf", "receipt.pdf", ("x",), ()),
        "manual": CorpusDocument("manual", "pkg", "DEVICE-A", "user_manual_pdf", "manual.pdf", ("x",), ()),
    }

    rows = PipelineRuntime._retrieve(
        runtime,
        "What warranty period and purchase date are stated?",
        ["terms", "receipt", "manual"],
        top_k=2,
    )

    assert [item["document_id"] for item in rows] == ["terms", "receipt"]


def _object_scope_fixture(root: Path, *, target_warranty: bool) -> tuple[Path, Path]:
    dataset = root / ("object-scope-with-target" if target_warranty else "object-scope-distractor")
    dataset.mkdir()
    package_ref = "pkg-object-a"
    docs = [
        {
            "document_id": document_id(package_ref, "target-manual"),
            "package_ref": package_ref,
            "object_id": "DEVICE-A",
            "document_type": "manual",
            "original_filename": "device-a-manual.pdf",
            "pages": ["Manual for DEVICE-A. Setup instruction: connect the blue cable."],
            "keywords": ["device-a", "manual", "setup"],
            "archived": False,
        },
        {
            "document_id": document_id(package_ref, "target-receipt"),
            "package_ref": package_ref,
            "object_id": "DEVICE-A",
            "document_type": "receipt",
            "original_filename": "device-a-receipt.pdf",
            "pages": ["Purchase receipt for DEVICE-A. Purchase date 3 May 2026."],
            "keywords": ["device-a", "purchase", "receipt", "date"],
            "archived": False,
        },
        {
            "document_id": document_id(package_ref, "distractor-warranty"),
            "package_ref": package_ref,
            "object_id": "DEVICE-B",
            "document_type": "warranty",
            "original_filename": "device-b-warranty.pdf",
            "pages": ["Warranty terms for DEVICE-B. Manufacturer warranty duration is 36 months."],
            "keywords": ["device-b", "warranty", "duration", "months"],
            "archived": False,
        },
    ]
    if target_warranty:
        docs.append(
            {
                "document_id": document_id(package_ref, "target-warranty"),
                "package_ref": package_ref,
                "object_id": "DEVICE-A",
                "document_type": "warranty",
                "original_filename": "device-a-warranty.pdf",
                "pages": ["Warranty terms for DEVICE-A. Manufacturer warranty duration is 24 months."],
                "keywords": ["device-a", "warranty", "duration", "months"],
                "archived": False,
            }
        )
    query = QueryInput(
        case_id="object-scope-case",
        evaluation_identity="scenario-user",
        query_text="How long is the manufacturer's warranty?",
        declared_purpose="grounded_question_answering",
        corpus_package_ref=package_ref,
        policy_fixture_ref="full",
        runtime_parameters={"top_k": 4},
    )
    write_jsonl(dataset / "query_inputs.jsonl", [query.to_dict()])
    corpus = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "metadata": {
            "dataset_version": "actual-pipeline-development-v1",
            "builder_version": "test",
            "synthetic": True,
        },
        "documents": docs,
        "policy_fixtures": [
            {
                "fixture_id": "full",
                "access_by_document": {item["document_id"]: "Full" for item in docs},
                "purpose": "grounded_question_answering",
                "conflict_policy": "query_sensitive",
                "aggregate_k": 3,
                "prohibited_markers": [],
            }
        ],
    }
    (dataset / "corpus_fixture.json").write_text(json.dumps(corpus), encoding="utf-8")
    return dataset / "query_inputs.jsonl", dataset / "corpus_fixture.json"


def test_object_scoped_query_rejects_different_object_distractor(tmp_path: Path) -> None:
    query_path, corpus_path = _object_scope_fixture(tmp_path, target_warranty=False)
    _run_minimal(tmp_path, query_path, corpus_path, "object-distractor")
    record = json.loads((tmp_path / "object-distractor/raw/raw_records.jsonl").read_text().splitlines()[0])
    assert record["actual_output_class"] == "REFUSE_INSUFFICIENT_EVIDENCE"
    assert record["actual_citations"] == []
    assert record["routing_trace"]["object_scope_applied"] is True


def test_object_scoped_query_allows_same_object_evidence(tmp_path: Path) -> None:
    query_path, corpus_path = _object_scope_fixture(tmp_path, target_warranty=True)
    _run_minimal(tmp_path, query_path, corpus_path, "object-target")
    record = json.loads((tmp_path / "object-target/raw/raw_records.jsonl").read_text().splitlines()[0])
    assert record["actual_output_class"] == "FULL_ANSWER"
    assert "24 months" in record["actual_output_text"]


def test_development_builder_separates_runtime_inputs_and_gold(tmp_path: Path) -> None:
    manifest = build_development_dataset(tmp_path / "dataset")
    assert manifest["query_count"] == manifest["gold_count"] == 20
    assert all(value == 2 for value in manifest["output_class_counts"].values())
    assert set(manifest["output_class_counts"]) == set(OUTPUT_CLASSES)
    query = json.loads((tmp_path / "dataset/query_inputs.jsonl").read_text().splitlines()[0])
    assert not {
        "expected_output_class",
        "reason_code",
        "gold_document_ids",
        "gold_page_or_message_ranges",
        "reference_answer",
    }.intersection(query)
    gold = json.loads((tmp_path / "dataset/gold_annotations.jsonl").read_text().splitlines()[0])
    assert gold["required_sources"] == gold["gold_document_ids"]
    assert "reference_citations" in gold


def test_runner_module_has_no_gold_loader_or_gold_field_access() -> None:
    source = (Path(__file__).parents[1] / "actual_pipeline_runner.py").read_text(encoding="utf-8")
    assert "actual_pipeline_gold" not in source
    assert "load_gold" not in source
    for forbidden in (
        "expected_output_class",
        "gold_document_ids",
        "gold_page",
        "reference_answer",
        "required_sources",
        "reference_citations",
    ):
        assert forbidden not in source


def test_runner_succeeds_without_gold_and_gold_corruption_cannot_change_raw(tmp_path: Path) -> None:
    query_path, corpus_path, gold_path = _minimal_fixture(tmp_path)
    seal = _run_minimal(tmp_path, query_path, corpus_path, "run-a")
    deterministic_before = seal["deterministic_content_sha256"]
    gold = json.loads(gold_path.read_text().splitlines()[0])
    gold["required_sources"] = []
    write_jsonl(gold_path, [gold])
    seal_after = _run_minimal(tmp_path, query_path, corpus_path, "run-b")
    assert seal_after["deterministic_content_sha256"] == deterministic_before


def test_runner_uses_query_identity_and_corpus_dataset_version(tmp_path: Path) -> None:
    query_path, corpus_path, gold_path = _minimal_fixture(tmp_path)
    query = json.loads(query_path.read_text().splitlines()[0])
    query["evaluation_identity"] = "scenario-user"
    write_jsonl(query_path, [query])
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus["metadata"]["dataset_version"] = "scenario-pack-development-v1"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    gold = json.loads(gold_path.read_text().splitlines()[0])
    gold["dataset_version"] = "scenario-pack-development-v1"
    write_jsonl(gold_path, [gold])

    _run_minimal(tmp_path, query_path, corpus_path, "scenario-version")
    raw_path = tmp_path / "scenario-version/raw/raw_records.jsonl"
    record = json.loads(raw_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["dataset_version"] == "scenario-pack-development-v1"
    assert record["actual_output_class"] == "FULL_ANSWER"
    score = score_sealed_run(
        raw_run_path=raw_path,
        seal_path=tmp_path / "scenario-version/raw/run_seal.json",
        gold_annotation_path=gold_path,
        output_dir=tmp_path / "scenario-version/scores",
    )
    assert score["dataset_version"] == "scenario-pack-development-v1"


def test_runner_uploads_external_source_pdf_bytes(tmp_path: Path) -> None:
    query_path, corpus_path, _ = _minimal_fixture(tmp_path)
    external_pdf = tmp_path / "dataset" / "source_documents" / "external-manual.pdf"
    digest = _write_test_pdf(
        external_pdf,
        "Synthetic TV-TEST-1 setup instruction: connect external HDMI 3.",
    )
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus["documents"][0]["pages"] = ["Decoy fixture text: connect internal port 9."]
    corpus["documents"][0]["source_pdf_path"] = "source_documents/external-manual.pdf"
    corpus["documents"][0]["source_pdf_sha256"] = digest
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    _run_minimal(tmp_path, query_path, corpus_path, "external-pdf")
    raw_path = tmp_path / "external-pdf/raw/raw_records.jsonl"
    record = json.loads(raw_path.read_text(encoding="utf-8").splitlines()[0])
    assert "connect external HDMI 3" in record["generator_visible_text"]
    assert "connect internal port 9" not in record["generator_visible_text"]


def test_gold_loader_accepts_legacy_and_prefers_explicit_roadmap_fields(tmp_path: Path) -> None:
    _, _, gold_path = _minimal_fixture(tmp_path)
    current = json.loads(gold_path.read_text().splitlines()[0])
    legacy = dict(current)
    legacy.pop("required_sources")
    legacy.pop("reference_citations")
    legacy_path = tmp_path / "legacy-gold.jsonl"
    write_jsonl(legacy_path, [legacy])
    legacy_annotation = load_gold_annotations(legacy_path)[0]
    assert legacy_annotation.required_sources is None
    assert legacy_annotation.required_source_ids == tuple(legacy["gold_document_ids"])
    assert legacy_annotation.reference_page_ranges == legacy["gold_page_or_message_ranges"]
    assert "required_sources" not in legacy_annotation.to_dict()
    assert "reference_citations" not in legacy_annotation.to_dict()

    current_annotation = load_gold_annotations(gold_path)[0]
    assert current_annotation.required_source_ids == tuple(current["required_sources"])
    assert current_annotation.reference_page_ranges == current["gold_page_or_message_ranges"]
    assert current_annotation.acceptable_page_ranges == current["gold_page_or_message_ranges"]

    validated = dict(current)
    validated["manual_validation_state"] = HUMAN_VALIDATED
    validated_path = tmp_path / "validated-gold.jsonl"
    write_jsonl(validated_path, [validated])
    validated_annotation = load_gold_annotations(validated_path)[0]
    assert validated_annotation.manual_validation_state == HUMAN_VALIDATED
    assert _human_validation_state([validated_annotation]) == "APPROVED"
    assert _human_validation_state([current_annotation, validated_annotation]) == "PENDING_HUMAN_REVIEW"

    inconsistent = dict(current)
    inconsistent["reference_citations"] = []
    inconsistent_path = tmp_path / "inconsistent-gold.jsonl"
    write_jsonl(inconsistent_path, [inconsistent])
    with pytest.raises(ValueError, match="must match legacy"):
        load_gold_annotations(inconsistent_path)


def test_false_answer_rate_is_over_expected_non_answer_cases() -> None:
    annotations = [
        GoldAnnotation(
            case_id="answer-ok",
            expected_output_class="FULL_ANSWER",
            reason_code="supported",
            gold_document_ids=("doc-a",),
            gold_page_or_message_ranges={"doc-a": [1]},
            reference_answer="supported fact",
            factual_atoms=("supported fact",),
            required_evidence_roles=(),
            action_status="NOT_APPLICABLE",
            required_sources=("doc-a",),
            reference_citations=({"source_id": "doc-a", "page": 1, "message_id": None, "record_id": None},),
        ),
        GoldAnnotation(
            case_id="answer-missed",
            expected_output_class="FULL_ANSWER",
            reason_code="supported",
            gold_document_ids=("doc-b",),
            gold_page_or_message_ranges={"doc-b": [1]},
            reference_answer="another fact",
            factual_atoms=("another fact",),
            required_evidence_roles=(),
            action_status="NOT_APPLICABLE",
            required_sources=("doc-b",),
            reference_citations=({"source_id": "doc-b", "page": 1, "message_id": None, "record_id": None},),
        ),
        GoldAnnotation(
            case_id="refusal-ok",
            expected_output_class="REFUSE_INSUFFICIENT_EVIDENCE",
            reason_code="evidential",
            gold_document_ids=(),
            gold_page_or_message_ranges={},
            reference_answer=None,
            factual_atoms=(),
            required_evidence_roles=(),
            action_status="NOT_APPLICABLE",
            required_sources=(),
            reference_citations=(),
        ),
        GoldAnnotation(
            case_id="false-answer",
            expected_output_class="REFUSE_INSUFFICIENT_EVIDENCE",
            reason_code="evidential",
            gold_document_ids=(),
            gold_page_or_message_ranges={},
            reference_answer=None,
            factual_atoms=(),
            required_evidence_roles=(),
            action_status="NOT_APPLICABLE",
            required_sources=(),
            reference_citations=(),
        ),
    ]
    records = [
        {
            "case_id": "answer-ok",
            "mode": "B3_FULL_ROLE_AWARE",
            "actual_output_class": "FULL_ANSWER",
            "actual_reason_code": "supported",
            "actual_output_text": "supported fact",
            "actual_citations": [{"available": True, "document_id": "doc-a", "page_number": 1}],
            "safety_constraints": {},
        },
        {
            "case_id": "answer-missed",
            "mode": "B3_FULL_ROLE_AWARE",
            "actual_output_class": "REFUSE_INSUFFICIENT_EVIDENCE",
            "actual_reason_code": "evidential",
            "actual_output_text": "The answer cannot be found in the document.",
            "actual_citations": [],
            "safety_constraints": {},
        },
        {
            "case_id": "refusal-ok",
            "mode": "B3_FULL_ROLE_AWARE",
            "actual_output_class": "REFUSE_INSUFFICIENT_EVIDENCE",
            "actual_reason_code": "evidential",
            "actual_output_text": "The answer cannot be found in the document.",
            "actual_citations": [],
            "safety_constraints": {},
        },
        {
            "case_id": "false-answer",
            "mode": "B3_FULL_ROLE_AWARE",
            "actual_output_class": "FULL_ANSWER",
            "actual_reason_code": "supported",
            "actual_output_text": "unsupported answer",
            "actual_citations": [],
            "safety_constraints": {},
        },
    ]
    summary, _ = _score_mode(records, annotations)
    assert summary["permitted_answer_accuracy"] == 0.5
    assert summary["expected_non_answer_count"] == 2
    assert summary["false_answer_count"] == 1
    assert summary["false_answer_rate_on_expected_abstentions"] == 0.5
    assert summary["false_or_unsupported_answer_rate"] == 0.5


def test_scorer_treats_gold_pages_as_acceptable_page_sets() -> None:
    cases = [
        ("one-page", "doc-a", [3], "doc-a", 3),
        ("two-pages-first", "doc-b", [3, 4], "doc-b", 3),
        ("two-pages-second", "doc-c", [3, 4], "doc-c", 4),
        ("outside-set", "doc-d", [10, 12, 13], "doc-d", 11),
        ("wrong-document", "doc-e", [3], "other-doc", 3),
    ]
    annotations = [
        GoldAnnotation(
            case_id=case_id,
            expected_output_class="FULL_ANSWER",
            reason_code="supported",
            gold_document_ids=(source_id,),
            gold_page_or_message_ranges={source_id: pages},
            reference_answer="supported fact",
            factual_atoms=("supported fact",),
            required_evidence_roles=(),
            action_status="NOT_APPLICABLE",
            required_sources=(source_id,),
            reference_citations=tuple(
                {"source_id": source_id, "page": page, "message_id": None, "record_id": None}
                for page in pages
            ),
        )
        for case_id, source_id, pages, _, _ in cases
    ]
    records = [
        {
            "case_id": case_id,
            "mode": "B3_FULL_ROLE_AWARE",
            "actual_output_class": "FULL_ANSWER",
            "actual_reason_code": "supported",
            "actual_output_text": "supported fact",
            "actual_citations": [{"available": True, "document_id": actual_doc_id, "page_number": actual_page}],
            "safety_constraints": {},
        }
        for case_id, _, _, actual_doc_id, actual_page in cases
    ]

    summary, _ = _score_mode(records, annotations)

    assert summary["citation_document_coverage"] == 0.8
    assert summary["citation_support_precision"] == 0.8
    assert summary["page_level_citation_correctness"] == 0.6
    assert summary["citation_coverage"] == 0.6


def test_scorer_compares_canonical_reason_codes() -> None:
    cases = [
        ("insufficient", "REFUSE_INSUFFICIENT_EVIDENCE", "insufficient_evidence", "evidential"),
        ("permission", "REFUSE_PERMISSION", "permission_refusal", "governance"),
        ("no-match", "REFUSE_NO_MATCH", "no_match", "epistemic"),
        ("conflict", "REFUSE_CONFLICT", "conflict", "conflict_defeat"),
        ("aggregate", "REFUSE_AGGREGATION_THRESHOLD", "aggregation_threshold_not_met", "aggregation_threshold_not_met"),
        ("clarify", "CLARIFICATION", "clarification", "underspecified_question"),
    ]
    annotations = [
        GoldAnnotation(
            case_id=case_id,
            expected_output_class=output_class,
            reason_code=expected_reason,
            gold_document_ids=(),
            gold_page_or_message_ranges={},
            reference_answer=None,
            factual_atoms=(),
            required_evidence_roles=(),
            action_status="NOT_APPLICABLE",
            required_sources=(),
            reference_citations=(),
        )
        for case_id, output_class, expected_reason, _ in cases
    ]
    records = [
        {
            "case_id": case_id,
            "mode": "B3_FULL_ROLE_AWARE",
            "actual_output_class": output_class,
            "actual_reason_code": actual_reason,
            "actual_output_text": "No grounded answer is available.",
            "actual_citations": [],
            "safety_constraints": {},
        }
        for case_id, output_class, _, actual_reason in cases
    ]

    summary, details = _score_mode(records, annotations)

    assert summary["reason_code_accuracy"] == 1.0
    assert {item["actual_reason_code"] for item in details} == {
        "aggregation_threshold_not_met",
        "clarification",
        "conflict",
        "insufficient_evidence",
        "no_match",
        "permission_refusal",
    }


def test_query_corruption_changes_raw_deterministic_content(tmp_path: Path) -> None:
    query_path, corpus_path, _ = _minimal_fixture(tmp_path)
    first = _run_minimal(tmp_path, query_path, corpus_path, "run-a")
    query = json.loads(query_path.read_text().splitlines()[0])
    query["query_text"] = "What unrelated battery capacity is stated for TV-TEST-1?"
    write_jsonl(query_path, [query])
    second = _run_minimal(tmp_path, query_path, corpus_path, "run-b")
    assert first["deterministic_content_sha256"] != second["deterministic_content_sha256"]


def test_scorer_requires_preexisting_seal_and_rejects_identity_and_version_errors(tmp_path: Path) -> None:
    query_path, corpus_path, gold_path = _minimal_fixture(tmp_path)
    _run_minimal(tmp_path, query_path, corpus_path, "run")
    raw = tmp_path / "run/raw/raw_records.jsonl"
    seal = tmp_path / "run/raw/run_seal.json"
    score_sealed_run(raw_run_path=raw, seal_path=seal, gold_annotation_path=gold_path, output_dir=tmp_path / "ok")

    gold = json.loads(gold_path.read_text().splitlines()[0])
    for label, mutation, match in (
        ("missing", lambda value: value.update(case_id="missing"), "identity mismatch"),
        ("version", lambda value: value.update(dataset_version="wrong-version"), "version mismatch"),
    ):
        changed = dict(gold)
        mutation(changed)
        changed_path = tmp_path / f"{label}.jsonl"
        write_jsonl(changed_path, [changed])
        with pytest.raises(ValueError, match=match):
            score_sealed_run(raw_run_path=raw, seal_path=seal, gold_annotation_path=changed_path, output_dir=tmp_path / label)

    duplicate_path = tmp_path / "duplicate.jsonl"
    write_jsonl(duplicate_path, [gold, gold])
    with pytest.raises(ValueError, match="duplicate"):
        score_sealed_run(raw_run_path=raw, seal_path=seal, gold_annotation_path=duplicate_path, output_dir=tmp_path / "dup")

    seal_value = json.loads(seal.read_text())
    seal_value["scoring_started"] = True
    bad_seal = tmp_path / "bad-seal.json"
    bad_seal.write_text(json.dumps(seal_value), encoding="utf-8")
    with pytest.raises(ValueError, match="sealed before scoring"):
        score_sealed_run(raw_run_path=raw, seal_path=bad_seal, gold_annotation_path=gold_path, output_dir=tmp_path / "bad")


def test_safety_scanner_detects_each_actual_trace_surface() -> None:
    denied = "00000000-0000-0000-0000-000000000099"
    record = {
        "candidate_ids": [denied],
        "retrieved_document_ids": [denied],
        "generator_visible_document_ids": [denied],
        "generator_visible_text": "PRIVATE-MARKER approval time is 7 days C:\\private\\source.pdf",
        "actual_output_text": f"Found {denied}; approval time is 7 days.",
        "actual_citations": [{"document_id": denied, "page_number": 1}],
        "safety_constraints": {
            "prohibited_document_ids": [denied],
            "prohibited_markers": ["PRIVATE-MARKER"],
            "archived_document_ids": [denied],
            "aggregate_individual_fragments": ["approval time is 7 days"],
        },
    }
    findings = scan_record_safety(record)
    assert findings and all(value == 1 for value in findings.values())


def test_production_routes_do_not_expose_b0_or_b1_switch() -> None:
    route_text = "\n".join(path.read_text(encoding="utf-8") for path in (Path(__file__).parents[2] / "backend_python/routers").glob("*.py"))
    assert "B0_VECTOR_ONLY" not in route_text
    assert "B1_VECTOR_ROUTING" not in route_text
