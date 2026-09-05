from __future__ import annotations

import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


DOCUMENT_MODES = ["standard_rag", "governance_only_rag", "role_aware_rag"]
BOOTSTRAP_SEED = 20260817


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def metric(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": round(numerator / denominator, 6) if denominator else None,
        "wilson_95": wilson_interval(numerator, denominator),
    }


def wilson_interval(numerator: int, denominator: int, z: float = 1.959963984540054) -> dict[str, float | None]:
    if denominator == 0:
        return {"low": None, "high": None}
    p = numerator / denominator
    z2 = z * z
    denom = 1.0 + z2 / denominator
    center = (p + z2 / (2.0 * denominator)) / denom
    margin = z * math.sqrt((p * (1.0 - p) / denominator) + z2 / (4.0 * denominator * denominator)) / denom
    return {"low": round(max(0.0, center - margin), 6), "high": round(min(1.0, center + margin), 6)}


def exact_mcnemar_pvalue(b: int, c: int) -> float | None:
    n = b + c
    if n == 0:
        return None
    tail = min(b, c)
    probability = sum(math.comb(n, k) * (0.5 ** n) for k in range(tail + 1))
    return round(min(1.0, 2.0 * probability), 12)


def holm_adjust(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in rows]
    sortable = [row for row in rows if row.get("p_value") is not None]
    sortable.sort(key=lambda row: row["p_value"])
    m = len(sortable)
    running = 0.0
    for index, row in enumerate(sortable):
        adjusted = min(1.0, row["p_value"] * (m - index))
        running = max(running, adjusted)
        row["holm_p_value"] = round(running, 12)
    adjusted_by_id = {id(row): row for row in sortable}
    return [adjusted_by_id.get(id(row), row | {"holm_p_value": None}) for row in rows]


def bool_majority(values: list[bool | None]) -> bool | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return sum(1 for value in filtered if value) >= math.ceil(len(filtered) / 2)


def all_consistent(values: list[Any]) -> bool | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    first = filtered[0]
    return all(value == first for value in filtered)


def document_case_aggregates(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        grouped[(score["case_id"], score["mode"])].append(score)
    rows: list[dict[str, Any]] = []
    keys = [
        "retrieval_target_recalled_at_4",
        "permitted_answer_correct",
        "prohibited_disclosure",
        "safe_withholding",
        "generator_exposure",
        "exact_output_class_conformance",
        "behavioral_conformance",
        "expected_source_role_conformance",
        "controlled_failure_conformance",
        "generation_skipped",
    ]
    for (case_id, mode), group in sorted(grouped.items()):
        first = group[0]
        row = {
            "case_id": case_id,
            "mode": mode,
            "scenario_family": first.get("scenario_family"),
            "case_subtype": first.get("case_subtype"),
            "pair_id": first.get("pair_id"),
            "metadata": first.get("metadata") or {},
            "repetition_count": len(group),
            "all_five_behavioral_consistency": all_consistent([item.get("behavioral_conformance") for item in group]),
        }
        for key in keys:
            row[f"{key}_majority"] = bool_majority([item.get(key) for item in group])
            row[f"{key}_all_consistent"] = all_consistent([item.get(key) for item in group])
        row["generation_calls"] = sum(int(item.get("generation_calls") or 0) for item in group)
        rows.append(row)
    return rows


def document_scenario_metrics(aggregates: list[dict[str, Any]], outcome_key: str = "behavioral_conformance_majority") -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for row in aggregates:
        grouped[(row["mode"], row.get("scenario_family"), row.get("case_subtype"))].append(row)
    output: list[dict[str, Any]] = []
    for (mode, scenario, subtype), rows in sorted(grouped.items()):
        values = [row.get(outcome_key) for row in rows if row.get(outcome_key) is not None]
        output.append(
            {
                "mode": mode,
                "scenario_family": scenario,
                "case_subtype": subtype,
                "metric": outcome_key,
                **metric(sum(1 for value in values if value), len(values)),
            }
        )
    return output


def document_statistical_tests(scores: list[dict[str, Any]], bootstrap_samples: int = 10_000) -> dict[str, Any]:
    aggregates = document_case_aggregates(scores)
    primary_keys = [
        "permitted_answer_correct_majority",
        "prohibited_disclosure_majority",
        "safe_withholding_majority",
        "generator_exposure_majority",
        "exact_output_class_conformance_majority",
        "expected_source_role_conformance_majority",
        "behavioral_conformance_majority",
    ]
    comparisons = [
        ("role_aware_rag", "standard_rag"),
        ("role_aware_rag", "governance_only_rag"),
        ("governance_only_rag", "standard_rag"),
    ]
    by_case_mode = {(row["case_id"], row["mode"]): row for row in aggregates}
    case_ids = sorted({row["case_id"] for row in aggregates})
    tests: list[dict[str, Any]] = []
    for key in primary_keys:
        for mode_a, mode_b in comparisons:
            paired = []
            for case_id in case_ids:
                a = by_case_mode.get((case_id, mode_a), {}).get(key)
                b = by_case_mode.get((case_id, mode_b), {}).get(key)
                if a is None or b is None:
                    continue
                paired.append((bool(a), bool(b)))
            b_only = sum(1 for a, b in paired if a and not b)
            c_only = sum(1 for a, b in paired if b and not a)
            a_success = sum(1 for a, _ in paired if a)
            b_success = sum(1 for _, b in paired if b)
            denominator = len(paired)
            tests.append(
                {
                    "metric": key,
                    "mode_a": mode_a,
                    "mode_b": mode_b,
                    "paired_cases": denominator,
                    "mode_a_success": a_success,
                    "mode_b_success": b_success,
                    "paired_risk_difference": round((a_success - b_success) / denominator, 6) if denominator else None,
                    "mcnemar_b": b_only,
                    "mcnemar_c": c_only,
                    "p_value": exact_mcnemar_pvalue(b_only, c_only),
                }
            )
    return {
        "case_level_mcnemar_holm": holm_adjust(tests),
        "clustered_bootstrap": clustered_bootstrap(scores, bootstrap_samples),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_samples": bootstrap_samples,
    }


def clustered_bootstrap(scores: list[dict[str, Any]], samples: int = 10_000) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        grouped[score["case_id"]].append(score)
    case_ids = sorted(grouped)
    if not case_ids:
        return []
    comparisons = [("role_aware_rag", "standard_rag"), ("role_aware_rag", "governance_only_rag")]
    keys = ["behavioral_conformance", "permitted_answer_correct", "prohibited_disclosure", "generator_exposure"]
    rng = random.Random(BOOTSTRAP_SEED)
    output: list[dict[str, Any]] = []
    for key in keys:
        for mode_a, mode_b in comparisons:
            diffs: list[float] = []
            for _ in range(samples):
                sampled = [grouped[rng.choice(case_ids)] for _ in case_ids]
                a_values: list[bool] = []
                b_values: list[bool] = []
                for group in sampled:
                    by_mode: dict[str, list[bool]] = defaultdict(list)
                    for row in group:
                        if row.get(key) is not None:
                            by_mode[row["mode"]].append(bool(row[key]))
                    if by_mode.get(mode_a) and by_mode.get(mode_b):
                        a_values.append(sum(by_mode[mode_a]) / len(by_mode[mode_a]) >= 0.5)
                        b_values.append(sum(by_mode[mode_b]) / len(by_mode[mode_b]) >= 0.5)
                if a_values:
                    diffs.append((sum(a_values) - sum(b_values)) / len(a_values))
            if diffs:
                diffs.sort()
                low = diffs[int(0.025 * (len(diffs) - 1))]
                high = diffs[int(0.975 * (len(diffs) - 1))]
                output.append(
                    {
                        "metric": key,
                        "mode_a": mode_a,
                        "mode_b": mode_b,
                        "samples": len(diffs),
                        "mean_difference": round(statistics.mean(diffs), 6),
                        "ci_low": round(low, 6),
                        "ci_high": round(high, 6),
                    }
                )
    return output


def evidence_case_aggregates(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        grouped[score["case_id"]].append(score)
    rows: list[dict[str, Any]] = []
    for case_id, group in sorted(grouped.items()):
        first = group[0]
        statuses = [item.get("observed_status") for item in group]
        status_counter = Counter(statuses)
        observed_majority = status_counter.most_common(1)[0][0] if status_counter else None
        case_pass_values = [item.get("case_pass") for item in group]
        rows.append(
            {
                "case_id": case_id,
                "seed_id": first.get("seed_id"),
                "scenario": first.get("scenario"),
                "expected_status": first.get("expected_status"),
                "observed_status_majority": observed_majority,
                "case_pass_majority": bool_majority(case_pass_values),
                "case_pass_all_consistent": all_consistent(case_pass_values),
                "status_all_consistent": all_consistent(statuses),
                "role_pass_majority": bool_majority([item.get("role_pass") for item in group]),
                "linking_pass_majority": bool_majority([item.get("linking_pass") for item in group]),
                "repetition_count": len(group),
                "failure_categories": sorted({item.get("failure_category") for item in group if item.get("failure_category")}),
            }
        )
    return rows


def evidence_determinism(aggregates: list[dict[str, Any]]) -> dict[str, Any]:
    return metric(sum(1 for row in aggregates if row.get("status_all_consistent") and row.get("case_pass_all_consistent")), len(aggregates)) | {
        "status_consistent": metric(sum(1 for row in aggregates if row.get("status_all_consistent")), len(aggregates)),
        "case_pass_consistent": metric(sum(1 for row in aggregates if row.get("case_pass_all_consistent")), len(aggregates)),
    }


def triplet_results(evidence_aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_seed: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in evidence_aggregates:
        if row.get("scenario") in {"D6", "D7", "D8"}:
            by_seed[row["seed_id"]][row["scenario"]] = row
    rows: list[dict[str, Any]] = []
    for seed_id, group in sorted(by_seed.items()):
        if set(group) != {"D6", "D7", "D8"}:
            continue
        rows.append(
            {
                "seed_id": seed_id,
                "d6_case_id": group["D6"]["case_id"],
                "d7_case_id": group["D7"]["case_id"],
                "d8_case_id": group["D8"]["case_id"],
                "d6_open": group["D6"].get("observed_status_majority") == "OPEN",
                "d7_absent": group["D7"].get("observed_status_majority") == "ABSENT",
                "d8_closed": group["D8"].get("observed_status_majority") == "CLOSED",
                "triplet_pass": group["D6"].get("observed_status_majority") == "OPEN"
                and group["D7"].get("observed_status_majority") == "ABSENT"
                and group["D8"].get("observed_status_majority") == "CLOSED",
            }
        )
    return rows


def summarize_api_usage(document_records: list[dict[str, Any]], evidence_records: list[dict[str, Any]]) -> dict[str, Any]:
    by_mode: dict[str, dict[str, Any]] = defaultdict(lambda: {"record_count": 0, "generation_calls": 0, "generation_skipped": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "embedding_calls": 0, "retries": 0, "errors": 0})
    for record in document_records:
        usage = record.get("api_usage") or {}
        row = by_mode[record.get("mode") or "unknown"]
        generation_calls = int(usage.get("generation_calls") or 0)
        row["record_count"] += 1
        row["generation_calls"] += generation_calls
        row["generation_skipped"] += 1 if generation_calls == 0 else 0
        row["input_tokens"] += int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        row["output_tokens"] += int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        row["total_tokens"] += int(usage.get("total_tokens") or 0)
        row["embedding_calls"] += int(usage.get("embedding_calls") or 0)
        row["retries"] += int(usage.get("retries") or 0)
        row["errors"] += len(usage.get("errors") or [])
    by_mode["role_aware_action_reconstruction"]["record_count"] += len(evidence_records)
    return {
        "by_mode": dict(sorted(by_mode.items())),
        "totals": {
            "record_count": sum(row["record_count"] for row in by_mode.values()),
            "generation_calls": sum(row["generation_calls"] for row in by_mode.values()),
            "generation_skipped": sum(row["generation_skipped"] for row in by_mode.values()),
            "input_tokens": sum(row["input_tokens"] for row in by_mode.values()),
            "output_tokens": sum(row["output_tokens"] for row in by_mode.values()),
            "total_tokens": sum(row["total_tokens"] for row in by_mode.values()),
            "embedding_calls": sum(row["embedding_calls"] for row in by_mode.values()),
            "retries": sum(row["retries"] for row in by_mode.values()),
            "errors": sum(row["errors"] for row in by_mode.values()),
        },
    }


def latency_summary(document_records: list[dict[str, Any]], evidence_records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "not_recorded",
        "document_record_count": len(document_records),
        "evidence_record_count": len(evidence_records),
        "note": "The current production wrappers do not expose per-call latency; record counts are retained for audit.",
    }


def retry_summary(api_usage: dict[str, Any]) -> dict[str, Any]:
    totals = api_usage.get("totals") or {}
    return {
        "retries": totals.get("retries", 0),
        "errors": totals.get("errors", 0),
        "by_mode": {mode: {"retries": row.get("retries", 0), "errors": row.get("errors", 0)} for mode, row in (api_usage.get("by_mode") or {}).items()},
    }


def failure_rows(document_scores: list[dict[str, Any]], evidence_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in document_scores:
        if not row.get("behavioral_conformance"):
            rows.append(
                {
                    "phase": "document_rag",
                    "case_id": row.get("case_id"),
                    "scenario": row.get("scenario_family"),
                    "mode": row.get("mode"),
                    "repetition": row.get("repetition"),
                    "expected_class": row.get("expected_behavioral_class"),
                    "observed_class": row.get("output_mode"),
                    "expected_roles": row.get("expected_source_roles"),
                    "observed_roles": row.get("observed_source_roles"),
                    "retrieved_candidate_ids": row.get("retrieved_document_aliases"),
                    "generation_skipped": row.get("generation_skipped"),
                    "prohibited_disclosure": row.get("prohibited_disclosure"),
                    "generator_exposure": row.get("generator_exposure"),
                    "failure_category": document_failure_category(row),
                }
            )
    for row in evidence_scores:
        if not row.get("case_pass"):
            rows.append(
                {
                    "phase": "evidence_unit",
                    "case_id": row.get("case_id"),
                    "seed_id": row.get("seed_id"),
                    "scenario": row.get("scenario"),
                    "mode": "role_aware_action_reconstruction",
                    "repetition": row.get("clean_repetition"),
                    "expected_status": row.get("expected_status"),
                    "observed_status": row.get("observed_status"),
                    "failure_category": row.get("failure_category"),
                }
            )
    return rows


def document_failure_category(row: dict[str, Any]) -> str:
    if row.get("retrieval_target_recalled_at_4") is False:
        return "retrieval miss"
    if row.get("prohibited_disclosure"):
        return "forbidden disclosure"
    if row.get("generator_exposure"):
        return "generator exposure"
    if row.get("permitted_answer_correct") is False:
        return "wrong answer"
    if row.get("exact_output_class_conformance") is False:
        return "wrong output class"
    if row.get("expected_source_role_conformance") is False:
        return "wrong source role"
    if (row.get("api_usage") or {}).get("errors"):
        return "API failure"
    return "policy failure"


def write_latex_tables(publication_dir: Path, document_metrics: dict[str, Any], scenario_metrics: list[dict[str, Any]], evidence_metrics: dict[str, Any], triplets: list[dict[str, Any]], api_usage: dict[str, Any], benchmark_composition: dict[str, Any], statistical_tests: dict[str, Any]) -> None:
    tables = publication_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    write_table(tables / "document_overall_metrics.tex", ["Mode", "Permitted", "Disclosure", "Exposure", "Safe", "Exact", "Roles"], [
        [
            mode,
            fmt_metric(row.get("permitted_answer_accuracy")),
            fmt_metric(row.get("prohibited_disclosure_rate")),
            fmt_metric(row.get("generator_exposure_rate")),
            fmt_metric(row.get("safe_withholding_rate")),
            fmt_metric(row.get("exact_output_class_conformance")),
            fmt_metric(row.get("source_role_conformance")),
        ]
        for mode, row in sorted((document_metrics.get("by_mode") or {}).items())
    ])
    write_table(tables / "document_scenario_metrics.tex", ["Mode", "Scenario", "Subtype", "Success"], [
        [row["mode"], str(row.get("scenario_family")), str(row.get("case_subtype") or ""), fmt_metric(row)]
        for row in scenario_metrics
    ])
    test_rows = statistical_tests.get("case_level_mcnemar_holm") or []
    write_table(tables / "document_statistical_tests.tex", ["Metric", "A", "B", "Diff", "p", "Holm p"], [
        [row["metric"], row["mode_a"], row["mode_b"], str(row.get("paired_risk_difference")), str(row.get("p_value")), str(row.get("holm_p_value"))]
        for row in test_rows
    ])
    write_table(tables / "evidence_metrics.tex", ["Metric", "Value"], [[key, str(value)] for key, value in sorted(evidence_metrics.items()) if key != "failures"])
    write_table(tables / "evidence_closure_subtypes.tex", ["Subtype", "Count"], [[key, str(value)] for key, value in sorted((benchmark_composition.get("d8_closure_distribution") or {}).items())])
    write_table(tables / "triplet_consistency.tex", ["Metric", "Value"], [["complete_triplets", str(len(triplets))], ["triplet_pass", fmt_metric(metric(sum(1 for row in triplets if row.get("triplet_pass")), len(triplets)))]])
    write_table(tables / "api_usage.tex", ["Mode", "Generation", "Skipped", "Tokens", "Retries", "Errors"], [
        [mode, str(row.get("generation_calls")), str(row.get("generation_skipped")), str(row.get("total_tokens")), str(row.get("retries")), str(row.get("errors"))]
        for mode, row in sorted((api_usage.get("by_mode") or {}).items())
    ])
    composition_rows = []
    for key, value in sorted(benchmark_composition.items()):
        if isinstance(value, dict):
            composition_rows.extend([[f"{key}:{inner}", str(count)] for inner, count in sorted(value.items())])
        else:
            composition_rows.append([key, str(value)])
    write_table(tables / "benchmark_composition.tex", ["Item", "Value"], composition_rows)


def write_table(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    align = "l" * len(headers)
    lines = [
        "\\begin{tabular}{" + align + "}",
        "\\hline",
        " & ".join(escape_tex(item) for item in headers) + r" \\",
        "\\hline",
    ]
    for row in rows:
        lines.append(" & ".join(escape_tex(str(item)) for item in row) + r" \\")
    lines.extend(["\\hline", "\\end{tabular}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def escape_tex(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("_", "\\_")
        .replace("%", "\\%")
        .replace("&", "\\&")
        .replace("#", "\\#")
        .replace("{", "\\{")
        .replace("}", "\\}")
    )


def fmt_metric(value: Any) -> str:
    if isinstance(value, dict) and "numerator" in value:
        rate = value.get("rate")
        return f"{value['numerator']}/{value['denominator']} ({rate})"
    return str(value)
