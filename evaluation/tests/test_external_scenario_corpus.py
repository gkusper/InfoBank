from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from evaluation.external_scenario_corpus import (
    resolve_source_pdf,
    verify_package_checksums,
    write_external_primary_contract_actual_inputs,
    write_external_scenario_actual_inputs,
)
from evaluation.scenario_pack import write_scenario_pack_projection


def _windows_api_path(path: Path) -> str | Path:
    if os.name != "nt":
        return path
    resolved = str(path.resolve())
    if resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved.lstrip("\\")
    return "\\\\?\\" + resolved


def _read_bytes(path: Path) -> bytes:
    with open(_windows_api_path(path), "rb") as handle:
        return handle.read()


def _read_text(path: Path) -> str:
    with open(_windows_api_path(path), "r", encoding="utf-8") as handle:
        return handle.read()


def _write_bytes(path: Path, content: bytes) -> None:
    os.makedirs(_windows_api_path(path.parent), exist_ok=True)
    with open(_windows_api_path(path), "wb") as handle:
        handle.write(content)


def _write_text(path: Path, content: str) -> None:
    os.makedirs(_windows_api_path(path.parent), exist_ok=True)
    with open(_windows_api_path(path), "w", encoding="utf-8") as handle:
        handle.write(content)


def _write_pdf(path: Path, pages: list[str]) -> None:
    import fitz

    pdf = fitz.open()
    for text in pages:
        page = pdf.new_page(width=595, height=842)
        page.insert_textbox(fitz.Rect(72, 72, 523, 770), text, fontsize=11, fontname="helv")
    try:
        _write_bytes(path, pdf.tobytes(garbage=4, deflate=True, no_new_id=True))
    except TypeError:
        _write_bytes(path, pdf.tobytes(garbage=4, deflate=True))
    finally:
        pdf.close()


def _pack(scenario_id: str) -> dict:
    return {
        "scenario_id": scenario_id,
        "user_id": "scenario-user",
        "object_id": "DEVICE-TEST-1",
        "account_id": None,
        "sources": [
            {
                "source_id": "manual-source",
                "source_type": "user_manual_pdf",
                "date": None,
                "valid_from": None,
                "valid_to": None,
                "relation_key": "DEVICE-TEST-1",
                "permission": "Owner",
            }
        ],
        "queries": [
            {
                "query_id": "TEST-Q1",
                "query": "What setup instruction is stated for DEVICE-TEST-1?",
                "required_sources": ["manual-source"],
                "supporting_sources": [],
                "expected_output": "FULL_ANSWER",
                "reference_answer": "Connect the external source.",
                "reference_citations": [
                    {"source_id": "manual-source", "page": 1, "message_id": None, "record_id": None}
                ],
                "negative_reason": None,
            }
        ],
    }


def _write_test_package(root: Path, scenario_id: str = "TEST_SCENARIO_01") -> None:
    pack = _pack(scenario_id)
    scenario_root = root / "scenario_packs" / scenario_id
    _write_pdf(scenario_root / "source_documents" / "device-manual.pdf", ["Connect the external source."])
    scenario_root.mkdir(parents=True, exist_ok=True)
    _write_text(
        scenario_root / "scenario_pack.json",
        json.dumps(pack, sort_keys=True, indent=2) + "\n",
    )
    write_scenario_pack_projection(pack, root / "projections" / scenario_id)
    manifest = {
        "package_name": "test-package",
        "scenario_ids": [scenario_id],
        "scenario_question_counts": {scenario_id: 1},
        "files": [],
    }
    _write_text(
        root / "PACKAGE_MANIFEST.json",
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
    )
    checksums = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        relative = path.relative_to(root).as_posix()
        checksums.append(f"{hashlib.sha256(_read_bytes(path)).hexdigest()}  {relative}\n")
    _write_text(root / "SHA256SUMS.txt", "".join(checksums))


def _write_checksums(root: Path, filename: str) -> None:
    checksums = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != filename):
        relative = path.relative_to(root).as_posix()
        checksums.append(f"{hashlib.sha256(_read_bytes(path)).hexdigest()}  {relative}\n")
    _write_text(root / filename, "".join(checksums))


def _write_primary_contract_package(root: Path) -> None:
    scenario_id = "PRIMARY_CONTRACT_SCENARIO"
    case_id = "CONTRACT-Q1"
    pack = _pack(scenario_id)
    pack["queries"][0]["query_id"] = case_id
    pack["queries"][0]["expected_output"] = "AGGREGATE_RESULT"
    pack["queries"][0]["reference_answer"] = "The governed aggregate metric is 17.5."
    pack["queries"][0]["reference_citations"] = []
    scenario_root = root / "independent_evaluation_packs" / scenario_id
    _write_pdf(scenario_root / "source_documents" / "metric-data.pdf", ["Private contributor metric is 17.5 units."])
    _write_text(
        scenario_root / "scenario_pack.json",
        json.dumps(pack, sort_keys=True, indent=2) + "\n",
    )
    _write_text(
        scenario_root / "source_documents_manifest.json",
        json.dumps(
            {
                "scenario_id": scenario_id,
                "binding_count": 1,
                "documents": [
                    {
                        "source_id": "manual-source",
                        "filename": "metric-data.pdf",
                        "page_count": 1,
                        "sha256": hashlib.sha256(_read_bytes(scenario_root / "source_documents" / "metric-data.pdf")).hexdigest(),
                        "reused_from": None,
                    }
                ],
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    primary = root / "evaluation_contracts" / "primary"
    runtime_rows = [
        {
            "case_id": case_id,
            "evaluation_identity": "scenario-user-aggregate",
            "query_text": pack["queries"][0]["query"],
            "declared_purpose": "grounded_question_answering",
            "corpus_package_ref": scenario_id,
            "policy_fixture_ref": f"{case_id}:aggregate",
            "runtime_parameters": {"top_k": 1},
            "schema_version": "infobank-query-input-v1",
        }
    ]
    reference_rows = [
        {
            "case_id": case_id,
            "expected_output_class": "AGGREGATE_RESULT",
            "reason_code": "aggregate_threshold_satisfied",
            "gold_document_ids": ["manual-source"],
            "gold_page_or_message_ranges": {},
            "required_sources": ["manual-source"],
            "reference_citations": [],
            "reference_answer": pack["queries"][0]["reference_answer"],
            "factual_atoms": ["17.5"],
            "required_evidence_roles": [],
            "action_status": "NOT_APPLICABLE",
            "manual_validation_state": "HUMAN_VALIDATED",
            "dataset_version": "contract-candidate-v1",
            "schema_version": "infobank-gold-annotation-v1",
            "metadata": {
                "scenario_id": scenario_id,
                "supporting_sources": [],
                "author_decision_id": "HR-GENERIC-001",
                "permission_mode": "Aggregate",
                "effective_use_decision": "Aggregate",
                "aggregate_k": 2,
                "expected_contributor_count": 2,
                "prohibited_disclosures": ["private-token"],
                "public_document_citations_expected": False,
            },
        }
    ]
    policy_fixtures = {
        "schema_version": "infobank-policy-fixtures-v1",
        "contract_version": "infobank-scenario-contract-v1.2",
        "status": "AUTHOR_REVIEWED_CANDIDATE_NOT_FROZEN",
        "policy_fixtures": [
            {
                "fixture_id": f"{case_id}:aggregate",
                "access_by_document": {"manual-source": "Aggregate"},
                "purpose": "grounded_question_answering",
                "conflict_policy": "query_sensitive",
                "aggregate_k": 2,
                "prohibited_markers": ["private-token"],
                "author_decision_id": "HR-GENERIC-001",
                "author_reviewed": True,
                "effective_use_decision": "Aggregate",
                "expected_contributor_count": 2,
            }
        ],
    }
    retrieval = {
        "contract_version": "infobank-scenario-contract-v1.2",
        "query_count": 1,
        "bounded_queries": [
            {
                "query_id": case_id,
                "scenario_id": scenario_id,
                "required_sources": ["manual-source"],
                "reference_citations": [],
                "public_citations_expected": False,
                "status": "BOUNDED",
                "top_k": 1,
            }
        ],
    }
    primary.mkdir(parents=True, exist_ok=True)
    (primary / "runtime").mkdir()
    (primary / "scorer").mkdir()
    _write_text(
        primary / "runtime" / "query_inputs.jsonl",
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in runtime_rows),
    )
    _write_text(
        primary / "scorer" / "gold_annotations.jsonl",
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in reference_rows),
    )
    _write_text(primary / "policy_fixtures.json", json.dumps(policy_fixtures, sort_keys=True, indent=2) + "\n")
    _write_text(primary / "retrieval_contracts.json", json.dumps(retrieval, sort_keys=True, indent=2) + "\n")
    _write_text(
        primary / "contract_manifest.json",
        json.dumps(
            {
                "status": "AUTHOR_REVIEWED_CANDIDATE_NOT_FROZEN",
                "dataset_version": "contract-candidate-v1",
                "scenario_count": 1,
                "question_count": 1,
                "source_pdf_count": 1,
                "output_class_distribution": {"AGGREGATE_RESULT": 1},
                "runtime_gold_separated": True,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    _write_text(
        root / "scenario_pack_index.json",
        json.dumps(
            {
                "dataset_version": "contract-candidate-v1",
                "primary_scenario_count": 1,
                "primary_query_count": 1,
                "primary_source_count": 1,
                "primary_scenarios": [
                    {
                        "scenario_id": scenario_id,
                        "manifest_path": f"independent_evaluation_packs/{scenario_id}/scenario_pack.json",
                        "query_count": 1,
                        "source_count": 1,
                        "sha256": hashlib.sha256(_read_bytes(scenario_root / "scenario_pack.json")).hexdigest(),
                    }
                ],
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    _write_text(
        root / "PACKAGE_MANIFEST.json",
        json.dumps(
            {
                "package_identity": "contract-package",
                "dataset_version": "contract-candidate-v1",
                "status": "AUTHOR_REVIEWED_CANDIDATE_NOT_FROZEN",
                "primary_scenario_count": 1,
                "primary_question_count": 1,
                "primary_source_pdf_count": 1,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    _write_checksums(root, "PACKAGE_SHA256SUMS.txt")


def test_resolve_source_pdf_requires_explicit_map_when_names_differ(tmp_path: Path) -> None:
    root = tmp_path / "package"
    _write_test_package(root)
    scenario_dir = root / "scenario_packs" / "TEST_SCENARIO_01"
    source = _pack("TEST_SCENARIO_01")["sources"][0]
    with pytest.raises(FileNotFoundError):
        resolve_source_pdf(scenario_dir, source)
    resolved = resolve_source_pdf(
        scenario_dir,
        source,
        source_filename_map={"TEST_SCENARIO_01:manual-source": "device-manual.pdf"},
    )
    assert resolved.name == "device-manual.pdf"


def test_external_scenario_package_binding_writes_gold_blind_runtime(tmp_path: Path) -> None:
    root = tmp_path / "package"
    output = tmp_path / "bound"
    _write_test_package(root)
    manifest = write_external_scenario_actual_inputs(
        root,
        output,
        scenario_ids=("TEST_SCENARIO_01",),
        source_filename_map={"manual-source": "device-manual.pdf"},
        package_sha256="0" * 64,
    )
    assert manifest["status"] == "READY_FOR_ACTUAL_PIPELINE"
    assert manifest["query_count"] == manifest["gold_count"] == 1
    corpus = json.loads(_read_text(output / "corpus_fixture.json"))
    document = corpus["documents"][0]
    assert document["document_id"] == manifest["source_bindings"][0]["document_id"]
    assert document["source_pdf_path"] == "source_documents/TEST_SCENARIO_01/device-manual.pdf"
    assert len(document["source_pdf_sha256"]) == 64
    runtime_text = _read_text(output / "query_inputs.jsonl")
    assert "reference_answer" not in runtime_text
    assert "required_sources" not in runtime_text
    gold_text = _read_text(output / "gold_annotations.jsonl")
    assert "required_sources" in gold_text
    gold = json.loads(gold_text.splitlines()[0])
    assert gold["required_sources"] == [document["document_id"]]
    assert gold["metadata"]["logical_source_id_map"] == {"manual-source": document["document_id"]}


def test_package_checksum_verification_accepts_package_sha256sums(tmp_path: Path) -> None:
    root = tmp_path / "package"
    _write_primary_contract_package(root)

    result = verify_package_checksums(root)

    assert result["status"] == "PASS"
    assert result["checksum_file"] == "PACKAGE_SHA256SUMS.txt"


def test_primary_contract_binding_preserves_case_policy_and_gold_blind_runtime(tmp_path: Path) -> None:
    root = tmp_path / "package"
    output = tmp_path / "bound"
    _write_primary_contract_package(root)

    manifest = write_external_primary_contract_actual_inputs(
        root,
        output,
        package_sha256="1" * 64,
    )

    assert manifest["status"] == "READY_FOR_ACTUAL_PIPELINE"
    assert manifest["query_count"] == manifest["reference_annotation_count"] == 1
    assert manifest["document_count"] == manifest["policy_fixture_count"] == 1
    corpus = json.loads(_read_text(output / "corpus_fixture.json"))
    document = corpus["documents"][0]
    fixture = corpus["policy_fixtures"][0]
    assert document["source_pdf_path"] == "source_documents/PRIMARY_CONTRACT_SCENARIO/metric-data.pdf"
    assert fixture["access_by_document"] == {document["document_id"]: "Aggregate"}
    assert fixture["aggregate_k"] == 2
    assert fixture["prohibited_markers"] == ["private-token"]
    runtime_text = _read_text(output / "query_inputs.jsonl")
    assert all(
        field not in runtime_text
        for field in ("reference_answer", "required_sources", "author_decision_id", "factual_atoms")
    )
    reference = json.loads(_read_text(output / "gold_annotations.jsonl").splitlines()[0])
    assert reference["required_sources"] == [document["document_id"]]
    assert reference["gold_document_ids"] == [document["document_id"]]
    assert reference["metadata"]["logical_source_id_map"] == {"manual-source": document["document_id"]}
    assert manifest["verification"]["case_checks"][0]["author_decision_id"] == "HR-GENERIC-001"
