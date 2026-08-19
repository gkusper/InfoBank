"""Build separate development QueryInput, GoldAnnotation, and corpus fixtures."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .actual_pipeline_gold import GoldAnnotation
from .actual_pipeline_inputs import (
    CORPUS_SCHEMA_VERSION,
    CorpusDocument,
    PolicyFixture,
    QueryInput,
    write_jsonl,
)


DATASET_VERSION = "actual-pipeline-development-v1"
BUILDER_VERSION = "actual-pipeline-development-builder-v1"
OUTPUT_CLASSES = (
    "FULL_ANSWER",
    "CONSTRAINED_ANSWER",
    "AGGREGATE_RESULT",
    "METADATA_ONLY",
    "CLARIFICATION",
    "REFUSE_PERMISSION",
    "REFUSE_INSUFFICIENT_EVIDENCE",
    "REFUSE_NO_MATCH",
    "REFUSE_AGGREGATION_THRESHOLD",
    "REFUSE_CONFLICT",
)


@dataclass(frozen=True)
class Package:
    package_ref: str
    family: str
    object_id: str
    setup: str
    support: str
    warranty_months: int
    approval_days: int


PACKAGES = (
    Package("pkg-tv-aurora41", "television", "TV-AURORA-41", "Connect the receiver to HDMI 2.", "Firmware 5.4 resolves HDMI wake failures.", 24, 6),
    Package("pkg-router-r620", "router", "ROUTER-R620", "Connect the blue WAN port.", "Firmware 3.2 enables wired mesh on LAN 1.", 12, 9),
    Package("pkg-printer-px220", "printer", "PRINTER-PX220", "Load A4 paper in tray 1.", "Jam J42 is cleared at the rear duplex roller.", 18, 12),
)


def document_id(package_ref: str, document_type: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:actual-development:{package_ref}:{document_type}"))


def _documents() -> list[CorpusDocument]:
    documents: list[CorpusDocument] = []
    for package in PACKAGES:
        values = {
            "manual_user_guide": (
                f"Synthetic owned object {package.object_id}. Setup instruction: {package.setup}",
                f"Synthetic owned object {package.object_id}. Support instruction: {package.support}",
            ),
            "quick_start_specification": (
                f"Quick start for {package.object_id} uses the labelled connection described in the setup guide.",
                f"Specification code for {package.object_id} is QS-{package.object_id}.",
            ),
            "warranty": (
                f"Authoritative warranty for {package.object_id}: duration is {package.warranty_months} months.",
                f"Warranty claim for {package.object_id} requires a synthetic invoice code; accidental damage is excluded.",
            ),
            "synthetic_purchase_service_record": (
                f"Governed cohort metric for {package.object_id}: approval time is {package.approval_days} days.",
                f"Synthetic service record for {package.object_id} confirms one routine inspection.",
            ),
            "thematic_distractor": (
                f"Generic packaging note near {package.object_id}; it is not an instruction for the owned object.",
                f"Unverified insert for {package.object_id} contradicts the authoritative warranty and claims {max(1, package.warranty_months - 6)} months. It must not override the authoritative warranty.",
            ),
        }
        for document_type, pages in values.items():
            semantic_keywords = {
                "manual_user_guide": {"manual", "setup", "support"},
                "quick_start_specification": {"quick", "setup", "specification"},
                "warranty": {"warranty", "authoritative", "conflict"},
                "synthetic_purchase_service_record": {"aggregate", "approval", "cohort"},
                "thematic_distractor": {"warranty", "conflict", "unverified"},
            }[document_type]
            documents.append(
                CorpusDocument(
                    document_id=document_id(package.package_ref, document_type),
                    package_ref=package.package_ref,
                    object_id=package.object_id,
                    document_type=document_type,
                    original_filename=f"{package.object_id.lower()}-{document_type}.pdf",
                    pages=pages,
                    keywords=tuple(sorted({package.family, package.object_id.lower(), *document_type.split("_"), *semantic_keywords})),
                    archived=False,
                )
            )
    return documents


def _fixture_documents(documents: list[CorpusDocument], document_type: str | None = None) -> list[str]:
    return [item.document_id for item in documents if document_type is None or item.document_type == document_type]


def _fixtures(documents: list[CorpusDocument]) -> list[PolicyFixture]:
    by_package = {
        package.package_ref: [item.document_id for item in documents if item.package_ref == package.package_ref]
        for package in PACKAGES
    }
    all_full = {item.document_id: "Full" for item in documents}
    tv_manual = document_id(PACKAGES[0].package_ref, "manual_user_guide")
    router_manual = document_id(PACKAGES[1].package_ref, "manual_user_guide")
    printer_manual = document_id(PACKAGES[2].package_ref, "manual_user_guide")
    aggregate_ids = _fixture_documents(documents, "synthetic_purchase_service_record")
    return [
        PolicyFixture("full_all", all_full),
        PolicyFixture("full_tv", {doc_id: "Full" for doc_id in by_package[PACKAGES[0].package_ref]}),
        PolicyFixture("full_router", {doc_id: "Full" for doc_id in by_package[PACKAGES[1].package_ref]}),
        PolicyFixture("full_printer", {doc_id: "Full" for doc_id in by_package[PACKAGES[2].package_ref]}),
        PolicyFixture("metadata_tv", {tv_manual: "Metadata"}),
        PolicyFixture("metadata_router", {router_manual: "Metadata"}),
        PolicyFixture("deny_tv", {}, prohibited_markers=(tv_manual,)),
        PolicyFixture("deny_router", {}, prohibited_markers=(router_manual,)),
        PolicyFixture("aggregate_three", {doc_id: "Aggregate" for doc_id in aggregate_ids}, aggregate_k=3),
        PolicyFixture("aggregate_two", {doc_id: "Aggregate" for doc_id in aggregate_ids[:2]}, aggregate_k=3),
        PolicyFixture("insufficient_tv", {tv_manual: "Full"}),
        PolicyFixture("insufficient_printer", {printer_manual: "Full"}),
        PolicyFixture("no_match_all", all_full),
    ]


def _case(
    index: int,
    output_class: str,
    query: str,
    package_ref: str,
    fixture: str,
    reason: str,
    gold_docs: list[str],
    pages: dict[str, list[int]],
    atoms: list[str],
    roles: list[str],
) -> tuple[QueryInput, GoldAnnotation]:
    case_id = f"ap-dev-{index:03d}"
    query_input = QueryInput(
        case_id=case_id,
        evaluation_identity=f"eval-{fixture}",
        query_text=query,
        declared_purpose="grounded_question_answering",
        corpus_package_ref=package_ref,
        policy_fixture_ref=fixture,
        runtime_parameters={"top_k": 6},
    )
    gold = GoldAnnotation(
        case_id=case_id,
        expected_output_class=output_class,
        reason_code=reason,
        gold_document_ids=tuple(gold_docs),
        gold_page_or_message_ranges=pages,
        reference_answer=" ".join(atoms) if atoms else None,
        factual_atoms=tuple(atoms),
        required_evidence_roles=tuple(roles),
        action_status="NOT_APPLICABLE",
        dataset_version=DATASET_VERSION,
        metadata={"coverage_class": output_class},
    )
    return query_input, gold


def _cases() -> tuple[list[QueryInput], list[GoldAnnotation]]:
    tv, router, printer = PACKAGES
    tv_manual = document_id(tv.package_ref, "manual_user_guide")
    rt_manual = document_id(router.package_ref, "manual_user_guide")
    tv_warranty = document_id(tv.package_ref, "warranty")
    tv_conflict = document_id(tv.package_ref, "thematic_distractor")
    rt_warranty = document_id(router.package_ref, "warranty")
    rt_conflict = document_id(router.package_ref, "thematic_distractor")
    aggregate_docs = [document_id(item.package_ref, "synthetic_purchase_service_record") for item in PACKAGES]
    specs = [
        ("FULL_ANSWER", f"What setup instruction is stated for {tv.object_id}?", tv.package_ref, "full_tv", "supported", [tv_manual], {tv_manual: [1]}, [tv.setup], ["primary"]),
        ("FULL_ANSWER", f"What support instruction is stated for {router.object_id}?", router.package_ref, "full_router", "supported", [rt_manual], {rt_manual: [2]}, [router.support], ["primary"]),
        ("CONSTRAINED_ANSWER", f"Give a bounded summary of the warranty conflict for {tv.object_id}.", tv.package_ref, "full_tv", "conflict_defeat", [tv_warranty, tv_conflict], {tv_warranty: [1], tv_conflict: [2]}, [], ["primary", "contrastive"]),
        ("CONSTRAINED_ANSWER", f"Give a bounded summary of the warranty conflict for {router.object_id}.", router.package_ref, "full_router", "conflict_defeat", [rt_warranty, rt_conflict], {rt_warranty: [1], rt_conflict: [2]}, [], ["primary", "contrastive"]),
        ("AGGREGATE_RESULT", "What is the average approval time across the permitted cohort?", "cohort-all", "aggregate_three", "aggregate_threshold_satisfied", aggregate_docs, {}, ["Governed aggregate mean: 9"], ["aggregate-only"]),
        ("AGGREGATE_RESULT", "What is the aggregate mean approval time for the governed cohort?", "cohort-all", "aggregate_three", "aggregate_threshold_satisfied", aggregate_docs, {}, ["Governed aggregate mean: 9"], ["aggregate-only"]),
        ("METADATA_ONLY", f"What metadata is available for the {tv.object_id} manual?", tv.package_ref, "metadata_tv", "governance", [tv_manual], {}, [], ["contextual"]),
        ("METADATA_ONLY", f"What metadata is available for the {router.object_id} manual?", router.package_ref, "metadata_router", "governance", [rt_manual], {}, [], ["contextual"]),
        ("CLARIFICATION", "this?", "unspecified", "full_all", "epistemic", [], {}, [], []),
        ("CLARIFICATION", "What about this?", "unspecified", "full_all", "epistemic", [], {}, [], []),
        ("REFUSE_PERMISSION", f"What setup instruction is stated for {tv.object_id}?", tv.package_ref, "deny_tv", "governance", [], {}, [], ["governance-excluded"]),
        ("REFUSE_PERMISSION", f"What setup instruction is stated for {router.object_id}?", router.package_ref, "deny_router", "governance", [], {}, [], ["governance-excluded"]),
        ("REFUSE_INSUFFICIENT_EVIDENCE", f"What is the battery capacity in watt hours for {tv.object_id}?", tv.package_ref, "insufficient_tv", "evidential", [], {}, [], []),
        ("REFUSE_INSUFFICIENT_EVIDENCE", f"What fax speed is specified for {printer.object_id}?", printer.package_ref, "insufficient_printer", "evidential", [], {}, [], []),
        ("REFUSE_NO_MATCH", "What setup is specified for DEVICE-X999?", "missing-device", "no_match_all", "epistemic", [], {}, [], []),
        ("REFUSE_NO_MATCH", "What warranty applies to ROUTER-Z404?", "missing-device", "no_match_all", "epistemic", [], {}, [], []),
        ("REFUSE_AGGREGATION_THRESHOLD", "What is the average approval time across the permitted cohort?", "cohort-partial", "aggregate_two", "aggregation_threshold_not_met", [], {}, [], ["aggregate-only"]),
        ("REFUSE_AGGREGATION_THRESHOLD", "What is the aggregate mean approval time for the governed cohort?", "cohort-partial", "aggregate_two", "aggregation_threshold_not_met", [], {}, [], ["aggregate-only"]),
        ("REFUSE_CONFLICT", f"Which source has final authority to resolve the warranty conflict for {tv.object_id}?", tv.package_ref, "full_tv", "conflict_defeat", [tv_warranty, tv_conflict], {tv_warranty: [1], tv_conflict: [2]}, [], ["primary", "contrastive"]),
        ("REFUSE_CONFLICT", f"Which source is authoritative to resolve the warranty conflict for {router.object_id}?", router.package_ref, "full_router", "conflict_defeat", [rt_warranty, rt_conflict], {rt_warranty: [1], rt_conflict: [2]}, [], ["primary", "contrastive"]),
    ]
    pairs = [_case(index, *spec) for index, spec in enumerate(specs, start=1)]
    return [item[0] for item in pairs], [item[1] for item in pairs]


def build_development_dataset(output_dir: str | Path) -> dict[str, Any]:
    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing to mix dataset output: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    documents = _documents()
    fixtures = _fixtures(documents)
    queries, gold = _cases()
    write_jsonl(destination / "query_inputs.jsonl", (item.to_dict() for item in queries))
    write_jsonl(destination / "gold_annotations.jsonl", (item.to_dict() for item in gold))
    corpus = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "metadata": {
            "dataset_version": DATASET_VERSION,
            "builder_version": BUILDER_VERSION,
            "synthetic": True,
            "health_content_prohibited": True,
            "retained_output_classes": list(OUTPUT_CLASSES),
            "future_output_classes": ["ESCALATE_TO_HUMAN"],
        },
        "documents": [item.to_dict() for item in documents],
        "policy_fixtures": [item.to_dict() for item in fixtures],
    }
    (destination / "corpus_fixture.json").write_text(
        json.dumps(corpus, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_version": DATASET_VERSION,
        "builder_version": BUILDER_VERSION,
        "query_count": len(queries),
        "gold_count": len(gold),
        "document_count": len(documents),
        "policy_fixture_count": len(fixtures),
        "output_class_counts": {name: sum(item.expected_output_class == name for item in gold) for name in OUTPUT_CLASSES},
        "query_input_sha256": hashlib.sha256((destination / "query_inputs.jsonl").read_bytes()).hexdigest(),
        "gold_sha256": hashlib.sha256((destination / "gold_annotations.jsonl").read_bytes()).hexdigest(),
        "corpus_sha256": hashlib.sha256((destination / "corpus_fixture.json").read_bytes()).hexdigest(),
        "candidate_holdout_accessed": False,
        "manual_validation_state": "PENDING_HUMAN_REVIEW",
    }
    (destination / "dataset_manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest
