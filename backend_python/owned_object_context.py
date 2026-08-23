"""Governance-safe, content-derived owned-object context resolution.

This module deliberately knows nothing about ScenarioPack or evaluation labels.
It groups policy-permitted FULL document content by explicit product identifiers
and treats a group as owned only when its content contains purchase evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterable


RESOLUTION_VERSION = "infobank-owned-object-context-v1"
STATUS_INACTIVE = "inactive"
STATUS_RESOLVED = "resolved"
STATUS_CLARIFICATION_REQUIRED = "clarification_required"

_PRODUCT_CODE_PATTERN = re.compile(
    r"(?im)\b(?:product|model|item|device)\s*(?:code|id|number|no\.?)\s*[:#-]?\s*"
    r"([a-z0-9][a-z0-9._-]{2,})\b"
)
_QUERY_IDENTIFIER_PATTERN = re.compile(
    r"(?i)\b(?=[a-z0-9-]{6,}\b)(?=[a-z0-9-]*\d)[a-z0-9]+(?:-[a-z0-9]+)+\b"
)
_PURCHASE_RECORD_PATTERN = re.compile(
    r"(?i)\b(?:purchase\s+receipt|sales\s+receipt|receipt|invoice|proof\s+of\s+purchase|purchase\s+record|sales\s+order)\b"
)
_TRANSACTION_SIGNAL_PATTERNS = (
    re.compile(r"(?i)\b(?:purchase|order|invoice|transaction)\s+date\b"),
    re.compile(r"(?i)\b(?:total|amount|unit\s+price|price)\s*(?:paid|due)?\b"),
    re.compile(r"(?i)\bpayment\s+(?:status|method)\b|\bpaid\b"),
    re.compile(r"(?i)\b(?:customer|sold\s+to|bill\s+to)\b"),
    re.compile(r"(?i)\b(?:receipt|invoice|order|transaction)\s+(?:number|no\.?|id)\b"),
)

# These are generic product-type lexical aliases, not scenario labels. They are
# used only when the user explicitly names an object type in the question and
# the same type occurs in a permitted product document.
_OBJECT_TYPE_ALIASES = {
    "air_conditioner": ("air conditioner", "air conditioning unit"),
    "armchair": ("armchair",),
    "camera": ("camera",),
    "car": ("car", "vehicle"),
    "chair": ("chair",),
    "computer": ("computer", "desktop computer"),
    "dishwasher": ("dishwasher",),
    "fridge": ("fridge", "refrigerator"),
    "laptop": ("laptop", "notebook computer"),
    "modem": ("modem",),
    "monitor": ("monitor", "display"),
    "oven": ("oven",),
    "phone": ("phone", "smartphone", "mobile phone"),
    "printer": ("printer",),
    "router": ("router",),
    "rug": ("rug", "carpet"),
    "sofa": ("sofa", "couch", "settee"),
    "speaker": ("speaker",),
    "tablet": ("tablet",),
    "television": ("television", "tv"),
    "vacuum": ("vacuum", "vacuum cleaner"),
    "washer": ("washing machine", "washer"),
}


def _config_hash() -> str:
    payload = {
        "version": RESOLUTION_VERSION,
        "product_identifier": "label_scoped_product_model_item_device_code",
        "purchase_evidence": "record_marker_and_two_transaction_signals",
        "content_scope": "policy_permitted_full_content_only",
        "object_aliases": _OBJECT_TYPE_ALIASES,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


CONFIG_HASH = _config_hash()


@dataclass(frozen=True)
class PermittedDocumentContent:
    document_id: str
    text: str


@dataclass(frozen=True)
class OwnedObjectResolution:
    status: str
    reason: str
    candidate_document_ids: tuple[str, ...]
    structured_document_count: int
    object_cluster_count: int
    purchase_evidenced_object_count: int
    explicit_reference_match_count: int

    def public_trace(self) -> dict:
        """Return a privacy-safe trace with no identifiers or source content."""

        return {
            "version": RESOLUTION_VERSION,
            "config_hash": CONFIG_HASH,
            "status": self.status,
            "reason": self.reason,
            "content_scope": "policy_permitted_full_content_only",
            "governance_preserved": True,
            "structured_document_count": self.structured_document_count,
            "object_cluster_count": self.object_cluster_count,
            "purchase_evidenced_object_count": self.purchase_evidenced_object_count,
            "explicit_reference_match_count": self.explicit_reference_match_count,
            "candidate_document_count": len(self.candidate_document_ids),
        }


def extract_product_codes(text: str) -> tuple[str, ...]:
    codes: set[str] = set()
    for match in _PRODUCT_CODE_PATTERN.finditer(text or ""):
        code = match.group(1).upper()
        if any(character.isdigit() for character in code):
            codes.add(code)
    return tuple(sorted(codes))


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.IGNORECASE))


def extract_object_types(text: str) -> tuple[str, ...]:
    normalized = text or ""
    return tuple(
        object_type
        for object_type, aliases in sorted(_OBJECT_TYPE_ALIASES.items())
        if any(_contains_phrase(normalized, alias) for alias in aliases)
    )


def _declared_product_descriptions(text: str) -> tuple[str, ...]:
    """Extract PRODUCT/ITEM field values without reading narrative mentions."""

    lines = [line.strip() for line in (text or "").splitlines()]
    descriptions: list[str] = []
    label_pattern = re.compile(r"(?i)^(?:product|item|device)(?:\s+(?:name|description))?\s*:?$")
    inline_pattern = re.compile(
        r"(?i)^(?:product|item|device)(?:\s+(?:name|description))?\s*(?::|\s)\s*"
        r"(?!code\b|id\b|number\b|no\.?\b)(.+)$"
    )
    for index, line in enumerate(lines):
        if not line:
            continue
        if label_pattern.fullmatch(line):
            for following in lines[index + 1:]:
                if following:
                    descriptions.append(following)
                    break
            continue
        inline = inline_pattern.match(line)
        if inline:
            descriptions.append(inline.group(1).strip())
    return tuple(descriptions)


def extract_declared_object_types(text: str) -> tuple[str, ...]:
    descriptions = "\n".join(_declared_product_descriptions(text))
    return extract_object_types(descriptions)


def contains_purchase_evidence(text: str) -> bool:
    normalized = text or ""
    if not _PURCHASE_RECORD_PATTERN.search(normalized):
        return False
    signal_count = sum(bool(pattern.search(normalized)) for pattern in _TRANSACTION_SIGNAL_PATTERNS)
    return signal_count >= 2


def _resolution(
    *,
    status: str,
    reason: str,
    candidates: Iterable[str],
    structured_document_count: int,
    object_cluster_count: int,
    purchase_evidenced_object_count: int,
    explicit_reference_match_count: int = 0,
) -> OwnedObjectResolution:
    return OwnedObjectResolution(
        status=status,
        reason=reason,
        candidate_document_ids=tuple(sorted(set(candidates))),
        structured_document_count=structured_document_count,
        object_cluster_count=object_cluster_count,
        purchase_evidenced_object_count=purchase_evidenced_object_count,
        explicit_reference_match_count=explicit_reference_match_count,
    )


def resolve_owned_object_context(
    question: str,
    documents: Iterable[PermittedDocumentContent],
) -> OwnedObjectResolution:
    """Resolve the smallest content-derived product cluster for a question.

    Callers are responsible for passing only FULL content that has already been
    authorized for the current user and purpose. An unstructured corpus leaves
    existing retrieval behavior untouched.
    """

    records = tuple(sorted(documents, key=lambda item: item.document_id))
    codes_by_document = {record.document_id: extract_product_codes(record.text) for record in records}
    structured_document_count = sum(bool(codes) for codes in codes_by_document.values())
    if not structured_document_count:
        return _resolution(
            status=STATUS_INACTIVE,
            reason="no_structured_product_identifiers",
            candidates=(),
            structured_document_count=0,
            object_cluster_count=0,
            purchase_evidenced_object_count=0,
        )

    documents_by_code: dict[str, set[str]] = {}
    types_by_code: dict[str, set[str]] = {}
    purchase_codes: set[str] = set()
    for record in records:
        codes = codes_by_document[record.document_id]
        object_types = set(extract_declared_object_types(record.text))
        purchase_evidence = contains_purchase_evidence(record.text)
        for code in codes:
            documents_by_code.setdefault(code, set()).add(record.document_id)
            types_by_code.setdefault(code, set()).update(object_types)
            if purchase_evidence:
                purchase_codes.add(code)

    cluster_count = len(documents_by_code)
    purchase_count = len(purchase_codes)
    question_upper = (question or "").upper()
    requested_identifiers = {match.group(0).upper() for match in _QUERY_IDENTIFIER_PATTERN.finditer(question_upper)}
    if requested_identifiers:
        matching_codes = requested_identifiers.intersection(documents_by_code)
        if len(matching_codes) == 1:
            code = next(iter(matching_codes))
            return _resolution(
                status=STATUS_RESOLVED,
                reason="explicit_product_identifier",
                candidates=documents_by_code[code],
                structured_document_count=structured_document_count,
                object_cluster_count=cluster_count,
                purchase_evidenced_object_count=purchase_count,
                explicit_reference_match_count=1,
            )
        return _resolution(
            status=STATUS_CLARIFICATION_REQUIRED,
            reason="explicit_product_identifier_not_uniquely_resolved",
            candidates=(),
            structured_document_count=structured_document_count,
            object_cluster_count=cluster_count,
            purchase_evidenced_object_count=purchase_count,
            explicit_reference_match_count=len(matching_codes),
        )

    question_types = set(extract_object_types(question))
    if question_types:
        matching_codes = {
            code for code, object_types in types_by_code.items()
            if object_types.intersection(question_types)
        }
        if len(matching_codes) == 1:
            code = next(iter(matching_codes))
            return _resolution(
                status=STATUS_RESOLVED,
                reason="explicit_object_type",
                candidates=documents_by_code[code],
                structured_document_count=structured_document_count,
                object_cluster_count=cluster_count,
                purchase_evidenced_object_count=purchase_count,
                explicit_reference_match_count=1,
            )
        return _resolution(
            status=STATUS_CLARIFICATION_REQUIRED,
            reason="explicit_object_type_not_uniquely_resolved",
            candidates=(),
            structured_document_count=structured_document_count,
            object_cluster_count=cluster_count,
            purchase_evidenced_object_count=purchase_count,
            explicit_reference_match_count=len(matching_codes),
        )

    if purchase_count == 1:
        code = next(iter(purchase_codes))
        return _resolution(
            status=STATUS_RESOLVED,
            reason="unique_purchase_evidenced_object",
            candidates=documents_by_code[code],
            structured_document_count=structured_document_count,
            object_cluster_count=cluster_count,
            purchase_evidenced_object_count=1,
        )

    reason = "multiple_purchase_evidenced_objects" if purchase_count > 1 else "no_purchase_evidenced_object"
    return _resolution(
        status=STATUS_CLARIFICATION_REQUIRED,
        reason=reason,
        candidates=(),
        structured_document_count=structured_document_count,
        object_cluster_count=cluster_count,
        purchase_evidenced_object_count=purchase_count,
    )
