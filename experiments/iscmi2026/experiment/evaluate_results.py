from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from experiment_core import (
    CONDITIONS,
    EXPERIMENT_DIR,
    append_jsonl,
    load_benchmark,
    parse_model_output,
    read_json,
    read_jsonl,
    write_json,
)


PRIMARY_FAMILIES = {
    "OPEN_TASKS",
    "CLOSED_TASKS",
    "ACTOR_RESPONSIBILITY",
    "REQUESTER",
    "TASK_HISTORY",
}
SECONDARY_FAMILIES = {"DEADLINE", "WAITING_FOR", "BLOCKED_BY"}
ATTRIBUTE_FIELDS = {
    "ACTOR_RESPONSIBILITY": "actor",
    "REQUESTER": "requester",
    "DEADLINE": "deadline",
    "WAITING_FOR": "waiting_for",
    "BLOCKED_BY": "blocked_by",
}
COMPARISONS = (
    ("STANDARD_RAG", "THREAD_AWARE_RAG"),
    ("THREAD_AWARE_RAG", "ORACLE_TASK_STATE_RAG"),
    ("STANDARD_RAG", "ORACLE_TASK_STATE_RAG"),
)


def normalize_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[^\w@.-]+", " ", text)
    return " ".join(text.split())


def normalize_people(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"\s*;\s*", text) if part.strip()]
    return ";".join(sorted(parts))


def normalize_date(value: Any) -> str:
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", str(value or ""))
    return match.group(0) if match else normalize_text(value)


def f1_counts(true_positive: int, predicted: int, gold: int) -> dict[str, float | int]:
    precision = true_positive / predicted if predicted else (1.0 if gold == 0 else 0.0)
    recall = true_positive / gold if gold else (1.0 if predicted == 0 else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "predicted": predicted,
        "gold": gold,
        "precision": round(precision, 8),
        "recall": round(recall, 8),
        "f1": round(f1, 8),
    }


def task_evidence(task: dict[str, Any]) -> set[str]:
    evidence = set(str(item) for item in task.get("evidence_message_ids", []) if item)
    for event in task.get("events", []):
        if isinstance(event, dict) and event.get("message_id"):
            evidence.add(str(event["message_id"]))
    return evidence


def align_tasks(
    predicted: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    task_evidence_by_id: dict[str, set[str]],
) -> list[tuple[int, int, str, float]]:
    matches: list[tuple[int, int, str, float]] = []
    used_predicted: set[int] = set()
    used_gold: set[int] = set()
    gold_by_id = {str(task.get("task_id")): index for index, task in enumerate(gold) if task.get("task_id")}
    for pred_index, task in enumerate(predicted):
        task_id = str(task.get("task_id") or "")
        gold_index = gold_by_id.get(task_id)
        if gold_index is not None and gold_index not in used_gold:
            matches.append((pred_index, gold_index, "task_id", 1.0))
            used_predicted.add(pred_index)
            used_gold.add(gold_index)

    candidates: list[tuple[float, int, int]] = []
    for pred_index, task in enumerate(predicted):
        if pred_index in used_predicted:
            continue
        pred_evidence = task_evidence(task)
        if not pred_evidence:
            continue
        for gold_index, gold_task in enumerate(gold):
            if gold_index in used_gold:
                continue
            gold_evidence = task_evidence_by_id.get(str(gold_task.get("task_id")), set())
            union = pred_evidence | gold_evidence
            overlap = len(pred_evidence & gold_evidence) / len(union) if union else 0.0
            if overlap > 0:
                candidates.append((overlap, pred_index, gold_index))
    for overlap, pred_index, gold_index in sorted(candidates, key=lambda row: (-row[0], row[1], row[2])):
        if pred_index in used_predicted or gold_index in used_gold:
            continue
        matches.append((pred_index, gold_index, "evidence_jaccard", overlap))
        used_predicted.add(pred_index)
        used_gold.add(gold_index)
    return sorted(matches, key=lambda row: row[1])


def lcs_length(left: list[tuple[str, str]], right: list[tuple[str, str]]) -> int:
    previous = [0] * (len(right) + 1)
    for left_item in left:
        current = [0]
        for index, right_item in enumerate(right, start=1):
            if left_item == right_item:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(current[-1], previous[index]))
        previous = current
    return previous[-1]


def sequence(event_rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [
        (
            str(event.get("transition") or "").upper(),
            str(event.get("resulting_state") or event.get("state") or "").upper(),
        )
        for event in event_rows
        if isinstance(event, dict) and event.get("transition")
    ]


def evidence_metrics(
    parsed: dict[str, Any], gold_ids: list[str], retrieved_message_ids: list[str], all_message_ids: set[str]
) -> dict[str, Any]:
    predicted_ids = set(str(item) for item in parsed.get("evidence_message_ids", []) if item)
    for task in parsed.get("tasks", []):
        predicted_ids.update(task_evidence(task))
    gold = set(gold_ids)
    counts = f1_counts(len(predicted_ids & gold), len(predicted_ids), len(gold))
    counts.update(
        {
            "predicted_evidence_message_ids": sorted(predicted_ids),
            "gold_evidence_message_ids": sorted(gold),
            "all_ids_resolve": predicted_ids <= all_message_ids,
            "all_ids_in_retrieved_email_context": predicted_ids <= set(retrieved_message_ids),
            "exact_match": predicted_ids == gold,
        }
    )
    return counts


def score_result(
    inference: dict[str, Any],
    question: dict[str, Any],
    task_evidence_by_key: dict[tuple[str, str], set[str]],
    all_message_ids: set[str],
) -> dict[str, Any]:
    family = question["question_family"]
    gold_structured = question["gold_structured"]
    parsed = inference.get("parsed_output") or {}
    predicted_tasks = [row for row in parsed.get("tasks", []) if isinstance(row, dict)]
    gold_tasks = [row for row in gold_structured.get("tasks", []) if isinstance(row, dict)]
    task_evidence_by_id = {
        task_id: evidence
        for (pilot_id, task_id), evidence in task_evidence_by_key.items()
        if pilot_id == question["pilot_id"]
    }
    matches = align_tasks(predicted_tasks, gold_tasks, task_evidence_by_id)
    match_rows = [
        {
            "predicted_index": pred_index,
            "gold_index": gold_index,
            "method": method,
            "overlap": round(overlap, 8),
        }
        for pred_index, gold_index, method, overlap in matches
    ]
    score_components: dict[str, Any] = {"task_alignment": match_rows}
    exact = False
    structured_score = 0.0

    if family in {"OPEN_TASKS", "CLOSED_TASKS"}:
        task_set = f1_counts(len(matches), len(predicted_tasks), len(gold_tasks))
        target_state = str(gold_structured.get("state") or "").upper()
        state_consistent = all(
            not task.get("final_state") or str(task["final_state"]).upper() == target_state
            for task in predicted_tasks
        )
        exact = bool(task_set["f1"] == 1.0 and state_consistent)
        structured_score = float(task_set["f1"])
        score_components.update({"task_set": task_set, "state_consistent": state_consistent})
    elif family in ATTRIBUTE_FIELDS:
        field = ATTRIBUTE_FIELDS[family]
        normalizer = normalize_people if field in {"actor", "requester"} else normalize_date if field == "deadline" else normalize_text
        correct = 0
        comparisons = []
        for pred_index, gold_index, _method, _overlap in matches:
            predicted_value = normalizer(predicted_tasks[pred_index].get(field))
            gold_value = normalizer(gold_tasks[gold_index].get(field))
            value_correct = bool(predicted_value and predicted_value == gold_value)
            correct += int(value_correct)
            comparisons.append(
                {
                    "task_id": gold_tasks[gold_index].get("task_id"),
                    "predicted": predicted_value,
                    "gold": gold_value,
                    "correct": value_correct,
                }
            )
        attribute = f1_counts(correct, len(predicted_tasks), len(gold_tasks))
        exact = bool(attribute["f1"] == 1.0)
        structured_score = float(attribute["f1"])
        score_components.update({"attribute": field, "attribute_task_pairs": attribute, "comparisons": comparisons})
    elif family == "TASK_HISTORY":
        exact_sequences = 0
        lcs_total = 0
        predicted_event_total = sum(
            len(sequence(task.get("events", []))) for task in predicted_tasks
        )
        gold_event_total = sum(len(sequence(task.get("events", []))) for task in gold_tasks)
        transition_tp = 0
        predicted_transition_total = predicted_event_total
        gold_transition_total = gold_event_total
        history_rows = []
        for pred_index, gold_index, _method, _overlap in matches:
            predicted_sequence = sequence(predicted_tasks[pred_index].get("events", []))
            gold_sequence = sequence(gold_tasks[gold_index].get("events", []))
            common = lcs_length(predicted_sequence, gold_sequence)
            lcs_total += common
            exact_sequence = predicted_sequence == gold_sequence
            exact_sequences += int(exact_sequence)
            predicted_transitions = Counter(item[0] for item in predicted_sequence)
            gold_transitions = Counter(item[0] for item in gold_sequence)
            transition_tp += sum((predicted_transitions & gold_transitions).values())
            history_rows.append(
                {
                    "task_id": gold_tasks[gold_index].get("task_id"),
                    "predicted_sequence": predicted_sequence,
                    "gold_sequence": gold_sequence,
                    "exact_sequence": exact_sequence,
                    "lcs_length": common,
                }
            )
        lcs = f1_counts(lcs_total, predicted_event_total, gold_event_total)
        transition_multiset = f1_counts(
            transition_tp, predicted_transition_total, gold_transition_total
        )
        exact = bool(
            len(matches) == len(predicted_tasks) == len(gold_tasks)
            and exact_sequences == len(gold_tasks)
        )
        structured_score = float(lcs["f1"])
        score_components.update(
            {
                "history_tasks": history_rows,
                "exact_sequence_tasks": exact_sequences,
                "exact_sequence_all": exact,
                "ordered_subsequence": lcs,
                "transition_multiset": transition_multiset,
            }
        )
    elif family == "NO_TASK_CONTROL":
        exact = bool(parsed.get("answer_type") == "NO_TASK" or parsed.get("none") is True)
        structured_score = 1.0 if exact else 0.0
        score_components["no_task_correct"] = exact
    else:
        raise ValueError(f"Unsupported question family: {family}")

    evidence = evidence_metrics(
        parsed,
        question["evidence_message_ids"],
        inference.get("retrieved_message_ids", []),
        all_message_ids,
    )
    expected_control = bool(question.get("negative_control"))
    predicted_control = bool(
        parsed.get("controlled_failure")
        or parsed.get("answer_type") in {"NO_TASK", "INSUFFICIENT_EVIDENCE"}
        or parsed.get("none") is True
    )
    controlled_failure_correct = predicted_control if expected_control else not predicted_control
    if inference.get("error"):
        exact = False
        structured_score = 0.0
    return {
        **inference,
        "gold_structured": gold_structured,
        "gold_evidence_message_ids": question["evidence_message_ids"],
        "negative_control": expected_control,
        "score_components": score_components,
        "exact_correct": exact,
        "structured_score": round(structured_score, 8),
        "controlled_failure_expected": expected_control,
        "controlled_failure_predicted": predicted_control,
        "controlled_failure_correct": controlled_failure_correct,
        "evidence_grounding": evidence,
    }


def average(rows: list[dict[str, Any]], getter: Any) -> float:
    return round(mean(float(getter(row)) for row in rows), 8) if rows else 0.0


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "questions": len(rows),
        "exact_accuracy": average(rows, lambda row: bool(row["exact_correct"])),
        "mean_structured_score": average(rows, lambda row: row["structured_score"]),
        "controlled_failure_accuracy": average(rows, lambda row: bool(row["controlled_failure_correct"])),
        "evidence_precision": average(rows, lambda row: row["evidence_grounding"]["precision"]),
        "evidence_recall": average(rows, lambda row: row["evidence_grounding"]["recall"]),
        "evidence_f1": average(rows, lambda row: row["evidence_grounding"]["f1"]),
        "evidence_exact_accuracy": average(rows, lambda row: bool(row["evidence_grounding"]["exact_match"])),
        "evidence_source_validity": average(rows, lambda row: bool(row["evidence_grounding"]["all_ids_resolve"])),
        "errors": sum(1 for row in rows if row.get("error")),
        "api_calls": sum(int(row.get("api_calls") or 0) for row in rows),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in rows),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in rows),
        "average_tokens_per_question": round(
            sum(int(row.get("total_tokens") or 0) for row in rows) / len(rows)
            if rows
            else 0.0,
            4,
        ),
        "mean_latency_seconds": average(rows, lambda row: row.get("latency_seconds") or 0.0),
    }


def exact_mcnemar_pvalue(wins_left: int, wins_right: int) -> float | None:
    discordant = wins_left + wins_right
    if discordant == 0:
        return None
    tail = min(wins_left, wins_right)
    probability = sum(math.comb(discordant, k) * (0.5**discordant) for k in range(tail + 1))
    return min(1.0, 2.0 * probability)


def wilcoxon_signed_rank(left: list[float], right: list[float]) -> dict[str, Any]:
    differences = [a - b for a, b in zip(left, right) if not math.isclose(a, b, abs_tol=1e-12)]
    if not differences:
        return {"n_nonzero": 0, "p_value": None, "rank_biserial": 0.0}
    indexed = sorted(enumerate(abs(value) for value in differences), key=lambda row: row[1])
    ranks = [0.0] * len(differences)
    tie_sizes: list[int] = []
    position = 0
    while position < len(indexed):
        end = position + 1
        while end < len(indexed) and math.isclose(indexed[end][1], indexed[position][1], abs_tol=1e-12):
            end += 1
        average_rank = ((position + 1) + end) / 2.0
        for original_index, _value in indexed[position:end]:
            ranks[original_index] = average_rank
        tie_sizes.append(end - position)
        position = end
    positive = sum(rank for rank, difference in zip(ranks, differences) if difference > 0)
    negative = sum(rank for rank, difference in zip(ranks, differences) if difference < 0)
    n = len(differences)
    variance = (n * (n + 1) * (2 * n + 1) - sum(size**3 - size for size in tie_sizes)) / 24.0
    if variance <= 0:
        p_value = None
    else:
        z = (abs(positive - n * (n + 1) / 4.0) - 0.5) / math.sqrt(variance)
        p_value = math.erfc(max(0.0, z) / math.sqrt(2.0))
    total_rank = positive + negative
    effect = (positive - negative) / total_rank if total_rank else 0.0
    return {
        "n_nonzero": n,
        "positive_rank_sum": round(positive, 8),
        "negative_rank_sum": round(negative, 8),
        "p_value": p_value,
        "rank_biserial": round(effect, 8),
    }


def holm_adjust(rows: list[dict[str, Any]], key: str, output_key: str) -> None:
    sortable = sorted(
        [(index, float(row[key])) for index, row in enumerate(rows) if row.get(key) is not None],
        key=lambda item: item[1],
    )
    running = 0.0
    count = len(sortable)
    for rank, (index, p_value) in enumerate(sortable):
        adjusted = min(1.0, p_value * (count - rank))
        running = max(running, adjusted)
        rows[index][output_key] = running
    for row in rows:
        row.setdefault(output_key, None)


def pairwise_comparisons(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pair = {(row["question_id"], row["condition"]): row for row in scored}
    questions = {row["question_id"]: row for row in scored}
    rows: list[dict[str, Any]] = []
    scopes = ["PRIMARY_OVERALL", *sorted(PRIMARY_FAMILIES)]
    for left_condition, right_condition in COMPARISONS:
        for scope in scopes:
            question_ids = sorted(
                question_id
                for question_id, row in questions.items()
                if (
                    row["question_family"] in PRIMARY_FAMILIES
                    if scope == "PRIMARY_OVERALL"
                    else row["question_family"] == scope
                )
                and (question_id, left_condition) in by_pair
                and (question_id, right_condition) in by_pair
            )
            left = [by_pair[(question_id, left_condition)] for question_id in question_ids]
            right = [by_pair[(question_id, right_condition)] for question_id in question_ids]
            wins_left = sum(a["exact_correct"] and not b["exact_correct"] for a, b in zip(left, right))
            wins_right = sum(b["exact_correct"] and not a["exact_correct"] for a, b in zip(left, right))
            ties = len(question_ids) - wins_left - wins_right
            continuous = wilcoxon_signed_rank(
                [float(row["structured_score"]) for row in left],
                [float(row["structured_score"]) for row in right],
            )
            sufficient = len(question_ids) >= 20
            rows.append(
                {
                    "left_condition": left_condition,
                    "right_condition": right_condition,
                    "scope": scope,
                    "questions": len(question_ids),
                    "left_exact_accuracy": average(left, lambda row: row["exact_correct"]),
                    "right_exact_accuracy": average(right, lambda row: row["exact_correct"]),
                    "absolute_exact_difference_left_minus_right": round(
                        average(left, lambda row: row["exact_correct"])
                        - average(right, lambda row: row["exact_correct"]),
                        8,
                    ),
                    "left_structured_score": average(left, lambda row: row["structured_score"]),
                    "right_structured_score": average(right, lambda row: row["structured_score"]),
                    "absolute_structured_difference_left_minus_right": round(
                        average(left, lambda row: row["structured_score"])
                        - average(right, lambda row: row["structured_score"]),
                        8,
                    ),
                    "left_wins": wins_left,
                    "right_wins": wins_right,
                    "ties": ties,
                    "mcnemar_p_value": exact_mcnemar_pvalue(wins_left, wins_right) if sufficient else None,
                    "wilcoxon_p_value": continuous["p_value"] if sufficient else None,
                    "wilcoxon_n_nonzero": continuous["n_nonzero"],
                    "rank_biserial_effect_left_minus_right": continuous["rank_biserial"],
                    "primary_family_test": True,
                    "small_sample_test_suppressed": not sufficient,
                }
            )
    holm_adjust(rows, "mcnemar_p_value", "mcnemar_holm_p_value")
    holm_adjust(rows, "wilcoxon_p_value", "wilcoxon_holm_p_value")
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    aggregate: dict[str, Any],
    family_rows: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    run_manifest: dict[str, Any],
) -> None:
    lines = [
        "# ISCMI 2026 Oracle Task-State RAG Experiment",
        "",
        f"Run mode: `{aggregate['run_mode']}`. Questions: {aggregate['questions']}. "
        f"Conditions: {len(CONDITIONS)}. Evaluations: {aggregate['condition_question_pairs']}.",
        "",
        "The three conditions use the same generator and output schema. STANDARD_RAG uses semantic email-message retrieval; THREAD_AWARE_RAG expands to the complete chronological email thread; ORACLE_TASK_STATE_RAG additionally receives the human-derived task representation.",
        "",
        "## Frozen Configuration",
        "",
        f"Generator: `{run_manifest.get('generator_model')}`; embedding: `{run_manifest.get('embedding_model')}`; temperature: `{run_manifest.get('temperature')}`; maximum output tokens: `{run_manifest.get('max_output_tokens')}`.",
        "",
        "## Primary Summary",
        "",
        "| Condition | Exact | Structured | Controlled failure | Evidence F1 | Calls | Tokens |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        row = aggregate["by_condition"][condition]["primary"]
        overall = aggregate["by_condition"][condition]["overall"]
        lines.append(
            f"| {condition} | {row['exact_accuracy']:.4f} | {row['mean_structured_score']:.4f} | "
            f"{overall['controlled_failure_accuracy']:.4f} | {row['evidence_f1']:.4f} | "
            f"{overall['api_calls']} | {overall['total_tokens']} |"
        )
    lines.extend(
        [
            "",
            "## Family Results",
            "",
            "| Condition | Family | N | Exact | Structured | Evidence F1 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in family_rows:
        lines.append(
            f"| {row['condition']} | {row['question_family']} | {row['questions']} | "
            f"{row['exact_accuracy']:.4f} | {row['mean_structured_score']:.4f} | {row['evidence_f1']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## History",
            "",
            "The dedicated 42-question HISTORY result compares exact transition/state sequences and ordered-subsequence LCS F1.",
            "",
            "| Condition | Exact sequence | Ordered structured score | Evidence F1 |",
            "|---|---:|---:|---:|",
        ]
    )
    for condition in CONDITIONS:
        row = aggregate["by_condition"][condition]["history"]
        lines.append(
            f"| {condition} | {row['exact_accuracy']:.4f} | "
            f"{row['mean_structured_score']:.4f} | {row['evidence_f1']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Evidence, Failure Control, And Usage",
            "",
            "| Condition | Controlled failure | Evidence precision | Evidence recall | Evidence F1 | Input tokens | Output tokens | Total tokens | Tokens/question | Latency (s) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for condition in CONDITIONS:
        row = aggregate["by_condition"][condition]["overall"]
        lines.append(
            f"| {condition} | {row['controlled_failure_accuracy']:.4f} | "
            f"{row['evidence_precision']:.4f} | {row['evidence_recall']:.4f} | "
            f"{row['evidence_f1']:.4f} | {row['input_tokens']} | {row['output_tokens']} | "
            f"{row['total_tokens']} | {row['average_tokens_per_question']:.2f} | "
            f"{row['mean_latency_seconds']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Paired Comparisons",
            "",
            "Primary-family p-values use paired McNemar and Wilcoxon signed-rank tests with Holm correction. Negative differences favor the right-hand condition.",
            "",
            "| Left | Right | Scope | Exact difference | Structured difference | Exact wins L/R | Holm McNemar | Holm Wilcoxon |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparisons:
        if row["scope"] not in {"PRIMARY_OVERALL", "TASK_HISTORY"}:
            continue
        lines.append(
            f"| {row['left_condition']} | {row['right_condition']} | {row['scope']} | "
            f"{row['absolute_exact_difference_left_minus_right']:.4f} | "
            f"{row['absolute_structured_difference_left_minus_right']:.4f} | "
            f"{row['left_wins']}/{row['right_wins']} | "
            f"{row['mcnemar_holm_p_value']} | {row['wilcoxon_holm_p_value']} |"
        )
    lines.extend(
        [
            "",
            "## Output Completeness",
            "",
            f"Recorded output statuses: `{json.dumps(aggregate.get('output_status_counts', {}), sort_keys=True)}`. "
            f"Deterministic parser recoveries: {aggregate['parser_recoveries']}.",
            "",
            "## Limitations",
            "",
            f"The fixed {run_manifest.get('max_output_tokens')}-token output ceiling produced "
            f"{aggregate.get('output_status_counts', {}).get('truncated_by_output_limit', 0)} explicitly truncated responses. "
            "When malformed output occurs, the deterministic parser retains only complete emitted JSON values and discards incomplete suffixes; no value is inferred. "
            f"Remaining evaluation errors: {sum(row['errors'] for row in (aggregate['by_condition'][condition]['overall'] for condition in CONDITIONS))}.",
            "",
            "Raw email content remains external. Task alignment without an oracle task ID relies on source-message overlap. Secondary families have limited sample sizes and are exploratory.",
            "",
            "## Interpretation Boundary",
            "",
            "This is an oracle representation experiment. A positive result supports the usefulness of explicit task state, but does not establish that task state can be reconstructed automatically at the same quality.",
            "",
            "Primary families are OPEN_TASKS, CLOSED_TASKS, ACTOR_RESPONSIBILITY, REQUESTER, and TASK_HISTORY. DEADLINE, WAITING_FOR, BLOCKED_BY, and rare REJECT observations are exploratory because of limited sample sizes.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def evaluate(args: argparse.Namespace) -> int:
    inference_path = Path(args.inference_results).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else inference_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    benchmark = load_benchmark()
    questions = {row["question_id"]: row for row in benchmark["questions"]}
    task_evidence_by_key = {
        (row["pilot_id"], row["task_id"]): set(row["evidence_message_ids"])
        for row in benchmark["histories"]
    }
    all_message_ids = {row["message_id"] for row in benchmark["evidence"]}
    inference = []
    for original in read_jsonl(inference_path):
        row = dict(original)
        reparsed, parser_error = parse_model_output(str(row.get("raw_model_output") or ""))
        if parser_error is None:
            previous_error = row.get("error")
            row["parsed_output"] = reparsed
            if reparsed.get("_parser_recovery"):
                row["parser_recovery"] = {
                    "strategy": reparsed.get("_parser_recovery", "deterministic_reparse"),
                    "original_error": previous_error.get("message") if previous_error else None,
                }
            if previous_error and previous_error.get("type") == "parser_error":
                row["error"] = None
        inference.append(row)
    pairs = [(row["question_id"], row["condition"]) for row in inference]
    if len(pairs) != len(set(pairs)):
        raise ValueError("Duplicate question/condition inference record")
    unknown_ids = sorted({row["question_id"] for row in inference} - set(questions))
    if unknown_ids:
        raise ValueError(f"Unknown question IDs in inference: {unknown_ids}")
    result_conditions = {row["condition"] for row in inference}
    if result_conditions != set(CONDITIONS):
        raise ValueError(f"Expected all three conditions, found {sorted(result_conditions)}")
    condition_ids = {
        condition: {row["question_id"] for row in inference if row["condition"] == condition}
        for condition in CONDITIONS
    }
    if len({frozenset(ids) for ids in condition_ids.values()}) != 1:
        raise ValueError("Conditions do not contain exactly the same question IDs")

    scored = [
        score_result(row, questions[row["question_id"]], task_evidence_by_key, all_message_ids)
        for row in inference
    ]
    per_question_path = output_dir / "per_question_results.jsonl"
    if per_question_path.exists():
        per_question_path.unlink()
    for row in scored:
        append_jsonl(per_question_path, row)

    family_rows = []
    for condition in CONDITIONS:
        for family in sorted({row["question_family"] for row in scored}):
            subset = [
                row for row in scored if row["condition"] == condition and row["question_family"] == family
            ]
            if subset:
                family_rows.append({"condition": condition, "question_family": family, **summarize_rows(subset)})
    write_csv(output_dir / "family_results.csv", family_rows)

    by_condition: dict[str, Any] = {}
    for condition in CONDITIONS:
        condition_rows = [row for row in scored if row["condition"] == condition]
        by_condition[condition] = {
            "overall": summarize_rows(condition_rows),
            "primary": summarize_rows(
                [row for row in condition_rows if row["question_family"] in PRIMARY_FAMILIES]
            ),
            "secondary_exploratory": summarize_rows(
                [row for row in condition_rows if row["question_family"] in SECONDARY_FAMILIES]
            ),
            "history": summarize_rows(
                [row for row in condition_rows if row["question_family"] == "TASK_HISTORY"]
            ),
            "negative_controls": summarize_rows(
                [row for row in condition_rows if row["negative_control"]]
            ),
        }
    run_manifest_path = inference_path.parent / "run_manifest.json"
    run_manifest = read_json(run_manifest_path) if run_manifest_path.exists() else {}
    aggregate = {
        "schema_version": "1.0",
        "run_id": inference[0].get("run_id") if inference else None,
        "run_mode": inference[0].get("run_mode") if inference else None,
        "questions": len(condition_ids[CONDITIONS[0]]),
        "condition_question_pairs": len(scored),
        "parser_recoveries": sum(1 for row in scored if row.get("parser_recovery")),
        "output_status_counts": dict(
            sorted(Counter(row.get("output_status") or "legacy_unspecified" for row in scored).items())
        ),
        "output_status_by_condition": {
            condition: dict(
                sorted(
                    Counter(
                        row.get("output_status") or "legacy_unspecified"
                        for row in scored
                        if row["condition"] == condition
                    ).items()
                )
            )
            for condition in CONDITIONS
        },
        "primary_families": sorted(PRIMARY_FAMILIES),
        "secondary_exploratory_families": sorted(SECONDARY_FAMILIES),
        "by_condition": by_condition,
        "shared_embedding_usage": run_manifest.get("embedding_usage", {}),
    }
    write_json(output_dir / "aggregate_results.json", aggregate)

    comparisons = pairwise_comparisons(scored)
    write_csv(output_dir / "pairwise_comparisons.csv", comparisons)
    errors = {
        "total_errors": sum(1 for row in scored if row.get("error")),
        "parser_recoveries": sum(1 for row in scored if row.get("parser_recovery")),
        "output_status_counts": aggregate["output_status_counts"],
        "output_status_by_condition": aggregate["output_status_by_condition"],
        "by_condition": {
            condition: Counter(
                (row.get("error") or {}).get("type", "none")
                for row in scored
                if row["condition"] == condition and row.get("error")
            )
            for condition in CONDITIONS
        },
        "controlled_failures": {
            condition: sum(
                1
                for row in scored
                if row["condition"] == condition and row["controlled_failure_predicted"]
            )
            for condition in CONDITIONS
        },
    }
    write_json(output_dir / "error_summary.json", errors)
    write_report(
        output_dir / "experiment_report.md",
        aggregate,
        family_rows,
        comparisons,
        run_manifest,
    )
    print(f"Evaluated {len(scored)} records; outputs: {output_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministically score ISCMI 2026 RAG inference results."
    )
    parser.add_argument(
        "--inference-results",
        default=str(EXPERIMENT_DIR / "results" / "inference_results.jsonl"),
        help="Gold-free inference JSONL produced by run_experiment.py.",
    )
    parser.add_argument(
        "--output-dir",
        help="Evaluation output directory (defaults to the inference file directory).",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(evaluate(build_parser().parse_args()))
