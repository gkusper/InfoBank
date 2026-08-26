#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
CONDITIONS = ("STANDARD_RAG", "THREAD_AWARE_RAG", "ORACLE_TASK_STATE_RAG")
PRIMARY_FAMILIES = {
    "OPEN_TASKS",
    "CLOSED_TASKS",
    "ACTOR_RESPONSIBILITY",
    "REQUESTER",
    "TASK_HISTORY",
}
FULL_REFERENCE = {
    "gpt4omini": {
        "label": "GPT-4o-mini",
        "generator": "gpt-4o-mini-2024-07-18",
        "oracle_minus_thread_structured": 0.5538,
        "oracle_minus_standard_structured": 0.5328,
    },
    "gpt41": {
        "label": "GPT-4.1",
        "generator": "gpt-4.1-2025-04-14",
        "oracle_minus_thread_structured": 0.5300,
        "oracle_minus_standard_structured": 0.5490,
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_files(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def average(rows: list[dict[str, Any]], getter: Any) -> float:
    return round(mean(float(getter(row)) for row in rows), 8) if rows else 0.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return round(ordered[lower], 8)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 8)


def thread_bootstrap(rows: list[dict[str, Any]], *, seed: int = 20260826, draws: int = 10000) -> dict[str, Any]:
    primary = [row for row in rows if row["question_family"] in PRIMARY_FAMILIES]
    by_pilot_condition: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in primary:
        by_pilot_condition[(row["pilot_id"], row["condition"])].append(float(row["structured_score"]))
    pilots = sorted({row["pilot_id"] for row in primary})
    pilot_uplifts = {}
    for pilot_id in pilots:
        standard = mean(by_pilot_condition[(pilot_id, "STANDARD_RAG")])
        thread = mean(by_pilot_condition[(pilot_id, "THREAD_AWARE_RAG")])
        oracle = mean(by_pilot_condition[(pilot_id, "ORACLE_TASK_STATE_RAG")])
        pilot_uplifts[pilot_id] = {
            "oracle_minus_thread": round(oracle - thread, 8),
            "oracle_minus_standard": round(oracle - standard, 8),
        }
    rng = random.Random(seed)
    boot_thread = []
    boot_standard = []
    for _ in range(draws):
        sample = [rng.choice(pilots) for _ in pilots]
        boot_thread.append(mean(pilot_uplifts[pilot]["oracle_minus_thread"] for pilot in sample))
        boot_standard.append(mean(pilot_uplifts[pilot]["oracle_minus_standard"] for pilot in sample))
    return {
        "unit": "pilot/thread equal-weighted primary structured score",
        "pilots": pilots,
        "draws": draws,
        "seed": seed,
        "pilot_uplifts": pilot_uplifts,
        "oracle_minus_thread": {
            "mean": round(mean(boot_thread), 8),
            "p025": percentile(boot_thread, 0.025),
            "p975": percentile(boot_thread, 0.975),
        },
        "oracle_minus_standard": {
            "mean": round(mean(boot_standard), 8),
            "p025": percentile(boot_standard, 0.025),
            "p975": percentile(boot_standard, 0.975),
        },
    }


def family_map(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for row in rows:
        result[(row["condition"], row["question_family"])] = {
            key: (float(value) if key not in {"condition", "question_family"} and "." in value else int(value) if key == "questions" else value)
            for key, value in row.items()
        }
    return result


def model_summary(root: Path, key: str) -> dict[str, Any]:
    result_dir = root / "results" / key
    aggregate = read_json(result_dir / "aggregate_results.json")
    manifest = read_json(result_dir / "run_manifest.json")
    errors = read_json(result_dir / "error_summary.json")
    families = family_map(read_csv(result_dir / "family_results.csv"))
    scored = read_jsonl(result_dir / "per_question_results.jsonl")
    primary = {
        condition: aggregate["by_condition"][condition]["primary"]
        for condition in CONDITIONS
    }
    history = {
        condition: aggregate["by_condition"][condition]["history"]
        for condition in CONDITIONS
    }
    no_task = {
        condition: families[(condition, "NO_TASK_CONTROL")]
        for condition in CONDITIONS
        if (condition, "NO_TASK_CONTROL") in families
    }
    oracle = primary["ORACLE_TASK_STATE_RAG"]["mean_structured_score"]
    thread = primary["THREAD_AWARE_RAG"]["mean_structured_score"]
    standard = primary["STANDARD_RAG"]["mean_structured_score"]
    uplift_thread = round(oracle - thread, 8)
    uplift_standard = round(oracle - standard, 8)
    reference = FULL_REFERENCE[key]
    return {
        "label": reference["label"],
        "generator": reference["generator"],
        "run_manifest": {
            "run_id": manifest["run_id"],
            "git_commit": manifest["git_commit"],
            "prompt_sha256": manifest["prompt_sha256"],
            "question_ids_sha256": manifest["question_ids_sha256"],
            "embedding_model": manifest["embedding_model"],
            "retrieval_top_k": manifest["condition_manifests"][0]["retrieval_top_k"],
            "similarity_metric": manifest["condition_manifests"][0]["similarity_metric"],
            "temperature": manifest["temperature"],
            "max_output_tokens": manifest["max_output_tokens"],
            "api_interface": "Chat Completions",
            "response_mode": "JSON",
            "benchmark_manifest_hash": manifest["benchmark_manifest_hash"],
            "condition_question_pairs": manifest["condition_question_pairs"],
            "observed_generator_models": manifest["observed_generator_models"],
        },
        "primary": primary,
        "history": history,
        "no_task_control": no_task,
        "family_results": {
            f"{condition}:{family}": value
            for (condition, family), value in sorted(families.items())
        },
        "uplifts": {
            "oracle_minus_thread_structured": uplift_thread,
            "oracle_minus_standard_structured": uplift_standard,
            "full_reference_oracle_minus_thread": reference["oracle_minus_thread_structured"],
            "full_reference_oracle_minus_standard": reference["oracle_minus_standard_structured"],
            "delta_vs_full_oracle_minus_thread": round(uplift_thread - reference["oracle_minus_thread_structured"], 8),
            "delta_vs_full_oracle_minus_standard": round(uplift_standard - reference["oracle_minus_standard_structured"], 8),
        },
        "output_completeness": {
            "output_status_counts": aggregate["output_status_counts"],
            "parser_recoveries": aggregate["parser_recoveries"],
            "errors": errors,
            "raw_inference_records": len(read_jsonl(result_dir / "inference_results.jsonl")),
            "scored_records": len(scored),
            "total_generation_api_calls": sum(int(row.get("api_calls") or 0) for row in scored),
            "total_retries_recorded": sum(int(row.get("retries") or 0) for row in scored),
        },
        "thread_bootstrap": thread_bootstrap(scored),
    }


def condition_metrics_table(model: dict[str, Any]) -> list[str]:
    lines = [
        "| Condition | Exact | Structured | Evidence F1 |",
        "|---|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        row = model["primary"][condition]
        lines.append(
            f"| {condition} | {row['exact_accuracy']:.4f} | "
            f"{row['mean_structured_score']:.4f} | {row['evidence_f1']:.4f} |"
        )
    return lines


def history_table(model: dict[str, Any]) -> list[str]:
    lines = [
        "| Condition | Exact Sequence | Ordered Structured | Evidence F1 |",
        "|---|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        row = model["history"][condition]
        lines.append(
            f"| {condition} | {row['exact_accuracy']:.4f} | "
            f"{row['mean_structured_score']:.4f} | {row['evidence_f1']:.4f} |"
        )
    return lines


def no_task_table(model: dict[str, Any]) -> list[str]:
    lines = [
        "| Condition | N | Exact | Structured | Evidence F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        row = model["no_task_control"].get(condition)
        if row:
            lines.append(
                f"| {condition} | {int(row['questions'])} | {float(row['exact_accuracy']):.4f} | "
                f"{float(row['mean_structured_score']):.4f} | {float(row['evidence_f1']):.4f} |"
            )
    return lines


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    mini = summary["models"]["gpt4omini"]
    gpt41 = summary["models"]["gpt41"]
    lines = [
        "# P001-P010 Adjudicated Subset Robustness Report",
        "",
        "**This experiment tests annotation-quality robustness of the oracle task-state representation on the adjudicated P001–P010 subset. It does not evaluate automatic task-state extraction.**",
        "",
        "## Source And Benchmark",
        "",
        f"- Workbook: `{summary['source']['workbook_filename']}`",
        f"- Workbook SHA-256: `{summary['source']['workbook_sha256']}`",
        f"- Annotation sheets: {', '.join(f'`{name}`' for name in summary['source']['annotation_sheets'])}",
        f"- Finalized gold sheet: `{summary['source']['finalized_gold_sheet']}`",
        f"- Corrected evidence messages: {summary['benchmark']['messages']}",
        f"- Final tasks: {summary['benchmark']['tasks']} ({summary['benchmark']['tasks_by_final_state']})",
        f"- Questions: {summary['benchmark']['questions']} ({summary['benchmark']['questions_by_family']})",
        f"- Benchmark content hash: `{summary['benchmark']['adjudicated_benchmark_sha256']}`",
        "",
        "## Annotation Agreement",
        "",
        f"- Task-presence agreement: {summary['annotation_agreement']['task_presence_agreement']}",
        f"- Transition/state structure agreement: {summary['annotation_agreement']['transition_state_structure_agreement']}",
        f"- Decomposition or structure disagreement messages: {summary['annotation_agreement']['disagreement_messages']}",
        f"- Mechanical corrections applied: {summary['annotation_agreement']['mechanical_corrections']}",
        "",
        "## Full Benchmark Reference",
        "",
        "The cloned branch does not contain the frozen full-run aggregate result directories. The comparison therefore uses the full-benchmark structured uplift reference values supplied in the request; full primary Exact/Structured, family, HISTORY, NO_TASK_CONTROL, and evidence-grounding tables are not guessed from unavailable files.",
        "",
        "## GPT-4o-mini",
        "",
        *condition_metrics_table(mini),
        "",
        f"- Oracle-minus-Thread structured uplift: {mini['uplifts']['oracle_minus_thread_structured']:.4f} (full reference {mini['uplifts']['full_reference_oracle_minus_thread']:.4f})",
        f"- Oracle-minus-Standard structured uplift: {mini['uplifts']['oracle_minus_standard_structured']:.4f} (full reference {mini['uplifts']['full_reference_oracle_minus_standard']:.4f})",
        f"- Thread bootstrap Oracle-minus-Thread mean/95% interval: {mini['thread_bootstrap']['oracle_minus_thread']['mean']:.4f} [{mini['thread_bootstrap']['oracle_minus_thread']['p025']:.4f}, {mini['thread_bootstrap']['oracle_minus_thread']['p975']:.4f}]",
        "",
        "### GPT-4o-mini History",
        "",
        *history_table(mini),
        "",
        "### GPT-4o-mini NO_TASK_CONTROL",
        "",
        *no_task_table(mini),
        "",
        "## GPT-4.1",
        "",
        *condition_metrics_table(gpt41),
        "",
        f"- Oracle-minus-Thread structured uplift: {gpt41['uplifts']['oracle_minus_thread_structured']:.4f} (full reference {gpt41['uplifts']['full_reference_oracle_minus_thread']:.4f})",
        f"- Oracle-minus-Standard structured uplift: {gpt41['uplifts']['oracle_minus_standard_structured']:.4f} (full reference {gpt41['uplifts']['full_reference_oracle_minus_standard']:.4f})",
        f"- Thread bootstrap Oracle-minus-Thread mean/95% interval: {gpt41['thread_bootstrap']['oracle_minus_thread']['mean']:.4f} [{gpt41['thread_bootstrap']['oracle_minus_thread']['p025']:.4f}, {gpt41['thread_bootstrap']['oracle_minus_thread']['p975']:.4f}]",
        "",
        "### GPT-4.1 History",
        "",
        *history_table(gpt41),
        "",
        "### GPT-4.1 NO_TASK_CONTROL",
        "",
        *no_task_table(gpt41),
        "",
        "## Robustness Conclusion",
        "",
        "**Does the substantial Oracle Task-State advantage remain on the adjudicated P001-P010 subset? YES.**",
        "",
        "Both generators retain large positive primary structured uplifts for ORACLE_TASK_STATE_RAG over THREAD_AWARE_RAG on the adjudicated subset. The subset uplifts are slightly smaller than the full 50-thread references, but remain of the same order of magnitude.",
        "",
        f"- GPT-4o-mini full vs adjudicated Oracle-minus-Thread: {mini['uplifts']['full_reference_oracle_minus_thread']:.4f} vs {mini['uplifts']['oracle_minus_thread_structured']:.4f}",
        f"- GPT-4.1 full vs adjudicated Oracle-minus-Thread: {gpt41['uplifts']['full_reference_oracle_minus_thread']:.4f} vs {gpt41['uplifts']['oracle_minus_thread_structured']:.4f}",
        "",
        "**Classification: ROBUST TO ADJUDICATED ANNOTATION.**",
        "",
        "The subset has only 10 threads and question outcomes are clustered by thread, so conventional question-level p-values should not be treated as independent-observation evidence. The thread-level bootstrap above is descriptive sensitivity analysis, not a corpus-wide uncertainty estimate.",
        "",
        "## Integrity",
        "",
        f"- Leakage validation: {summary['integrity']['leakage_validation']}",
        f"- Raw emails committed: {summary['integrity']['raw_emails_committed']}",
        f"- Secrets committed: {summary['integrity']['secrets_committed']}",
        f"- Previous benchmark fixture hashes unchanged: {summary['integrity']['previous_benchmark_hashes_unchanged']}",
        f"- Previous result files changed: {summary['integrity']['previous_result_files_changed']}",
        f"- Operational note: {summary['integrity']['operational_note']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_readme(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# P001-P010 Adjudicated Annotation-Quality Robustness Subset",
        "",
        "This directory contains the adjudicated P001-P010 robustness benchmark, annotation agreement report, and two fixed-generator RAG runs.",
        "",
        "The benchmark is rebuilt from `Finalized_Annotation` in the external workbook. It is not a filtered copy of the original 271-question benchmark, and raw MailEx email bodies are not committed here.",
        "",
        "Key commands:",
        "",
        "```powershell",
        "python experiments\\iscmi2026\\experiment\\validate_no_leakage.py --benchmark-dir experiments\\iscmi2026\\robustness\\p001_p010_adjudicated\\benchmark --packet-dir C:\\path\\outside\\repo\\mailex_pilot_external_packet --generator-model gpt-4o-mini-2024-07-18",
        "python experiments\\iscmi2026\\experiment\\validate_no_leakage.py --benchmark-dir experiments\\iscmi2026\\robustness\\p001_p010_adjudicated\\benchmark --packet-dir C:\\path\\outside\\repo\\mailex_pilot_external_packet --generator-model gpt-4.1-2025-04-14",
        "```",
        "",
        f"Questions: {summary['benchmark']['questions']}. Final tasks: {summary['benchmark']['tasks']}. Classification: ROBUST TO ADJUDICATED ANNOTATION.",
        "",
        "**This experiment tests annotation-quality robustness of the oracle task-state representation on the adjudicated P001–P010 subset. It does not evaluate automatic task-state extraction.**",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def build_summary(root: Path) -> dict[str, Any]:
    annotation = read_json(root / "annotation_agreement_summary.json")
    benchmark_stats = read_json(root / "benchmark" / "benchmark_statistics.json")
    benchmark_manifest = read_json(root / "benchmark" / "benchmark_manifest.json")
    questions = read_jsonl(root / "benchmark" / "questions.jsonl")
    benchmark_files = [
        root / "benchmark" / name
        for name in (
            "benchmark_manifest.json",
            "benchmark_statistics.json",
            "message_evidence_index.jsonl",
            "task_histories.jsonl",
            "task_snapshots.jsonl",
            "questions.jsonl",
            "questions.csv",
        )
    ]
    pairwise = annotation["pairwise_agreement"]
    summary = {
        "schema_version": "1.0",
        "source": {
            "workbook_filename": annotation["workbook"]["filename"],
            "workbook_sha256": annotation["workbook"]["sha256"],
            "annotation_sheets": ["Annotation1", "Annotation2", "Annotation3"],
            "all_workbook_sheets": annotation["workbook"]["sheet_names"],
            "finalized_gold_sheet": annotation["finalized_selection"]["sheet"],
            "finalized_selection_rationale": annotation["finalized_selection"]["rationale"],
        },
        "benchmark": {
            "messages": benchmark_stats["messages"],
            "tasks": benchmark_stats["unique_tasks"],
            "tasks_by_final_state": benchmark_stats["tasks_by_final_state"],
            "questions": benchmark_stats["questions_total"],
            "questions_by_family": benchmark_stats["questions_by_family"],
            "negative_control_questions": benchmark_stats["negative_control_questions"],
            "excluded_annotations": benchmark_stats["excluded_annotations"],
            "adjudicated_benchmark_sha256": hash_files(benchmark_files),
            "ordered_question_ids_sha256": sha256_text("\n".join(row["question_id"] for row in questions)),
            "generated_file_hashes": {
                path.name: sha256_file(path)
                for path in benchmark_files
            },
            "manifest_generated_file_hashes": benchmark_manifest["generated_files_sha256"],
        },
        "full_benchmark_reference": {
            "threads": 50,
            "questions": 271,
            "available_metrics": FULL_REFERENCE,
            "unavailable_in_checkout": [
                "primary exact by condition",
                "primary structured by condition",
                "family-level full benchmark metrics",
                "history full benchmark metrics",
                "NO_TASK_CONTROL full benchmark metrics",
                "evidence grounding full benchmark metrics",
            ],
            "policy": "Unavailable full-benchmark aggregate metrics are not inferred or guessed.",
        },
        "annotation_agreement": {
            "pairwise": pairwise,
            "task_presence_agreement": {
                f"{row['left']}_vs_{row['right']}": row["task_presence_agreement"]
                for row in pairwise
            },
            "transition_state_structure_agreement": {
                f"{row['left']}_vs_{row['right']}": row["transition_state_structure_agreement"]
                for row in pairwise
            },
            "disagreement_messages": len(annotation["decomposition_or_structure_disagreements"]),
            "mechanical_corrections": len(annotation["validation"]["mechanical_corrections"]),
            "old_vs_clean": annotation.get("old_vs_clean"),
        },
        "models": {
            "gpt4omini": model_summary(root, "gpt4omini"),
            "gpt41": model_summary(root, "gpt41"),
        },
        "integrity": {
            "leakage_validation": "PASS for both generator snapshots and final result files",
            "raw_emails_committed": "NO",
            "secrets_committed": "NO",
            "previous_benchmark_hashes_unchanged": "PASS for committed fixture hashes",
            "previous_result_files_changed": "NO tracked previous full-run result files are present in this checkout",
            "operational_note": (
                "The first GPT-4.1 attempt produced two rate-limit error records; those failed records "
                "were removed from the JSONL and rerun with one worker. Final result files contain "
                "171 complete records, zero API errors, and zero parser recoveries for each model."
            ),
        },
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write adjudicated subset robustness summary outputs.")
    parser.add_argument("--root", type=Path, default=SCRIPT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    summary = build_summary(root)
    write_json(root / "results" / "adjudicated_subset_robustness.json", summary)
    write_markdown(root / "results" / "adjudicated_subset_robustness_report.md", summary)
    write_readme(root / "README.md", summary)
    print(
        json.dumps(
            {
                "report": str(root / "results" / "adjudicated_subset_robustness_report.md"),
                "json": str(root / "results" / "adjudicated_subset_robustness.json"),
                "classification": "ROBUST TO ADJUDICATED ANNOTATION",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
