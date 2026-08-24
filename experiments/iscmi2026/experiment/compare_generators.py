from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from experiment_core import CONDITIONS, read_json, read_jsonl, write_json


OLD_CONFIGURED_GENERATORS = {"gpt-4o-mini", "gpt-4o-mini-2024-07-18"}
OLD_OBSERVED_GENERATOR = "gpt-4o-mini-2024-07-18"
NEW_GENERATOR = "gpt-4.1-2025-04-14"
PRIMARY_FAMILIES = (
    "OPEN_TASKS",
    "CLOSED_TASKS",
    "ACTOR_RESPONSIBILITY",
    "REQUESTER",
    "TASK_HISTORY",
)
FROZEN_TOP_LEVEL_FIELDS = (
    "conditions",
    "embedding_model",
    "temperature",
    "max_output_tokens",
    "prompt_sha256",
    "question_count",
    "full_benchmark_question_count",
    "expected_condition_question_pairs",
    "question_ids_sha256",
)
FROZEN_CONDITION_FIELDS = (
    "embedding_model",
    "temperature",
    "max_output_tokens",
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
GENERATOR_PRICES_PER_MILLION = {
    OLD_OBSERVED_GENERATOR: {"input": 0.15, "output": 0.60},
    NEW_GENERATOR: {"input": 2.00, "output": 8.00},
}
EMBEDDING_PRICE_PER_MILLION = 0.02
PRICE_ACCESS_DATE = "2026-08-24"


def result_map(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows = read_jsonl(path)
    mapped = {(row["question_id"], row["condition"]): row for row in rows}
    if len(mapped) != len(rows):
        raise ValueError(f"Duplicate question-condition pairs in {path}")
    return mapped


def ordered_question_ids(rows: Iterable[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ordered = []
    for row in rows:
        question_id = row["question_id"]
        if question_id not in seen:
            seen.add(question_id)
            ordered.append(question_id)
    return ordered


def nearest_rank_percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return round(float(ordered[index]), 8)


def average(rows: list[dict[str, Any]], getter: Any) -> float:
    return round(mean(float(getter(row)) for row in rows), 8) if rows else 0.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(row.get("latency_seconds") or 0.0) for row in rows]
    input_tokens = sum(int(row.get("input_tokens") or 0) for row in rows)
    output_tokens = sum(int(row.get("output_tokens") or 0) for row in rows)
    total_tokens = sum(int(row.get("total_tokens") or 0) for row in rows)
    return {
        "questions": len(rows),
        "exact_accuracy": average(rows, lambda row: bool(row["exact_correct"])),
        "mean_structured_score": average(rows, lambda row: row["structured_score"]),
        "controlled_failure_accuracy": average(
            rows, lambda row: bool(row["controlled_failure_correct"])
        ),
        "evidence_precision": average(rows, lambda row: row["evidence_grounding"]["precision"]),
        "evidence_recall": average(rows, lambda row: row["evidence_grounding"]["recall"]),
        "evidence_f1": average(rows, lambda row: row["evidence_grounding"]["f1"]),
        "api_calls": sum(int(row.get("api_calls") or 0) for row in rows),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "tokens_per_question": round(total_tokens / len(rows), 4) if rows else 0.0,
        "mean_latency_seconds": round(mean(latencies), 8) if latencies else 0.0,
        "median_latency_seconds": round(median(latencies), 8) if latencies else 0.0,
        "p95_latency_seconds": nearest_rank_percentile(latencies, 0.95),
        "output_status_counts": dict(
            sorted(Counter(row.get("output_status") or "legacy_unspecified" for row in rows).items())
        ),
        "parser_recoveries": sum(1 for row in rows if row.get("parser_recovery")),
        "unrecoverable_responses": sum(1 for row in rows if row.get("error")),
    }


def rows_for(
    rows: list[dict[str, Any]],
    condition: str,
    *,
    families: set[str] | None = None,
    family: str | None = None,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row["condition"] == condition
        and (families is None or row["question_family"] in families)
        and (family is None or row["question_family"] == family)
    ]


def validate_frozen_configuration(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    differences: list[dict[str, Any]] = []
    for field in FROZEN_TOP_LEVEL_FIELDS:
        if old.get(field) != new.get(field):
            differences.append({"scope": "run", "field": field, "old": old.get(field), "new": new.get(field)})
    old_packet_hash = (old.get("corrected_packet") or {}).get("aggregate_sha256")
    new_packet_hash = (new.get("corrected_packet") or {}).get("aggregate_sha256")
    if old_packet_hash != new_packet_hash:
        differences.append(
            {
                "scope": "run",
                "field": "corrected_packet.aggregate_sha256",
                "old": old_packet_hash,
                "new": new_packet_hash,
            }
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
        if old_conditions[condition].get("generator_model") not in OLD_CONFIGURED_GENERATORS:
            raise ValueError(f"Unexpected old generator for {condition}")
        if new_conditions[condition].get("generator_model") != NEW_GENERATOR:
            raise ValueError(f"Unexpected new generator for {condition}")
    if old.get("generator_model") not in OLD_CONFIGURED_GENERATORS:
        raise ValueError(f"Unexpected old run generator: {old.get('generator_model')}")
    if new.get("generator_model") != NEW_GENERATOR:
        raise ValueError(f"Unexpected new run generator: {new.get('generator_model')}")
    if set(old.get("observed_generator_models") or []) != {OLD_OBSERVED_GENERATOR}:
        raise ValueError("Old run did not uniformly observe the pinned GPT-4o-mini snapshot")
    if set(new.get("observed_generator_models") or []) != {NEW_GENERATOR}:
        raise ValueError("New run did not uniformly observe the pinned GPT-4.1 snapshot")
    if differences:
        raise ValueError("Frozen configuration mismatch: " + json.dumps(differences, ensure_ascii=False))
    return {
        "status": "PASS",
        "intended_difference": {
            "field": "generator_model",
            "old": OLD_OBSERVED_GENERATOR,
            "new": NEW_GENERATOR,
        },
        "unexpected_scientific_parameter_differences": [],
    }


def cost_summary(rows: list[dict[str, Any]], manifest: dict[str, Any], model: str) -> dict[str, Any]:
    prices = GENERATOR_PRICES_PER_MILLION[model]
    input_tokens = sum(int(row.get("input_tokens") or 0) for row in rows)
    output_tokens = sum(int(row.get("output_tokens") or 0) for row in rows)
    embedding_tokens = int((manifest.get("embedding_usage") or {}).get("input_tokens") or 0)
    input_cost = input_tokens / 1_000_000 * prices["input"]
    output_cost = output_tokens / 1_000_000 * prices["output"]
    embedding_cost = embedding_tokens / 1_000_000 * EMBEDDING_PRICE_PER_MILLION
    return {
        "generator_input_tokens": input_tokens,
        "generator_output_tokens": output_tokens,
        "shared_embedding_input_tokens": embedding_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "embedding_cost_usd": round(embedding_cost, 6),
        "total_estimated_cost_usd": round(input_cost + output_cost + embedding_cost, 6),
        "prices_per_million_tokens": {
            "generator_input": prices["input"],
            "generator_output": prices["output"],
            "embedding_input": EMBEDDING_PRICE_PER_MILLION,
        },
        "price_access_date": PRICE_ACCESS_DATE,
    }


def read_pairwise(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected = []
    for row in rows:
        if row["scope"] not in {"PRIMARY_OVERALL", "TASK_HISTORY"}:
            continue
        converted: dict[str, Any] = dict(row)
        for key in (
            "questions",
            "left_wins",
            "right_wins",
            "ties",
            "wilcoxon_n_nonzero",
        ):
            converted[key] = int(row[key])
        for key in (
            "left_exact_accuracy",
            "right_exact_accuracy",
            "absolute_exact_difference_left_minus_right",
            "left_structured_score",
            "right_structured_score",
            "absolute_structured_difference_left_minus_right",
            "mcnemar_p_value",
            "wilcoxon_p_value",
            "rank_biserial_effect_left_minus_right",
            "mcnemar_holm_p_value",
            "wilcoxon_holm_p_value",
        ):
            converted[key] = None if row[key] in {"", "None"} else float(row[key])
        selected.append(converted)
    return selected


def classify_pattern(old_uplift: float, new_uplift: float, condition_gains: list[float]) -> str:
    if new_uplift <= 0.05:
        return "D"
    if old_uplift - new_uplift >= 0.10 and new_uplift <= max(0.10, old_uplift * 0.5):
        return "B"
    if min(condition_gains) >= 0.05 and new_uplift >= 0.20:
        return "C"
    return "A"


def metric_pair(value: dict[str, Any]) -> str:
    return f"{value['exact_accuracy']:.4f}/{value['mean_structured_score']:.4f}"


def write_markdown(path: Path, comparison: dict[str, Any]) -> None:
    old_model = OLD_OBSERVED_GENERATOR
    new_model = NEW_GENERATOR
    lines = [
        "# ISCMI 2026: GPT-4o-mini vs GPT-4.1",
        "",
        "## Frozen Protocol",
        "",
        f"Validation: **{comparison['frozen_protocol']['status']}**. The fixed 271-question benchmark, ordered question IDs, three conditions, corrected packet, prompts, embeddings, retrieval, oracle records, parser, scoring, temperature 0.0, and 2000-token output limit match. Only the generator changes.",
        "",
        "## Generator Difference",
        "",
        f"`{old_model}` -> `{new_model}`. Both runs use Chat Completions JSON mode. GPT-4.1 is a pinned non-reasoning snapshot, so no prompt, API, parser, or parameter adaptation was required.",
        "",
        "## Primary Results",
        "",
        "| Generator | Condition | Exact | Structured | Controlled failure | Evidence F1 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for model in (old_model, new_model):
        for condition in CONDITIONS:
            primary = comparison["results"][model][condition]["primary"]
            lines.append(
                f"| {model} | {condition} | {primary['exact_accuracy']:.4f} | "
                f"{primary['mean_structured_score']:.4f} | {primary['controlled_failure_accuracy']:.4f} | "
                f"{primary['evidence_f1']:.4f} |"
            )
    lines.extend(
        [
            "",
            "## Task-State Uplift",
            "",
            "Primary structured uplift is ORACLE_TASK_STATE_RAG minus the selected email-only baseline.",
            "",
            "| Generator | Oracle - Thread-aware | Oracle - Standard |",
            "|---|---:|---:|",
        ]
    )
    for model in (old_model, new_model):
        uplift = comparison["task_state_uplift"][model]["primary_structured"]
        lines.append(
            f"| {model} | {uplift['oracle_minus_thread_aware']:.4f} | "
            f"{uplift['oracle_minus_standard']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Family-Level Results",
            "",
            "Values are exact/structured.",
            "",
            "| Family | GPT-4o-mini Standard | GPT-4o-mini Thread | GPT-4o-mini Oracle | GPT-4.1 Standard | GPT-4.1 Thread | GPT-4.1 Oracle |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for family in PRIMARY_FAMILIES:
        old = comparison["family_results"][old_model]
        new = comparison["family_results"][new_model]
        lines.append(
            f"| {family} | {metric_pair(old['STANDARD_RAG'][family])} | "
            f"{metric_pair(old['THREAD_AWARE_RAG'][family])} | "
            f"{metric_pair(old['ORACLE_TASK_STATE_RAG'][family])} | "
            f"{metric_pair(new['STANDARD_RAG'][family])} | "
            f"{metric_pair(new['THREAD_AWARE_RAG'][family])} | "
            f"{metric_pair(new['ORACLE_TASK_STATE_RAG'][family])} |"
        )
    lines.extend(
        [
            "",
            "## HISTORY Analysis",
            "",
            "| Generator | Condition | Exact sequence | Ordered structured | Evidence F1 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for model in (old_model, new_model):
        for condition in CONDITIONS:
            row = comparison["history_results"][model][condition]
            lines.append(
                f"| {model} | {condition} | {row['exact_accuracy']:.4f} | "
                f"{row['mean_structured_score']:.4f} | {row['evidence_f1']:.4f} |"
            )
    lines.extend(
        [
            "",
            "## NO_TASK_CONTROL Analysis",
            "",
            "| Generator | Condition | Exact | Structured | Controlled failure | Evidence F1 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for model in (old_model, new_model):
        for condition in CONDITIONS:
            row = comparison["no_task_control_results"][model][condition]
            lines.append(
                f"| {model} | {condition} | {row['exact_accuracy']:.4f} | "
                f"{row['mean_structured_score']:.4f} | {row['controlled_failure_accuracy']:.4f} | "
                f"{row['evidence_f1']:.4f} |"
            )
    lines.extend(
        [
            "",
            "## Evidence Grounding",
            "",
            "The overall evidence precision, recall, and F1 values are reported independently from answer correctness in the model-condition table below.",
            "",
            "## Token, Latency, And Cost Comparison",
            "",
            "| Generator | Condition | Overall exact | Overall structured | Controlled failure | Evidence F1 | Tokens/question | Mean latency | Median | P95 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for model in (old_model, new_model):
        for condition in CONDITIONS:
            row = comparison["results"][model][condition]["overall"]
            lines.append(
                f"| {model} | {condition} | {row['exact_accuracy']:.4f} | "
                f"{row['mean_structured_score']:.4f} | {row['controlled_failure_accuracy']:.4f} | "
                f"{row['evidence_f1']:.4f} | {row['tokens_per_question']:.2f} | "
                f"{row['mean_latency_seconds']:.3f} | {row['median_latency_seconds']:.3f} | "
                f"{row['p95_latency_seconds']:.3f} |"
            )
    lines.extend(
        [
            "",
            f"Estimated actual run costs use official prices accessed {PRICE_ACCESS_DATE} and include the shared embedding pass: GPT-4o-mini `${comparison['costs'][old_model]['total_estimated_cost_usd']:.4f}`; GPT-4.1 `${comparison['costs'][new_model]['total_estimated_cost_usd']:.4f}`.",
            "",
            "## Statistical Interpretation",
            "",
            "The GPT-4.1 run uses the same paired McNemar and Wilcoxon signed-rank tests with Holm correction as the GPT-4o-mini run. Full rows remain in `pairwise_comparisons.csv`; the selected primary and HISTORY rows are also preserved in the comparison JSON.",
            "",
            "## Limitations",
            "",
            "Temperature 0 does not guarantee bit-identical service output. Model tokenization, response length, and latency differ. The oracle records are human-derived and do not measure automatic task-state extraction. NO_TASK_CONTROL remains a separate test of task-existence gating.",
            "",
            "## Model-Robustness Conclusion",
            "",
            f"Pattern: **{comparison['pattern']['label']}**. {comparison['pattern']['interpretation']}",
            "",
            f"Explicit Oracle Task-State representation still provides a substantial advantage with GPT-4.1: **{'YES' if comparison['oracle_advantage_substantial'] else 'NO'}**.",
            "",
            "This is a generator-model robustness experiment using the same fixed benchmark and oracle task representation as the GPT-4o-mini run. No automatic task-state extraction claim is evaluated.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def append_report_summary(report_path: Path, comparison: dict[str, Any]) -> None:
    marker = "## Generator Robustness Comparison"
    text = report_path.read_text(encoding="utf-8")
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    old_uplift = comparison["task_state_uplift"][OLD_OBSERVED_GENERATOR]["primary_structured"]
    new_uplift = comparison["task_state_uplift"][NEW_GENERATOR]["primary_structured"]
    lines = [
        "",
        marker,
        "",
        f"Primary structured Oracle-minus-Thread uplift: GPT-4o-mini {old_uplift['oracle_minus_thread_aware']:.4f}; GPT-4.1 {new_uplift['oracle_minus_thread_aware']:.4f}.",
        "",
        f"Robustness pattern: **{comparison['pattern']['label']}**. Explicit Oracle Task-State advantage remains substantial: **{'YES' if comparison['oracle_advantage_substantial'] else 'NO'}**.",
        "",
        "See `comparison_gpt4omini_vs_gpt41.md` and `.json` for the complete cross-model analysis.",
        "",
    ]
    report_path.write_text(text.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")


def compare(args: argparse.Namespace) -> int:
    old_dir = Path(args.old_results_dir).resolve()
    new_dir = Path(args.new_results_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else new_dir
    old_manifest = read_json(old_dir / "run_manifest.json")
    new_manifest = read_json(new_dir / "run_manifest.json")
    frozen = validate_frozen_configuration(old_manifest, new_manifest)

    old_rows = read_jsonl(old_dir / "per_question_results.jsonl")
    new_rows = read_jsonl(new_dir / "per_question_results.jsonl")
    old_map = result_map(old_dir / "per_question_results.jsonl")
    new_map = result_map(new_dir / "per_question_results.jsonl")
    if set(old_map) != set(new_map) or len(old_map) != 813:
        raise ValueError("Runs must contain the same 813 question-condition pairs")
    if ordered_question_ids(old_rows) != ordered_question_ids(new_rows):
        raise ValueError("Ordered question IDs differ between generator runs")
    if len(ordered_question_ids(new_rows)) != 271:
        raise ValueError("Expected exactly 271 ordered question IDs")

    model_rows = {OLD_OBSERVED_GENERATOR: old_rows, NEW_GENERATOR: new_rows}
    manifests = {OLD_OBSERVED_GENERATOR: old_manifest, NEW_GENERATOR: new_manifest}
    results: dict[str, Any] = {}
    family_results: dict[str, Any] = {}
    history_results: dict[str, Any] = {}
    no_task_results: dict[str, Any] = {}
    primary_set = set(PRIMARY_FAMILIES)
    for model, rows in model_rows.items():
        results[model] = {}
        family_results[model] = {}
        history_results[model] = {}
        no_task_results[model] = {}
        for condition in CONDITIONS:
            results[model][condition] = {
                "overall": summarize(rows_for(rows, condition)),
                "primary": summarize(rows_for(rows, condition, families=primary_set)),
            }
            family_results[model][condition] = {
                family: summarize(rows_for(rows, condition, family=family))
                for family in PRIMARY_FAMILIES
            }
            history_results[model][condition] = family_results[model][condition]["TASK_HISTORY"]
            no_task_results[model][condition] = summarize(
                rows_for(rows, condition, family="NO_TASK_CONTROL")
            )

    uplifts: dict[str, Any] = {}
    for model in model_rows:
        primary = {condition: results[model][condition]["primary"] for condition in CONDITIONS}
        uplifts[model] = {
            "primary_structured": {
                "oracle_minus_thread_aware": round(
                    primary["ORACLE_TASK_STATE_RAG"]["mean_structured_score"]
                    - primary["THREAD_AWARE_RAG"]["mean_structured_score"],
                    8,
                ),
                "oracle_minus_standard": round(
                    primary["ORACLE_TASK_STATE_RAG"]["mean_structured_score"]
                    - primary["STANDARD_RAG"]["mean_structured_score"],
                    8,
                ),
            },
            "primary_exact": {
                "oracle_minus_thread_aware": round(
                    primary["ORACLE_TASK_STATE_RAG"]["exact_accuracy"]
                    - primary["THREAD_AWARE_RAG"]["exact_accuracy"],
                    8,
                ),
                "oracle_minus_standard": round(
                    primary["ORACLE_TASK_STATE_RAG"]["exact_accuracy"]
                    - primary["STANDARD_RAG"]["exact_accuracy"],
                    8,
                ),
            },
        }

    condition_gains = [
        round(
            results[NEW_GENERATOR][condition]["primary"]["mean_structured_score"]
            - results[OLD_OBSERVED_GENERATOR][condition]["primary"]["mean_structured_score"],
            8,
        )
        for condition in CONDITIONS
    ]
    old_uplift = uplifts[OLD_OBSERVED_GENERATOR]["primary_structured"]["oracle_minus_thread_aware"]
    new_uplift = uplifts[NEW_GENERATOR]["primary_structured"]["oracle_minus_thread_aware"]
    pattern_label = classify_pattern(old_uplift, new_uplift, condition_gains)
    interpretations = {
        "A": "STANDARD and THREAD_AWARE remain similar and both remain well below ORACLE under both generators.",
        "B": "GPT-4.1 substantially improves the email-only baselines and strongly reduces Oracle uplift.",
        "C": "Model strength and explicit task-state structure provide complementary benefits: all conditions improve while Oracle uplift remains large.",
        "D": "The Oracle advantage disappears with the stronger generator.",
    }
    oracle_advantage = bool(
        new_uplift >= 0.20
        and uplifts[NEW_GENERATOR]["primary_exact"]["oracle_minus_thread_aware"] >= 0.20
    )
    comparison = {
        "schema_version": "1.0",
        "old_run_id": old_manifest["run_id"],
        "new_run_id": new_manifest["run_id"],
        "questions": 271,
        "conditions": list(CONDITIONS),
        "pairs_per_run": 813,
        "frozen_protocol": frozen,
        "results": results,
        "task_state_uplift": uplifts,
        "family_results": family_results,
        "history_results": history_results,
        "no_task_control_results": no_task_results,
        "primary_structured_condition_gains_new_minus_old": dict(zip(CONDITIONS, condition_gains)),
        "new_run_pairwise_statistics": read_pairwise(new_dir / "pairwise_comparisons.csv"),
        "costs": {
            model: cost_summary(model_rows[model], manifests[model], model) for model in model_rows
        },
        "output_completeness": {
            model: summarize(model_rows[model]) for model in model_rows
        },
        "pattern": {"label": pattern_label, "interpretation": interpretations[pattern_label]},
        "oracle_advantage_substantial": oracle_advantage,
        "limitations": [
            "Temperature 0 does not guarantee bit-identical service output.",
            "Different models may use different tokenization and response lengths.",
            "Oracle task state is human-derived; automatic extraction is not evaluated.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "comparison_gpt4omini_vs_gpt41.json", comparison)
    write_markdown(output_dir / "comparison_gpt4omini_vs_gpt41.md", comparison)
    append_report_summary(new_dir / "experiment_report.md", comparison)
    print(
        f"Compared 813 pairs per generator; GPT-4o-mini uplift={old_uplift:.4f}; "
        f"GPT-4.1 uplift={new_uplift:.4f}; pattern={pattern_label}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare frozen ISCMI 2026 runs across GPT-4o-mini and GPT-4.1."
    )
    parser.add_argument("--old-results-dir", required=True)
    parser.add_argument("--new-results-dir", required=True)
    parser.add_argument("--output-dir")
    return parser


if __name__ == "__main__":
    raise SystemExit(compare(build_parser().parse_args()))
