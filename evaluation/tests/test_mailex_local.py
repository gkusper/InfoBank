from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

from evaluation.actual_pipeline_dataset import build_development_dataset
from evaluation.human_qa import build_human_qa_package
from evaluation.mailex_local import build_local_mailex_candidate
from evaluation.mailex_reconciliation import build_mailex_reconciliation


def _source_zip(path: Path) -> None:
    prohibited = "medi" + "cal"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index in range(102):
            stem = f"thread{index:03d}"
            annotation = {
                "events": {
                    "turn_0": {"Request_Action": {"labels": [[0, 1]], "triggers": ["review"], "extras": [""]}},
                    "turn_1": {"Deliver_Action_Data": {"labels": [[0, 1]], "triggers": ["completed"], "extras": [""]}},
                },
                "sentences": [["Please", "review", stem], ["Completed", stem]],
            }
            archive.writestr(f"root/data/full_data/{stem}.json", json.dumps(annotation))
            archive.writestr(f"root/data/train/{stem}.json", json.dumps(annotation))
            body = prohibited if index == 0 else f"Please review synthetic item {index}."
            raw = (
                f"From: Worker {index} <worker{index}@example.test>\n"
                f"To: Reviewer <reviewer@example.test>\nSubject: Synthetic request {index}\n\n{body}\n"
                "-----------------------------\n"
                f"From: Reviewer <reviewer@example.test>\nTo: Worker {index} <worker{index}@example.test>\n"
                f"Subject: Synthetic request {index}\n\nCompleted synthetic item {index}."
            )
            archive.writestr(f"root/data/raw_threads/thread_{index:03d}", raw)


def test_actual_format_zip_builder_preserves_structure_and_pending_human_state(tmp_path: Path) -> None:
    source = tmp_path / "data.zip"
    _source_zip(source)
    output = tmp_path / "candidate"
    result = build_local_mailex_candidate(source, output, limit=100)
    manifest = result["manifest"]
    assert manifest["selected_thread_count"] == 100
    assert manifest["second_annotation_count"] == 20
    assert manifest["licence_status"] == "LICENCE_PENDING_HUMAN_CONFIRMATION"
    assert manifest["human_annotation_complete"] is False
    rows = [json.loads(line) for line in (output / "candidate_threads.jsonl").read_text().splitlines()]
    assert all([item["message_order"] for item in row["messages"]] == list(range(len(row["messages"]))) for row in rows)
    serialized = json.dumps(rows)
    assert "@example.test" not in serialized
    assert "@example.invalid" in serialized
    exclusions = json.loads((output / "no_health_exclusion_log.json").read_text())["excluded"]
    assert exclusions and all("raw" not in item for item in exclusions)
    preannotations = [json.loads(line) for line in (output / "action_closure_preannotations.jsonl").read_text().splitlines()]
    assert len(preannotations) == 100
    assert all(item["annotation_status"] == "MACHINE_SUGGESTION_NOT_GOLD" for item in preannotations)
    assignments = list(csv.DictReader((output / "annotation_assignments.csv").open(encoding="utf-8")))
    assert len(assignments) == 100
    assert sum(item["second_annotation_required"] == "True" for item in assignments) == 20


def test_human_qa_package_has_exact_pending_rows_and_no_fabricated_decisions(tmp_path: Path) -> None:
    dataset = tmp_path / "actual"
    build_development_dataset(dataset)
    gold_rows = [json.loads(line) for line in (dataset / "gold_annotations.jsonl").read_text().splitlines()]
    raw_paths = []
    for run_index in (1, 2):
        path = tmp_path / f"raw-{run_index}.jsonl"
        records = [
            {
                "mode": "C3_FULL_ROLE_AWARE",
                "case_id": item["case_id"],
                "actual_output_text": "Pending human audit fixture.",
                "actual_citations": [],
            }
            for item in gold_rows
        ]
        path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
        raw_paths.append(path)
    mail_dir = tmp_path / "mail"
    mail_dir.mkdir()
    (mail_dir / "candidate_manifest.json").write_text(
        json.dumps({
            "selected_thread_count": 120,
            "primary_annotation_count": 120,
            "second_annotation_count": 24,
            "licence_status": "LICENCE_PENDING_HUMAN_CONFIRMATION",
        }),
        encoding="utf-8",
    )
    result = build_human_qa_package(
        output_dir=tmp_path / "qa",
        actual_gold_path=dataset / "gold_annotations.jsonl",
        actual_raw_run_paths=raw_paths,
        mailex_candidate_dir=mail_dir,
    )
    assert result["owned_object_gold_rows"] == 90
    assert result["citation_audit_rows"] == 40
    assert result["agreement_calculated"] is False
    citation_rows = list(csv.DictReader((tmp_path / "qa/citation_audit_40.csv").open(encoding="utf-8")))
    assert all(item["review_status"] == "PENDING_HUMAN_AUDIT" for item in citation_rows)
    assert all(item["reviewer_id"] == "" and item["human_notes"] == "" for item in citation_rows)


def test_reconciliation_accounts_alias_duplicate_unmatched_and_macos_metadata(tmp_path: Path) -> None:
    source = tmp_path / "data.zip"
    _source_zip(source)
    with zipfile.ZipFile(source, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        alias_json = {
            "events": {},
            "sentences": [
                ["Please", "review", "synthetic", "item", "1"],
                ["Completed", "synthetic", "item", "1"],
            ],
        }
        archive.writestr("root/data/full_data/alias-record.json", json.dumps(alias_json))
        duplicate_raw = archive.read("root/data/raw_threads/thread_001")
        archive.writestr("root/data/raw_threads/content-alias", duplicate_raw)
        archive.writestr("root/data/raw_threads/content-alias-duplicate", duplicate_raw)
        archive.writestr(
            "root/data/raw_threads/unmatched-record",
            "From: Unmatched <unmatched@example.test>\nSubject: Separate fixture\n\nNo aligned JSON annotation exists.",
        )
        archive.writestr("root/data/.DS_Store", b"finder-metadata")
        archive.writestr("__MACOSX/root/data/._prompt_data.txt", b"apple-double")

    output = tmp_path / "reconciliation"
    summary = build_mailex_reconciliation(source, output)
    assert summary["status"] == "PASS"
    assert summary["alias_relationship_count"] >= 1
    assert summary["duplicate_raw_count"] >= 1
    assert summary["unmatched_raw_count"] == 1
    assert summary["unmatched_json_count"] == 0
    assert summary["unexplained_count"] == 0
    assert summary["logical_entry_count_after_all_macos_metadata"] == summary["non_directory_entry_count"] - 2
    for filename in (
        "source_entry_inventory.jsonl",
        "json_raw_match_table.csv",
        "unmatched_json_records.csv",
        "unmatched_raw_records.csv",
        "duplicate_or_alias_records.csv",
        "reconciliation_summary.json",
        "reconciliation_checksums.csv",
    ):
        assert (output / filename).is_file()
    serialized = "".join(path.read_text(encoding="utf-8") for path in output.iterdir())
    assert "No aligned JSON annotation exists" not in serialized
