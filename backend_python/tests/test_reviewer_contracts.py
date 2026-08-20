from __future__ import annotations

import json
from pathlib import Path

import evidence_service
from routers.chat import chat_success_payload, controlled_failure_payload


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _source(text: str, *, use_decision: str = "full") -> dict:
    return {
        "file_name": "synthetic-source.pdf",
        "text": text,
        "use_decision": use_decision,
        "usable_relevance": {"genre": ["manual"]},
    }


def test_question_source_support_distinguishes_supported_insufficient_and_wrong_object() -> None:
    sources = [_source("TVX-900 warranty term is twenty-four months. Support reset procedure takes ten seconds.")]
    supported = evidence_service.question_source_support(
        "What is the TVX-900 warranty term and support reset procedure?", sources
    )
    insufficient = evidence_service.question_source_support(
        "Does TVX-900 provide satellite uplink cryptographic rotation?", sources
    )
    wrong_object = evidence_service.question_source_support("What is the warranty term for TVX-999?", sources)
    assert supported["sufficient"] is True
    assert insufficient["reason"] == "insufficient_lexical_support" and insufficient["sufficient"] is False
    assert wrong_object["reason"] == "wrong_object_identifier" and wrong_object["matched_object_identifiers"] == []


def test_chat_response_contract_exposes_same_audit_id_for_success_and_failure() -> None:
    audit_id = "00000000-0000-0000-0000-000000000123"
    success = chat_success_payload("q", [], {}, {}, {}, {}, {}, "a", [], audit_id=audit_id)
    failure = controlled_failure_payload("safe", {}, {}, {}, {"status": "REFUSE_NO_MATCH"}, audit_id=audit_id)
    assert success["audit_id"] == failure["audit_id"] == audit_id


def test_permission_and_no_match_public_failures_remove_source_identifiers() -> None:
    denied_id = "11111111-1111-1111-1111-111111111111"
    query_profile = {
        "routing_trace": {
            "mode": "KEYWORD_ROUTING",
            "candidate_set_size": 0,
            "candidate_document_ids": [denied_id],
            "excluded_document_ids": [denied_id],
        }
    }
    governance = {
        "content_doc_ids": [],
        "metadata_only_doc_ids": [],
        "denied_doc_ids": [denied_id],
        "usable_doc_ids": [],
        "use_decisions": {denied_id: "deny"},
        "policy_reasons": {denied_id: "private_no_permission"},
    }
    for output_mode in ("REFUSE_PERMISSION", "REFUSE_NO_MATCH"):
        payload = controlled_failure_payload(
            "The request cannot be answered from the sources available for this purpose.",
            query_profile,
            governance,
            {},
            {"status": output_mode},
            audit_id="00000000-0000-0000-0000-000000000123",
        )
        serialized = json.dumps(payload, sort_keys=True)
        assert denied_id not in serialized
        assert "candidate_document_ids" not in serialized
        assert "excluded_document_ids" not in serialized
        assert payload["sources"] == []
        assert payload["governance"]["denied_source_count"] == 1


def test_reviewer_frontend_has_four_screens_fields_and_api_wiring() -> None:
    html = (REPOSITORY_ROOT / "frontend/index.html").read_text(encoding="utf-8")
    javascript = (REPOSITORY_ROOT / "frontend/js/api.js").read_text(encoding="utf-8")
    for screen in ("view-manager", "view-chat", "view-policy", "view-actions"):
        assert screen in html
    for field in (
        "document-uuid", "owner-reader-aggregate", "effective-full-aggregate-metadata-deny",
        "purpose", "expiry", "action-closure-states", "evidence-roles", "action-audit-trail",
        "answer-audit-summary", "page-message-citation", "permission-badge", "document-uuid-hash",
    ):
        assert field in html + javascript
    for endpoint in (
        "/documents/${id}/${action}",
        "/policy/documents/${docId}/permissions", "/policy/resolve/document/${docId}",
        "/policy/rules", "/evidence/action-list",
    ):
        assert endpoint in javascript
    for action in ("reindexDoc", "archiveDoc", "restoreDoc"):
        assert action in javascript


def test_policy_router_has_no_duplicate_http_method_path_pairs() -> None:
    from main import app

    pairs = []
    for route in app.routes:
        for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
            pairs.append((method, route.path))
    assert len(pairs) == len(set(pairs))
