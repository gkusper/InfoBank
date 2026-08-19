from __future__ import annotations

from routing import RoutingMode, route_documents, routing_config_hash


def test_routing_off_returns_every_governed_document_in_stable_order() -> None:
    decision = route_documents(
        ["doc-z", "doc-a", "doc-a"],
        {"doc-z": ["router"], "doc-a": ["television"]},
        ["router"],
        RoutingMode.ROUTING_OFF,
    )
    assert decision.candidate_document_ids == ("doc-a", "doc-z")
    assert decision.excluded_document_ids == ()
    assert decision.fallback_used is False
    assert decision.mode == "ROUTING_OFF"


def test_keyword_routing_narrows_only_within_governed_input() -> None:
    decision = route_documents(
        ["allowed-tv", "allowed-router"],
        {
            "allowed-tv": [" Television ", "HDMI"],
            "allowed-router": ["router"],
            "denied-tv": ["television"],
        },
        ["TELEVISION"],
        RoutingMode.KEYWORD_ROUTING,
    )
    assert decision.candidate_document_ids == ("allowed-tv",)
    assert decision.excluded_document_ids == ("allowed-router",)
    assert "denied-tv" not in decision.candidate_document_ids
    assert decision.matched_keywords == ("television",)


def test_keyword_routing_falls_back_to_full_governed_set_on_no_match() -> None:
    decision = route_documents(
        ["doc-b", "doc-a"],
        {"doc-a": ["television"], "doc-b": ["router"]},
        ["printer"],
        "KEYWORD_ROUTING",
    )
    assert decision.candidate_document_ids == ("doc-a", "doc-b")
    assert decision.fallback_used is True
    assert decision.fallback_reason == "no_governed_keyword_match"


def test_routing_trace_and_config_hash_are_deterministic() -> None:
    first = route_documents(["b", "a"], {"a": ["x"], "b": ["y"]}, ["x"], RoutingMode.KEYWORD_ROUTING)
    second = route_documents(["a", "b"], {"b": ["y"], "a": ["x"]}, ["x"], RoutingMode.KEYWORD_ROUTING)
    assert first == second
    assert first.config_hash == routing_config_hash()
    assert len(first.config_hash) == 64
    serialized = str(first.to_trace())
    assert "\\" not in serialized
    assert "/home/" not in serialized
    assert "source text" not in serialized.lower()
