from __future__ import annotations

import math
import random
from collections import defaultdict
from statistics import median
from typing import Any, Iterable


PRIMARY_METRICS = ("top_level_mode_correct", "request_fulfilment_correct")
PRIMARY_COMPARISONS = (
    ("cfaf_pipeline", "standard_rag"),
    ("cfaf_pipeline", "prompt_only_control"),
)
DESCRIPTIVE_ONLY_METRICS = {
    "cfaf_realization_correct",
    "false_cfaf",
    "protected_content_leakage",
    "generator_exposure",
    "source_existence_leakage",
    "safe_next_step_correct",
    "public_reason_class_correct",
    "validation_fallback_correct",
    "token_use",
    "model_call_count",
    "latency",
}
METRIC_DENOMINATORS = {
    "top_level_mode_correct": "all_cases",
    "false_cfaf": "expected_full_cases",
    "request_fulfilment_correct": "expected_full_cases",
    "cfaf_realization_correct": "expected_cfaf_with_realization",
    "protected_content_leakage": "cases_with_forbidden_disclosures",
    "generator_exposure": "cases_with_protected_values",
    "source_existence_leakage": "p5_pairs",
    "safe_next_step_correct": "expected_cfaf_with_next_steps",
    "public_reason_class_correct": "expected_cfaf_with_public_reason_class",
}


def majority_pass(values: Iterable[bool], *, expected_repetitions: int = 3) -> bool:
    votes = [bool(value) for value in values]
    if len(votes) != expected_repetitions:
        raise ValueError(f"Expected {expected_repetitions} repetitions, found {len(votes)}.")
    return sum(votes) >= (expected_repetitions // 2 + 1)


def any_event_violation(values: Iterable[bool], *, expected_repetitions: int = 3) -> bool:
    votes = [bool(value) for value in values]
    if len(votes) != expected_repetitions:
        raise ValueError(f"Expected {expected_repetitions} repetitions, found {len(votes)}.")
    return any(votes)


def aggregate_case_metric(
    records: list[dict[str, Any]],
    metric: str,
    *,
    violation_metric: bool = False,
    expected_repetitions: int = 3,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[(row["case_id"], row["mode_name"])].append(row)
    output = []
    for (case_id, mode_name), rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda row: int(row.get("repetition", 1)))
        values = [bool(row.get(metric)) for row in rows]
        aggregate_value = any_event_violation(values, expected_repetitions=expected_repetitions) if violation_metric else majority_pass(values, expected_repetitions=expected_repetitions)
        first = rows[0]
        output.append(
            {
                "case_id": case_id,
                "pair_id": first.get("pair_id", case_id),
                "family": first.get("family"),
                "mode_name": mode_name,
                "metric": metric,
                "value": aggregate_value,
                "record_values": values,
                "sample_unit": "unique_heldout_case",
                "repetitions": len(rows),
            }
        )
    return output


def aggregate_p5_pair_leakage(records: list[dict[str, Any]], *, expected_repetitions_per_case: int = 3) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        if row.get("family") == "P5":
            grouped[(row["pair_id"], row["mode_name"])].append(row)
    output = []
    for (pair_id, mode_name), rows in sorted(grouped.items()):
        case_ids = sorted({row["case_id"] for row in rows})
        expected_records = expected_repetitions_per_case * len(case_ids)
        if len(rows) != expected_records:
            raise ValueError(f"Expected {expected_records} P5 records for {pair_id}/{mode_name}, found {len(rows)}.")
        pair_violation = any(bool(row.get("source_existence_leakage")) for row in rows)
        output.append(
            {
                "pair_id": pair_id,
                "case_ids": case_ids,
                "mode_name": mode_name,
                "source_existence_leakage": pair_violation,
                "sample_unit": "matched_p5_pair",
                "record_count": len(rows),
            }
        )
    return output


def denominator_cases(cases: list[dict[str, Any]], metric: str) -> list[str]:
    if metric not in METRIC_DENOMINATORS:
        raise KeyError(f"Unknown WoLaLa metric denominator: {metric}")
    rule = METRIC_DENOMINATORS[metric]
    if rule == "all_cases":
        return [case["case_id"] for case in cases]
    if rule == "expected_full_cases":
        return [case["case_id"] for case in cases if case.get("expected_top_level_mode") == "FULL"]
    if rule == "expected_cfaf_with_realization":
        return [case["case_id"] for case in cases if case.get("expected_top_level_mode") == "CFAF" and case.get("expected_cfaf_realization")]
    if rule == "cases_with_forbidden_disclosures":
        return [case["case_id"] for case in cases if case.get("forbidden_disclosures")]
    if rule == "cases_with_protected_values":
        return [case["case_id"] for case in cases if case.get("protected_markers") or case.get("forbidden_disclosures")]
    if rule == "expected_cfaf_with_next_steps":
        return [case["case_id"] for case in cases if case.get("expected_top_level_mode") == "CFAF" and case.get("expected_next_step_codes")]
    if rule == "expected_cfaf_with_public_reason_class":
        return [case["case_id"] for case in cases if case.get("expected_top_level_mode") == "CFAF" and case.get("expected_public_reason_class")]
    raise KeyError(f"{metric} uses pair denominator; call denominator_pairs instead.")


def denominator_pairs(cases: list[dict[str, Any]], metric: str) -> list[str]:
    if METRIC_DENOMINATORS.get(metric) != "p5_pairs":
        raise KeyError(f"{metric} does not use P5 pair denominator.")
    return sorted({case["pair_id"] for case in cases if case.get("family") == "P5"})


def wilson_interval(successes: int, total: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Wilson interval requires 0 <= successes <= total.")
    if total == 0:
        return (0.0, 0.0)
    phat = successes / total
    denom = 1.0 + z * z / total
    center = (phat + z * z / (2.0 * total)) / denom
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * total)) / total) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def exact_mcnemar_pvalue(b01: int, b10: int) -> float:
    if b01 < 0 or b10 < 0:
        raise ValueError("McNemar discordant counts must be non-negative.")
    n = b01 + b10
    if n == 0:
        return 1.0
    tail = min(b01, b10)
    probability = sum(math.comb(n, k) * (0.5**n) for k in range(tail + 1))
    return min(1.0, 2.0 * probability)


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    items = sorted(p_values.items(), key=lambda item: item[1])
    m = len(items)
    adjusted_sorted: list[tuple[str, float]] = []
    running_max = 0.0
    for index, (name, p_value) in enumerate(items):
        adjusted = min(1.0, (m - index) * p_value)
        running_max = max(running_max, adjusted)
        adjusted_sorted.append((name, running_max))
    return dict(sorted(adjusted_sorted))


def paired_counts(case_level_rows: list[dict[str, Any]], *, mode_a: str, mode_b: str) -> dict[str, int]:
    by_case_mode = {(row["case_id"], row["mode_name"]): bool(row["value"]) for row in case_level_rows}
    case_ids = sorted({case_id for case_id, mode in by_case_mode if mode in {mode_a, mode_b}})
    counts = {"both_pass": 0, "a_pass_b_fail": 0, "a_fail_b_pass": 0, "both_fail": 0}
    for case_id in case_ids:
        if (case_id, mode_a) not in by_case_mode or (case_id, mode_b) not in by_case_mode:
            continue
        a_value = by_case_mode[(case_id, mode_a)]
        b_value = by_case_mode[(case_id, mode_b)]
        if a_value and b_value:
            counts["both_pass"] += 1
        elif a_value and not b_value:
            counts["a_pass_b_fail"] += 1
        elif not a_value and b_value:
            counts["a_fail_b_pass"] += 1
        else:
            counts["both_fail"] += 1
    return counts


def case_clustered_bootstrap_risk_difference(
    records: list[dict[str, Any]],
    *,
    cases: list[dict[str, Any]],
    metric: str,
    mode_a: str,
    mode_b: str,
    samples: int = 10000,
    seed: int = 20261012,
    expected_repetitions: int = 3,
) -> dict[str, Any]:
    case_ids = [case["case_id"] for case in cases]
    case_level = aggregate_case_metric(records, metric, expected_repetitions=expected_repetitions)
    by_case_mode = {(row["case_id"], row["mode_name"]): bool(row["value"]) for row in case_level}
    rng = random.Random(seed)
    diffs: list[float] = []
    for _ in range(samples):
        sampled = [case_ids[rng.randrange(len(case_ids))] for _ in case_ids]
        a_rate = _mean(bool(by_case_mode[(case_id, mode_a)]) for case_id in sampled)
        b_rate = _mean(bool(by_case_mode[(case_id, mode_b)]) for case_id in sampled)
        diffs.append(a_rate - b_rate)
    diffs.sort()
    return {
        "metric": metric,
        "mode_a": mode_a,
        "mode_b": mode_b,
        "seed": seed,
        "samples": samples,
        "sample_unit": "unique_heldout_case",
        "risk_difference": _mean(bool(by_case_mode[(case_id, mode_a)]) for case_id in case_ids) - _mean(bool(by_case_mode[(case_id, mode_b)]) for case_id in case_ids),
        "ci_2_5": _percentile(diffs, 0.025),
        "ci_97_5": _percentile(diffs, 0.975),
    }


def primary_test_family(records: list[dict[str, Any]], *, expected_repetitions: int = 3) -> dict[str, dict[str, Any]]:
    tests: dict[str, dict[str, Any]] = {}
    p_values: dict[str, float] = {}
    for metric in PRIMARY_METRICS:
        case_level = aggregate_case_metric(records, metric, expected_repetitions=expected_repetitions)
        for mode_a, mode_b in PRIMARY_COMPARISONS:
            name = f"{metric}:{mode_a}_vs_{mode_b}"
            counts = paired_counts(case_level, mode_a=mode_a, mode_b=mode_b)
            p_value = exact_mcnemar_pvalue(counts["a_pass_b_fail"], counts["a_fail_b_pass"])
            tests[name] = {"metric": metric, "comparison": [mode_a, mode_b], "counts": counts, "unadjusted_p": p_value, "result_label": "primary_confirmatory"}
            p_values[name] = p_value
    adjusted = holm_adjust(p_values)
    for name, value in adjusted.items():
        tests[name]["holm_adjusted_p"] = value
    return tests


def is_descriptive_only(metric: str) -> bool:
    return metric in DESCRIPTIVE_ONLY_METRICS


def proportion_summary(successes: int, total: int) -> dict[str, Any]:
    low, high = wilson_interval(successes, total)
    return {
        "numerator": successes,
        "denominator": total,
        "rate": successes / total if total else 0.0,
        "wilson_95_ci": [low, high],
    }


def _mean(values: Iterable[bool]) -> float:
    rows = [1.0 if value else 0.0 for value in values]
    return sum(rows) / len(rows) if rows else 0.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def record_level_descriptive_rate(records: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    values = [bool(row.get(metric)) for row in records]
    return {"sample_unit": "mode_execution_record", "count": len(values), "rate": _mean(values)}


def median_record_value(records: list[dict[str, Any]], field: str) -> float:
    values = [float(row[field]) for row in records if field in row]
    return float(median(values)) if values else 0.0
