from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .common import canonical_json, sha256_text, stable_hash
from .labels import TopLevelMode, json_safe
from .pipeline import run_pipeline
from .retrieval import build_retrieval_snapshot


MODE_STANDARD_RAG = "standard_rag"
MODE_PROMPT_ONLY_CONTROL = "prompt_only_control"
MODE_CFAF_PIPELINE = "cfaf_pipeline"
ALL_MODES = [MODE_STANDARD_RAG, MODE_PROMPT_ONLY_CONTROL, MODE_CFAF_PIPELINE]
PACKAGE_DIR = Path(__file__).resolve().parent


class ExperimentAdapter(Protocol):
    mode: str

    def run(self, case: dict[str, Any], retrieval_snapshot: dict[str, Any], *, run_id: str, repetition: int) -> dict[str, Any]:
        ...


@dataclass
class StandardRagAdapter:
    mode: str = MODE_STANDARD_RAG

    def run(self, case: dict[str, Any], retrieval_snapshot: dict[str, Any], *, run_id: str, repetition: int) -> dict[str, Any]:
        start_ns = time.perf_counter_ns()
        context = _raw_context(retrieval_snapshot)
        raw_output = _standard_generate(case["query"], context)
        parsed = parse_output(raw_output)
        elapsed_ms = _elapsed_ms(start_ns)
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
            model_calls=0,
            embedding_calls=0,
            stage_timings=_baseline_timings(elapsed_ms),
            token_usage=_token_usage(context, raw_output),
            errors=[],
        )


@dataclass
class PromptOnlyControlAdapter:
    mode: str = MODE_PROMPT_ONLY_CONTROL
    prompt_path: Path = PACKAGE_DIR / "prompts" / "prompt_only_v1.txt"

    def run(self, case: dict[str, Any], retrieval_snapshot: dict[str, Any], *, run_id: str, repetition: int) -> dict[str, Any]:
        start_ns = time.perf_counter_ns()
        context = _raw_context(retrieval_snapshot)
        prompt = self.prompt_path.read_text(encoding="utf-8") if self.prompt_path.exists() else ""
        raw_output = _prompt_only_generate(case["query"], context, prompt)
        parsed = parse_output(raw_output)
        elapsed_ms = _elapsed_ms(start_ns)
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
            model_calls=0,
            embedding_calls=0,
            stage_timings=_baseline_timings(elapsed_ms),
            token_usage=_token_usage({"system_instruction": prompt, "raw_context": context}, raw_output),
            errors=[],
        )


@dataclass
class CFAFPipelineAdapter:
    mode: str = MODE_CFAF_PIPELINE
    prompt_path: Path = PACKAGE_DIR / "prompts" / "cfaf_generator_v1.txt"

    def run(self, case: dict[str, Any], retrieval_snapshot: dict[str, Any], *, run_id: str, repetition: int) -> dict[str, Any]:
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
        return _result_envelope(
            run_id=run_id,
            case=case,
            mode_name=self.mode,
            repetition=repetition,
            retrieval_snapshot=retrieval_snapshot,
            raw_model_output=canonical_json(parsed),
            parsed=parsed,
            generator_context=context,
            validation_status=state.validation.status.value if state.validation else None,
            fallback_used=state.validation.fallback_used if state.validation else False,
            model_calls=state.model_call_count,
            embedding_calls=0,
            stage_timings={**state.stage_timings, **state.api_timings},
            token_usage=state.token_usage,
            errors=[],
        )


def adapter_for_mode(mode: str) -> ExperimentAdapter:
    if mode == MODE_STANDARD_RAG:
        return StandardRagAdapter()
    if mode == MODE_PROMPT_ONLY_CONTROL:
        return PromptOnlyControlAdapter()
    if mode == MODE_CFAF_PIPELINE:
        return CFAFPipelineAdapter()
    raise ValueError(f"Unknown WoLaLa mode: {mode}")


def run_adapters_for_case(case: dict[str, Any], modes: list[str], *, run_id: str, repetition: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    snapshot = build_retrieval_snapshot(case)
    return snapshot, [adapter_for_mode(mode).run(case, snapshot, run_id=run_id, repetition=repetition) for mode in modes]


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
            return {
                "answer": str(parsed.get("answer") or ""),
                "top_level_mode": parsed.get("top_level_mode"),
                "fulfilment_status": parsed.get("fulfilment_status"),
                "realization": parsed.get("realization"),
                "public_reason_class": parsed.get("public_reason_class"),
                "next_step_codes": list(parsed.get("next_step_codes") or []),
            }
    except Exception:
        pass
    lowered = raw_model_output.lower()
    return {
        "answer": raw_model_output,
        "top_level_mode": "CFAF" if "cannot" in lowered or "insufficient" in lowered else "FULL",
        "fulfilment_status": "NONE" if "cannot" in lowered else "FULL",
        "realization": "ABSTAIN" if "cannot" in lowered else None,
        "public_reason_class": "EVIDENTIAL" if "cannot" in lowered else None,
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
    token_usage: dict[str, Any],
    stage_timings: dict[str, float],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    context_text = canonical_json(generator_context)
    protected_found = sorted({marker for marker in case.get("protected_markers", []) if marker and marker in context_text})
    stage_timings = {key: max(0.0, float(value)) for key, value in stage_timings.items()}
    if "end_to_end_ms" not in stage_timings:
        stage_timings["end_to_end_ms"] = sum(stage_timings.values())
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
        "validation_status": validation_status,
        "fallback_used": bool(fallback_used),
        "model_calls": int(model_calls),
        "embedding_calls": int(embedding_calls),
        "token_usage": token_usage,
        "stage_timings": stage_timings,
        "end_to_end_ms": stage_timings["end_to_end_ms"],
        "errors": errors,
        "generator_context_contains_cfaf_decision": "response_contract" in context_text or "top_level_mode" in context_text,
        "generator_context_hash_input": context_text if mode_name == MODE_CFAF_PIPELINE else None,
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
