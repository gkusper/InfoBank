"""Gold-annotation schema and scorer-only loader.

Execution modules must never import this module.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


GOLD_SCHEMA_VERSION = "infobank-gold-annotation-v1"


@dataclass(frozen=True)
class GoldAnnotation:
    case_id: str
    expected_output_class: str
    reason_code: str
    gold_document_ids: tuple[str, ...]
    gold_page_or_message_ranges: dict[str, list[int]]
    reference_answer: str | None
    factual_atoms: tuple[str, ...]
    required_evidence_roles: tuple[str, ...]
    action_status: str
    manual_validation_state: str = "PENDING_HUMAN_REVIEW"
    dataset_version: str = "actual-pipeline-development-v1"
    schema_version: str = GOLD_SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["gold_document_ids"] = list(self.gold_document_ids)
        value["factual_atoms"] = list(self.factual_atoms)
        value["required_evidence_roles"] = list(self.required_evidence_roles)
        return value


def load_gold_annotations(path: str | Path) -> list[GoldAnnotation]:
    annotations: list[GoldAnnotation] = []
    seen: set[str] = set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        case_id = str(value.get("case_id", ""))
        if not case_id or case_id in seen:
            raise ValueError(f"Missing or duplicate gold case_id at line {line_number}")
        if value.get("schema_version") != GOLD_SCHEMA_VERSION:
            raise ValueError("Gold schema/version mismatch")
        seen.add(case_id)
        annotations.append(
            GoldAnnotation(
                **{
                    **value,
                    "gold_document_ids": tuple(value.get("gold_document_ids", [])),
                    "factual_atoms": tuple(value.get("factual_atoms", [])),
                    "required_evidence_roles": tuple(value.get("required_evidence_roles", [])),
                }
            )
        )
    return annotations
