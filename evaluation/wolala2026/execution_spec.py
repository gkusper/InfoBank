from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters import ALL_MODES
from .common import read_json
from .pilot_data import HELDOUT_DATASET
from .retry_policy import retry_policy_summary


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_EXECUTION_SPEC_PATH = PACKAGE_DIR / "HELDOUT_EXECUTION_SPEC_v2.json"
SPEC_SCHEMA_VERSION = "wolala-heldout-execution-spec-v2"


def load_execution_spec(path: str | Path | dict[str, Any] | None = None) -> dict[str, Any]:
    if path is None:
        path = DEFAULT_EXECUTION_SPEC_PATH
    if isinstance(path, dict):
        return dict(path)
    return read_json(path)


def validate_execution_spec(
    spec: dict[str, Any],
    *,
    cases: list[dict[str, Any]] | None = None,
    modes: list[str] | None = None,
    repetitions: int | None = None,
    max_mode_executions: int | None = None,
    max_embedding_calls: int | None = None,
    max_generation_calls: int | None = None,
    max_total_external_calls: int | None = None,
    plan_only: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    expected = _expected_core_values()
    for key, value in expected.items():
        if spec.get(key) != value:
            errors.append(f"{key} expected {value!r}, found {spec.get(key)!r}")
    if spec.get("schema_version") != SPEC_SCHEMA_VERSION:
        errors.append(f"schema_version expected {SPEC_SCHEMA_VERSION!r}, found {spec.get('schema_version')!r}")
    if spec.get("modes") != ALL_MODES:
        errors.append(f"modes expected {ALL_MODES!r}, found {spec.get('modes')!r}")
    if modes is not None and list(modes) != list(spec["modes"]):
        errors.append(f"requested modes {modes!r} do not match execution spec modes {spec['modes']!r}")
    if repetitions is not None and repetitions != int(spec["repetitions"]):
        errors.append(f"requested repetitions {repetitions!r} do not match execution spec repetitions {spec['repetitions']!r}")
    _validate_requested_cap("max_mode_executions", max_mode_executions, spec, errors)
    _validate_requested_cap("max_embedding_calls", max_embedding_calls, spec, errors)
    _validate_requested_cap("max_generation_calls", max_generation_calls, spec, errors)
    _validate_requested_cap("max_total_external_calls", max_total_external_calls, spec, errors)
    if cases is not None:
        case_ids = [case["case_id"] for case in cases]
        if len(case_ids) != int(spec["cases"]):
            errors.append(f"case count expected {spec['cases']}, found {len(case_ids)}")
        if not all(case_id.startswith("HELD_") for case_id in case_ids):
            errors.append("held-out spec may validate only HELD_* case IDs")
    planned_mode_executions = int(spec["cases"]) * len(spec["modes"]) * int(spec["repetitions"])
    planned_external_without_retries = int(spec["planned_unique_embedding_requests"]) + int(spec["planned_generation_requests_maximum"])
    if planned_mode_executions != int(spec["planned_mode_executions"]):
        errors.append("planned_mode_executions does not equal cases x modes x repetitions")
    if planned_external_without_retries != int(spec["planned_external_requests_without_retries_maximum"]):
        errors.append("planned external request total does not equal embedding plus generation requests")
    if int(spec["planned_mode_executions"]) > int(spec["max_mode_executions"]):
        errors.append("planned mode executions exceed hard cap")
    if int(spec["planned_unique_embedding_requests"]) > int(spec["max_embedding_calls"]):
        errors.append("planned embedding requests exceed embedding cap")
    if int(spec["planned_generation_requests_maximum"]) > int(spec["max_generation_calls"]):
        errors.append("planned generation requests exceed generation cap")
    if planned_external_without_retries > int(spec["max_total_external_calls"]):
        errors.append("planned external requests exceed total external cap")
    summary = retry_policy_summary(spec)
    if summary["total_cap_retry_slack"] != int(spec["max_total_retry_attempts"]):
        errors.append("total retry budget must equal total cap slack")
    if int(spec["max_retries_per_logical_request"]) != 1:
        errors.append("Protocol v2 freezes one retry maximum per logical request")
    if int(spec["external_warmup_calls"]) != 0:
        errors.append("Protocol v2 permits no external warm-up calls")
    if not plan_only:
        if spec.get("allow_real_api_required") is not True:
            errors.append("held-out execution spec must require --allow-real-api")
        if spec.get("allow_heldout_required") is not True:
            errors.append("held-out execution spec must require --allow-heldout")
    if "checksums" not in spec or not isinstance(spec["checksums"], dict):
        errors.append("execution spec must include frozen artifact checksums")
    if errors:
        raise RuntimeError("Invalid WoLaLa Protocol v2 execution spec: " + "; ".join(errors))
    return {
        "valid": True,
        "cases": int(spec["cases"]),
        "mode_count": len(spec["modes"]),
        "repetitions": int(spec["repetitions"]),
        "planned_mode_executions": int(spec["planned_mode_executions"]),
        "planned_unique_embedding_requests": int(spec["planned_unique_embedding_requests"]),
        "planned_generation_requests_maximum": int(spec["planned_generation_requests_maximum"]),
        "planned_external_requests_without_retries_maximum": int(spec["planned_external_requests_without_retries_maximum"]),
        "hard_total_external_cap": int(spec["max_total_external_calls"]),
        "retry_budget": int(spec["max_total_retry_attempts"]),
        "external_warmup_calls": int(spec["external_warmup_calls"]),
    }


def build_heldout_plan_only(spec: dict[str, Any], *, cases: list[dict[str, Any]], modes: list[str], repetitions: int) -> dict[str, Any]:
    validation = validate_execution_spec(
        spec,
        cases=cases,
        modes=modes,
        repetitions=repetitions,
        max_mode_executions=int(spec["max_mode_executions"]),
        max_embedding_calls=int(spec["max_embedding_calls"]),
        max_generation_calls=int(spec["max_generation_calls"]),
        max_total_external_calls=int(spec["max_total_external_calls"]),
        plan_only=True,
    )
    return {
        "schema_version": "wolala-heldout-plan-only-v2",
        "dataset": HELDOUT_DATASET,
        "protocol": spec["protocol"],
        "case_ids": [case["case_id"] for case in cases],
        "cases": validation["cases"],
        "modes": list(modes),
        "mode_count": validation["mode_count"],
        "repetitions": validation["repetitions"],
        "planned_mode_executions": validation["planned_mode_executions"],
        "planned_unique_embedding_requests": validation["planned_unique_embedding_requests"],
        "planned_generation_requests_maximum": validation["planned_generation_requests_maximum"],
        "planned_external_requests_without_retries_maximum": validation["planned_external_requests_without_retries_maximum"],
        "max_mode_executions": int(spec["max_mode_executions"]),
        "max_embedding_calls": int(spec["max_embedding_calls"]),
        "max_generation_calls": int(spec["max_generation_calls"]),
        "hard_total_external_cap": validation["hard_total_external_cap"],
        "max_total_retry_attempts": validation["retry_budget"],
        "max_retries_per_logical_request": int(spec["max_retries_per_logical_request"]),
        "external_warmup_calls": validation["external_warmup_calls"],
        "retrieval_computed_once_per_case": True,
        "retrieval_reused_across_modes_and_repetitions": True,
        "heldout_model_execution_count": 0,
        "heldout_embedding_calls": 0,
        "heldout_generation_calls": 0,
        "external_api_calls_in_plan_only": 0,
        "no_retrieval_embedding_adapter_generation_or_scoring_performed": True,
        "not_a_heldout_result": True,
    }


def _expected_core_values() -> dict[str, Any]:
    return {
        "protocol": "WOLALA2026_PILOT_PROTOCOL_v2.md",
        "dataset": HELDOUT_DATASET,
        "provider": "openai",
        "provider_implementation": "direct_https_openai_provider_wrapper",
        "embedding_model": "text-embedding-3-small",
        "generator_model": "gpt-4o-mini",
        "temperature": 0,
        "top_k": 4,
        "max_output_tokens": 160,
        "cases": 40,
        "repetitions": 3,
        "planned_mode_executions": 360,
        "planned_unique_embedding_requests": 40,
        "planned_generation_requests_maximum": 360,
        "planned_external_requests_without_retries_maximum": 400,
        "max_mode_executions": 360,
        "max_embedding_calls": 60,
        "max_generation_calls": 380,
        "max_total_external_calls": 420,
        "max_total_retry_attempts": 20,
        "max_retries_per_logical_request": 1,
        "external_warmup_calls": 0,
        "allow_real_api_required": True,
        "allow_heldout_required": True,
        "run_attempt": 1,
    }


def _validate_requested_cap(key: str, requested: int | None, spec: dict[str, Any], errors: list[str]) -> None:
    if requested is not None and int(requested) != int(spec[key]):
        errors.append(f"requested {key} {requested!r} does not match execution spec {spec[key]!r}")
