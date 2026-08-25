"""Validated loader for the versioned controlled-failure configuration."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parent / "config" / "controlled_failure_v3.json"
REQUIRED_OUTPUT_CLASSES = {
    "FULL_ANSWER", "CONSTRAINED_ANSWER", "AGGREGATE_RESULT", "METADATA_ONLY",
    "CLARIFICATION", "REFUSE_PERMISSION", "REFUSE_INSUFFICIENT_EVIDENCE",
    "REFUSE_NO_MATCH", "REFUSE_AGGREGATION_THRESHOLD", "REFUSE_CONFLICT",
}


@lru_cache(maxsize=1)
def load_controlled_failure_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    missing = REQUIRED_OUTPUT_CLASSES - set(config.get("output_classes", []))
    if missing:
        raise RuntimeError(f"Controlled-failure config is missing output classes: {sorted(missing)}")
    thresholds = config.get("thresholds", {})
    if int(thresholds.get("aggregate_k", 0)) < 2:
        raise RuntimeError("Controlled-failure aggregate_k must be at least 2")
    minimum_support = float(thresholds.get("minimum_support_score", -1))
    if not 0.0 <= minimum_support <= 1.0:
        raise RuntimeError("Controlled-failure minimum_support_score must be within [0, 1]")
    if not config.get("precedence") or not config.get("config_version"):
        raise RuntimeError("Controlled-failure precedence and config_version are required")
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return config | {"config_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
