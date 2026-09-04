import json
from hashlib import sha256
from pathlib import Path

import pytest

from evaluation.actual_pipeline_gold import GoldAnnotation
from evaluation.actual_pipeline_scorer import score_repetition_aware_sealed_run, score_sealed_run


DATASET_VERSION = "actual-pipeline-development-v1"
MODES = [
    "C0_VECTOR_ONLY",
    "C1_VECTOR_ROUTING",
    "P1_PROMPT_ONLY_GOVERNANCE",
    "C2_PERMISSION_FILTERED",
    "C3_FULL_ROLE_AWARE",
]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _gold_rows(count: int = 42) -> list[dict]:
    return [
        GoldAnnotation(
            case_id=f"S1-Q{index:02d}",
            expected_output_class="FULL_ANSWER",
            reason_code="supported",
            gold_document_ids=(),
            gold_page_or_message_ranges={},
            reference_answer=f"answer {index}",
            factual_atoms=(),
            required_evidence_roles=(),
            action_status="allowed",
            dataset_version=DATASET_VERSION,
        ).to_dict()
        for index in range(1, count + 1)
    ]


def _record(case_id: str, mode: str, repetition: int) -> dict:
    return {
        "schema_version": "actual-pipeline-raw-record-v1",
        "dataset_version": DATASET_VERSION,
        "case_id": case_id,
        "mode": mode,
        "repetition_index": repetition,
        "actual_output_class": "FULL_ANSWER",
        "actual_reason_code": "supported",
        "actual_output_text": "answer text",
        "actual_citations": [],
        "error": None,
    }


def _records(*, modes: list[str], repetitions: int, case_count: int = 42) -> list[dict]:
    return [
        _record(f"S1-Q{index:02d}", mode, repetition)
        for mode in modes
        for repetition in range(1, repetitions + 1)
        for index in range(1, case_count + 1)
    ]


def _write_fixture(
    tmp_path: Path,
    *,
    records: list[dict],
    modes: list[str],
    repetitions: int,
    case_count: int = 42,
) -> tuple[Path, Path, Path]:
    raw = tmp_path / "raw_records.jsonl"
    gold = tmp_path / "gold.jsonl"
    seal = tmp_path / "run_seal.json"
    _write_jsonl(raw, records)
    _write_jsonl(gold, _gold_rows(case_count))
    seal.write_text(
        json.dumps(
            {
                "scoring_started": False,
                "raw_run_sha256": sha256(raw.read_bytes()).hexdigest(),
                "deterministic_content_sha256": "0" * 64,
                "run_id": "test-run",
                "dataset_version": DATASET_VERSION,
                "modes": modes,
                "repetitions": repetitions,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return raw, seal, gold


def test_legacy_scorer_accepts_single_mode_single_repetition(tmp_path: Path) -> None:
    raw, seal, gold = _write_fixture(
        tmp_path,
        records=_records(modes=["C0_VECTOR_ONLY"], repetitions=1),
        modes=["C0_VECTOR_ONLY"],
        repetitions=1,
    )

    result = score_sealed_run(raw_run_path=raw, seal_path=seal, gold_annotation_path=gold, output_dir=tmp_path / "scores")

    assert result["modes"]["C0_VECTOR_ONLY"]["case_count"] == 42
    assert result["modes"]["C0_VECTOR_ONLY"]["output_class_accuracy"] == 1.0


def test_legacy_scorer_rejects_duplicate_case_ids_from_repetitions(tmp_path: Path) -> None:
    raw, seal, gold = _write_fixture(
        tmp_path,
        records=_records(modes=["C0_VECTOR_ONLY"], repetitions=3),
        modes=["C0_VECTOR_ONLY"],
        repetitions=3,
    )

    with pytest.raises(ValueError, match="Missing or duplicate raw case IDs"):
        score_sealed_run(raw_run_path=raw, seal_path=seal, gold_annotation_path=gold, output_dir=tmp_path / "scores")


def test_repetition_aware_scorer_partitions_all_modes_and_repetitions(tmp_path: Path) -> None:
    raw, seal, gold = _write_fixture(
        tmp_path,
        records=_records(modes=MODES, repetitions=3),
        modes=MODES,
        repetitions=3,
    )

    result = score_repetition_aware_sealed_run(
        raw_run_path=raw,
        seal_path=seal,
        gold_annotation_path=gold,
        output_dir=tmp_path / "scores",
    )

    assert result["scoring_strategy"] == "repetition_aware_mode_repetition_partitioned_v1"
    assert result["group_count"] == 15
    assert {row["case_count"] for row in result["mode_repetition_groups"]} == {42}
    assert all(summary["case_count"] == 126 for summary in result["modes"].values())
    assert all(summary["output_class_accuracy"] == 1.0 for summary in result["modes"].values())
    assert (tmp_path / "scores" / "case_scores.jsonl").read_text(encoding="utf-8").count("\n") == 630
    assert (tmp_path / "scores" / "mode_repetition_summary.csv").read_text(encoding="utf-8").count("\n") == 16


def test_repetition_aware_scorer_rejects_missing_group_member(tmp_path: Path) -> None:
    records = _records(modes=["C0_VECTOR_ONLY"], repetitions=2)
    records = [record for record in records if not (record["repetition_index"] == 2 and record["case_id"] == "S1-Q42")]
    raw, seal, gold = _write_fixture(
        tmp_path,
        records=records,
        modes=["C0_VECTOR_ONLY"],
        repetitions=2,
    )

    with pytest.raises(ValueError, match="Expected 42 raw records for C0_VECTOR_ONLY repetition 2; got 41"):
        score_repetition_aware_sealed_run(
            raw_run_path=raw,
            seal_path=seal,
            gold_annotation_path=gold,
            output_dir=tmp_path / "scores",
        )


def test_repetition_aware_scorer_rejects_duplicate_composite_key(tmp_path: Path) -> None:
    records = _records(modes=["C0_VECTOR_ONLY"], repetitions=2)
    records.append(dict(records[0]))
    raw, seal, gold = _write_fixture(
        tmp_path,
        records=records,
        modes=["C0_VECTOR_ONLY"],
        repetitions=2,
    )

    with pytest.raises(ValueError, match="Duplicate raw composite case/mode/repetition keys"):
        score_repetition_aware_sealed_run(
            raw_run_path=raw,
            seal_path=seal,
            gold_annotation_path=gold,
            output_dir=tmp_path / "scores",
        )
