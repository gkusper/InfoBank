from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.external_scenario_corpus import (
    resolve_source_pdf,
    write_external_scenario_actual_inputs,
)
from evaluation.scenario_pack import write_scenario_pack_projection


def _write_pdf(path: Path, pages: list[str]) -> None:
    import fitz

    pdf = fitz.open()
    for text in pages:
        page = pdf.new_page(width=595, height=842)
        page.insert_textbox(fitz.Rect(72, 72, 523, 770), text, fontsize=11, fontname="helv")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(pdf.tobytes(garbage=4, deflate=True, no_new_id=True))
    except TypeError:
        path.write_bytes(pdf.tobytes(garbage=4, deflate=True))
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
    (scenario_root / "scenario_pack.json").write_text(
        json.dumps(pack, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    write_scenario_pack_projection(pack, root / "projections" / scenario_id)
    manifest = {
        "package_name": "test-package",
        "scenario_ids": [scenario_id],
        "scenario_question_counts": {scenario_id: 1},
        "files": [],
    }
    (root / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    checksums = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        relative = path.relative_to(root).as_posix()
        checksums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n")
    (root / "SHA256SUMS.txt").write_text("".join(checksums), encoding="utf-8")


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
    corpus = json.loads((output / "corpus_fixture.json").read_text(encoding="utf-8"))
    document = corpus["documents"][0]
    assert document["document_id"] == manifest["source_bindings"][0]["document_id"]
    assert document["source_pdf_path"] == "source_documents/TEST_SCENARIO_01/device-manual.pdf"
    assert len(document["source_pdf_sha256"]) == 64
    runtime_text = (output / "query_inputs.jsonl").read_text(encoding="utf-8")
    assert "reference_answer" not in runtime_text
    assert "required_sources" not in runtime_text
    gold_text = (output / "gold_annotations.jsonl").read_text(encoding="utf-8")
    assert "required_sources" in gold_text
    gold = json.loads(gold_text.splitlines()[0])
    assert gold["required_sources"] == [document["document_id"]]
    assert gold["metadata"]["logical_source_id_map"] == {"manual-source": document["document_id"]}
