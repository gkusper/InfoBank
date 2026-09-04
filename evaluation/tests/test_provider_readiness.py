from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_provider import AnthropicProvider, DeterministicMockProvider
from evaluation.actual_pipeline_dataset import build_development_dataset
from evaluation.provider_readiness import (
    CachedEvaluationProvider,
    E1_MODES,
    ReadinessConfig,
    cache_key,
    estimate_evaluation,
    estimate_full_e1,
    validate_provider_request,
    write_e1_estimate_bundle,
)
from evaluation.reviewer_v2_candidate import build_candidate


def test_openai_requires_explicit_network_approval_and_has_no_fallback() -> None:
    with pytest.raises(RuntimeError, match="explicit --allow-network-provider"):
        validate_provider_request("openai", False)
    validate_provider_request("openai", True)
    with pytest.raises(RuntimeError, match="explicit --allow-network-provider"):
        validate_provider_request("anthropic", False)
    validate_provider_request("anthropic", True)
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
    assert set(cached["cache_identity"]) == {
        "input_hash",
        "provider",
        "model",
        "prompt_version",
        "config_hash",
        "generation_config_hash",
    }


def test_llm_cache_key_separates_provider_model_and_generation_config(tmp_path: Path) -> None:
    class Messages:
        @staticmethod
        def create(**kwargs):
            del kwargs
            usage = type("Usage", (), {"input_tokens": 3, "output_tokens": 2})()
            block = type("TextBlock", (), {"type": "text", "text": "Synthetic answer."})()
            return type(
                "Response",
                (),
                {"id": "msg_cache", "content": [block], "usage": usage, "stop_reason": "end_turn"},
            )()

    messages = [{"role": "user", "content": "Question: What?\n\nContext from the document(s):\nSynthetic answer."}]
    anthropic_config = ReadinessConfig(
        provider="anthropic",
        embedding_provider="openai",
        generation_model="claude-sonnet-5",
        embedding_model="text-embedding-3-small",
    )
    anthropic = CachedEvaluationProvider(
        AnthropicProvider(
            client_factory=lambda: type("Client", (), {"messages": Messages()})(),
            max_tokens=64,
        ),
        tmp_path / "cache",
        anthropic_config.config_hash,
    )
    anthropic.generate_with_usage(messages, model="claude-sonnet-5")
    cache_files = list((tmp_path / "cache/generation").glob("*.json"))
    assert len(cache_files) == 1
    cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert cached["cache_identity"]["provider"] == "anthropic"
    assert cached["cache_identity"]["model"] == "claude-sonnet-5"
    assert "generation_config_hash" in cached["cache_identity"]

    openai_key, _ = cache_key(
        input_value={"messages": messages, "generation_config": {"temperature": 0.0}},
        provider="openai",
        model="gpt-4o-mini",
        prompt_version="actual-pipeline-answer-v1",
        config_hash=anthropic_config.config_hash,
        generation_config={"temperature": 0.0},
    )
    assert openai_key != cache_files[0].stem


def test_real_provider_cli_exposes_required_guards() -> None:
    source = (Path(__file__).parents[2] / "scripts/run_real_provider_evaluation.py").read_text(encoding="utf-8")
    for flag in (
        "--provider", "--allow-network-provider", "--max-cases", "--estimated-cost-only", "--estimate-only",
        "--repeats", "--modes", "--include-scale-subset", "--pricing-config",
        "--average-provider-latency-ms", "--max-estimated-cost", "--output",
    ):
        assert flag in source


def test_full_e1_estimate_reads_holdout_counts_and_keeps_unknowns_explicit(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    manifest = build_candidate(candidate)
    result = estimate_full_e1(
        dataset_manifest_path=candidate / "dataset_manifest.json",
        gold_queries_path=candidate / "gold_queries.json",
        source_manifest_path=candidate / "source_manifest.json",
        repeats=2,
    )
    assert manifest["gold_query_count"] == 90
    assert result["source_scope"]["query_count"] == 45
    assert result["source_scope"]["document_count"] == 15
    assert result["source_scope"]["page_count"] == 30
    assert result["base_e1"]["modes"] == list(E1_MODES)
    assert result["base_e1"]["total_case_count"] == 360
    assert result["base_e1"]["generation_operations"] == 360
    assert result["pricing_status"] == "NO_LOCAL_PRICING_CONFIG"
    assert result["combined_projected_cost"] is None
    assert result["base_e1"]["provider_runtime_estimate"] == "UNKNOWN"
    assert result["base_e1"]["estimated_provider_wall_clock_ms"] is None
    assert result["network_called"] is False
    assert result["api_key_read"] is False
    assert result["authorization_status"] == "DO_NOT_RUN_FINAL_E1_YET"


def test_full_e1_estimate_supports_local_pricing_latency_scale_and_csv(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    build_candidate(candidate)
    from evaluation.c_gate import scale_manifest

    scale_path = tmp_path / "scale.json"
    scale_path.write_text(json.dumps(scale_manifest(50), sort_keys=True), encoding="utf-8")
    pricing_path = tmp_path / "pricing.json"
    pricing_path.write_text(json.dumps({
        "gpt-4o-mini": {"input_per_million": 1.0, "output_per_million": 2.0},
        "text-embedding-3-small": {"input_per_million": 0.5},
    }), encoding="utf-8")
    result = estimate_full_e1(
        dataset_manifest_path=candidate / "dataset_manifest.json",
        gold_queries_path=candidate / "gold_queries.json",
        source_manifest_path=candidate / "source_manifest.json",
        repeats=1,
        modes=["C2_PERMISSION_FILTERED", "C3_FULL_ROLE_AWARE"],
        include_scale_subset=True,
        scale_manifest_path=scale_path,
        pricing_config=pricing_path,
        average_provider_latency_ms=100.0,
    )
    assert result["base_e1"]["total_case_count"] == 90
    assert result["base_e1"]["projected_cost"] > 0
    assert result["base_e1"]["provider_runtime_estimate"] == "LOCAL_LATENCY_ASSUMPTION"
    assert result["optional_scale_subset"]["query_count"] == 24
    assert result["optional_scale_subset"]["total_case_count"] == 48
    assert result["optional_scale_subset"]["separate_from_base_e1"] is True
    json_path, csv_path = write_e1_estimate_bundle(result, tmp_path / "estimate.json")
    assert json_path.is_file() and csv_path.is_file()
    assert len(csv_path.read_text(encoding="utf-8").splitlines()) == 3


def test_full_e1_estimate_rejects_manifest_count_drift(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    build_candidate(candidate)
    manifest_path = candidate / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["gold_query_count"] = 89
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="gold_query_count"):
        estimate_full_e1(
            dataset_manifest_path=manifest_path,
            gold_queries_path=candidate / "gold_queries.json",
            source_manifest_path=candidate / "source_manifest.json",
            repeats=1,
        )
