from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from .adapters import ALL_MODES, adapter_for_mode, run_adapters_for_case
from .common import read_json, read_jsonl, sha256_file, stable_hash, write_checksums, write_json, write_jsonl
from .execution_spec import build_heldout_plan_only, load_execution_spec, validate_execution_spec
from .pilot_data import DATA_DIR, DEV_DATASET, HELDOUT_DATASET
from .retrieval import build_retrieval_snapshot
from .real_api import EmbeddingCallResult, OpenAIProvider, ProviderCallResult, RealApiProvider
from .retry_policy import classify_retryable_condition
from .run_manifest import build_manifest, now_utc, write_schema
from .score_pilot import write_score_outputs


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PACKAGE_DIR / "development_run"


def run_pilot(
    *,
    dataset: str,
    modes: list[str],
    repetitions: int,
    output_dir: str | Path,
    max_mode_executions: int,
    max_embedding_calls: int,
    max_generation_calls: int,
    max_total_external_calls: int,
    max_total_retry_attempts: int = 0,
    max_retries_per_logical_request: int = 0,
    allow_real_api: bool = False,
    allow_heldout: bool = False,
    plan_only: bool = False,
    provider: RealApiProvider | None = None,
    execution_spec: str | Path | dict[str, Any] | None = None,
) -> dict[str, Any]:
    dataset_dir = DATA_DIR / dataset
    cases = read_jsonl(dataset_dir / "cases.jsonl")
    dataset_manifest = read_json(dataset_dir / "manifest.json")
    spec = load_execution_spec(execution_spec) if execution_spec is not None else None
    if dataset == HELDOUT_DATASET and plan_only:
        if spec is None:
            raise RuntimeError("Held-out Protocol v2 plan-only validation requires --execution-spec.")
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        plan = build_heldout_plan_only(spec, cases=cases, modes=modes, repetitions=repetitions)
        write_json(out / "execution_plan.json", plan)
        return {
            "completion_status": "PLANNED",
            "mode_execution_count": plan["planned_mode_executions"],
            "heldout_mode_execution_count": 0,
            "heldout_model_execution_count": 0,
            "planned_mode_executions": plan["planned_mode_executions"],
            "planned_unique_embedding_requests": plan["planned_unique_embedding_requests"],
            "planned_generation_requests_maximum": plan["planned_generation_requests_maximum"],
            "planned_external_requests_without_retries_maximum": plan["planned_external_requests_without_retries_maximum"],
            "hard_total_external_cap": plan["hard_total_external_cap"],
            "execution_plan_path": str(out / "execution_plan.json"),
            "external_api_calls_in_plan_only": 0,
        }
    if dataset == HELDOUT_DATASET and not allow_heldout:
        raise RuntimeError("Held-out pilot execution refused: supply an explicit held-out approval flag for a future run.")
    if dataset == HELDOUT_DATASET:
        if spec is None:
            raise RuntimeError("Held-out Protocol v2 execution requires --execution-spec.")
        validate_execution_spec(
            spec,
            cases=cases,
            modes=modes,
            repetitions=repetitions,
            max_mode_executions=max_mode_executions,
            max_embedding_calls=max_embedding_calls,
            max_generation_calls=max_generation_calls,
            max_total_external_calls=max_total_external_calls,
        )
        if not allow_real_api:
            raise RuntimeError("Protocol v2 held-out execution requires --allow-real-api.")
        max_total_retry_attempts = int(spec["max_total_retry_attempts"])
        max_retries_per_logical_request = int(spec["max_retries_per_logical_request"])
    mode_executions = len(cases) * len(modes) * repetitions
    estimated_embedding_calls = len(cases) if allow_real_api else 0
    estimated_generation_calls = mode_executions if allow_real_api else 0
    estimated_total = estimated_embedding_calls + estimated_generation_calls
    if mode_executions > max_mode_executions:
        raise RuntimeError(f"Mode execution cap exceeded: requested {mode_executions}, cap {max_mode_executions}.")
    if estimated_embedding_calls > max_embedding_calls:
        raise RuntimeError(f"Embedding call cap exceeded: requested {estimated_embedding_calls}, cap {max_embedding_calls}.")
    if estimated_generation_calls > max_generation_calls:
        raise RuntimeError(f"Generation call cap exceeded: requested {estimated_generation_calls}, cap {max_generation_calls}.")
    if estimated_total > max_total_external_calls:
        raise RuntimeError(f"Total external call cap exceeded: requested {estimated_total}, cap {max_total_external_calls}.")
    if allow_real_api and provider is None and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --allow-real-api and is not visible in the environment.")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    plan = _execution_plan(
        dataset=dataset,
        cases=cases,
        modes=modes,
        repetitions=repetitions,
        max_mode_executions=max_mode_executions,
        max_embedding_calls=max_embedding_calls,
        max_generation_calls=max_generation_calls,
        max_total_external_calls=max_total_external_calls,
        allow_real_api=allow_real_api,
    )
    write_json(out / "execution_plan.json", plan)
    if plan_only:
        return {
            "completion_status": "PLANNED",
            "mode_execution_count": mode_executions,
            "heldout_mode_execution_count": 0,
            "execution_plan_path": str(out / "execution_plan.json"),
        }
    if allow_real_api and ((out / "raw_results.jsonl").exists() or (out / "run_manifest.json").exists()):
        raise RuntimeError(f"Refusing to overwrite an existing real-API run artifact directory: {out}")

    active_provider: RealApiProvider | None = None
    counters = _CallCounters(
        max_embedding_calls=max_embedding_calls,
        max_generation_calls=max_generation_calls,
        max_total_external_calls=max_total_external_calls,
        max_total_retry_attempts=max_total_retry_attempts,
        max_retries_per_logical_request=max_retries_per_logical_request,
    )
    if allow_real_api:
        base_provider = provider or OpenAIProvider()
        active_provider = _BudgetedProvider(base_provider, counters)
    protocol_filename = str(spec["protocol"]) if spec else "WOLALA2026_PILOT_PROTOCOL_v1.md"
    protocol_checksum = sha256_file(PACKAGE_DIR / protocol_filename)
    start_time = now_utc()
    run_id = f"{dataset}_real_api_v1" if allow_real_api else f"{dataset}_deterministic_v1"
    manifest = build_manifest(
        run_id=run_id,
        run_type="real_api_development_integration" if allow_real_api and dataset == DEV_DATASET else ("development_integration_pilot_v1" if dataset == DEV_DATASET else "heldout_pilot_v1"),
        development_or_heldout="development" if dataset == DEV_DATASET else "heldout",
        dataset_name=dataset,
        dataset_checksum=dataset_manifest["dataset_checksum"],
        protocol_checksum=protocol_checksum,
        case_ids=[case["case_id"] for case in cases],
        modes=modes,
        repetitions=repetitions,
        max_mode_executions=max_mode_executions,
        max_embedding_calls=max_embedding_calls,
        max_generation_calls=max_generation_calls,
        max_total_external_calls=max_total_external_calls,
        start_time_utc=start_time,
        allow_real_api=allow_real_api,
    )
    manifest["real_api"] = bool(allow_real_api)
    manifest["mock_or_stub_used"] = bool(active_provider.is_mock) if active_provider else False
    manifest["retry_count"] = 0
    if spec:
        manifest["protocol_version"] = Path(protocol_filename).stem
        manifest["protocol_checksum"] = protocol_checksum
        manifest["planned_logical_embedding_requests"] = int(spec["planned_unique_embedding_requests"])
        manifest["planned_logical_generation_requests_maximum"] = int(spec["planned_generation_requests_maximum"])
        manifest["planned_external_requests_without_retries_maximum"] = int(spec["planned_external_requests_without_retries_maximum"])
        manifest["actual_provider_attempts"] = 0
        manifest["actual_retry_attempts"] = 0
        manifest["max_total_retry_attempts"] = int(spec["max_total_retry_attempts"])
        manifest["max_retries_per_logical_request"] = int(spec["max_retries_per_logical_request"])
        manifest["external_warmup_calls"] = int(spec["external_warmup_calls"])
        manifest["run_attempt"] = int(spec["run_attempt"])
        manifest["invalidation_class"] = None
        manifest["retry_events"] = []
        manifest["protocol_v2_checksum"] = protocol_checksum
        manifest["statistical_plan_checksum"] = spec.get("checksums", {}).get("statistical_plan")
        manifest["latency_definition_checksum"] = spec.get("checksums", {}).get("latency_definition")
        manifest["execution_spec_checksum"] = sha256_file(execution_spec) if isinstance(execution_spec, (str, Path)) else stable_hash(spec)
    manifest["heldout_mode_execution_count"] = 0
    manifest["cold_or_warm_state"] = "cold-real-api-process" if allow_real_api else manifest["cold_or_warm_state"]
    manifest["cache_configuration"] = {"external_cache": "not-used", "retrieval_cache": "shared-once-per-case"}
    results: list[dict[str, Any]] = []
    retrieval_snapshots = []
    errors: list[dict[str, Any]] = []
    completion_status = "COMPLETED"
    try:
        for repetition in range(1, repetitions + 1):
            for case in cases:
                if active_provider:
                    snapshot, embedding = _real_retrieval_snapshot(case, active_provider)
                    case_results = [
                        adapter_for_mode(mode).run(
                            case,
                            snapshot,
                            run_id=run_id,
                            repetition=repetition,
                            provider=active_provider,
                            max_output_tokens=manifest["max_output_tokens"],
                        )
                        for mode in modes
                    ]
                    _attach_shared_embedding_latency(case_results, embedding)
                else:
                    snapshot, case_results = run_adapters_for_case(case, modes, run_id=run_id, repetition=repetition)
                retrieval_snapshots.append(snapshot)
                results.extend(case_results)
    except Exception as exc:
        completion_status = "FAILED"
        errors.append({"category": "PROVIDER_ERROR" if allow_real_api else "OTHER", "message": str(exc), "case_count_completed": len({r["case_id"] for r in results})})
    write_jsonl(out / "raw_results.jsonl", results)
    write_jsonl(out / "shared_retrieval_snapshots.jsonl", retrieval_snapshots)
    scores = write_score_outputs(cases, results, out)
    verification_files = _write_phase3_verifications(cases, results, retrieval_snapshots, scores, out, run_id)
    latency_payload = {
        "diagnostic_only": True,
        "not_publication_ready": True,
        "latency_summaries": scores["latency_summaries"],
        "external_latency_summaries": _external_latency_summaries(results),
        "expected_mode_latency_summaries": _expected_mode_latency_summaries(cases, results),
        "generation_used_latency_summaries": _generation_used_latency_summaries(results),
        "mode_execution_count": mode_executions,
    }
    write_json(out / "latency_diagnostics.json", latency_payload)
    write_jsonl(out / "errors.jsonl", errors)
    manifest["end_time_utc"] = now_utc()
    manifest["actual_embedding_calls"] = counters.embedding_calls if allow_real_api else 0
    manifest["actual_generation_calls"] = counters.generation_calls if allow_real_api else 0
    manifest["actual_total_external_calls"] = counters.total_external_calls if allow_real_api else 0
    manifest["retry_count"] = counters.retry_count
    if spec:
        manifest["actual_provider_attempts"] = counters.total_external_calls if allow_real_api else 0
        manifest["actual_retry_attempts"] = counters.retry_count
        manifest["retry_events"] = counters.retry_log
    manifest["mode_execution_count"] = mode_executions
    manifest["heldout_mode_execution_count"] = 0 if dataset == DEV_DATASET else mode_executions
    manifest["completion_status"] = completion_status
    manifest["errors"] = errors
    if active_provider:
        manifest["provider"] = active_provider.provider_name
        manifest["embedding_model"] = active_provider.embedding_model
        manifest["generator_model"] = active_provider.generator_model
    write_json(out / "run_manifest.json", manifest)
    _write_run_readme(out, manifest, verification_files)
    write_schema(PACKAGE_DIR / "run_manifest_schema.json")
    checksum_files = [
        out / "execution_plan.json",
        out / "run_manifest.json",
        out / "raw_results.jsonl",
        out / "case_scores.jsonl",
        out / "pair_scores.jsonl",
        out / "summary.json",
        out / "summary.csv",
        out / "summary_table.tex",
        out / "latency_diagnostics.json",
        out / "error_analysis.json",
        out / "errors.jsonl",
        out / "shared_retrieval_snapshots.jsonl",
        out / "shared_retrieval_verification.json",
        out / "adapter_integrity_verification.json",
        out / "generator_context_exposure_verification.json",
        out / "source_existence_leakage_verification.json",
        out / "README.md",
    ]
    write_checksums(out / "checksums.sha256", checksum_files, root=out)
    return manifest


def parse_modes(value: str) -> list[str]:
    modes = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [mode for mode in modes if mode not in ALL_MODES]
    if unknown:
        raise ValueError(f"Unknown mode(s): {unknown}")
    return modes


class _CallCounters:
    def __init__(
        self,
        *,
        max_embedding_calls: int,
        max_generation_calls: int,
        max_total_external_calls: int,
        max_total_retry_attempts: int = 0,
        max_retries_per_logical_request: int = 0,
    ) -> None:
        self.max_embedding_calls = max_embedding_calls
        self.max_generation_calls = max_generation_calls
        self.max_total_external_calls = max_total_external_calls
        self.max_total_retry_attempts = max_total_retry_attempts
        self.max_retries_per_logical_request = max_retries_per_logical_request
        self.embedding_calls = 0
        self.generation_calls = 0
        self.total_external_calls = 0
        self.retry_count = 0
        self.retry_log: list[dict[str, Any]] = []

    def reserve_embedding(self) -> None:
        self._reserve(kind="embedding")

    def reserve_generation(self) -> None:
        self._reserve(kind="generation")

    def reserve_retry(self, *, kind: str, reason: str, wait_seconds: float) -> dict[str, Any]:
        if self.max_retries_per_logical_request < 1:
            raise RuntimeError("Retry refused: max_retries_per_logical_request is 0.")
        if self.retry_count + 1 > self.max_total_retry_attempts:
            raise RuntimeError(f"Retry budget exceeded: requested {self.retry_count + 1}, cap {self.max_total_retry_attempts}.")
        self._reserve(kind=kind)
        self.retry_count += 1
        event = {
            "retry_attempt": self.retry_count,
            "logical_request_kind": kind,
            "retry_reason": reason,
            "wait_seconds": wait_seconds,
            "outcome": "PENDING",
        }
        self.retry_log.append(event)
        return event

    def _reserve(self, *, kind: str) -> None:
        next_embedding = self.embedding_calls + (1 if kind == "embedding" else 0)
        next_generation = self.generation_calls + (1 if kind == "generation" else 0)
        next_total = self.total_external_calls + 1
        if next_embedding > self.max_embedding_calls:
            raise RuntimeError(f"Embedding call cap exceeded: requested {next_embedding}, cap {self.max_embedding_calls}.")
        if next_generation > self.max_generation_calls:
            raise RuntimeError(f"Generation call cap exceeded: requested {next_generation}, cap {self.max_generation_calls}.")
        if next_total > self.max_total_external_calls:
            raise RuntimeError(f"Total external call cap exceeded: requested {next_total}, cap {self.max_total_external_calls}.")
        self.embedding_calls = next_embedding
        self.generation_calls = next_generation
        self.total_external_calls = next_total


class _BudgetedProvider:
    def __init__(self, provider: RealApiProvider, counters: _CallCounters, *, retry_wait_seconds: float = 2.0) -> None:
        self._provider = provider
        self._counters = counters
        self._retry_wait_seconds = retry_wait_seconds
        self.provider_name = provider.provider_name
        self.embedding_model = provider.embedding_model
        self.generator_model = provider.generator_model
        self.is_mock = provider.is_mock

    def embed_query(self, query: str) -> EmbeddingCallResult:
        self._counters.reserve_embedding()
        return self._call_with_single_retry("embedding", lambda: self._provider.embed_query(query))

    def generate_json(self, *, mode_name: str, system_prompt: str, user_payload: dict[str, Any], max_output_tokens: int) -> ProviderCallResult:
        self._counters.reserve_generation()
        return self._call_with_single_retry(
            "generation",
            lambda: self._provider.generate_json(
                mode_name=mode_name,
                system_prompt=system_prompt,
                user_payload=user_payload,
                max_output_tokens=max_output_tokens,
            ),
        )

    def _call_with_single_retry(self, kind: str, call: Any) -> Any:
        try:
            return call()
        except Exception as exc:
            classification = classify_retryable_condition(exc)
            if not classification.retryable:
                raise
            event = self._counters.reserve_retry(kind=kind, reason=classification.reason, wait_seconds=self._retry_wait_seconds)
            if self._retry_wait_seconds:
                time.sleep(self._retry_wait_seconds)
            try:
                result = call()
            except Exception as retry_exc:
                event["outcome"] = "FAILED"
                event["retry_error"] = str(retry_exc)
                raise RuntimeError(f"Provider {kind} retry failed after {classification.reason}: {retry_exc}") from retry_exc
            event["outcome"] = "SUCCEEDED"
            result.retry_count += 1
            result.retry_events.append(dict(event))
            return result


def _execution_plan(
    *,
    dataset: str,
    cases: list[dict[str, Any]],
    modes: list[str],
    repetitions: int,
    max_mode_executions: int,
    max_embedding_calls: int,
    max_generation_calls: int,
    max_total_external_calls: int,
    allow_real_api: bool,
) -> dict[str, Any]:
    case_ids = [case["case_id"] for case in cases]
    heldout_ids = [case_id for case_id in case_ids if case_id.startswith("HELD_")]
    if heldout_ids:
        raise RuntimeError(f"Plan contains held-out case IDs and cannot proceed: {heldout_ids}")
    planned_mode_executions = len(cases) * len(modes) * repetitions
    plan = {
        "schema_version": "wolala-real-api-execution-plan-v1",
        "dataset": dataset,
        "development_cases": len(cases),
        "case_ids": case_ids,
        "modes": modes,
        "mode_count": len(modes),
        "repetitions": repetitions,
        "planned_mode_executions": planned_mode_executions,
        "heldout_mode_executions": 0,
        "maximum_embedding_calls": max_embedding_calls,
        "maximum_generation_calls": max_generation_calls,
        "maximum_total_external_calls": max_total_external_calls,
        "retrieval_computed_once_per_case": True,
        "retrieval_reused_across_modes": True,
        "allow_real_api": allow_real_api,
        "not_a_heldout_result": True,
        "not_publication_ready": True,
    }
    if planned_mode_executions != 30 or max_mode_executions != 30:
        raise RuntimeError("Phase 3 development plan must contain exactly 30 planned mode executions with cap 30.")
    return plan


def _real_retrieval_snapshot(case: dict[str, Any], provider: RealApiProvider) -> tuple[dict[str, Any], EmbeddingCallResult]:
    embedding = provider.embed_query(case["query"])
    snapshot = build_retrieval_snapshot(case)
    snapshot["embedding_calls"] = 1
    snapshot["embedding_model"] = embedding.model
    snapshot["embedding_api_ms"] = embedding.latency_ms
    snapshot["real_api_embedding"] = True
    snapshot["embedding_response_id"] = embedding.response_id
    snapshot["snapshot_hash"] = stable_hash({key: value for key, value in snapshot.items() if key != "snapshot_hash"})
    return snapshot, embedding


def _attach_shared_embedding_latency(results: list[dict[str, Any]], embedding: EmbeddingCallResult) -> None:
    for result in results:
        timings = result["stage_timings"]
        timings["embedding_api_ms"] = embedding.latency_ms
        timings["external_api_ms"] = max(0.0, float(timings.get("generation_api_ms", 0.0)) + embedding.latency_ms)
        timings["end_to_end_ms"] = max(0.0, float(timings.get("end_to_end_ms", 0.0)) + embedding.latency_ms)
        result["end_to_end_ms"] = timings["end_to_end_ms"]
        result["shared_retrieval_embedding_call_count"] = 1
        result["embedding_model"] = embedding.model


def _write_phase3_verifications(
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
    retrieval_snapshots: list[dict[str, Any]],
    scores: dict[str, Any],
    output_dir: Path,
    run_id: str,
) -> list[Path]:
    files = [
        _write_shared_retrieval_verification(results, retrieval_snapshots, output_dir),
        _write_adapter_integrity_verification(results, output_dir),
        _write_generator_context_exposure_verification(cases, results, output_dir),
        _write_source_existence_leakage_verification(cases, results, output_dir),
        _write_error_analysis(cases, results, scores, output_dir, run_id),
    ]
    return files


def _write_shared_retrieval_verification(results: list[dict[str, Any]], snapshots: list[dict[str, Any]], output_dir: Path) -> Path:
    rows = []
    by_case: dict[str, list[dict[str, Any]]] = {}
    snapshot_by_case = {snapshot["case_id"]: snapshot for snapshot in snapshots}
    for result in results:
        by_case.setdefault(result["case_id"], []).append(result)
    for case_id, case_results in sorted(by_case.items()):
        hashes = sorted({result["retrieval_snapshot_hash"] for result in case_results})
        modes = sorted({result["mode_name"] for result in case_results})
        snapshot = snapshot_by_case.get(case_id, {})
        rows.append(
            {
                "case_id": case_id,
                "modes": modes,
                "snapshot_hashes": hashes,
                "candidate_ids": snapshot.get("candidate_ids", []),
                "candidate_order": snapshot.get("candidate_order", []),
                "retrieval_scores": snapshot.get("retrieval_scores", []),
                "same_snapshot_across_modes": len(hashes) == 1 and len(modes) == 3,
                "retrieval_computed_once": snapshot.get("embedding_calls") == 1,
            }
        )
    payload = {
        "schema_version": "wolala-shared-retrieval-verification-v1",
        "records": rows,
        "all_cases_share_retrieval": bool(rows) and all(row["same_snapshot_across_modes"] and row["retrieval_computed_once"] for row in rows),
    }
    path = output_dir / "shared_retrieval_verification.json"
    write_json(path, payload)
    return path


def _write_adapter_integrity_verification(results: list[dict[str, Any]], output_dir: Path) -> Path:
    records = []
    for result in results:
        profile = result.get("adapter_input_profile") or {}
        mode = result["mode_name"]
        if mode in {"standard_rag", "prompt_only_control"}:
            pass_condition = (
                profile.get("receives_raw_retrieved_candidates") is True
                and profile.get("contains_expected_mode") is False
                and profile.get("contains_gold_reason") is False
                and profile.get("contains_external_cfaf_decision") is False
                and profile.get("contains_source_role_gate_result") is False
                and profile.get("contains_permitted_output_object") is False
                and profile.get("contains_cfaf_response_contract") is False
                and profile.get("contains_internal_trace") is False
            )
        else:
            pass_condition = (
                profile.get("uses_eight_stage_pipeline_state") is True
                and profile.get("contains_authoritative_access_labels") is True
                and profile.get("contains_claim_relative_evidence_labels") is True
                and profile.get("contains_deterministic_mode_selection") is True
                and profile.get("contains_cfaf_response_contract") is True
                and profile.get("generator_receives_filtered_evidence_only") is True
            )
        records.append({"case_id": result["case_id"], "mode_name": mode, "pass": pass_condition, "profile": profile})
    payload = {
        "schema_version": "wolala-adapter-integrity-verification-v1",
        "records": records,
        "baselines_free_of_gold_or_external_cfaf_labels": all(row["pass"] for row in records if row["mode_name"] != "cfaf_pipeline"),
        "cfaf_uses_filtered_pipeline_context": all(row["pass"] for row in records if row["mode_name"] == "cfaf_pipeline"),
    }
    path = output_dir / "adapter_integrity_verification.json"
    write_json(path, payload)
    return path


def _write_generator_context_exposure_verification(cases: list[dict[str, Any]], results: list[dict[str, Any]], output_dir: Path) -> Path:
    cases_by_id = {case["case_id"]: case for case in cases}
    cfaf = [result for result in results if result["mode_name"] == "cfaf_pipeline"]
    rows = []
    for result in cfaf:
        case = cases_by_id[result["case_id"]]
        protected_markers = result.get("generator_context_protected_markers") or []
        leakage_values = [
            value
            for value in case.get("protected_markers", []) + case.get("forbidden_disclosures", [])
            if value and value in (result.get("public_response") or "")
        ]
        rows.append(
            {
                "case_id": result["case_id"],
                "context_hash": result.get("generator_context_hash"),
                "protected_markers": protected_markers,
                "generator_exposure": bool(protected_markers),
                "public_response_contains_protected_marker": bool(leakage_values),
                "public_response_protected_values": leakage_values,
                "sanitized_context_summary": (result.get("generator_context_audit") or {}).get("sanitized_context_summary"),
            }
        )
    payload = {
        "schema_version": "wolala-generator-context-exposure-verification-v1",
        "records": rows,
        "generator_exposure_rate": sum(1 for row in rows if row["generator_exposure"]) / len(rows) if rows else 0.0,
        "protected_content_leakage_rate": sum(1 for row in rows if row["public_response_contains_protected_marker"]) / len(rows) if rows else 0.0,
        "all_cfaf_contexts_filtered": bool(rows) and all(not row["generator_exposure"] and not row["public_response_contains_protected_marker"] for row in rows),
    }
    path = output_dir / "generator_context_exposure_verification.json"
    write_json(path, payload)
    return path


def _write_source_existence_leakage_verification(cases: list[dict[str, Any]], results: list[dict[str, Any]], output_dir: Path) -> Path:
    cases_by_pair: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        if case["family"] == "P5":
            cases_by_pair.setdefault(case["pair_id"], []).append(case)
    records = []
    for pair_id, pair_cases in sorted(cases_by_pair.items()):
        pair_results = [result for result in results if result["mode_name"] == "cfaf_pipeline" and result["pair_id"] == pair_id]
        normalized = [_normalize_public(result.get("public_response") or "") for result in pair_results]
        hidden_values = [value for case in pair_cases for value in case.get("forbidden_disclosures", []) + case.get("protected_markers", []) if value]
        hidden_absent = not any(value in (result.get("public_response") or "") for value in hidden_values for result in pair_results)
        reason_classes = {result.get("observed_public_reason_class") for result in pair_results}
        internal_hashes = {result.get("internal_trace_hash") for result in pair_results}
        records.append(
            {
                "pair_id": pair_id,
                "case_ids": [case["case_id"] for case in pair_cases],
                "public_reason_class_identical": len(reason_classes) == 1,
                "normalized_public_response_identical": len(normalized) == 2 and normalized[0] == normalized[1],
                "hidden_source_values_absent": hidden_absent,
                "internal_traces_differ": len(internal_hashes) == 2,
                "source_existence_leakage": not (len(reason_classes) == 1 and len(normalized) == 2 and normalized[0] == normalized[1] and hidden_absent),
            }
        )
    payload = {
        "schema_version": "wolala-source-existence-leakage-verification-v1",
        "records": records,
        "source_existence_leakage_rate": sum(1 for row in records if row["source_existence_leakage"]) / len(records) if records else 0.0,
    }
    path = output_dir / "source_existence_leakage_verification.json"
    write_json(path, payload)
    return path


def _write_error_analysis(
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
    scores: dict[str, Any],
    output_dir: Path,
    run_id: str,
) -> Path:
    cases_by_id = {case["case_id"]: case for case in cases}
    errors = []
    for score in scores.get("case_scores", []):
        categories: list[str] = []
        if not score["top_level_mode_correct"] and score["mode_name"] == "cfaf_pipeline":
            categories.append("TOP_LEVEL_MODE_ERROR")
        if score["false_cfaf"]:
            categories.append("FALSE_CFAF")
        if score["protected_content_leakage"]:
            categories.append("PROTECTED_CONTENT_LEAKAGE")
        if score["generator_exposure"]:
            categories.append("GENERATOR_EXPOSURE")
        if not score["cfaf_realization_correct"] and score["mode_name"] == "cfaf_pipeline":
            categories.append("CFAF_REALIZATION_ERROR")
        if not score["request_fulfilment_correct"] and score["expected_top_level_mode"] == "FULL":
            categories.append("FULL_ANSWER_CONTENT_ERROR")
        if not score["safe_next_step_correct"]:
            categories.append("SAFE_NEXT_STEP_ERROR")
        if not categories:
            continue
        case = cases_by_id[score["case_id"]]
        errors.append(
            {
                "run_id": run_id,
                "case_id": score["case_id"],
                "pair_id": score["pair_id"],
                "adapter": score["mode_name"],
                "expected_behavior": {
                    "top_level_mode": case["expected_top_level_mode"],
                    "realization": case.get("expected_cfaf_realization"),
                },
                "observed_behavior": {
                    "top_level_mode": score["observed_top_level_mode"],
                    "realization": score["observed_realization"],
                },
                "category": categories,
                "likely_component": "baseline_model" if score["mode_name"] != "cfaf_pipeline" else "cfaf_realization_or_validation",
                "blocks_heldout_pilot": score["mode_name"] == "cfaf_pipeline" and any(cat in categories for cat in ["TOP_LEVEL_MODE_ERROR", "PROTECTED_CONTENT_LEAKAGE", "GENERATOR_EXPOSURE", "CFAF_REALIZATION_ERROR"]),
                "recommended_correction": "Open a separate development-only follow-up if this blocks readiness; do not tune held-out data.",
            }
        )
    payload = {
        "schema_version": "wolala-error-analysis-v1",
        "diagnostic_only": True,
        "not_publication_ready": True,
        "errors": errors,
        "blocking_error_count": sum(1 for error in errors if error["blocks_heldout_pilot"]),
    }
    path = output_dir / "error_analysis.json"
    write_json(path, payload)
    return path


def _external_latency_summaries(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[float]] = {}
    for result in results:
        grouped.setdefault(result["mode_name"], []).append(float((result.get("stage_timings") or {}).get("external_api_ms", 0.0)))
    return {key: _percentiles(values) for key, values in sorted(grouped.items())}


def _expected_mode_latency_summaries(cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {case["case_id"]: case["expected_top_level_mode"] for case in cases}
    grouped: dict[str, list[float]] = {}
    for result in results:
        grouped.setdefault(expected.get(result["case_id"], "UNKNOWN"), []).append(float(result.get("end_to_end_ms", 0.0)))
    return {key: _percentiles(values) for key, values in sorted(grouped.items())}


def _generation_used_latency_summaries(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[float]] = {"generation_used": [], "generation_skipped": []}
    for result in results:
        key = "generation_skipped" if result.get("generation_skipped") else "generation_used"
        grouped.setdefault(key, []).append(float(result.get("end_to_end_ms", 0.0)))
    return {key: _percentiles(values) for key, values in sorted(grouped.items())}


def _percentiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "p50_ms": 0.0, "p95_ms": 0.0}
    if len(ordered) == 1:
        return {"count": 1, "p50_ms": ordered[0], "p95_ms": ordered[0]}
    midpoint = len(ordered) // 2
    p50 = ordered[midpoint] if len(ordered) % 2 else (ordered[midpoint - 1] + ordered[midpoint]) / 2
    p95_index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return {"count": len(ordered), "p50_ms": p50, "p95_ms": ordered[p95_index]}


def _normalize_public(value: str) -> str:
    return " ".join(value.lower().replace(".", "").split())


def _write_run_readme(output_dir: Path, manifest: dict[str, Any], verification_files: list[Path]) -> None:
    lines = [
        "# WoLaLa Real-API Development Integration v1",
        "",
        "Not a held-out result.",
        "Not a publication-ready empirical result.",
        "Used only for real-API integration and pilot-readiness assessment.",
        "",
        f"- Run ID: `{manifest['run_id']}`",
        f"- Provider: `{manifest['provider']}`",
        f"- Embedding model: `{manifest['embedding_model']}`",
        f"- Generator model: `{manifest['generator_model']}`",
        f"- Mode executions: `{manifest['mode_execution_count']}`",
        f"- External calls: `{manifest['actual_total_external_calls']}`",
        f"- Held-out mode executions: `{manifest['heldout_mode_execution_count']}`",
        "",
        "Verification files:",
    ]
    lines.extend(f"- `{path.name}`" for path in verification_files)
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a capped WoLaLa 2026 development integration pilot.")
    parser.add_argument("--dataset", choices=[DEV_DATASET, HELDOUT_DATASET], required=True)
    parser.add_argument("--modes", default=",".join(ALL_MODES))
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-mode-executions", type=int, required=True)
    parser.add_argument("--max-embedding-calls", type=int, required=True)
    parser.add_argument("--max-generation-calls", type=int, required=True)
    parser.add_argument("--max-total-external-calls", type=int, required=True)
    parser.add_argument("--max-total-retry-attempts", type=int, default=0)
    parser.add_argument("--max-retries-per-logical-request", type=int, default=0)
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--allow-heldout", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--execution-spec")
    args = parser.parse_args()
    manifest = run_pilot(
        dataset=args.dataset,
        modes=parse_modes(args.modes),
        repetitions=args.repetitions,
        output_dir=args.output_dir,
        max_mode_executions=args.max_mode_executions,
        max_embedding_calls=args.max_embedding_calls,
        max_generation_calls=args.max_generation_calls,
        max_total_external_calls=args.max_total_external_calls,
        max_total_retry_attempts=args.max_total_retry_attempts,
        max_retries_per_logical_request=args.max_retries_per_logical_request,
        allow_real_api=args.allow_real_api,
        allow_heldout=args.allow_heldout,
        plan_only=args.plan_only,
        execution_spec=args.execution_spec,
    )
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in [
                    "completion_status",
                    "mode_execution_count",
                    "heldout_mode_execution_count",
                    "planned_mode_executions",
                    "planned_unique_embedding_requests",
                    "planned_generation_requests_maximum",
                    "hard_total_external_cap",
                    "external_api_calls_in_plan_only",
                ]
                if key in manifest
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
