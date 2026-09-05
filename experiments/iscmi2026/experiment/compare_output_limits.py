from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiment_core import CONDITIONS, read_json, read_jsonl, write_json


FROZEN_TOP_LEVEL_FIELDS = (
    "conditions",
    "generator_model",
    "embedding_model",
    "temperature",
    "prompt_sha256",
    "question_count",
    "full_benchmark_question_count",
    "expected_condition_question_pairs",
    "question_ids_sha256",
)
FROZEN_CONDITION_FIELDS = (
    "generator_model",
    "embedding_model",
    "temperature",
    "top_p",
    "seed",
    "retrieval_top_k",
    "chunking",
    "similarity_metric",
    "thread_scope",
    "question_count",
    "benchmark_manifest_hash",
    "task_representation_mode",
)


def result_map(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows = read_jsonl(path)
    mapped = {(row["question_id"], row["condition"]): row for row in rows}
    if len(mapped) != len(rows):
        raise ValueError(f"Duplicate question-condition pairs in {path}")
    return mapped


def strip_parser_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_parser_metadata(child)
            for key, child in value.items()
            if key != "_parser_recovery"
        }
    if isinstance(value, list):
        return [strip_parser_metadata(child) for child in value]
    return value


def canonical_parsed_answer(row: dict[str, Any]) -> str:
    return json.dumps(
        strip_parser_metadata(row.get("parsed_output")),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def validate_frozen_configuration(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    differences: list[dict[str, Any]] = []
    for field in FROZEN_TOP_LEVEL_FIELDS:
        if old.get(field) != new.get(field):
            differences.append({"scope": "run", "field": field, "old": old.get(field), "new": new.get(field)})
    old_packet_hash = (old.get("corrected_packet") or {}).get("aggregate_sha256")
    new_packet_hash = (new.get("corrected_packet") or {}).get("aggregate_sha256")
    if old_packet_hash != new_packet_hash:
        differences.append(
            {"scope": "run", "field": "corrected_packet.aggregate_sha256", "old": old_packet_hash, "new": new_packet_hash}
        )
    old_conditions = {row["condition"]: row for row in old["condition_manifests"]}
    new_conditions = {row["condition"]: row for row in new["condition_manifests"]}
    if set(old_conditions) != set(CONDITIONS) or set(new_conditions) != set(CONDITIONS):
        raise ValueError("Both manifests must contain exactly the three frozen conditions")
    for condition in CONDITIONS:
        for field in FROZEN_CONDITION_FIELDS:
            if old_conditions[condition].get(field) != new_conditions[condition].get(field):
                differences.append(
                    {
                        "scope": condition,
                        "field": field,
                        "old": old_conditions[condition].get(field),
                        "new": new_conditions[condition].get(field),
                    }
                )
    old_limits = {row["max_output_tokens"] for row in old_conditions.values()}
    new_limits = {row["max_output_tokens"] for row in new_conditions.values()}
    if old_limits != {800} or new_limits != {2000}:
        raise ValueError(f"Expected uniform 800 -> 2000 limits, found {old_limits} -> {new_limits}")
    if differences:
        raise ValueError("Frozen configuration mismatch: " + json.dumps(differences, ensure_ascii=False))
    return {
        "status": "PASS",
        "old_max_output_tokens": 800,
        "new_max_output_tokens": 2000,
        "intended_differences": ["max_output_tokens", "run identity/provenance", "observed usage/outputs"],
        "unexpected_scientific_parameter_differences": [],
    }


def is_old_truncated(row: dict[str, Any], inference: dict[str, Any]) -> bool:
    return bool(
        row.get("parser_recovery")
        or inference.get("output_status") == "truncated_by_output_limit"
        or (
            (inference.get("error") or {}).get("type") == "parser_error"
            and int(inference.get("output_tokens") or 0) == 800
        )
    )


def metric_transition(old: Any, new: Any) -> dict[str, float]:
    return {
        "old": float(old),
        "new": float(new),
        "difference_new_minus_old": round(float(new) - float(old), 8),
    }


def write_markdown(path: Path, comparison: dict[str, Any]) -> None:
    lines = [
        "# ISCMI 2026: max_output_tokens 800 vs 2000",
        "",
        "The rerun changes only the uniform output-token ceiling. API responses can vary even at temperature 0, so changes are not attributed to truncation unless the pair belonged to the 64-case truncated subset.",
        "",
        "## Frozen Configuration",
        "",
        f"Validation: **{comparison['frozen_configuration']['status']}**. Questions: {comparison['questions']}; conditions: 3; pairs: {comparison['pairs']}.",
        "",
        "## Overall Comparison",
        "",
        "| Condition | Exact 800 -> 2000 | Structured 800 -> 2000 | Controlled failure 800 -> 2000 | Evidence F1 800 -> 2000 | Truncated 800 -> 2000 | Tokens 800 -> 2000 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        row = comparison["by_condition"][condition]
        lines.append(
            f"| {condition} | {row['exact_accuracy']['old']:.4f} -> {row['exact_accuracy']['new']:.4f} | "
            f"{row['structured_score']['old']:.4f} -> {row['structured_score']['new']:.4f} | "
            f"{row['controlled_failure_accuracy']['old']:.4f} -> {row['controlled_failure_accuracy']['new']:.4f} | "
            f"{row['evidence_f1']['old']:.4f} -> {row['evidence_f1']['new']:.4f} | "
            f"{row['truncated_outputs']['old']} -> {row['truncated_outputs']['new']} | "
            f"{row['total_tokens']['old']} -> {row['total_tokens']['new']} |"
        )
    changes = comparison["all_pair_changes"]
    lines.extend(
        [
            "",
            "## Pair-Level Changes",
            "",
            f"Parsed answers changed: {changes['parsed_answer_changed']}/{comparison['pairs']}. Exact correctness changed: {changes['exact_correctness_changed']}. Improved: {changes['exact_improved']}; worsened: {changes['exact_worsened']}; unchanged: {changes['exact_unchanged']}.",
            "",
            f"Structured score improved: {changes['structured_improved']}; worsened: {changes['structured_worsened']}; unchanged: {changes['structured_unchanged']}.",
            "",
            "## Previously Truncated 64 Cases",
            "",
            f"Recovered subset size: {comparison['previously_truncated_summary']['cases']}. New complete outputs: {comparison['previously_truncated_summary']['new_complete']}. Exact improved: {comparison['previously_truncated_summary']['exact_improved']}; worsened: {comparison['previously_truncated_summary']['exact_worsened']}; unchanged: {comparison['previously_truncated_summary']['exact_unchanged']}.",
            "",
            "| Question | Condition | Family | Exact 800 -> 2000 | Structured 800 -> 2000 | New output complete |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for row in comparison["previously_truncated_cases"]:
        lines.append(
            f"| {row['question_id']} | {row['condition']} | {row['question_family']} | "
            f"{int(row['old_exact_correct'])} -> {int(row['new_exact_correct'])} | "
            f"{row['old_structured_score']:.4f} -> {row['new_structured_score']:.4f} | "
            f"{'YES' if row['new_output_complete'] else 'NO'} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion Stability",
            "",
            f"Main oracle-superiority conclusion retained: **{'YES' if comparison['main_conclusion_retained'] else 'NO'}**.",
            "",
            "This remains an oracle task-state representation experiment. No automatic task-state extraction claim is evaluated.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def append_report_summary(report_path: Path, comparison: dict[str, Any]) -> None:
    marker = "## Comparison With The 800-Token Run"
    text = report_path.read_text(encoding="utf-8")
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    lines = [
        "",
        marker,
        "",
        "| Condition | Exact 800 -> 2000 | Structured 800 -> 2000 | Truncated 800 -> 2000 | Total tokens 800 -> 2000 |",
        "|---|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        row = comparison["by_condition"][condition]
        lines.append(
            f"| {condition} | {row['exact_accuracy']['old']:.4f} -> {row['exact_accuracy']['new']:.4f} | "
            f"{row['structured_score']['old']:.4f} -> {row['structured_score']['new']:.4f} | "
            f"{row['truncated_outputs']['old']} -> {row['truncated_outputs']['new']} | "
            f"{row['total_tokens']['old']} -> {row['total_tokens']['new']} |"
        )
    changes = comparison["all_pair_changes"]
    lines.extend(
        [
            "",
            f"Parsed answers changed in {changes['parsed_answer_changed']} of 813 pairs. Exact correctness improved in {changes['exact_improved']}, worsened in {changes['exact_worsened']}, and was unchanged in {changes['exact_unchanged']}.",
            "",
            f"The 64 previously truncated cases produced {comparison['previously_truncated_summary']['new_complete']} complete new outputs. See `comparison_max800_vs_max2000.md` and `.json` for pair-level details.",
            "",
            f"Main oracle-superiority conclusion retained: **{'YES' if comparison['main_conclusion_retained'] else 'NO'}**.",
            "",
        ]
    )
    report_path.write_text(text.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")


def compare(args: argparse.Namespace) -> int:
    old_dir = Path(args.old_results_dir).resolve()
    new_dir = Path(args.new_results_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else new_dir
    old_manifest = read_json(old_dir / "run_manifest.json")
    new_manifest = read_json(new_dir / "run_manifest.json")
    frozen = validate_frozen_configuration(old_manifest, new_manifest)

    old_inference = result_map(old_dir / "inference_results.jsonl")
    new_inference = result_map(new_dir / "inference_results.jsonl")
    old_scored = result_map(old_dir / "per_question_results.jsonl")
    new_scored = result_map(new_dir / "per_question_results.jsonl")
    keys = set(old_inference)
    if keys != set(new_inference) or keys != set(old_scored) or keys != set(new_scored):
        raise ValueError("Old and new runs do not contain identical question-condition pairs")
    if len(keys) != 813:
        raise ValueError(f"Expected 813 pairs, found {len(keys)}")
    question_ids = {question_id for question_id, _condition in keys}
    if len(question_ids) != 271:
        raise ValueError(f"Expected 271 question IDs, found {len(question_ids)}")

    old_aggregate = read_json(old_dir / "aggregate_results.json")
    new_aggregate = read_json(new_dir / "aggregate_results.json")
    old_truncated_keys = {
        key for key in keys if is_old_truncated(old_scored[key], old_inference[key])
    }
    if len(old_truncated_keys) != 64:
        raise ValueError(f"Expected 64 previously truncated pairs, found {len(old_truncated_keys)}")
    new_truncated_keys = {
        key for key in keys if new_inference[key].get("output_status") == "truncated_by_output_limit"
    }

    by_condition: dict[str, Any] = {}
    all_changes = Counter()
    per_condition_changes: dict[str, Counter[str]] = {condition: Counter() for condition in CONDITIONS}
    for key in sorted(keys):
        condition = key[1]
        old_row = old_scored[key]
        new_row = new_scored[key]
        parsed_changed = canonical_parsed_answer(old_row) != canonical_parsed_answer(new_row)
        old_exact = bool(old_row["exact_correct"])
        new_exact = bool(new_row["exact_correct"])
        old_score = float(old_row["structured_score"])
        new_score = float(new_row["structured_score"])
        all_changes["parsed_answer_changed" if parsed_changed else "parsed_answer_unchanged"] += 1
        per_condition_changes[condition]["parsed_answer_changed" if parsed_changed else "parsed_answer_unchanged"] += 1
        if old_exact == new_exact:
            exact_label = "exact_unchanged"
        elif new_exact:
            exact_label = "exact_improved"
        else:
            exact_label = "exact_worsened"
        all_changes[exact_label] += 1
        per_condition_changes[condition][exact_label] += 1
        if new_score > old_score + 1e-12:
            structured_label = "structured_improved"
        elif new_score < old_score - 1e-12:
            structured_label = "structured_worsened"
        else:
            structured_label = "structured_unchanged"
        all_changes[structured_label] += 1
        per_condition_changes[condition][structured_label] += 1

    for condition in CONDITIONS:
        old_overall = old_aggregate["by_condition"][condition]["overall"]
        new_overall = new_aggregate["by_condition"][condition]["overall"]
        by_condition[condition] = {
            "exact_accuracy": metric_transition(old_overall["exact_accuracy"], new_overall["exact_accuracy"]),
            "structured_score": metric_transition(old_overall["mean_structured_score"], new_overall["mean_structured_score"]),
            "controlled_failure_accuracy": metric_transition(
                old_overall["controlled_failure_accuracy"], new_overall["controlled_failure_accuracy"]
            ),
            "evidence_f1": metric_transition(old_overall["evidence_f1"], new_overall["evidence_f1"]),
            "truncated_outputs": {
                "old": sum(1 for key in old_truncated_keys if key[1] == condition),
                "new": sum(1 for key in new_truncated_keys if key[1] == condition),
            },
            "total_tokens": {"old": old_overall["total_tokens"], "new": new_overall["total_tokens"]},
            "pair_changes": dict(sorted(per_condition_changes[condition].items())),
        }

    truncated_cases = []
    truncated_summary = Counter()
    for key in sorted(old_truncated_keys):
        old_row = old_scored[key]
        new_row = new_scored[key]
        old_exact = bool(old_row["exact_correct"])
        new_exact = bool(new_row["exact_correct"])
        if old_exact == new_exact:
            truncated_summary["exact_unchanged"] += 1
        elif new_exact:
            truncated_summary["exact_improved"] += 1
        else:
            truncated_summary["exact_worsened"] += 1
        new_complete = new_inference[key].get("output_status") == "complete"
        truncated_summary["new_complete" if new_complete else "new_not_complete"] += 1
        truncated_cases.append(
            {
                "question_id": key[0],
                "condition": key[1],
                "question_family": old_row["question_family"],
                "pilot_id": old_row["pilot_id"],
                "old_exact_correct": old_exact,
                "new_exact_correct": new_exact,
                "old_structured_score": float(old_row["structured_score"]),
                "new_structured_score": float(new_row["structured_score"]),
                "new_output_status": new_inference[key].get("output_status"),
                "new_output_complete": new_complete,
            }
        )

    exact_changed = all_changes["exact_improved"] + all_changes["exact_worsened"]
    all_change_summary = dict(sorted(all_changes.items()))
    for key in (
        "parsed_answer_changed",
        "parsed_answer_unchanged",
        "exact_improved",
        "exact_worsened",
        "exact_unchanged",
        "structured_improved",
        "structured_worsened",
        "structured_unchanged",
    ):
        all_change_summary.setdefault(key, 0)
    all_change_summary["exact_correctness_changed"] = exact_changed
    truncated_change_summary = dict(sorted(truncated_summary.items()))
    for key in ("new_complete", "new_not_complete", "exact_improved", "exact_worsened", "exact_unchanged"):
        truncated_change_summary.setdefault(key, 0)
    old_primary = old_aggregate["by_condition"]
    new_primary = new_aggregate["by_condition"]
    old_oracle_wins = all(
        old_primary["ORACLE_TASK_STATE_RAG"]["primary"][metric]
        > max(old_primary[baseline]["primary"][metric] for baseline in CONDITIONS[:2])
        for metric in ("exact_accuracy", "mean_structured_score")
    )
    new_oracle_wins = all(
        new_primary["ORACLE_TASK_STATE_RAG"]["primary"][metric]
        > max(new_primary[baseline]["primary"][metric] for baseline in CONDITIONS[:2])
        for metric in ("exact_accuracy", "mean_structured_score")
    )
    comparison = {
        "schema_version": "1.0",
        "old_run_id": old_manifest["run_id"],
        "new_run_id": new_manifest["run_id"],
        "questions": 271,
        "pairs": 813,
        "frozen_configuration": frozen,
        "by_condition": by_condition,
        "all_pair_changes": all_change_summary,
        "previously_truncated_summary": {
            "cases": len(truncated_cases),
            **truncated_change_summary,
        },
        "previously_truncated_cases": truncated_cases,
        "new_output_status_counts": new_aggregate.get("output_status_counts", {}),
        "old_oracle_superiority_conclusion": old_oracle_wins,
        "new_oracle_superiority_conclusion": new_oracle_wins,
        "main_conclusion_retained": old_oracle_wins and new_oracle_wins,
        "caution": "Temperature 0 does not guarantee bit-identical API output; not all changes are attributable to truncation.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "comparison_max800_vs_max2000.json", comparison)
    write_markdown(output_dir / "comparison_max800_vs_max2000.md", comparison)
    append_report_summary(new_dir / "experiment_report.md", comparison)
    print(
        f"Compared {len(keys)} pairs; parsed changed={all_changes['parsed_answer_changed']}; "
        f"exact improved={all_changes['exact_improved']}, worsened={all_changes['exact_worsened']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare frozen ISCMI runs at output limits 800 and 2000.")
    parser.add_argument("--old-results-dir", required=True)
    parser.add_argument("--new-results-dir", required=True)
    parser.add_argument("--output-dir")
    return parser


if __name__ == "__main__":
    raise SystemExit(compare(build_parser().parse_args()))
