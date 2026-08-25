from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import ai_service
import relevance
from ai_provider import (
    KEYWORD_SELECTION_STRATEGY_VERSION,
    DeterministicMockProvider,
    LocalCompatibleProvider,
    OpenAIProvider,
    create_provider,
    deterministic_allowed_keyword_matches,
    keyword_provider_error_fallback,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("provider", [DeterministicMockProvider(), LocalCompatibleProvider()])
def test_network_free_provider_contract_is_deterministic(provider) -> None:
    text = "Television warranty setup warranty support."
    assert provider.extract_keywords(
        text,
        model="keyword-test",
        prompt="keywords",
        prompt_version="test-v1",
    ) == provider.extract_keywords(
        text,
        model="keyword-test",
        prompt="keywords",
        prompt_version="test-v1",
    )
    assert provider.embed([text], model="embedding-test") == provider.embed([text], model="embedding-test")
    messages = [
        {
            "role": "user",
            "content": "Question: What is the setup fact?\n\nContext from the document(s):\nThe setup fact is deterministic.",
        }
    ]
    assert provider.generate(messages, model="generation-test") == "The setup fact is deterministic."
    usage = provider.generate_with_usage(messages, model="generation-test")
    assert usage.text == "The setup fact is deterministic."
    assert usage.total_tokens == usage.input_tokens + usage.output_tokens
    assert usage.retries == 0 and usage.cost == 0.0
    manifest = provider.manifest("model-test")
    assert manifest["external_network_required"] is False
    assert len(manifest["config_hash"]) == 64


def test_deterministic_provider_is_context_only_and_ignores_external_labels() -> None:
    provider = DeterministicMockProvider()
    messages = [
        {
            "role": "user",
            "content": "Question: What is stated?\n\nContext from the document(s):\nOnly this context sentence is stated.",
        }
    ]
    baseline = provider.generate_with_usage(messages, model="test")
    for irrelevant in (
        {"case_id": "renamed"},
        {"case_order": [9, 1]},
        {"annotation": None},
        {"reference": "modified outside the provider input"},
    ):
        assert irrelevant
        assert provider.generate_with_usage(messages, model="test") == baseline
    assert "reference_answer" not in BACKEND_DIR.joinpath("ai_provider.py").read_text(encoding="utf-8")


def test_provider_selection_and_missing_configuration_fail_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "deterministic-mock")
    ai_service.reset_ai_provider()
    assert ai_service.get_ai_provider().provider_name == "deterministic-mock"
    monkeypatch.setenv("AI_PROVIDER", "local-compatible")
    assert ai_service.get_ai_provider().provider_name == "local-compatible"
    monkeypatch.setenv("AI_PROVIDER", "missing-provider")
    with pytest.raises(RuntimeError, match="Unsupported AI_PROVIDER"):
        ai_service.get_ai_provider()
    ai_service.reset_ai_provider()


def test_switching_provider_does_not_change_governance_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    governance = {
        "full": relevance.USE_FULL,
        "aggregate": relevance.USE_AGGREGATE,
        "metadata": relevance.USE_METADATA,
        "deny": relevance.USE_DENY,
    }
    snapshots = []
    for name in ("deterministic-mock", "local-compatible"):
        monkeypatch.setenv("AI_PROVIDER", name)
        ai_service.reset_ai_provider()
        _ = ai_service.extract_provider_keywords(
            "television setup", available_keywords=["television", "router"], model="test"
        )
        snapshots.append(json.dumps(governance, sort_keys=True))
    assert snapshots[0] == snapshots[1]


def test_domain_modules_have_no_direct_openai_client_calls() -> None:
    allowed = {"ai_provider.py", "ai_service.py"}
    violations = []
    for path in BACKEND_DIR.rglob("*.py"):
        if (
            "tests" in path.parts
            or path.name in allowed
            or any(part.startswith(".venv") or part == "venv" for part in path.parts)
        ):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "openai_client":
                violations.append(str(path.relative_to(BACKEND_DIR)))
            if isinstance(node, ast.Name) and node.id == "OpenAI":
                violations.append(str(path.relative_to(BACKEND_DIR)))
    assert violations == []


def test_openai_adapter_remains_lazy_and_never_calls_network_during_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def forbidden_client():
        nonlocal called
        called = True
        raise AssertionError("network client must remain lazy")

    provider = create_provider("openai", openai_client_factory=forbidden_client)
    manifest = provider.manifest("gpt-test")
    assert manifest["provider"] == "openai"
    assert manifest["external_network_required"] is True
    assert called is False


def test_openai_usage_and_retry_metadata_are_provider_reported() -> None:
    class Completions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs):
            del kwargs
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient synthetic provider error")
            usage = type("Usage", (), {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18})()
            message = type("Message", (), {"content": "synthetic answer"})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"usage": usage, "choices": [choice]})()

    completions = Completions()
    client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
    result = OpenAIProvider(client_factory=lambda: client).generate_with_usage(
        [{"role": "user", "content": "synthetic"}], model="fixed-model", temperature=0.0
    )
    assert result.text == "synthetic answer"
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (11, 7, 18)
    assert result.retries == 1
    assert result.cost is None
    assert result.usage_source == "provider_reported"


@pytest.mark.parametrize(
    ("raw_response", "expected_values", "expected_outcome", "expected_rejected"),
    [
        ("NONE", [], "provider_none", 0),
        ("", [], "empty_response", 0),
        ("television and router", [], "parser_rejected", 1),
        ("Television, router", ["television", "router"], "selected", 0),
    ],
)
def test_openai_keyword_selection_trace_is_precise_and_content_free(
    raw_response: str,
    expected_values: list[str],
    expected_outcome: str,
    expected_rejected: int,
) -> None:
    class Completions:
        def create(self, **kwargs):
            del kwargs
            message = type("Message", (), {"content": raw_response})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    completions = Completions()
    client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
    values, trace = OpenAIProvider(client_factory=lambda: client).extract_keywords_with_trace(
        "private question text",
        model="fixed-model",
        prompt="fixed prompt",
        prompt_version="routing-keyword-test-v1",
        available_keywords=["television", "router"],
        limit=3,
    )
    assert values == expected_values
    assert trace["outcome"] == expected_outcome
    assert trace["selected_keyword_count"] == len(expected_values)
    assert trace["rejected_item_count"] == expected_rejected
    assert trace["available_keyword_count"] == 2
    serialized = json.dumps(trace, sort_keys=True)
    if raw_response:
        assert raw_response not in serialized
    assert "private question text" not in serialized
    assert "television" not in serialized
    assert "router" not in serialized


def test_deterministic_keyword_selection_trace_reports_no_overlap() -> None:
    values, trace = DeterministicMockProvider().extract_keywords_with_trace(
        "unrelated question",
        model="fixed-model",
        prompt="fixed prompt",
        prompt_version="routing-keyword-test-v1",
        available_keywords=["television", "router"],
        limit=3,
    )
    assert values == []
    assert trace["outcome"] == "no_overlap"
    assert trace["selected_keyword_count"] == 0
    assert trace["available_keyword_count"] == 2


def test_openai_none_cannot_override_an_explicit_allowed_keyword_match() -> None:
    class Completions:
        def create(self, **kwargs):
            del kwargs
            message = type("Message", (), {"content": "NONE"})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    values, trace = OpenAIProvider(client_factory=lambda: client).extract_keywords_with_trace(
        "How long is the demonstration warranty for TV-AURORA-41?",
        model="fixed-model",
        prompt="fixed prompt",
        prompt_version="routing-keyword-v1",
        available_keywords=["router", "warranty", "service"],
        limit=3,
    )
    assert values == ["warranty"]
    assert trace["outcome"] == "deterministic_recovery"
    assert trace["provider_outcome"] == "provider_none"
    assert trace["provider_selected_keyword_count"] == 0
    assert trace["deterministic_match_count"] == 1
    assert trace["selection_strategy_version"] == KEYWORD_SELECTION_STRATEGY_VERSION


def test_deterministic_keyword_anchor_uses_token_boundaries_and_stable_ranking() -> None:
    assert deterministic_allowed_keyword_matches(
        "Compare warranty support for the Wi-Fi router.",
        ["router", "support", "warranty", "wi-fi", "warrant"],
        limit=4,
    ) == ["wi-fi", "router", "support", "warranty"]
    assert deterministic_allowed_keyword_matches(
        "This claim is unwarranted.",
        ["warranty"],
        limit=3,
    ) == []
    assert deterministic_allowed_keyword_matches(
        "Mennyi a jótállás időtartama?",
        ["jótállás", "router"],
        limit=3,
    ) == ["jótállás"]


def test_openai_selector_enforces_an_explicit_empty_allowed_vocabulary() -> None:
    class Completions:
        def create(self, **kwargs):
            del kwargs
            message = type("Message", (), {"content": "router"})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    values, trace = OpenAIProvider(client_factory=lambda: client).extract_keywords_with_trace(
        "router",
        model="fixed-model",
        prompt="fixed prompt",
        prompt_version="routing-keyword-v1",
        available_keywords=[],
        limit=3,
    )
    assert values == []
    assert trace["outcome"] == "parser_rejected"
    assert trace["rejected_item_count"] == 1


def test_provider_error_recovers_exact_keyword_without_leaking_content() -> None:
    values, trace = keyword_provider_error_fallback(
        "Private question about warranty",
        available_keywords=["warranty", "router"],
        limit=3,
        provider="openai",
        adapter="openai-python",
        prompt_version="routing-keyword-v1",
    )
    assert values == ["warranty"]
    assert trace["outcome"] == "deterministic_recovery"
    assert trace["provider_outcome"] == "provider_error"
    assert trace["deterministic_match_count"] == 1
    serialized = json.dumps(trace, sort_keys=True)
    assert "Private question" not in serialized
    assert "warranty" not in serialized


def test_provider_error_without_exact_match_preserves_permitted_corpus_fallback() -> None:
    values, trace = keyword_provider_error_fallback(
        "Unrelated question",
        available_keywords=["warranty", "router"],
        limit=3,
        provider="openai",
        adapter="openai-python",
        prompt_version="routing-keyword-v1",
    )
    assert values == []
    assert trace["outcome"] == "provider_error"
    assert trace["provider_outcome"] == "provider_error"
    assert trace["deterministic_match_count"] == 0
