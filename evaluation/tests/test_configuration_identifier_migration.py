from __future__ import annotations

import csv
import json
from pathlib import Path

from evaluation.d_gate import run_c0_c3
from evaluation.provider_readiness import E1_MODES
from evaluation.schemas import EvaluationMode, RunRecord


REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_ARTIFACT = REPO_ROOT / "artifacts" / "configuration_identifier_migration_b_to_c.json"
VALIDATION_ARTIFACT = REPO_ROOT / "artifacts" / "configuration_identifier_migration_b_to_c_validation.json"
CANONICAL_MODES = (
    "C0_VECTOR_ONLY",
    "C1_VECTOR_ROUTING",
    "C2_PERMISSION_FILTERED",
    "C3_FULL_ROLE_AWARE",
)
MAPPING = {
    "B0_VECTOR_ONLY": "C0_VECTOR_ONLY",
    "B1_VECTOR_ROUTING": "C1_VECTOR_ROUTING",
    "B2_PERMISSION_FILTERED": "C2_PERMISSION_FILTERED",
    "B3_FULL_ROLE_AWARE": "C3_FULL_ROLE_AWARE",
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_c0_c3_enum_parsing_and_serialization() -> None:
    assert tuple(mode.value for mode in EvaluationMode) == CANONICAL_MODES
    assert [EvaluationMode(value).value for value in CANONICAL_MODES] == list(CANONICAL_MODES)

    record = RunRecord(
        run_id="migration-regression",
        case_id="case-1",
        mode=EvaluationMode.C3_FULL_ROLE_AWARE,
        retrieved_ids=["doc-1"],
        generator_visible_context_hash="sha256:" + "a" * 64,
        output_class="FULL_ANSWER",
        reason_code="supported",
        latency_ms=1.0,
    )

    serialized = record.to_dict()
    assert serialized["mode"] == "C3_FULL_ROLE_AWARE"
    assert "B3_FULL_ROLE_AWARE" not in json.dumps(serialized, sort_keys=True)


def test_cli_and_provider_estimate_modes_are_c0_c3_only() -> None:
    assert E1_MODES == CANONICAL_MODES
    runner = (REPO_ROOT / "scripts" / "run_real_provider_evaluation.py").read_text(encoding="utf-8")
    actual_pipeline = (REPO_ROOT / "scripts" / "run_actual_pipeline_evaluation.py").read_text(encoding="utf-8")
    assert "choices=E1_MODES" in runner
    assert 'modes=["C3_FULL_ROLE_AWARE"]' in runner
    assert all(mode in actual_pipeline for mode in CANONICAL_MODES)
    assert "B0_VECTOR_ONLY" not in runner + actual_pipeline


def test_new_d_gate_runs_emit_no_canonical_b_modes_and_report_c_rows(tmp_path: Path) -> None:
    result = run_c0_c3(tmp_path / "c0_c3")
    modes = {record["mode"] for record in result["records"]}
    assert modes == set(CANONICAL_MODES)
    assert not any(mode.startswith("B") for mode in modes)

    rows = list(csv.DictReader((tmp_path / "c0_c3" / "summary.csv").open(encoding="utf-8")))
    assert [row["mode"] for row in rows] == list(CANONICAL_MODES)
    summary_md = (tmp_path / "c0_c3" / "summary.md").read_text(encoding="utf-8")
    assert "D-GATE C0-C3 development table" in summary_md
    assert "B0" not in summary_md and "B3" not in summary_md


def test_artifact_directory_naming_uses_c0_c3() -> None:
    deterministic = REPO_ROOT / "artifacts" / "s1s2_publication_ablation_deterministic"
    openai = REPO_ROOT / "artifacts" / "s1s2_publication_ablation_openai"

    assert {path.name for path in deterministic.iterdir() if path.name in {"C0", "C1", "C2", "C3"}} == {"C0", "C1", "C2", "C3"}
    assert not any((deterministic / old).exists() for old in ("B0", "B1", "B2", "B3"))
    for repeat in ("R1", "R2", "R3"):
        repeat_dir = openai / repeat
        assert {path.name for path in repeat_dir.iterdir() if path.name in {"C0", "C1", "C2", "C3"}} == {"C0", "C1", "C2", "C3"}
        assert not any((repeat_dir / old).exists() for old in ("B0", "B1", "B2", "B3"))

    assert (deterministic / "c0_c3_summary.json").is_file()
    assert (openai / "c0_c3_real_provider_summary.json").is_file()
    assert (openai / "openai_c0_c3_runner.py").is_file()


def test_migration_mapping_is_one_to_one() -> None:
    assert len(MAPPING) == len(set(MAPPING)) == 4
    assert MAPPING == {
        "B0_VECTOR_ONLY": "C0_VECTOR_ONLY",
        "B1_VECTOR_ROUTING": "C1_VECTOR_ROUTING",
        "B2_PERMISSION_FILTERED": "C2_PERMISSION_FILTERED",
        "B3_FULL_ROLE_AWARE": "C3_FULL_ROLE_AWARE",
    }


def test_migration_validation_preserves_numeric_values_case_counts_and_provider_calls() -> None:
    validation = _json(VALIDATION_ARTIFACT)
    migration = _json(MIGRATION_ARTIFACT)

    assert validation["status"] == "PASS"
    assert validation["SEMANTIC_DIFFERENCE_COUNT"] == 0
    assert validation["NUMERICAL_DIFFERENCE_COUNT"] == 0
    assert validation["MISSING_RECORD_COUNT"] == 0
    assert validation["EXTRA_RECORD_COUNT"] == 0
    assert validation["openai_provider_calls_performed"] == 0
    assert validation["real_provider"]["total_measured_records"] == 144
    assert validation["real_provider"]["repetitions"] == 3
    assert validation["real_provider"]["configurations"] == 4
    assert validation["real_provider"]["cases_per_configuration_per_repetition"] == 12
    assert migration["provider_calls_performed"] == 0
    assert migration["numeric_result_equality_verified"] is True
    assert migration["evaluation_semantics_unchanged"] is True
