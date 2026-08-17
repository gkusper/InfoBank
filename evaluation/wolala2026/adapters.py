from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .pipeline import run_pipeline


MODE_STANDARD_RAG = "standard_rag"
MODE_PROMPT_ONLY_CONTROL = "prompt_only_control"
MODE_CFAF_PIPELINE = "cfaf_pipeline"


class ExperimentAdapter(Protocol):
    mode: str

    def run(self, case: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass
class StandardRagAdapter:
    mode: str = MODE_STANDARD_RAG

    def run(self, case: dict[str, Any]) -> dict[str, Any]:
        raw_context = [source.get("content", "") for source in case.get("sources", []) if source.get("retrieved", True)]
        return {
            "mode": self.mode,
            "case_id": case["case_id"],
            "raw_context_count": len(raw_context),
            "external_cfaf_gate_used": False,
            "notes": "Prepared stub: later Standard RAG receives raw retrieved content and bypasses CFAF enforcement.",
        }


@dataclass
class PromptOnlyControlAdapter:
    mode: str = MODE_PROMPT_ONLY_CONTROL

    def run(self, case: dict[str, Any]) -> dict[str, Any]:
        raw_context = [source.get("content", "") for source in case.get("sources", []) if source.get("retrieved", True)]
        return {
            "mode": self.mode,
            "case_id": case["case_id"],
            "raw_context_count": len(raw_context),
            "external_cfaf_gate_used": False,
            "instruction": "Abstain or restrict when the prompt says evidence or permission is insufficient.",
            "notes": "Prepared stub: later prompt-only control gets the same raw content as Standard RAG plus refusal instructions.",
        }


@dataclass
class CFAFPipelineAdapter:
    mode: str = MODE_CFAF_PIPELINE

    def run(self, case: dict[str, Any]) -> dict[str, Any]:
        state = run_pipeline(case, adapter_mode=self.mode)
        return {
            "mode": self.mode,
            "case_id": case["case_id"],
            "top_level_mode": state.mode_decision.mode.value if state.mode_decision else None,
            "external_cfaf_gate_used": True,
            "generation_skipped": state.generation_skipped,
        }


def smoke_test_adapters(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [StandardRagAdapter().run(case), PromptOnlyControlAdapter().run(case), CFAFPipelineAdapter().run(case)]
