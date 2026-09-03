from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPO_ROOT
    / "artifacts"
    / "s1_s6_publication_experiment"
    / "scripts"
    / "run_s1_s6_publication_experiment.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location("s1_s6_publication_experiment_v2", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publication_v2_run_plan_includes_p1_between_c1_and_c2() -> None:
    module = _load_script_module()

    assert [module.MODE_SHORT[mode] for mode in module.MODES] == ["C0", "C1", "P1", "C2", "C3"]
    assert module.EXPECTED_DETERMINISTIC_RECORDS == 210
    assert module.EXPECTED_OPENAI_RECORDS == 630


def test_af_always_full_label_only_baseline_sanity_metrics() -> None:
    module = _load_script_module()
    rows = []
    for output_class, count in module.EXPECTED_OUTPUT_CLASS_DISTRIBUTION.items():
        rows.extend(
            {
                "expected_output_class": output_class,
                "actual_output_class": "FULL_ANSWER",
                "output_class_correct": int(output_class == "FULL_ANSWER"),
            }
            for _ in range(count)
        )

    summary = module.label_balance_summary(rows)
    accuracy = module.ratio(sum(row["output_class_correct"] for row in rows), len(rows))

    assert accuracy == 0.690476
    assert summary["balanced_accuracy"] == 0.166667
    assert summary["macro_recall"] == 0.166667
    assert summary["per_class_recall"]["FULL_ANSWER"] == 1.0
    assert summary["per_class_recall"]["AGGREGATE_RESULT"] == 0.0
    assert len(summary["output_class_confusion_matrix"]) == 36


def test_publication_v2_configuration_summary_classifies_p1_as_prompt_only() -> None:
    module = _load_script_module()
    rows = {item["Configuration"]: item for item in module.configuration_semantics()}
    p1 = rows["P1_PROMPT_ONLY_GOVERNANCE"]

    assert "policy labels" in p1["Permission filtering"]
    assert "no governed aggregate executor" in p1["Aggregate handling"]
    assert "provider response" in p1["Controlled-failure logic"]


def test_prompt_manifest_matches_runtime_prompt_hash() -> None:
    module = _load_script_module()
    manifest = module.load_json(module.PROTOCOL_DIR / "prompt_only_governance_prompt.json")

    assert manifest["version"] == "prompt-only-governance-v1"
    assert manifest["sha256"] == module.sha256_text(module.prompt_only_governance_prompt())
    prompt = module.prompt_only_governance_prompt()
    for forbidden in ("expected_output_class", "reference_answer", "gold_document_ids", "S1-Q", "S6-Q"):
        assert forbidden not in prompt
