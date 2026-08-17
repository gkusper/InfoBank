from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters import smoke_test_adapters
from .data_readiness import write_data_inventory
from .labels import TopLevelMode, json_safe
from .pipeline import assert_pipeline_invariants, latency_summary, run_pipeline, write_json
from .yaml_util import load_yaml_subset


PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
DEFAULT_CONFIG = PACKAGE_DIR / "smoke_config.yaml"


def load_smoke_cases(path: str | Path = DEFAULT_CONFIG) -> list[dict[str, Any]]:
    data = load_yaml_subset(path)
    return list(data.get("cases") or [])


def run_smoke(config_path: str | Path = DEFAULT_CONFIG, output_dir: str | Path = PACKAGE_DIR) -> dict[str, Any]:
    cases = load_smoke_cases(config_path)
    output = Path(output_dir)
    states = []
    records = []
    adapter_smoke = smoke_test_adapters(cases[0]) if cases else []
    for case in cases:
        state = run_pipeline(case)
        assert_pipeline_invariants(state)
        states.append(state)
        record = _smoke_record(case, state)
        records.append(record)
    failures = [record for record in records if not record["passed"]]
    payload = {
        "schema_version": "wolala2026-smoke-results-v1",
        "case_count": len(records),
        "passed": not failures,
        "failures": failures,
        "records": records,
        "latency_summary": latency_summary(states),
        "adapter_smoke": adapter_smoke,
        "full_benchmark_executed": False,
        "paid_api_calls_executed": False,
    }
    write_json(output / "smoke_results.json", payload)
    if states:
        example_state = next((state for state in states if state.case_id == "S4B_CONTENT_WITH_METADATA_ACCESS"), states[0])
        write_json(output / "example_internal_trace.json", example_state.internal_trace)
        write_json(
            output / "example_public_response.json",
            {
                "case_id": example_state.case_id,
                "response": example_state.final_response,
                "public_trace": example_state.public_trace,
            },
        )
    write_data_inventory(REPO_ROOT, output / "data_inventory.json")
    if failures:
        raise AssertionError(f"WoLaLa smoke failures: {[failure['case_id'] for failure in failures]}")
    return payload


def _smoke_record(case: dict[str, Any], state: Any) -> dict[str, Any]:
    mode = state.mode_decision.mode.value if state.mode_decision else None
    reason_class = state.mode_decision.reason_class.value if state.mode_decision and state.mode_decision.reason_class else None
    realization = state.mode_decision.cfaf_realization.value if state.mode_decision and state.mode_decision.cfaf_realization else None
    checks = {
        "mode": mode == case.get("expected_top_level_mode"),
        "internal_reason_class": reason_class == case.get("expected_internal_reason_class"),
        "cfaf_realization": (case.get("expected_cfaf_realization") is None or realization == case.get("expected_cfaf_realization")),
        "validation_status": state.validation.status.value == case.get("expected_validation_status", "PASS"),
        "fallback_used": state.validation.fallback_used == bool(case.get("expected_fallback_used", False)),
    }
    if state.response_contract and state.response_contract.public_reason_class:
        checks["public_reason_class"] = state.response_contract.public_reason_class.value == case.get("expected_public_reason_class")
    elif case.get("expected_public_reason_class") is None:
        checks["public_reason_class"] = True
    else:
        checks["public_reason_class"] = False
    if mode == TopLevelMode.FULL.value and not case.get("force_invalid_generation"):
        checks["gold_marker"] = case.get("gold_answer", "") in (state.final_response or "")
    return {
        "case_id": case["case_id"],
        "description": case.get("description"),
        "expected_top_level_mode": case.get("expected_top_level_mode"),
        "observed_top_level_mode": mode,
        "observed_reason_class": reason_class,
        "observed_public_reason_class": state.response_contract.public_reason_class.value if state.response_contract and state.response_contract.public_reason_class else None,
        "observed_cfaf_realization": realization,
        "validation_status": state.validation.status.value if state.validation else None,
        "fallback_used": state.validation.fallback_used if state.validation else None,
        "generation_skipped": state.generation_skipped,
        "model_call_count": state.model_call_count,
        "stage_timings": state.stage_timings,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic WoLaLa 2026 CFAF smoke tests.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to smoke_config.yaml.")
    parser.add_argument("--output-dir", default=str(PACKAGE_DIR), help="Directory for smoke result artifacts.")
    args = parser.parse_args()
    payload = run_smoke(args.config, args.output_dir)
    print(json.dumps({"passed": payload["passed"], "case_count": payload["case_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
