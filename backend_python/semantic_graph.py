"""Deterministic Semantic Co-occurrence Graph export."""

from __future__ import annotations

import re
import uuid
from itertools import combinations
from typing import Iterable, Mapping


GRAPH_SCHEMA_VERSION = "semantic-cooccurrence-graph-v1"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def stable_node_id(keyword: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:{GRAPH_SCHEMA_VERSION}:{_normalize(keyword)}"))


def build_semantic_cooccurrence_graph(document_keywords: Mapping[str, Iterable[str]]) -> dict:
    """Build a stable keyword graph without paths or source content."""

    normalized_documents: list[tuple[str, tuple[str, ...]]] = []
    for document_id, keywords in document_keywords.items():
        normalized = tuple(sorted({item for value in keywords if (item := _normalize(value))}))
        if normalized:
            normalized_documents.append((str(document_id), normalized))
    normalized_documents.sort(key=lambda item: item[0])

    frequencies: dict[str, int] = {}
    pair_counts: dict[tuple[str, str], int] = {}
    for _, keywords in normalized_documents:
        for keyword in keywords:
            frequencies[keyword] = frequencies.get(keyword, 0) + 1
        for left, right in combinations(keywords, 2):
            pair_counts[(left, right)] = pair_counts.get((left, right), 0) + 1

    nodes = [
        {
            "id": stable_node_id(keyword),
            "keyword": keyword,
            "document_frequency": frequencies[keyword],
            "val": frequencies[keyword],
        }
        for keyword in sorted(frequencies)
    ]
    links = [
        {
            "source": stable_node_id(left),
            "target": stable_node_id(right),
            "source_keyword": left,
            "target_keyword": right,
            "shared_document_count": count,
            "value": count,
        }
        for (left, right), count in sorted(pair_counts.items())
    ]
    return {
        "status": "success",
        "schema_version": GRAPH_SCHEMA_VERSION,
        "scope": "governance-filtered_visualization_only",
        "document_count": len(normalized_documents),
        "nodes": nodes,
        "links": links,
    }
