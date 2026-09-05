from __future__ import annotations

from typing import Any

from .common import stable_hash


RETRIEVER_VERSION = "wolala_shared_retrieval_v1"


def build_retrieval_snapshot(case: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for index, source in enumerate([s for s in case.get("sources", []) if s.get("retrieved", True)], start=1):
        candidates.append(
            {
                "candidate_id": source.get("candidate_id", f"{case['case_id']}-candidate-{index}"),
                "source_id": source["source_id"],
                "source_type": source.get("source_type"),
                "title": source.get("title"),
                "candidate_order": index,
                "permitted_experimental_raw_text": source.get("content", ""),
                "metadata": {
                    "source_type": source.get("source_type"),
                    "title": source.get("title"),
                    "thread_id": source.get("thread_id"),
                    "evidence_unit_id": source.get("evidence_unit_id"),
                },
                "retrieval_score": source.get("retrieval_score", 1.0 / index),
                "retriever_name": source.get("retriever_name", RETRIEVER_VERSION),
            }
        )
    snapshot = {
        "query": case["query"],
        "case_id": case["case_id"],
        "candidate_ids": [candidate["candidate_id"] for candidate in candidates],
        "candidate_order": [candidate["candidate_id"] for candidate in candidates],
        "candidates": candidates,
        "retrieval_scores": [candidate["retrieval_score"] for candidate in candidates],
        "retriever_version": RETRIEVER_VERSION,
        "embedding_calls": 0,
    }
    snapshot["snapshot_hash"] = stable_hash(snapshot)
    return snapshot
