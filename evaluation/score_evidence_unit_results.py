from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def role_by_evidence(result: dict[str, Any]) -> dict[str, str]:
    return {unit["id"]: unit.get("role") for unit in result.get("classified_units") or []}


def item_contains(item: dict[str, Any], evidence_ids: set[str], bucket: str | None = None) -> bool:
    if bucket:
        units = item.get("evidence", {}).get(bucket) or []
        return bool(evidence_ids & {unit["id"] for unit in units})
    return bool(evidence_ids & set(item.get("E") or []))


def observed_status(result: dict[str, Any], gold: dict[str, Any]) -> str:
    primary = set(gold.get("primary_evidence_ids") or [])
    contrastive = set(gold.get("contrastive_evidence_ids") or [])
    if primary:
        for item in result.get("closed_items") or []:
            if item_contains(item, primary, "primary") and (not contrastive or item_contains(item, contrastive, "contrastive")):
                return "CLOSED"
        for item in result.get("open_items") or []:
            if item_contains(item, primary, "primary"):
                return "OPEN"
    if result.get("open_items"):
        return "OPEN"
    if result.get("closed_items"):
        return "CLOSED"
    return "ABSENT"


def classify_failure(score: dict[str, Any]) -> str | None:
    if score["case_pass"]:
        return None
    scenario = score["scenario"]
    if score["observed_status"] != score["expected_status"]:
        if scenario == "D6":
            return "obligation_not_recognized"
        if scenario == "D7":
            return "browser_history_promoted_to_action"
        if scenario == "D8":
            return "closure_not_recognized_or_unlinked"
        if scenario == "D8_NONCLOSING":
            return "nonclosing_message_treated_as_closure_or_lost_open_item"
    if not score.get("role_pass"):
        return "evidence_role_mismatch"
    return "unknown"


def score_case(result: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    roles = role_by_evidence(result)
    expected_status = gold["expected_status"]
    status = observed_status(result, gold)
    primary_ids = set(gold.get("primary_evidence_ids") or [])
    contextual_ids = set(gold.get("contextual_evidence_ids") or [])
    contrastive_ids = set(gold.get("contrastive_evidence_ids") or [])
    role_expectations = {evidence_id: "primary" for evidence_id in primary_ids}
    role_expectations.update({evidence_id: "contextual" for evidence_id in contextual_ids})
    role_expectations.update({evidence_id: "contrastive" for evidence_id in contrastive_ids})
    role_checks = {
        evidence_id: {
            "expected": expected_role,
            "observed": roles.get(evidence_id),
            "pass": roles.get(evidence_id) == expected_role,
        }
        for evidence_id, expected_role in sorted(role_expectations.items())
    }
    role_pass = all(check["pass"] for check in role_checks.values())
    linking_pass = True
    if gold["scenario"] == "D8":
        linking_pass = any(
            item_contains(item, primary_ids, "primary") and item_contains(item, contrastive_ids, "contrastive")
            for item in result.get("closed_items") or []
        )
    if gold["scenario"] == "D8_NONCLOSING":
        linking_pass = not any(item_contains(item, contextual_ids, "contrastive") for item in result.get("closed_items") or [])
    d7_primary_violation = gold["scenario"] == "D7" and any(roles.get(evidence_id) == "primary" for evidence_id in contextual_ids)
    case_pass = status == expected_status and role_pass and linking_pass and not d7_primary_violation
    score = {
        "case_id": gold["case_id"],
        "seed_id": gold.get("seed_id"),
        "scenario": gold["scenario"],
        "expected_status": expected_status,
        "observed_status": status,
        "expected_presence": gold.get("expected_presence"),
        "observed_presence": status == "OPEN",
        "case_pass": case_pass,
        "role_pass": role_pass,
        "linking_pass": linking_pass,
        "d7_primary_violation": d7_primary_violation,
        "role_checks": role_checks,
        "open_item_count": len(result.get("open_items") or []),
        "closed_item_count": len(result.get("closed_items") or []),
        "classified_roles": roles,
        "failure_category": None,
    }
    score["failure_category"] = classify_failure(score)
    return score


def compute_metrics(scores: list[dict[str, Any]], gold_rows: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        by_scenario[score["scenario"]].append(score)

    def rate(rows: list[dict[str, Any]], predicate) -> float | None:
        if not rows:
            return None
        return round(sum(1 for row in rows if predicate(row)) / len(rows), 6)

    role_total = 0
    role_correct = 0
    for score in scores:
        for check in score["role_checks"].values():
            role_total += 1
            role_correct += 1 if check["pass"] else 0

    labels = ["OPEN", "CLOSED", "ABSENT"]
    confusion = {expected: {observed: 0 for observed in labels} for expected in labels}
    for score in scores:
        confusion[score["expected_status"]][score["observed_status"]] += 1

    expected_open = [score for score in scores if score["expected_status"] == "OPEN"]
    observed_open = [score for score in scores if score["observed_status"] == "OPEN"]
    true_open = [score for score in observed_open if score["expected_status"] == "OPEN"]
    precision = len(true_open) / len(observed_open) if observed_open else 1.0
    recall = len(true_open) / len(expected_open) if expected_open else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0

    by_seed: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for score in scores:
        if score["scenario"] in {"D6", "D7", "D8"}:
            by_seed[score["seed_id"]][score["scenario"]] = score
    triplets = {seed: group for seed, group in by_seed.items() if set(group) == {"D6", "D7", "D8"}}
    triplet_correct = {
        seed: group["D6"]["observed_status"] == "OPEN"
        and group["D7"]["observed_status"] == "ABSENT"
        and group["D8"]["observed_status"] == "CLOSED"
        for seed, group in triplets.items()
    }

    return {
        "record_count": len(scores),
        "D6_open_action_accuracy": rate(by_scenario["D6"], lambda row: row["observed_status"] == "OPEN"),
        "D6_action_recall": rate(by_scenario["D6"], lambda row: row["observed_status"] == "OPEN"),
        "D7_browser_only_false_action_rate": rate(by_scenario["D7"], lambda row: row["observed_status"] == "OPEN" or row["d7_primary_violation"]),
        "D7_contextual_role_accuracy": rate(by_scenario["D7"], lambda row: row["role_pass"]),
        "D8_closure_status_accuracy": rate(by_scenario["D8"], lambda row: row["observed_status"] == "CLOSED"),
        "D8_primary_contrastive_linking_accuracy": rate(by_scenario["D8"], lambda row: row["linking_pass"]),
        "D8_NONCLOSING_open_status_accuracy": rate(by_scenario["D8_NONCLOSING"], lambda row: row["observed_status"] == "OPEN"),
        "EvidenceUnit_role_accuracy": round(role_correct / role_total, 6) if role_total else None,
        "OPEN_CLOSED_ABSENT_status_accuracy": rate(scores, lambda row: row["observed_status"] == row["expected_status"]),
        "OPEN_CLOSED_ABSENT_confusion_matrix": confusion,
        "action_precision": round(precision, 6),
        "action_recall": round(recall, 6),
        "action_F1": round(f1, 6),
        "matched_triplet_consistency": {
            "complete_triplets": len(triplets),
            "correct": sum(1 for ok in triplet_correct.values() if ok),
            "rate": round(sum(1 for ok in triplet_correct.values() if ok) / len(triplets), 6) if triplets else None,
            "failed_seed_ids": [seed for seed, ok in sorted(triplet_correct.items()) if not ok],
        },
        "by_scenario_counts": {scenario: len(rows) for scenario, rows in sorted(by_scenario.items())},
        "failures": [score for score in scores if not score["case_pass"]],
        "external_llm_calls": 0,
    }


def score_results(results: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    gold_by_case = {row["case_id"]: row for row in gold_rows}
    scores = [score_case(result, gold_by_case[result["case_id"]]) for result in results]
    return scores, compute_metrics(scores, gold_rows, results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score EvidenceUnit D6-D8 action reconstruction results.")
    parser.add_argument("--results", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--scores-out", required=True)
    parser.add_argument("--metrics-out", required=True)
    args = parser.parse_args(argv)
    results = read_jsonl(Path(args.results))
    gold = read_jsonl(Path(args.gold))
    scores, metrics = score_results(results, gold)
    write_jsonl(Path(args.scores_out), scores)
    write_json(Path(args.metrics_out), metrics)
    print(f"EVIDENCE SCORE: PASS cases={len(scores)} status_accuracy={metrics['OPEN_CLOSED_ABSENT_status_accuracy']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
