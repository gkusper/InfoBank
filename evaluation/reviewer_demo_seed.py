"""Build the privacy-safe reviewer screenshot seed from an actual local API trace."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from backend_python.action_closure import ACTION_ENGINE_VERSION, MessageEvidence, reconstruct_actions


DEMO_SEED_VERSION = "pre-freeze-reviewer-demo-v1"
NO_HEALTH_TERMS = {
    "clinical", "diagnosis", "disease", "doctor", "health", "healthcare",
    "hospital", "medical", "medication", "patient", "physician", "pregnancy",
    "symptom", "therapy", "treatment",
}


def _trace_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _single(records: list[dict[str, Any]], *, workflow: str, step: str) -> dict[str, Any]:
    matches = [item for item in records if item.get("workflow") == workflow and item.get("step") == step]
    if len(matches) != 1:
        raise ValueError(f"Expected one {workflow}/{step} trace record, found {len(matches)}")
    return matches[0]


def _action_evidence() -> dict[str, Any]:
    items = [
        MessageEvidence("ev-open-request", "Email", "2026-08-20T08:00:00Z", "requester@example.invalid", ("reviewer@example.invalid",), "Please prepare the synthetic review summary", "Please prepare the synthetic review summary.", relation_key="thread-open"),
        MessageEvidence("ev-open-context", "BrowserHistory", "2026-08-20T08:05:00Z", "reviewer@example.invalid", (), "Review checklist search", "Context only.", relation_key="thread-open"),
        MessageEvidence("ev-complete-request", "Email", "2026-08-20T08:10:00Z", "requester@example.invalid", ("reviewer@example.invalid",), "Please export the synthetic audit table", "Please export the synthetic audit table.", relation_key="thread-completed"),
        MessageEvidence("ev-complete-proof", "Email", "2026-08-20T08:20:00Z", "reviewer@example.invalid", ("requester@example.invalid",), "Synthetic audit table completed", "Completed and delivered the synthetic audit table.", relation_key="thread-completed"),
        MessageEvidence("ev-old-request", "Email", "2026-08-20T08:30:00Z", "requester@example.invalid", ("reviewer@example.invalid",), "Please use revision A", "Please use revision A.", relation_key="thread-superseded"),
        MessageEvidence("ev-new-authority", "Email", "2026-08-20T08:40:00Z", "requester@example.invalid", ("reviewer@example.invalid",), "Revision A superseded", "The synthetic request was superseded by revision B.", relation_key="thread-superseded"),
    ]
    result = reconstruct_actions(items)
    for action in result["actions"]:
        if action["status"] == "OPEN":
            action["R"] = {"primary": 1, "contextual": 1, "contrastive": 0}
        else:
            action["R"] = {"primary": 1, "contextual": 0, "contrastive": 1}
    result["audit_and_correction"] = "Evidence IDs, event links, and engine version preserve the correction and audit trail."
    return result


def _documents(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for step in ("upload-tv-warranty", "upload-tv-support"):
        record = _single(records, workflow="W1", step=step)
        response = record["response"]
        file_data = record["request"]["fields"]["file"]
        output.append({
            "document_id": response["document_id"],
            "file_name": file_data["filename"],
            "source_sha256": response["source_sha256"],
            "processing_status": "PROCESSED",
            "source_status": "ACTIVE",
            "page_count": response["page_count"],
            "chunk_count": response["chunk_count"],
            "keywords": response["keywords"],
            "permission": "Owner / Private",
            "provenance": [
                {"field": "keywords", "type": response["keyword_extraction_mode"]},
                {"field": "source", "type": "actual_api_workflow"},
            ],
        })
    return output


def build_reviewer_demo_seed(trace_path: Path) -> dict[str, Any]:
    trace_bytes = trace_path.read_bytes()
    records = _trace_records(trace_path)
    answer_record = _single(records, workflow="W2", step="answerable-multi-document")
    response = answer_record["response"]
    documents = _documents(records)
    document_id = documents[0]["document_id"]
    seed = {
        "demo_seed_version": DEMO_SEED_VERSION,
        "privacy_safe": True,
        "source_trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        "source_runtime": "actual local API workflow with deterministic provider",
        "assistant": {"question": answer_record["request"]["fields"]["question"], "response": response},
        "documents": documents,
        "policy": {
            "document_id": document_id,
            "target_username": "reviewer-reader",
            "persistent_permission": "Reader",
            "purpose": "grounded_question_answering",
            "selected_rule": "Full",
            "valid_from": "2026-08-20T08:00",
            "valid_until": "2026-12-31T18:00",
            "effective_resolution": {
                "status": "PERMITTED",
                "document_id": document_id,
                "target_username": "reviewer-reader",
                "purpose": "grounded_question_answering",
                "valid_at_demo_time": True,
                "selected": {"persistent_permission": "Reader", "effective_use_decision": "Full"},
                "resolution_matrix": {"Reader": "Full", "Aggregate": "Aggregate", "Metadata": "Metadata", "Deny": "Deny"},
                "governance_before_routing": True,
            },
        },
        "actions": _action_evidence(),
    }
    serialized = json.dumps(seed, sort_keys=True).lower()
    hits = sorted(term for term in NO_HEALTH_TERMS if re.search(rf"\b{re.escape(term)}\b", serialized))
    if hits:
        raise ValueError(f"No-health reviewer seed scan failed: {hits}")
    return seed


def write_reviewer_demo_seed(trace_path: Path, output_path: Path) -> dict[str, Any]:
    seed = build_reviewer_demo_seed(trace_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(seed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return seed
