from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .common import canonical_json, sha256_text, stable_hash
from .labels import TopLevelMode, json_safe
from .pipeline import SAFE_FALLBACK, run_pipeline
from .real_api import ProviderCallResult, RealApiProvider
from .retrieval import build_retrieval_snapshot


MODE_STANDARD_RAG = "standard_rag"
MODE_PROMPT_ONLY_CONTROL = "prompt_only_control"
MODE_CFAF_PIPELINE = "cfaf_pipeline"
ALL_MODES = [MODE_STANDARD_RAG, MODE_PROMPT_ONLY_CONTROL, MODE_CFAF_PIPELINE]
PACKAGE_DIR = Path(__file__).resolve().parent


class ExperimentAdapter(Protocol):
    mode: str

    def run(
        self,
        case: dict[str, Any],
        retrieval_snapshot: dict[str, Any],
        *,
        run_id: str,
        repetition: int,
        provider: RealApiProvider | None = None,
        max_output_tokens: int = 160,
    ) -> dict[str, Any]:
        ...


@dataclass
class StandardRagAdapter:
    mode: str = MODE_STANDARD_RAG

    def run(
        self,
        case: dict[str, Any],
        retrieval_snapshot: dict[str, Any],
        *,
        run_id: str,
        repetition: int,
        provider: RealApiProvider | None = None,
        max_output_tokens: int = 160,
    ) -> dict[str, Any]:
        start_ns = time.perf_counter_ns()
        context = _raw_context(retrieval_snapshot)
        provider_call: ProviderCallResult | None = None
        if provider:
            provider_call = provider.generate_json(
                mode_name=self.mode,
                system_prompt=_standard_rag_system_prompt(),
                user_payload=_baseline_user_payload(case["query"], context),
                max_output_tokens=max_output_tokens,
            )
            raw_output = provider_call.content
        else:
            raw_output = _standard_generate(case["query"], context)
        parsed = parse_output(raw_output)
        elapsed_ms = _elapsed_ms(start_ns)
        stage_timings = _baseline_timings(elapsed_ms)
        token_usage = _token_usage(context, raw_output)
        model_calls = 0
        if provider_call:
            stage_timings["generation_api_ms"] = provider_call.latency_ms
            stage_timings["external_api_ms"] = provider_call.latency_ms
            token_usage = {"input_tokens": provider_call.input_tokens, "output_tokens": provider_call.output_tokens}
            model_calls = 1
        return _result_envelope(
            run_id=run_id,
            case=case,
            mode_name=self.mode,
            repetition=repetition,
            retrieval_snapshot=retrieval_snapshot,
            raw_model_output=raw_output,
            parsed=parsed,
            generator_context=context,
            validation_status="PASS",
            fallback_used=False,
            model_calls=model_calls,
            embedding_calls=0,
            generation_calls=model_calls,
            retry_count=provider_call.retry_count if provider_call else 0,
            stage_timings=stage_timings,
            token_usage=token_usage,
            errors=[],
            provider=provider,
            generation_skipped=False if provider_call else False,
            adapter_input_profile=_baseline_input_profile(self.mode, context, uses_prompt=False),
            provider_response_id=provider_call.response_id if provider_call else None,
        )


@dataclass
class PromptOnlyControlAdapter:
    mode: str = MODE_PROMPT_ONLY_CONTROL
    prompt_path: Path = PACKAGE_DIR / "prompts" / "prompt_only_v1.txt"

    def run(
        self,
        case: dict[str, Any],
        retrieval_snapshot: dict[str, Any],
        *,
        run_id: str,
        repetition: int,
        provider: RealApiProvider | None = None,
        max_output_tokens: int = 160,
    ) -> dict[str, Any]:
        start_ns = time.perf_counter_ns()
        context = _raw_context(retrieval_snapshot)
        prompt = self.prompt_path.read_text(encoding="utf-8") if self.prompt_path.exists() else ""
        provider_call: ProviderCallResult | None = None
        if provider:
            provider_call = provider.generate_json(
                mode_name=self.mode,
                system_prompt=_prompt_only_system_prompt(prompt),
                user_payload=_baseline_user_payload(case["query"], context),
                max_output_tokens=max_output_tokens,
            )
            raw_output = provider_call.content
        else:
            raw_output = _prompt_only_generate(case["query"], context, prompt)
        parsed = parse_output(raw_output)
        elapsed_ms = _elapsed_ms(start_ns)
        stage_timings = _baseline_timings(elapsed_ms)
        token_usage = _token_usage({"system_instruction": prompt, "raw_context": context}, raw_output)
        model_calls = 0
        if provider_call:
            stage_timings["generation_api_ms"] = provider_call.latency_ms
            stage_timings["external_api_ms"] = provider_call.latency_ms
            token_usage = {"input_tokens": provider_call.input_tokens, "output_tokens": provider_call.output_tokens}
            model_calls = 1
        return _result_envelope(
            run_id=run_id,
            case=case,
            mode_name=self.mode,
            repetition=repetition,
            retrieval_snapshot=retrieval_snapshot,
            raw_model_output=raw_output,
            parsed=parsed,
            generator_context={"system_instruction": prompt, "raw_context": context},
            validation_status="PASS",
            fallback_used=False,
            model_calls=model_calls,
            embedding_calls=0,
            generation_calls=model_calls,
            retry_count=provider_call.retry_count if provider_call else 0,
            stage_timings=stage_timings,
            token_usage=token_usage,
            errors=[],
            provider=provider,
            generation_skipped=False if provider_call else False,
            adapter_input_profile=_baseline_input_profile(self.mode, context, uses_prompt=True),
            provider_response_id=provider_call.response_id if provider_call else None,
        )


@dataclass
class CFAFPipelineAdapter:
    mode: str = MODE_CFAF_PIPELINE
    prompt_path: Path = PACKAGE_DIR / "prompts" / "cfaf_generator_v1.txt"

    def run(
        self,
        case: dict[str, Any],
        retrieval_snapshot: dict[str, Any],
        *,
        run_id: str,
        repetition: int,
        provider: RealApiProvider | None = None,
        max_output_tokens: int = 160,
    ) -> dict[str, Any]:
        start_ns = time.perf_counter_ns()
        state = run_pipeline(case, adapter_mode=self.mode)
        prompt = self.prompt_path.read_text(encoding="utf-8") if self.prompt_path.exists() else ""
        parsed = {
            "answer": state.final_response or "",
            "top_level_mode": state.mode_decision.mode.value if state.mode_decision else None,
            "fulfilment_status": state.mode_decision.fulfilment_status.value if state.mode_decision else None,
            "realization": state.mode_decision.cfaf_realization.value if state.mode_decision and state.mode_decision.cfaf_realization else None,
            "public_reason_class": state.response_contract.public_reason_class.value if state.response_contract and state.response_contract.public_reason_class else None,
            "next_step_codes": _next_step_codes(state.mode_decision.next_steps if state.mode_decision else []),
        }
        context = {"generator_prompt": prompt, "pipeline_generator_context": state.generator_context}
        raw_output = canonical_json(parsed)
        provider_call: ProviderCallResult | None = None
        generation_calls = 0
        retry_count = 0
        fallback_used = state.validation.fallback_used if state.validation else False
        validation_status = state.validation.status.value if state.validation else None
        token_usage = state.token_usage
        stage_timings = {**state.stage_timings, **state.api_timings}
        if provider:
            provider_call = provider.generate_json(
                mode_name=self.mode,
                system_prompt=_cfaf_system_prompt(prompt),
                user_payload={"response_contract_and_permitted_evidence": state.generator_context},
                max_output_tokens=max_output_tokens,
            )
            raw_output = provider_call.content
            model_parsed = parse_output(raw_output)
            parsed = _cfaf_contract_observation(state, model_parsed)
            leak_values = _response_leak_values(case, parsed.get("answer") or "")
            if leak_values:
                parsed["answer"] = case.get("safe_fallback", SAFE_FALLBACK)
                validation_status = "FAIL"
                fallback_used = True
            stage_timings["generation_api_ms"] = provider_call.latency_ms
            stage_timings["external_api_ms"] = provider_call.latency_ms
            stage_timings["end_to_end_ms"] = _elapsed_ms(start_ns)
            token_usage = {"input_tokens": provider_call.input_tokens, "output_tokens": provider_call.output_tokens}
            generation_calls = 1
            retry_count = provider_call.retry_count
        return _result_envelope(
            run_id=run_id,
            case=case,
            mode_name=self.mode,
            repetition=repetition,
            retrieval_snapshot=retrieval_snapshot,
            raw_model_output=raw_output,
            parsed=parsed,
            generator_context=context,
            validation_status=validation_status,
            fallback_used=fallback_used,
            model_calls=generation_calls if provider else state.model_call_count,
            embedding_calls=0,
            generation_calls=generation_calls if provider else state.model_call_count,
            retry_count=retry_count,
            stage_timings=stage_timings,
            token_usage=token_usage,
            errors=[],
            provider=provider,
            generation_skipped=False if provider else state.generation_skipped,
            adapter_input_profile=_cfaf_input_profile(state),
            internal_trace_hash=stable_hash(state.internal_trace),
            public_trace_hash=stable_hash(state.public_trace),
            provider_response_id=provider_call.response_id if provider_call else None,
        )


def adapter_for_mode(mode: str) -> ExperimentAdapter:
    if mode == MODE_STANDARD_RAG:
        return StandardRagAdapter()
    if mode == MODE_PROMPT_ONLY_CONTROL:
        return PromptOnlyControlAdapter()
    if mode == MODE_CFAF_PIPELINE:
        return CFAFPipelineAdapter()
    raise ValueError(f"Unknown WoLaLa mode: {mode}")


def run_adapters_for_case(
    case: dict[str, Any],
    modes: list[str],
    *,
    run_id: str,
    repetition: int,
    provider: RealApiProvider | None = None,
    max_output_tokens: int = 160,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    snapshot = build_retrieval_snapshot(case)
    return snapshot, [
        adapter_for_mode(mode).run(case, snapshot, run_id=run_id, repetition=repetition, provider=provider, max_output_tokens=max_output_tokens)
        for mode in modes
    ]


def smoke_test_adapters(case: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot, results = run_adapters_for_case(case, ALL_MODES, run_id="adapter-smoke", repetition=1)
    return [
        {
            "mode": result["mode_name"],
            "case_id": result["case_id"],
            "retrieval_snapshot_hash": snapshot["snapshot_hash"],
            "observed_top_level_mode": result["observed_top_level_mode"],
            "external_cfaf_gate_used": result["mode_name"] == MODE_CFAF_PIPELINE,
            "raw_context_count": len(snapshot["candidates"]),
        }
        for result in results
    ]


def parse_output(raw_model_output: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_model_output)
        if isinstance(parsed, dict):
            answer = str(parsed.get("answer") or parsed.get("public_response") or "")
            inferred = _infer_mode_fields(answer)
            return {
                "answer": answer,
                "top_level_mode": parsed.get("top_level_mode") or inferred["top_level_mode"],
                "fulfilment_status": parsed.get("fulfilment_status") or inferred["fulfilment_status"],
                "realization": parsed.get("realization") or inferred["realization"],
                "public_reason_class": parsed.get("public_reason_class") or inferred["public_reason_class"],
                "next_step_codes": list(parsed.get("next_step_codes") or []),
            }
    except Exception:
        pass
    inferred = _infer_mode_fields(raw_model_output)
    return {
        "answer": raw_model_output,
        "top_level_mode": inferred["top_level_mode"],
        "fulfilment_status": inferred["fulfilment_status"],
        "realization": inferred["realization"],
        "public_reason_class": inferred["public_reason_class"],
        "next_step_codes": [],
    }


def _standard_generate(query: str, context: list[dict[str, Any]]) -> str:
    text = "\n".join(candidate["permitted_experimental_raw_text"] for candidate in context)
    answer = _extract_answer(query, text)
    if answer:
        return canonical_json(
            {
                "answer": answer,
                "top_level_mode": "FULL",
                "fulfilment_status": "FULL",
                "realization": None,
                "public_reason_class": None,
                "next_step_codes": [],
            }
        )
    return _cfaf_json("The currently usable evidence does not support the requested content.", "EVIDENTIAL", "ABSTAIN", ["provide_primary_evidence"])


def _prompt_only_generate(query: str, context: list[dict[str, Any]], prompt: str) -> str:
    text = "\n".join(candidate["permitted_experimental_raw_text"] for candidate in context)
    lowered = query.lower()
    if "individual" in lowered and "AGGREGATE_ANSWER:" in text:
        return _cfaf_json("The request should be restricted to aggregate information.", "GOVERNANCE_PRIVACY", "RESTRICT_GRANULARITY", ["ask_aggregate_or_request_individual_access"])
    if "body" in lowered and "METADATA_FIELDS:" in text:
        return _cfaf_json("The request should be restricted to metadata.", "GOVERNANCE_PRIVACY", "RESTRICT_CONTENT", ["request_content_access"])
    answer = _extract_answer(query, text)
    if answer:
        return canonical_json(
            {
                "answer": answer,
                "top_level_mode": "FULL",
                "fulfilment_status": "FULL",
                "realization": None,
                "public_reason_class": None,
                "next_step_codes": [],
            }
        )
    return _cfaf_json("The currently usable evidence does not support the requested content.", "EVIDENTIAL", "ABSTAIN", ["provide_primary_evidence"])


def _cfaf_json(answer: str, reason_class: str, realization: str, next_steps: list[str]) -> str:
    return canonical_json(
        {
            "answer": answer,
            "top_level_mode": "CFAF",
            "fulfilment_status": "RESTRICTED" if realization in {"RESTRICT_CONTENT", "RESTRICT_GRANULARITY"} else "NONE",
            "realization": realization,
            "public_reason_class": reason_class,
            "next_step_codes": next_steps,
        }
    )


def _extract_answer(query: str, text: str) -> str | None:
    for marker in ["ANSWER:", "AGGREGATE_ANSWER:", "OPEN_ACTION:", "HIDDEN_ANSWER:", "BODY_PRIVATE:"]:
        if marker in text:
            value = text.split(marker, 1)[1].split(" INDIVIDUAL_ROWS:", 1)[0].split(" BACKGROUND:", 1)[0].strip()
            return value.rstrip(".") + "."
    if "METADATA_FIELDS:" in text and ("file type" in query.lower() or "creation date" in query.lower()):
        value = text.split("METADATA_FIELDS:", 1)[1].split(". BODY_PRIVATE:", 1)[0].strip()
        return value.rstrip(".") + "."
    return None


def _raw_context(retrieval_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": candidate["candidate_id"],
            "source_id": candidate["source_id"],
            "source_type": candidate.get("source_type"),
            "title": candidate.get("title"),
            "permitted_experimental_raw_text": candidate.get("permitted_experimental_raw_text", ""),
            "metadata": candidate.get("metadata", {}),
            "retrieval_score": candidate.get("retrieval_score"),
        }
        for candidate in retrieval_snapshot.get("candidates", [])
    ]


def _result_envelope(
    *,
    run_id: str,
    case: dict[str, Any],
    mode_name: str,
    repetition: int,
    retrieval_snapshot: dict[str, Any],
    raw_model_output: str,
    parsed: dict[str, Any],
    generator_context: Any,
    validation_status: str | None,
    fallback_used: bool,
    model_calls: int,
    embedding_calls: int,
    generation_calls: int,
    retry_count: int,
    token_usage: dict[str, Any],
    stage_timings: dict[str, float],
    errors: list[dict[str, Any]],
    provider: RealApiProvider | None = None,
    generation_skipped: bool = True,
    adapter_input_profile: dict[str, Any] | None = None,
    internal_trace_hash: str | None = None,
    public_trace_hash: str | None = None,
    provider_response_id: str | None = None,
) -> dict[str, Any]:
    context_text = canonical_json(generator_context)
    protected_found = sorted({marker for marker in case.get("protected_markers", []) if marker and marker in context_text})
    stage_timings = {key: max(0.0, float(value)) for key, value in stage_timings.items()}
    for field in _required_latency_fields():
        stage_timings.setdefault(field, 0.0)
    if "end_to_end_ms" not in stage_timings:
        stage_timings["end_to_end_ms"] = sum(stage_timings.values())
    token_usage = dict(token_usage or {})
    token_usage.setdefault("input_tokens", 0)
    token_usage.setdefault("output_tokens", 0)
    return {
        "run_id": run_id,
        "case_id": case["case_id"],
        "pair_id": case.get("pair_id", case["case_id"]),
        "family": case.get("family", "smoke"),
        "variant": case.get("variant", "single"),
        "mode_name": mode_name,
        "repetition": repetition,
        "retrieval_snapshot_hash": retrieval_snapshot["snapshot_hash"],
        "raw_model_output": raw_model_output,
        "parsed_answer": parsed.get("answer"),
        "public_response": parsed.get("answer"),
        "observed_top_level_mode": parsed.get("top_level_mode"),
        "observed_fulfilment_status": parsed.get("fulfilment_status"),
        "observed_realization": parsed.get("realization"),
        "observed_public_reason_class": parsed.get("public_reason_class"),
        "observed_next_step_codes": list(parsed.get("next_step_codes") or []),
        "generator_context_hash": sha256_text(context_text),
        "generator_context_protected_markers": protected_found,
        "case_protected_markers": list(case.get("protected_markers", [])),
        "validation_status": validation_status,
        "fallback_used": bool(fallback_used),
        "model_calls": int(model_calls),
        "embedding_calls": int(embedding_calls),
        "generation_call_count": int(generation_calls),
        "retry_count": int(retry_count),
        "token_usage": token_usage,
        "input_tokens": token_usage.get("input_tokens"),
        "output_tokens": token_usage.get("output_tokens"),
        "stage_timings": stage_timings,
        "end_to_end_ms": stage_timings["end_to_end_ms"],
        "errors": errors,
        "generator_context_contains_cfaf_decision": "response_contract" in context_text or "top_level_mode" in context_text,
        "generator_context_hash_input": context_text if mode_name == MODE_CFAF_PIPELINE and provider is None else None,
        "generator_context_audit": _generator_context_audit(mode_name, generator_context, context_text, protected_found),
        "adapter_input_profile": adapter_input_profile or {},
        "real_api": provider is not None,
        "mock_or_stub_used": bool(provider.is_mock) if provider else False,
        "provider": provider.provider_name if provider else "deterministic-local",
        "generator_model": provider.generator_model if provider else "deterministic-envelope-generator-v1",
        "generation_skipped": bool(generation_skipped),
        "cache_state": "not-used",
        "cold_start_indicator": True,
        "internal_trace_hash": internal_trace_hash,
        "public_trace_hash": public_trace_hash,
        "provider_response_id": provider_response_id,
    }


def _baseline_timings(end_to_end_ms: float) -> dict[str, float]:
    return {
        "query_profiling_ms": 0.0,
        "candidate_retrieval_ms": 0.0,
        "access_and_safety_resolution_ms": 0.0,
        "evidence_labelling_ms": 0.0,
        "sufficiency_and_permitted_output_ms": 0.0,
        "top_level_mode_selection_ms": 0.0,
        "response_realization_ms": max(0.0, end_to_end_ms),
        "validation_trace_and_feedback_ms": 0.0,
        "embedding_api_ms": 0.0,
        "generation_api_ms": 0.0,
        "external_api_ms": 0.0,
        "end_to_end_ms": max(0.0, end_to_end_ms),
    }


def _elapsed_ms(start_ns: int) -> float:
    return max(0.0, (time.perf_counter_ns() - start_ns) / 1_000_000)


def _token_usage(context: Any, output: str) -> dict[str, int]:
    return {"input_tokens": len(canonical_json(context).split()), "output_tokens": len(output.split())}


def _next_step_codes(next_steps: list[str]) -> list[str]:
    codes = []
    joined = " ".join(next_steps).lower()
    if "content-level access" in joined:
        codes.append("request_content_access")
    if "aggregate" in joined or "individual-level access" in joined:
        codes.append("ask_aggregate_or_request_individual_access")
    if "primary evidence" in joined:
        codes.append("provide_primary_evidence")
    if "permitted source" in joined:
        codes.append("request_permitted_source_access")
    return codes or next_steps


def _infer_mode_fields(text: str) -> dict[str, Any]:
    lowered = text.lower()
    is_cfaf = any(marker in lowered for marker in ["cannot", "insufficient", "restrict", "not support", "permission", "access"])
    return {
        "top_level_mode": "CFAF" if is_cfaf else "FULL",
        "fulfilment_status": "NONE" if is_cfaf else "FULL",
        "realization": "ABSTAIN" if is_cfaf else None,
        "public_reason_class": "EVIDENTIAL" if is_cfaf else None,
    }


def _standard_rag_system_prompt() -> str:
    return (
        "You are the Standard RAG baseline for a development-only integration test. "
        "Use only the supplied raw synthetic retrieved candidates and query. "
        "You do not receive gold labels, CFAF decisions, access gates, response contracts, or internal traces. "
        "Return only a JSON object with keys answer, top_level_mode, fulfilment_status, realization, "
        "public_reason_class, and next_step_codes."
    )


def _prompt_only_system_prompt(prompt: str) -> str:
    return (
        prompt.strip()
        + "\nReturn only a JSON object with keys answer, top_level_mode, fulfilment_status, realization, "
        "public_reason_class, and next_step_codes. Do not claim access to labels, gates, response contracts, or internal traces."
    )


def _cfaf_system_prompt(prompt: str) -> str:
    return (
        prompt.strip()
        + "\nReturn only a JSON object with keys answer, top_level_mode, fulfilment_status, realization, "
        "public_reason_class, and next_step_codes. Copy the mode, fulfilment status, realization, reason class, "
        "and next-step codes from the response contract. If mode is FULL, the answer must use only allowed_claims. "
        "If mode is CFAF, the answer must be exactly public_reason_text. Never mention forbidden fields or hidden sources."
    )


def _baseline_user_payload(query: str, context: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "query": query,
        "retrieved_candidates": context,
        "output_schema": {
            "answer": "string",
            "top_level_mode": "FULL or CFAF",
            "fulfilment_status": "FULL, RESTRICTED, NONE, or DEFERRED",
            "realization": "null or CFAF realization label",
            "public_reason_class": "null or public reason class",
            "next_step_codes": "array of strings",
        },
    }


def _baseline_input_profile(mode_name: str, context: list[dict[str, Any]], *, uses_prompt: bool) -> dict[str, Any]:
    return {
        "mode_name": mode_name,
        "contains_query": True,
        "candidate_ids": [candidate["candidate_id"] for candidate in context],
        "receives_raw_retrieved_candidates": True,
        "uses_prompt_only_v1": uses_prompt,
        "contains_expected_mode": False,
        "contains_gold_reason": False,
        "contains_external_cfaf_decision": False,
        "contains_source_role_gate_result": False,
        "contains_permitted_output_object": False,
        "contains_cfaf_response_contract": False,
        "contains_internal_trace": False,
    }


def _cfaf_input_profile(state: Any) -> dict[str, Any]:
    return {
        "mode_name": MODE_CFAF_PIPELINE,
        "uses_eight_stage_pipeline_state": True,
        "contains_authoritative_access_labels": True,
        "contains_claim_relative_evidence_labels": True,
        "contains_permitted_output_computation": True,
        "contains_deterministic_mode_selection": True,
        "contains_cfaf_response_contract": state.response_contract is not None,
        "contains_internal_trace": False,
        "generator_receives_filtered_evidence_only": True,
        "allowed_evidence_view_count": len(state.response_contract.allowed_evidence_views) if state.response_contract else 0,
    }


def _cfaf_contract_observation(state: Any, model_parsed: dict[str, Any]) -> dict[str, Any]:
    contract = state.response_contract
    decision = state.mode_decision
    answer = str(model_parsed.get("answer") or "")
    if not answer and contract:
        if contract.mode == TopLevelMode.FULL:
            answer = " ".join(claim.get("answer") for claim in contract.allowed_claims if claim.get("answer"))
        else:
            answer = contract.public_reason_text
    return {
        "answer": answer,
        "top_level_mode": decision.mode.value if decision else model_parsed.get("top_level_mode"),
        "fulfilment_status": decision.fulfilment_status.value if decision else model_parsed.get("fulfilment_status"),
        "realization": decision.cfaf_realization.value if decision and decision.cfaf_realization else None,
        "public_reason_class": contract.public_reason_class.value if contract and contract.public_reason_class else None,
        "next_step_codes": _next_step_codes(decision.next_steps if decision else list(model_parsed.get("next_step_codes") or [])),
    }


def _response_leak_values(case: dict[str, Any], response: str) -> list[str]:
    values = [value for value in case.get("forbidden_disclosures", []) + case.get("protected_markers", []) if value]
    return sorted({value for value in values if value in response})


def _generator_context_audit(mode_name: str, generator_context: Any, context_text: str, protected_found: list[str]) -> dict[str, Any]:
    return {
        "mode_name": mode_name,
        "context_hash": sha256_text(context_text),
        "protected_marker_count": len(protected_found),
        "contains_response_contract": "response_contract" in context_text,
        "contains_raw_context": "raw_context" in context_text,
        "sanitized_context_summary": _context_summary(generator_context),
    }


def _context_summary(generator_context: Any) -> dict[str, Any]:
    if isinstance(generator_context, list):
        return {"container": "list", "item_count": len(generator_context)}
    if isinstance(generator_context, dict):
        return {"container": "dict", "top_level_keys": sorted(generator_context)}
    return {"container": type(generator_context).__name__}


def _required_latency_fields() -> list[str]:
    return [
        "query_profiling_ms",
        "candidate_retrieval_ms",
        "access_and_safety_resolution_ms",
        "evidence_labelling_ms",
        "sufficiency_and_permitted_output_ms",
        "top_level_mode_selection_ms",
        "response_realization_ms",
        "validation_trace_and_feedback_ms",
        "embedding_api_ms",
        "generation_api_ms",
        "external_api_ms",
        "end_to_end_ms",
    ]
