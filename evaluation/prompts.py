from __future__ import annotations

import json
from typing import Any

from .schemas import RetrievedCandidate


COMMON_TASK_INSTRUCTION = (
    "Answer the user's question using only the supplied retrieved passages. "
    "If the passages do not support an answer, say that the available passages are insufficient. "
    "Do not use outside knowledge."
)

STANDARD_CONSTRAINTS = (
    "Use the passages as a conventional private-corpus RAG system would. "
    "Do not add access-control analysis or evidence-role labels."
)

GOVERNANCE_CONSTRAINTS = (
    "Respect the supplied access decisions. Full passages may support answers. "
    "Metadata-only or denied sources have their contents withheld. Aggregate-only sources are non-quotable and may support only cohort-level or statistical statements."
)

ROLE_AWARE_CONSTRAINTS = (
    "Use the supplied governance, usable-relevance, source-role, evidence-check, and output-mode information. "
    "Primary sources may support direct claims. Contextual and analogical sources cannot create direct claims by themselves. "
    "Contrastive sources may weaken, cancel, or close claims. Metadata-only sources must not support content claims."
)


def format_raw_candidate_blocks(candidates: list[RetrievedCandidate]) -> list[str]:
    blocks: list[str] = []
    for candidate in candidates:
        blocks.append(
            "\n".join(
                [
                    f"[Passage {candidate.rank}]",
                    f"Document: {candidate.file_name}",
                    f"Document ID: {candidate.document_id}",
                    f"Chunk ID: {candidate.chunk_id}",
                    candidate.raw_text,
                ]
            )
        )
    return blocks


def build_standard_prompt(question: str, context_blocks: list[str]) -> tuple[str, str]:
    system_prompt = f"{COMMON_TASK_INSTRUCTION} {STANDARD_CONSTRAINTS}"
    user_prompt = "Question:\n{question}\n\nRetrieved passages:\n{context}".format(
        question=question,
        context="\n\n---\n\n".join(context_blocks),
    )
    return system_prompt, user_prompt


def build_governance_prompt(question: str, context_blocks: list[str], governance_context: dict[str, Any]) -> tuple[str, str]:
    system_prompt = f"{COMMON_TASK_INSTRUCTION} {GOVERNANCE_CONSTRAINTS}"
    user_prompt = "Question:\n{question}\n\nAccess decisions:\n{decisions}\n\nPermitted passages:\n{context}".format(
        question=question,
        decisions=json.dumps(governance_context.get("use_decisions", {}), ensure_ascii=False, sort_keys=True),
        context="\n\n---\n\n".join(context_blocks),
    )
    return system_prompt, user_prompt


def build_role_aware_prompt(
    *,
    question: str,
    query_profile: dict[str, Any],
    governance_context: dict[str, Any],
    role_summary: dict[str, Any],
    relevance_level_summary: dict[str, Any],
    evidence_check: dict[str, Any],
    output_gate: dict[str, Any],
    context_blocks: list[str],
) -> tuple[str, str]:
    system_prompt = f"{COMMON_TASK_INSTRUCTION} {ROLE_AWARE_CONSTRAINTS}"
    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Query profile:\n{json.dumps(query_profile, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Governance:\n{json.dumps(governance_context, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Source role summary:\n{json.dumps(role_summary, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Relevance level summary:\n{json.dumps(relevance_level_summary, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Evidence check:\n{json.dumps(evidence_check, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Output mode gate:\n{json.dumps(output_gate, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Retrieved passages:\n{chr(10).join(context_blocks)}"
    )
    return system_prompt, user_prompt
