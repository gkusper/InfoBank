from __future__ import annotations

from pathlib import Path
from typing import Any

from .modes import (
    Generator,
    run_governance_only_rag,
    run_role_aware_rag,
    run_standard_rag,
)
from .schemas import (
    EvaluationResult,
    GenerationConfig,
    MODE_GOVERNANCE,
    MODE_ROLE_AWARE,
    MODE_STANDARD,
    SharedRetrievalResult,
    write_jsonl_record,
)


MODE_ALIASES = {
    "standard": MODE_STANDARD,
    "standard_rag": MODE_STANDARD,
    "governance": MODE_GOVERNANCE,
    "governance-only": MODE_GOVERNANCE,
    "governance_only_rag": MODE_GOVERNANCE,
    "role-aware": MODE_ROLE_AWARE,
    "role_aware": MODE_ROLE_AWARE,
    "role_aware_rag": MODE_ROLE_AWARE,
}


def normalize_modes(modes: list[str] | str | None) -> list[str]:
    if modes is None:
        return [MODE_STANDARD, MODE_GOVERNANCE, MODE_ROLE_AWARE]
    if isinstance(modes, str):
        modes = [part.strip() for part in modes.split(",") if part.strip()]
    normalized = []
    for mode in modes:
        value = MODE_ALIASES.get(mode, mode)
        if value not in {MODE_STANDARD, MODE_GOVERNANCE, MODE_ROLE_AWARE}:
            raise ValueError(f"Unknown evaluation mode: {mode}")
        normalized.append(value)
    return normalized


def run_case(
    *,
    run_id: str,
    case_id: str,
    user_id: str,
    retrieval: SharedRetrievalResult,
    generation_config: GenerationConfig,
    generator: Generator,
    repetitions: int = 1,
    modes: list[str] | str | None = None,
    git_commit: str | None = None,
    db: Any | None = None,
    policy_context: dict[str, Any] | None = None,
    services: Any | None = None,
    results_jsonl: str | Path | None = None,
) -> list[EvaluationResult]:
    results: list[EvaluationResult] = []
    normalized_modes = normalize_modes(modes)
    for repetition in range(1, repetitions + 1):
        for index, mode in enumerate(normalized_modes):
            if mode == MODE_STANDARD:
                result = run_standard_rag(
                    run_id=run_id,
                    case_id=case_id,
                    repetition=repetition,
                    git_commit=git_commit,
                    retrieval=retrieval,
                    generation_config=generation_config,
                    generator=generator,
                )
            elif mode == MODE_GOVERNANCE:
                result = run_governance_only_rag(
                    run_id=run_id,
                    case_id=case_id,
                    repetition=repetition,
                    git_commit=git_commit,
                    retrieval=retrieval,
                    generation_config=generation_config,
                    generator=generator,
                    user_id=user_id,
                    db=db,
                    policy_context=policy_context,
                    services=services,
                )
            else:
                result = run_role_aware_rag(
                    run_id=run_id,
                    case_id=case_id,
                    repetition=repetition,
                    git_commit=git_commit,
                    retrieval=retrieval,
                    generation_config=generation_config,
                    generator=generator,
                    user_id=user_id,
                    db=db,
                    policy_context=policy_context,
                    services=services,
                )
            if repetition == 1 and index == 0:
                result.api_usage["embedding_calls"] = retrieval.api_usage.get("embedding_calls", 0)
                result.api_usage["keyword_routing_calls"] = retrieval.api_usage.get("keyword_routing_calls", 0)
            results.append(result)
            if results_jsonl:
                write_jsonl_record(results_jsonl, result)
    return results
