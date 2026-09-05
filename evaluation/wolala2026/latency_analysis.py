from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any


def derive_latency_record(result: dict[str, Any]) -> dict[str, Any]:
    raw_timings = dict(result.get("stage_timings") or {})
    embedding_api_ms = float(raw_timings.get("embedding_api_ms", 0.0))
    candidate_retrieval_ms = float(raw_timings.get("candidate_retrieval_ms", 0.0))
    snapshot_serialization_ms = float(raw_timings.get("snapshot_serialization_ms", 0.0))
    shared_retrieval_ms = float(raw_timings.get("shared_retrieval_ms", embedding_api_ms + candidate_retrieval_ms + snapshot_serialization_ms))
    end_to_end_ms = float(result.get("end_to_end_ms", raw_timings.get("end_to_end_ms", 0.0)))
    mode_processing_ms = float(raw_timings.get("mode_processing_ms", max(0.0, end_to_end_ms - shared_retrieval_ms)))
    retry_api_call_ms = _retry_api_ms(raw_timings)
    generation_api_ms = float(raw_timings.get("generation_api_ms", 0.0))
    return {
        "case_id": result["case_id"],
        "pair_id": result.get("pair_id", result["case_id"]),
        "family": result.get("family"),
        "mode_name": result["mode_name"],
        "repetition": int(result.get("repetition", 1)),
        "raw_timing_fields": raw_timings,
        "shared_embedding_api_ms": embedding_api_ms,
        "shared_retrieval_ms": max(0.0, shared_retrieval_ms),
        "mode_processing_ms": max(0.0, mode_processing_ms),
        "user_visible_end_to_end_ms": max(0.0, shared_retrieval_ms + mode_processing_ms),
        "generation_api_call_ms": max(0.0, generation_api_ms),
        "retry_api_call_ms": max(0.0, retry_api_call_ms),
        "user_visible_external_api_ms": max(0.0, embedding_api_ms + generation_api_ms + retry_api_call_ms),
        "generation_used": not bool(result.get("generation_skipped")),
        "sample_unit": "mode_execution_record",
    }


def derive_latency_records(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [derive_latency_record(result) for result in results]


def aggregate_case_mode_medians(records: list[dict[str, Any]], *, expected_repetitions: int = 3) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[(row["case_id"], row["mode_name"])].append(row)
    output = []
    for (case_id, mode_name), rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda row: int(row.get("repetition", 1)))
        if len(rows) != expected_repetitions:
            raise ValueError(f"Expected {expected_repetitions} latency repetitions for {case_id}/{mode_name}, found {len(rows)}.")
        values = [float(row["user_visible_end_to_end_ms"]) for row in rows]
        output.append(
            {
                "case_id": case_id,
                "pair_id": rows[0].get("pair_id", case_id),
                "family": rows[0].get("family"),
                "mode_name": mode_name,
                "case_mode_latency_ms": float(median(values)),
                "repetition_values_ms": values,
                "sample_unit": "case_mode_after_repetition_median",
                "repetitions": len(rows),
                "generation_used_values": [bool(row.get("generation_used")) for row in rows],
            }
        )
    return output


def summarize_case_mode_latency(case_mode_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in case_mode_rows:
        grouped[row["mode_name"]].append(float(row["case_mode_latency_ms"]))
    return {mode: percentile_summary(values, sample_unit="case_mode_after_repetition_median") for mode, values in sorted(grouped.items())}


def percentile_summary(values: list[float], *, sample_unit: str) -> dict[str, Any]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"sample_unit": sample_unit, "count": 0, "p50_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "mad_ms": 0.0}
    p50 = _percentile(ordered, 0.50)
    return {
        "sample_unit": sample_unit,
        "count": len(ordered),
        "p50_ms": p50,
        "p95_ms": _percentile(ordered, 0.95),
        "min_ms": ordered[0],
        "max_ms": ordered[-1],
        "mad_ms": median_absolute_deviation(ordered),
    }


def stratified_latency_summaries(case_mode_rows: list[dict[str, Any]], *, cases: list[dict[str, Any]]) -> dict[str, Any]:
    expected_by_case = {case["case_id"]: case.get("expected_top_level_mode") for case in cases}
    groups: dict[str, list[float]] = {
        "expected_FULL": [],
        "expected_CFAF": [],
        "generation_used": [],
        "generation_skipped": [],
    }
    for row in case_mode_rows:
        latency = float(row["case_mode_latency_ms"])
        expected = expected_by_case.get(row["case_id"])
        if expected == "FULL":
            groups["expected_FULL"].append(latency)
        elif expected == "CFAF":
            groups["expected_CFAF"].append(latency)
        if any(row.get("generation_used_values") or []):
            groups["generation_used"].append(latency)
        else:
            groups["generation_skipped"].append(latency)
    return {name: percentile_summary(values, sample_unit="case_mode_after_repetition_median") for name, values in sorted(groups.items())}


def median_absolute_deviation(values: list[float]) -> float:
    if not values:
        return 0.0
    center = median(values)
    return float(median([abs(value - center) for value in values]))


def _percentile(ordered_values: list[float], fraction: float) -> float:
    if len(ordered_values) == 1:
        return ordered_values[0]
    position = (len(ordered_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered_values[lower]
    return ordered_values[lower] + (ordered_values[upper] - ordered_values[lower]) * (position - lower)


def _retry_api_ms(raw_timings: dict[str, Any]) -> float:
    value = raw_timings.get("retry_api_call_ms", raw_timings.get("retry_api_ms", 0.0))
    if isinstance(value, list):
        return sum(float(item) for item in value)
    return float(value or 0.0)
