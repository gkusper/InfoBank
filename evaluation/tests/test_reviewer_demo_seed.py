from __future__ import annotations

import json
from pathlib import Path

from evaluation.reviewer_demo_seed import DEMO_SEED_VERSION, build_reviewer_demo_seed


def _record(workflow: str, step: str, response: dict, *, question: str | None = None, filename: str | None = None) -> dict:
    fields = {}
    if question is not None:
        fields["question"] = question
    if filename is not None:
        fields["file"] = {"filename": filename}
    return {"workflow": workflow, "step": step, "request": {"fields": fields}, "response": response}


def test_reviewer_seed_uses_actual_answer_and_deterministic_action_engine(tmp_path: Path) -> None:
    sources = []
    documents = []
    for index, kind in enumerate(("warranty", "support"), start=1):
        doc_id = f"00000000-0000-0000-0000-00000000000{index}"
        documents.append(_record("W1", f"upload-tv-{kind}", {
            "document_id": doc_id, "source_sha256": str(index) * 64,
            "page_count": 1, "chunk_count": 1, "keywords": ["TVX-900", kind],
            "keyword_extraction_mode": "rules",
        }, filename=f"tvx-900-{kind}.pdf"))
        sources.append({
            "document_id": doc_id, "file_name": f"tvx-900-{kind}.pdf", "role": "primary", "use_decision": "full",
            "text": f"Synthetic {kind} evidence.",
            "citation": {"document_id": doc_id, "page_number": 1, "chunk_id": f"chunk-{index}", "effective_use_decision": "full"},
        })
    response = {
        "status": "success", "answer": "Actual deterministic response.", "output_mode": "FULL_ANSWER", "audit_id": "audit-1",
        "extracted_keywords": ["TVX-900"], "query_profile": {"routing_trace": {"mode": "KEYWORD_ROUTING"}},
        "governance": {"routing_trace": {"mode": "KEYWORD_ROUTING"}}, "evidence_check": {"decision": "answer_allowed"},
        "source_role_summary": {"primary": 2}, "relevance_level_summary": {}, "sources": sources,
    }
    records = documents + [_record("W2", "answerable-multi-document", response, question="Complete focused question?")]
    trace = tmp_path / "trace.jsonl"
    trace.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")

    first = build_reviewer_demo_seed(trace)
    second = build_reviewer_demo_seed(trace)
    assert first == second
    assert first["demo_seed_version"] == DEMO_SEED_VERSION
    assert first["assistant"]["response"]["answer"] == "Actual deterministic response."
    assert {item["status"] for item in first["actions"]["actions"]} == {"OPEN", "CLOSED_COMPLETED", "SUPERSEDED"}
    assert first["actions"]["contextual_only_evidence_ids"] == ["ev-open-context"]
    assert first["actions"]["browser_only_false_actions"] == 0
    assert first["policy"]["effective_resolution"]["resolution_matrix"] == {
        "Reader": "Full", "Aggregate": "Aggregate", "Metadata": "Metadata", "Deny": "Deny"
    }
