"""Gold-annotation schema and scorer-only loader.

Execution modules must never import this module.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


GOLD_SCHEMA_VERSION = "infobank-gold-annotation-v1"
PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
HUMAN_VALIDATED = "HUMAN_VALIDATED"
HUMAN_VALIDATION_STATES = {PENDING_HUMAN_REVIEW, HUMAN_VALIDATED}


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
    manual_validation_state: str = PENDING_HUMAN_REVIEW
    dataset_version: str = "actual-pipeline-development-v1"
    schema_version: str = GOLD_SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)
    # Roadmap v1.8 canonical fields. None means a legacy v1 artifact; an empty
    # tuple is an explicit assertion that no content source is required.
    required_sources: tuple[str, ...] | None = None
    reference_citations: tuple[dict[str, Any], ...] | None = None

    def __post_init__(self) -> None:
        if self.manual_validation_state not in HUMAN_VALIDATION_STATES:
            raise ValueError("manual_validation_state is not recognized")
        if (self.required_sources is None) != (self.reference_citations is None):
            raise ValueError("required_sources and reference_citations must be present together")
        if self.required_sources is not None:
            if not all(isinstance(item, str) and item.strip() for item in self.required_sources):
                raise ValueError("required_sources must contain non-empty source IDs")
            if len(self.required_sources) != len(set(self.required_sources)):
                raise ValueError("required_sources must not contain duplicates")
            if not set(self.required_sources).issubset(self.gold_document_ids):
                raise ValueError("required_sources must be a subset of legacy gold_document_ids")
        if self.reference_citations is not None:
            page_ranges: dict[str, list[int]] = {}
            for citation in self.reference_citations:
                source_id = citation.get("source_id")
                if not isinstance(source_id, str) or not source_id:
                    raise ValueError("reference_citations require a source_id")
                if source_id not in self.gold_document_ids:
                    raise ValueError("reference citation source must be present in legacy gold_document_ids")
                locators = [citation.get("page"), citation.get("message_id"), citation.get("record_id")]
                if sum(value is not None for value in locators) != 1:
                    raise ValueError("reference citation requires exactly one locator")
                page = citation.get("page")
                if page is not None:
                    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
                        raise ValueError("reference citation page must be a positive integer")
                    page_ranges.setdefault(source_id, []).append(page)
                for name in ("message_id", "record_id"):
                    value = citation.get(name)
                    if value is not None and (not isinstance(value, str) or not value.strip()):
                        raise ValueError(f"reference citation {name} must be a non-empty string")
            normalized_ranges = {key: sorted(set(value)) for key, value in page_ranges.items()}
            normalized_legacy = {
                key: sorted(set(value))
                for key, value in self.gold_page_or_message_ranges.items()
                if value
            }
            citation_source_ids = {str(item["source_id"]) for item in self.reference_citations}
            page_mismatch = any(normalized_legacy.get(key) != pages for key, pages in normalized_ranges.items())
            uncited_legacy_source = bool(set(normalized_legacy) - citation_source_ids)
            if page_mismatch or uncited_legacy_source:
                raise ValueError("reference_citations page locators must match legacy gold_page_or_message_ranges")

    @property
    def required_source_ids(self) -> tuple[str, ...]:
        """Return the canonical minimal source set with legacy fallback."""

        return self.gold_document_ids if self.required_sources is None else self.required_sources

    @property
    def reference_page_ranges(self) -> dict[str, list[int]]:
        """Return canonical page locators with legacy fallback."""

        if self.reference_citations is None:
            return self.gold_page_or_message_ranges
        ranges: dict[str, list[int]] = {}
        for citation in self.reference_citations:
            page = citation.get("page")
            if page is not None:
                ranges.setdefault(str(citation["source_id"]), []).append(int(page))
        return {key: sorted(set(value)) for key, value in ranges.items()}

    @property
    def acceptable_page_ranges(self) -> dict[str, list[int]]:
        """Return document IDs mapped to human-approved acceptable page sets."""

        return self.reference_page_ranges

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["gold_document_ids"] = list(self.gold_document_ids)
        value["factual_atoms"] = list(self.factual_atoms)
        value["required_evidence_roles"] = list(self.required_evidence_roles)
        if self.required_sources is None:
            value.pop("required_sources")
        else:
            value["required_sources"] = list(self.required_sources)
        if self.reference_citations is None:
            value.pop("reference_citations")
        else:
            value["reference_citations"] = [dict(item) for item in self.reference_citations]
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
        required_sources = value.get("required_sources")
        reference_citations = value.get("reference_citations")
        if required_sources is not None and not isinstance(required_sources, list):
            raise ValueError("required_sources must be an array when present")
        if reference_citations is not None and not isinstance(reference_citations, list):
            raise ValueError("reference_citations must be an array when present")
        annotations.append(
            GoldAnnotation(
                **{
                    **value,
                    "gold_document_ids": tuple(value.get("gold_document_ids", [])),
                    "factual_atoms": tuple(value.get("factual_atoms", [])),
                    "required_evidence_roles": tuple(value.get("required_evidence_roles", [])),
                    "required_sources": None if required_sources is None else tuple(required_sources),
                    "reference_citations": None if reference_citations is None else tuple(reference_citations),
                }
            )
        )
    return annotations
