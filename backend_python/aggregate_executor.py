"""Deterministic, non-disclosing aggregate execution.

Only numeric contributions whose policy decision is Full or Aggregate may be
used. Individual values and identifiers are intentionally absent from every
public field, generator context, citation, and trace returned by this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

import relevance


AGGREGATE_CONFIG_VERSION = "infocom-aggregate-v1"
AGGREGATE_RESULT = "AGGREGATE_RESULT"
REFUSE_AGGREGATION_THRESHOLD = "REFUSE_AGGREGATION_THRESHOLD"
REASON_THRESHOLD_MET = "aggregate_threshold_satisfied"
REASON_THRESHOLD_NOT_MET = "aggregation_threshold_not_met"


@dataclass(frozen=True)
class AggregateConfig:
    k_threshold: int = 3
    operation: str = "mean"
    config_version: str = AGGREGATE_CONFIG_VERSION

    def __post_init__(self) -> None:
        if self.k_threshold < 2:
            raise ValueError("k_threshold must be at least 2")
        if self.operation not in {"mean", "sum", "count"}:
            raise ValueError("operation must be mean, sum, or count")

    @property
    def config_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AggregateContribution:
    source_id: str
    contributor_id: str
    value: float

    def __post_init__(self) -> None:
        if not self.source_id or not self.contributor_id:
            raise ValueError("source_id and contributor_id are required")
        if not math.isfinite(float(self.value)):
            raise ValueError("aggregate contribution value must be finite")


def _public_refusal(config: AggregateConfig) -> dict[str, Any]:
    return {
        "output_class": REFUSE_AGGREGATION_THRESHOLD,
        "reason_code": REASON_THRESHOLD_NOT_MET,
        "safe_output": "A governed aggregate result is unavailable for this request.",
        "aggregate": None,
        "generator_context": "",
        "citations": [],
        "public_trace": {
            "executor_version": config.config_version,
            "config_hash": config.config_hash,
            "threshold_satisfied": False,
        },
    }


def execute_aggregate(
    contributions: Iterable[AggregateContribution],
    policy_decisions: Mapping[str, str],
    config: AggregateConfig = AggregateConfig(),
) -> dict[str, Any]:
    """Execute one safe aggregate after policy filtering and contributor dedup."""

    eligible: dict[str, AggregateContribution] = {}
    excluded_count = 0
    for item in sorted(contributions, key=lambda value: (value.contributor_id, value.source_id)):
        decision = policy_decisions.get(item.source_id, relevance.USE_DENY)
        if decision not in {relevance.USE_FULL, relevance.USE_AGGREGATE}:
            excluded_count += 1
            continue
        eligible.setdefault(item.contributor_id, item)

    if len(eligible) < config.k_threshold:
        return _public_refusal(config)

    values = [float(item.value) for item in eligible.values()]
    if config.operation == "mean":
        result_value = statistics.fmean(values)
    elif config.operation == "sum":
        result_value = sum(values)
    else:
        result_value = float(len(values))
    rounded = round(result_value, 6)
    aggregate = {
        "operation": config.operation,
        "value": rounded,
        "contributor_count": len(values),
        "k_threshold": config.k_threshold,
    }
    generator_context = json.dumps(
        {"governed_aggregate": aggregate}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "output_class": AGGREGATE_RESULT,
        "reason_code": REASON_THRESHOLD_MET,
        "safe_output": (
            f"Governed aggregate {config.operation}: {rounded:g} "
            f"across {len(values)} distinct contributors."
        ),
        "aggregate": aggregate,
        "generator_context": generator_context,
        "citations": [],
        "public_trace": {
            "executor_version": config.config_version,
            "config_hash": config.config_hash,
            "threshold_satisfied": True,
            "contributor_count": len(values),
            "deduplicated_count": len(values),
            "excluded_by_policy": excluded_count,
        },
    }
