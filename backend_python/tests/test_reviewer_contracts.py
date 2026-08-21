from __future__ import annotations

import json
from pathlib import Path

import controlled_failure
import evidence_service
import relevance
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
    assert insufficient["reason"] == "unsupported_claim_relation" and insufficient["sufficient"] is False
    assert wrong_object["reason"] == "wrong_object_identifier" and wrong_object["matched_object_identifiers"] == []


def test_claim_relation_gate_separates_supported_ambiguous_and_unsupported_questions() -> None:
    sources = [_source(
        "TV-AURORA-41 has a 24 month warranty. Cracked panels and liquid damage are excluded."
    )]

    supported = evidence_service.question_source_support(
        "What types of damage are excluded for TV-AURORA-41?", sources
    )
    ambiguous = evidence_service.question_source_support(
        "What damage is described for cracked panels on TV-AURORA-41?", sources
    )
    unsupported = evidence_service.question_source_support(
        "What damage does a cracked panel cause on TV-AURORA-41?", sources
    )

    assert supported["decision"] == "supported"
    assert supported["threshold"] == 0.5
    assert ambiguous["decision"] == "clarification_required"
    assert ambiguous["reason"] == "ambiguous_claim_relation"
    assert unsupported["decision"] == "insufficient_evidence"
    assert unsupported["reason"] == "unsupported_claim_relation"
    assert unsupported["missing_claim_relations"] == ["causation"]


def test_generated_answer_relation_validation_blocks_exclusion_to_cause_hallucination() -> None:
    sources = [_source(
        "TV-AURORA-41 has a 24 month warranty. Cracked panels and liquid damage are excluded."
    )]

    supported = evidence_service.answer_source_support(
        "Cracked panels are excluded from the TV-AURORA-41 warranty.", sources
    )
    unsupported = evidence_service.answer_source_support(
        "A cracked panel causes damage on TV-AURORA-41.", sources
    )

    assert supported["sufficient"] is True
    assert unsupported["sufficient"] is False
    assert unsupported["missing_claim_relations"] == ["causation"]


def test_support_gate_handles_hungarian_accents_and_rejects_cross_object_frankenstein_support() -> None:
    accented = evidence_service.question_source_support(
        "Milyen jótállási időtartam érvényes a TVX-900 készülékre?",
        [_source("A TVX-900 készülék jótállási időtartama huszonnégy hónap.")],
    )
    assert accented["matched_question_terms"]
    assert {"jótállási", "időtartam", "készülékre"}.intersection(accented["matched_question_terms"])

    sources = [
        _source("TVX-900 setup and ownership record."),
        _source("ROUTER-R77 warranty term is 24 months."),
    ]
    question_support = evidence_service.question_source_support(
        "Is the TVX-900 warranty term 24 months?", sources
    )
    answer_support = evidence_service.answer_source_support(
        "The TVX-900 warranty term is 24 months.", sources
    )
    assert question_support["sufficient"] is False
    assert question_support["identifier_scoped_source_count"] == 1
    assert answer_support["sufficient"] is False
    assert answer_support["unsupported_numbers"] == ["24"]


def test_identifier_scope_still_allows_multi_document_support_for_same_object() -> None:
    sources = [
        _source("TVX-900 warranty term is twenty-four months."),
        _source("TVX-900 support reset procedure takes ten seconds."),
    ]
    support = evidence_service.question_source_support(
        "What is the TVX-900 warranty term and support reset procedure?", sources
    )
    assert support["sufficient"] is True
    assert support["identifier_scoped_source_count"] == 2


def test_claim_relation_decision_uses_clarification_without_bypassing_governance() -> None:
    question = "What damage is described for cracked panels on TV-AURORA-41?"
    profile = relevance.build_query_profile(question, ["cracked", "damage", "panels"])
    source = {
        "role": relevance.SOURCE_ROLE_PRIMARY,
        "use_decision": relevance.USE_FULL,
        "text": "TV-AURORA-41 cracked panels and liquid damage are excluded.",
        "usable_relevance": {"genre": ["warranty"], "levels": {}},
    }
    support = evidence_service.question_source_support(question, [source])
    allowed_governance = {
        "content_doc_ids": ["warranty"],
        "usable_doc_ids": ["warranty"],
        "metadata_only_doc_ids": [],
        "denied_doc_ids": [],
        "has_primary_evidence": True,
    }
    clarification = controlled_failure.select_rag_output_mode(
        question,
        [source],
        profile,
        allowed_governance,
        context_blocks_available=True,
        support_check=support,
    )
    assert clarification["output_mode"] == controlled_failure.STATUS_ASK_CLARIFICATION
    assert clarification["trace"]["gate"] == "claim_relation_clarification"

    denied_governance = {
        "content_doc_ids": [],
        "usable_doc_ids": [],
        "metadata_only_doc_ids": [],
        "denied_doc_ids": ["warranty"],
    }
    denied = controlled_failure.select_rag_output_mode(
        question,
        [source],
        profile,
        denied_governance,
        context_blocks_available=True,
        support_check=support,
    )
    assert denied["output_mode"] == controlled_failure.STATUS_REFUSE
    assert denied["controlled_failure"]["reason"] == controlled_failure.REASON_GOVERNANCE


def test_unsupported_generated_answer_maps_to_audited_evidential_refusal() -> None:
    question = "What damage does a cracked panel cause on TV-AURORA-41?"
    profile = relevance.build_query_profile(question, ["cracked", "damage", "panels"])
    source = {
        "role": relevance.SOURCE_ROLE_PRIMARY,
        "use_decision": relevance.USE_FULL,
        "text": "TV-AURORA-41 cracked panels and liquid damage are excluded.",
        "usable_relevance": {"genre": ["warranty"], "levels": {}},
    }
    answer_support = evidence_service.answer_source_support(
        "A cracked panel causes damage on TV-AURORA-41.", [source]
    )
    failure = controlled_failure.from_unsupported_generated_answer(
        question,
        [source],
        profile,
        {
            "content_doc_ids": ["warranty"],
            "usable_doc_ids": ["warranty"],
            "metadata_only_doc_ids": [],
            "denied_doc_ids": [],
        },
        answer_support,
    )
    assert failure["status"] == controlled_failure.STATUS_ABSTAIN
    assert failure["reason"] == controlled_failure.REASON_EVIDENTIAL
    assert failure["trace"]["gate"] == "generation_grounding_validation"


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
        internal_failure = {
            "status": output_mode,
            "reason": "governance",
            "policyState": {"denied_source_count": 1, "usable_source_count": 0},
        }
        payload = controlled_failure_payload(
            "The request cannot be answered from the sources available for this purpose.",
            query_profile,
            governance,
            {"decision": "controlled_failure", "controlled_failure": internal_failure},
            internal_failure,
            audit_id="00000000-0000-0000-0000-000000000123",
        )
        serialized = json.dumps(payload, sort_keys=True)
        assert denied_id not in serialized
        assert "candidate_document_ids" not in serialized
        assert "excluded_document_ids" not in serialized
        assert "denied_source_count" not in serialized
        assert payload["sources"] == []
        assert payload["governance"]["policy_enforced"] is True
        assert internal_failure["policyState"]["denied_source_count"] == 1


def test_public_permission_failure_does_not_reveal_hidden_corpus_presence() -> None:
    denied_id = "11111111-1111-1111-1111-111111111111"

    def public_payload(governance: dict) -> dict:
        internal_failure = {
            "status": "REFUSE_PERMISSION",
            "reason": "governance",
            "policyState": {
                "content_source_count": 0,
                "metadata_only_source_count": 0,
                "denied_source_count": len(governance.get("denied_doc_ids", [])),
                "usable_source_count": 0,
            },
        }
        return controlled_failure_payload(
            "The request cannot be answered from the sources available for this purpose.",
            {},
            governance,
            {"decision": "controlled_failure", "controlled_failure": internal_failure},
            internal_failure,
            audit_id="00000000-0000-0000-0000-000000000123",
        )

    empty_scope = public_payload({})
    hidden_scope = public_payload({
        "denied_doc_ids": [denied_id],
        "use_decisions": {denied_id: "deny"},
        "policy_reasons": {denied_id: "private_no_permission"},
    })
    assert hidden_scope == empty_scope


def test_success_payload_sanitizes_governance_and_nested_failure() -> None:
    denied_id = "11111111-1111-1111-1111-111111111111"
    governance = {
        "usable_doc_ids": ["permitted-document"],
        "content_doc_ids": ["permitted-document"],
        "denied_doc_ids": [denied_id],
        "pre_routing_denied_count": 1,
    }
    internal_failure = {
        "status": "CONSTRAINED_ANSWER",
        "policyState": {"denied_source_count": 1, "usable_source_count": 1},
    }
    payload = chat_success_payload(
        "q", [], {}, governance, {}, {},
        {"controlled_failure": internal_failure},
        "a", [], internal_failure, "CONSTRAINED_ANSWER",
    )
    serialized = json.dumps(payload, sort_keys=True)
    assert denied_id not in serialized
    assert "denied_source_count" not in serialized
    assert "pre_routing_denied_count" not in serialized
    assert payload["searched_documents_count"] == 1


def test_success_payload_exposes_only_privacy_safe_routing_observability() -> None:
    hidden_id = "11111111-1111-1111-1111-111111111111"
    query_profile = {
        "routing_trace": {
            "mode": "KEYWORD_ROUTING",
            "candidate_document_ids": [hidden_id],
            "excluded_document_ids": [hidden_id],
            "candidate_set_size": 1,
            "governed_input_count": 2,
            "fallback_used": True,
            "fallback_reason": "no_selected_keyword",
        },
        "keyword_selection_trace": {
            "provider": "openai",
            "outcome": "provider_none",
            "available_keyword_count": 7,
            "selected_keyword_count": 0,
            "selection_strategy_version": "infocom-keyword-selector-v2",
            "provider_outcome": "provider_none",
            "provider_selected_keyword_count": 0,
            "deterministic_match_count": 0,
            "raw_response": "private raw provider output",
        },
    }
    payload = chat_success_payload(
        "q", [], query_profile, {"usable_doc_ids": ["permitted-document"]}, {}, {}, {}, "a", []
    )
    serialized = json.dumps(payload, sort_keys=True)
    assert hidden_id not in serialized
    assert "candidate_document_ids" not in serialized
    assert "excluded_document_ids" not in serialized
    assert "private raw provider output" not in serialized
    assert payload["query_profile"]["routing_trace"]["candidate_set_size"] == 1
    assert payload["query_profile"]["keyword_selection_trace"]["outcome"] == "provider_none"
    assert payload["query_profile"]["keyword_selection_trace"]["selection_strategy_version"] == "infocom-keyword-selector-v2"


def test_conflict_role_is_scoped_to_the_question_subject() -> None:
    unrelated_question = "What details are required when contacting support for TVX-900?"
    unrelated_profile = relevance.build_query_profile(unrelated_question, ["support"])
    conflict_text = (
        "This notice contradicts the TVX-900 warranty record and states a twelve-month term. "
        "It is unverified and does not establish final authority."
    )
    incidental = relevance.classify_chunk_profile(
        unrelated_question,
        conflict_text,
        "tvx-900-conflict.pdf",
        unrelated_profile,
        relevance.SOURCE_ROLE_PRIMARY,
        relevance.USE_FULL,
    )
    assert incidental["conflict_scope"]["raw_signal"] is True
    assert incidental["conflict_signal"] is False
    assert incidental["role"] == relevance.SOURCE_ROLE_CONTEXTUAL
    assert "conflict_marker_outside_query_scope_context_only" in incidental["evidence_warnings"]

    warranty_question = "Which source has final authority for the TVX-900 warranty conflict?"
    warranty_profile = relevance.build_query_profile(warranty_question, ["warranty"])
    relevant = relevance.classify_chunk_profile(
        warranty_question,
        conflict_text,
        "tvx-900-conflict.pdf",
        warranty_profile,
        relevance.SOURCE_ROLE_PRIMARY,
        relevance.USE_FULL,
    )
    assert relevant["conflict_signal"] is True
    assert relevant["conflict_scope"]["matched_query_terms"] == []
    assert relevant["role"] == relevance.SOURCE_ROLE_CONTRASTIVE


def test_warranty_conflict_is_scoped_to_the_question_claim_relation() -> None:
    conflict_text = (
        "This notice contradicts the TV-AURORA-41 warranty record and states an 18-month term. "
        "It is unverified and does not establish final authority."
    )
    exclusion_question = "What types of damage are excluded from the TV-AURORA-41 warranty?"
    exclusion_profile = relevance.build_query_profile(exclusion_question, ["damage", "warranty"])
    incidental = relevance.classify_chunk_profile(
        exclusion_question,
        conflict_text,
        "tv-aurora41-conflict.pdf",
        exclusion_profile,
        relevance.SOURCE_ROLE_PRIMARY,
        relevance.USE_FULL,
    )
    assert incidental["conflict_scope"]["raw_signal"] is True
    assert incidental["conflict_scope"]["matched_claim_relations"] == []
    assert incidental["role"] == relevance.SOURCE_ROLE_CONTEXTUAL

    duration_question = "How long is the TV-AURORA-41 warranty?"
    duration_profile = relevance.build_query_profile(duration_question, ["warranty"])
    relevant = relevance.classify_chunk_profile(
        duration_question,
        conflict_text,
        "tv-aurora41-conflict.pdf",
        duration_profile,
        relevance.SOURCE_ROLE_PRIMARY,
        relevance.USE_FULL,
    )
    assert relevant["conflict_scope"]["matched_claim_relations"] == ["duration"]
    assert relevant["role"] == relevance.SOURCE_ROLE_CONTRASTIVE


def test_incidental_conflict_does_not_constrain_supported_w2_question() -> None:
    question = "What details are required when contacting support for TVX-900?"
    profile = relevance.build_query_profile(question, ["support"])
    support_profile = relevance.classify_chunk_profile(
        question,
        "For TVX-900 support, provide the serial number and a diagnostic log.",
        "tvx-900-support.pdf",
        profile,
        relevance.SOURCE_ROLE_PRIMARY,
        relevance.USE_FULL,
    )
    incidental_profile = relevance.classify_chunk_profile(
        question,
        "This notice contradicts the TVX-900 warranty record and states a twelve-month term.",
        "tvx-900-conflict.pdf",
        profile,
        relevance.SOURCE_ROLE_PRIMARY,
        relevance.USE_FULL,
    )
    sources = [
        {"role": support_profile["role"], "usable_relevance": support_profile},
        {"role": incidental_profile["role"], "usable_relevance": incidental_profile},
    ]
    decision = controlled_failure.select_rag_output_mode(
        question,
        sources,
        profile,
        {
            "content_doc_ids": ["support", "conflict"],
            "usable_doc_ids": ["support", "conflict"],
            "metadata_only_doc_ids": [],
            "denied_doc_ids": [],
        },
        context_blocks_available=True,
    )
    assert decision["output_mode"] == controlled_failure.STATUS_FULL_ANSWER
    assert decision["controlled_failure"] is None


def test_reviewer_frontend_has_four_screens_fields_and_api_wiring() -> None:
    html = (REPOSITORY_ROOT / "frontend/index.html").read_text(encoding="utf-8")
    javascript = (REPOSITORY_ROOT / "frontend/js/api.js").read_text(encoding="utf-8")
    assert "gov.denied_doc_ids" not in javascript
    assert "restricted-source details withheld" in javascript
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
    assert "aria-label=\"Re-index document\"" in javascript
    assert "aria-label=\"Archive document\"" in javascript
    assert "aria-label=\"Restore document\"" in javascript
    assert "loadReviewerDemoSeed" in javascript
    assert "expandedSources: true" in javascript
    assert "complete-question" in javascript
    assert "data-reviewer-field=\"routing-summary\"" in javascript
    assert "PERMITTED_CORPUS_FALLBACK" in javascript
    assert "Candidate-set effect" in javascript
    assert "Keyword selector outcome" in javascript
    assert "Policy valid from" in html and "Policy valid until" in html


def test_reviewer_frontend_enforces_contextual_owner_controls_and_session_reset() -> None:
    html = (REPOSITORY_ROOT / "frontend/index.html").read_text(encoding="utf-8")
    javascript = (REPOSITORY_ROOT / "frontend/js/api.js").read_text(encoding="utf-8")
    assert 'id="policy-owner-permission-editor" class="hidden' in html
    assert 'id="policy-owner-rule-editor" class="hidden' in html
    assert 'data-reviewer-field="owner-reader-context"' in html
    assert "DOCUMENT_CAPABILITIES" in javascript
    assert "capability?.isOwner === true" in javascript
    assert "readonly aria-readonly=\"true\"" in javascript
    assert "Only the Owner can review document keywords." in javascript
    assert "Individual source withheld by Aggregate policy" in javascript
    assert "resetSessionScopedUI" in javascript
    assert "lastPolicyTargetUserId = null" in javascript


def test_authorized_source_uses_governed_in_app_viewer_without_popup_dependency() -> None:
    html = (REPOSITORY_ROOT / "frontend/index.html").read_text(encoding="utf-8")
    javascript = (REPOSITORY_ROOT / "frontend/js/api.js").read_text(encoding="utf-8")
    function_body = javascript.split("async function openAuthorizedSource(path) {", 1)[1].split("\n}\n\nlet lastPolicyTargetUserId", 1)[0]
    assert 'id="source-viewer-modal"' in html
    assert 'id="source-viewer-text"' in html
    assert 'id="source-viewer-frame"' in html
    assert "modal.classList.remove('hidden')" in function_body
    assert "textView.textContent = data.text || JSON.stringify(data, null, 2)" in function_body
    assert "window.open" not in function_body
    assert "closeAuthorizedSource" in javascript


def test_policy_router_has_no_duplicate_http_method_path_pairs() -> None:
    from main import app

    pairs = []
    for route in app.routes:
        for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
            pairs.append((method, route.path))
    assert len(pairs) == len(set(pairs))


def test_frontend_identity_and_filename_rendering_avoids_untrusted_html() -> None:
    javascript = (REPOSITORY_ROOT / "frontend/js/ui.js").read_text(encoding="utf-8")
    assert "${username.substring(0, 2)}" not in javascript
    assert "${fileInput.files[0].name}" not in javascript
    assert "`<strong>${user.username}</strong>`" not in javascript
    assert "monogram.textContent" in javascript
    assert "document.createTextNode(fileInput.files[0].name)" in javascript
    assert "label.textContent = String(user.username || '')" in javascript
    assert "encodeURIComponent(query)" in javascript
    assert "headers: authHeaders()" in javascript


def test_action_list_chat_cannot_bypass_server_side_ask_audit() -> None:
    javascript = (REPOSITORY_ROOT / "frontend/js/api.js").read_text(encoding="utf-8")
    ask_body = javascript.split("async function askQuestion() {", 1)[1].split("\n}\n\nasync function uploadDocument", 1)[0]
    assert "actionListChatResponse" not in javascript
    assert "isActionListQuestion" not in javascript
    assert "evidenceRoleSummary" not in javascript
    assert "fetch(`${API}/evidence/action-list`" not in ask_body
    assert "fetch(`${API}/ask`, { method: 'POST', headers: authHeaders(), body: fd })" in ask_body


def test_user_search_route_requires_authenticated_identity() -> None:
    from main import app
    import security

    route = next(route for route in app.routes if route.path == "/api/users/search")
    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
    assert security.get_current_user_id in dependency_calls
