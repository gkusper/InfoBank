from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_provider import DeterministicMockProvider
from evaluation.actual_pipeline_dataset import build_development_dataset
from evaluation.provider_readiness import (
    CachedEvaluationProvider,
    ReadinessConfig,
    cache_key,
    estimate_evaluation,
    validate_provider_request,
)


def test_openai_requires_explicit_network_approval_and_has_no_fallback() -> None:
    with pytest.raises(RuntimeError, match="explicit --allow-network-provider"):
        validate_provider_request("openai", False)
    validate_provider_request("openai", True)
    with pytest.raises(RuntimeError, match="Unsupported evaluation provider"):
        validate_provider_request("implicit-fallback", True)


def test_estimate_only_does_not_invent_pricing(tmp_path: Path) -> None:
    build_development_dataset(tmp_path / "dataset")
    result = estimate_evaluation(
        query_input_path=tmp_path / "dataset/query_inputs.jsonl",
        corpus_fixture_path=tmp_path / "dataset/corpus_fixture.json",
        max_cases=3,
        provider="openai",
        pricing_config=None,
    )
    assert result["case_count"] == 3
    assert result["network_called"] is False
    assert result["projected_cost"] is None
    assert result["pricing_status"] == "NO_LOCAL_PRICING_CONFIG"


def test_estimate_uses_only_supplied_local_pricing(tmp_path: Path) -> None:
    build_development_dataset(tmp_path / "dataset")
    pricing = tmp_path / "pricing.json"
    pricing.write_text(json.dumps({"gpt-4o-mini": {"input_per_million": 1.0, "output_per_million": 2.0}}), encoding="utf-8")
    result = estimate_evaluation(
        query_input_path=tmp_path / "dataset/query_inputs.jsonl",
        corpus_fixture_path=tmp_path / "dataset/corpus_fixture.json",
        max_cases=2,
        provider="openai",
        pricing_config=pricing,
    )
    assert result["projected_cost"] is not None and result["projected_cost"] > 0
    assert result["pricing_status"] == "LOCAL_PRICING_CONFIG"


def test_cache_identity_and_generation_cache_cover_required_fields(tmp_path: Path) -> None:
    config = ReadinessConfig(provider="deterministic-mock")
    key, identity = cache_key(
        input_value={"question": "synthetic"},
        provider=config.provider,
        model=config.generation_model,
        prompt_version=config.generation_prompt_version,
        config_hash=config.config_hash,
    )
    assert len(key) == 64
    assert set(identity) == {"input_hash", "provider", "model", "prompt_version", "config_hash"}
    provider = CachedEvaluationProvider(DeterministicMockProvider(), tmp_path / "cache", config.config_hash)
    messages = [{"role": "user", "content": "Question: What?\n\nContext from the document(s):\nSynthetic answer."}]
    first = provider.generate_with_usage(messages, model="test")
    second = provider.generate_with_usage(messages, model="test")
    assert first.text == second.text == "Synthetic answer."
    assert second.usage_source.startswith("cache:")
    cache_files = list((tmp_path / "cache/generation").glob("*.json"))
    assert len(cache_files) == 1
    cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert set(cached["cache_identity"]) == {"input_hash", "provider", "model", "prompt_version", "config_hash"}


def test_real_provider_cli_exposes_required_guards() -> None:
    source = (Path(__file__).parents[2] / "scripts/run_real_provider_evaluation.py").read_text(encoding="utf-8")
    for flag in (
        "--provider", "--allow-network-provider", "--max-cases", "--estimated-cost-only", "--max-estimated-cost",
    ):
        assert flag in source
