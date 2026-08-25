"""Explicit-network provider readiness, estimation, and deterministic caching."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Sequence

from .actual_pipeline_inputs import load_corpus_fixture, load_query_inputs
from .backend import ensure_backend_path


ensure_backend_path()
from ai_provider import AIProvider, KEYWORD_SELECTION_STRATEGY_VERSION, ProviderGenerationResult  # noqa: E402


READINESS_STATUS = "PENDING_EXPLICIT_PROVIDER_RUN_APPROVAL"
GENERATION_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_TEMPERATURE = 0.0
GENERATION_PROMPT_VERSION = "actual-pipeline-answer-v1"
ROUTING_PROMPT_VERSION = "routing-keyword-v1"
READINESS_CONFIG_VERSION = "real-provider-readiness-v2"
E1_ESTIMATE_SCHEMA_VERSION = "infocom-e1-estimate-v1"
E1_MODES = (
    "C0_VECTOR_ONLY",
    "C1_VECTOR_ROUTING",
    "C2_PERMISSION_FILTERED",
    "C3_FULL_ROLE_AWARE",
)
SCALE_SUBSET_MODES = ("ROUTING_OFF", "KEYWORD_ROUTING")
OUTPUT_TOKEN_BUDGET_PER_CASE = 512
MAX_CONTEXT_TOKEN_BUDGET_PER_CASE = 4096
MAX_GENERATION_RETRIES_PER_CASE = 2


def canonical_hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_provider_request(provider: str, allow_network_provider: bool) -> None:
    normalized = provider.strip().lower()
    if normalized == "openai" and not allow_network_provider:
        raise RuntimeError("OpenAI evaluation requires explicit --allow-network-provider approval; no mock fallback is permitted.")
    if normalized not in {"openai", "deterministic-mock"}:
        raise RuntimeError(f"Unsupported evaluation provider: {provider}")


@dataclass(frozen=True)
class ReadinessConfig:
    provider: str
    generation_model: str = GENERATION_MODEL
    embedding_model: str = EMBEDDING_MODEL
    temperature: float = GENERATION_TEMPERATURE
    generation_prompt_version: str = GENERATION_PROMPT_VERSION
    routing_prompt_version: str = ROUTING_PROMPT_VERSION
    keyword_selection_strategy_version: str = KEYWORD_SELECTION_STRATEGY_VERSION
    config_version: str = READINESS_CONFIG_VERSION

    @property
    def config_hash(self) -> str:
        return canonical_hash(asdict(self))


def cache_key(*, input_value: Any, provider: str, model: str, prompt_version: str, config_hash: str) -> tuple[str, dict[str, str]]:
    identity = {
        "input_hash": canonical_hash(input_value),
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "config_hash": config_hash,
    }
    return canonical_hash(identity), identity


class CachedEvaluationProvider(AIProvider):
    """File cache for evaluator-only provider outputs with auditable keys."""

    def __init__(self, wrapped: AIProvider, root: Path, config_hash: str, pricing: dict[str, float] | None = None) -> None:
        self.wrapped = wrapped
        self.root = Path(root)
        self.config_hash = config_hash
        self.pricing = pricing
        self.provider_name = wrapped.provider_name
        self.adapter_name = f"cached:{wrapped.adapter_name}"
        self.external_network_required = wrapped.external_network_required

    def _path(self, operation: str, key: str) -> Path:
        return self.root / operation / f"{key}.json"

    def _read(self, operation: str, key: str) -> dict[str, Any] | None:
        path = self._path(operation, key)
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def _write(self, operation: str, key: str, identity: dict[str, str], value: Any) -> None:
        path = self._path(operation, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"cache_identity": identity, "value": value}
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def extract_keywords(
        self, text: str, *, model: str, prompt: str, prompt_version: str,
        available_keywords: Sequence[str] | None = None, limit: int = 5,
    ) -> list[str]:
        input_value = {"text": text, "prompt": prompt, "available_keywords": list(available_keywords or []), "limit": limit}
        key, identity = cache_key(input_value=input_value, provider=self.provider_name, model=model, prompt_version=prompt_version, config_hash=self.config_hash)
        cached = self._read("keywords", key)
        if cached:
            return list(cached["value"])
        value = self.wrapped.extract_keywords(
            text, model=model, prompt=prompt, prompt_version=prompt_version,
            available_keywords=available_keywords, limit=limit,
        )
        self._write("keywords", key, identity, value)
        return value

    def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        input_value = {"texts": list(texts)}
        key, identity = cache_key(input_value=input_value, provider=self.provider_name, model=model, prompt_version="embedding-v1", config_hash=self.config_hash)
        cached = self._read("embeddings", key)
        if cached:
            return [list(row) for row in cached["value"]]
        value = self.wrapped.embed(texts, model=model)
        self._write("embeddings", key, identity, value)
        return value

    def generate(self, messages: Sequence[dict[str, str]], *, model: str, temperature: float = 0.0) -> str:
        return self.generate_with_usage(messages, model=model, temperature=temperature).text

    def generate_with_usage(
        self, messages: Sequence[dict[str, str]], *, model: str, temperature: float = 0.0,
    ) -> ProviderGenerationResult:
        input_value = {"messages": list(messages), "temperature": temperature}
        key, identity = cache_key(
            input_value=input_value, provider=self.provider_name, model=model,
            prompt_version=GENERATION_PROMPT_VERSION, config_hash=self.config_hash,
        )
        cached = self._read("generation", key)
        if cached:
            value = dict(cached["value"])
            value["usage_source"] = f"cache:{value.get('usage_source', 'unknown')}"
            return self._apply_cost(ProviderGenerationResult(**value))
        value = self.wrapped.generate_with_usage(messages, model=model, temperature=temperature)
        value = self._apply_cost(value)
        self._write("generation", key, identity, value.to_dict())
        return value

    def _apply_cost(self, value: ProviderGenerationResult) -> ProviderGenerationResult:
        if not self.pricing:
            return value
        cost = (
            value.input_tokens / 1_000_000 * self.pricing["input_per_million"]
            + value.output_tokens / 1_000_000 * self.pricing["output_per_million"]
        )
        return replace(value, cost=round(cost, 10))


def load_pricing(path: Path | None, model: str) -> tuple[dict[str, float] | None, str]:
    if path is None:
        return None, "NO_LOCAL_PRICING_CONFIG"
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    row = value.get(model)
    if not isinstance(row, dict) or not {"input_per_million", "output_per_million"}.issubset(row):
        raise ValueError(f"Local pricing configuration has no complete entry for {model}")
    return {
        "input_per_million": float(row["input_per_million"]),
        "output_per_million": float(row["output_per_million"]),
    }, "LOCAL_PRICING_CONFIG"


def estimate_evaluation(
    *, query_input_path: Path, corpus_fixture_path: Path, max_cases: int | None,
    provider: str, pricing_config: Path | None,
) -> dict[str, Any]:
    queries = load_query_inputs(query_input_path)
    documents, _, _ = load_corpus_fixture(corpus_fixture_path)
    selected = queries[:max_cases] if max_cases is not None else queries
    corpus_text = " ".join(page for document in documents for page in document.pages)
    # A transparent local estimate, not provider-billed tokenizer output.
    corpus_tokens = max(1, (len(corpus_text) + 3) // 4)
    query_tokens = sum(max(1, (len(item.query_text) + 3) // 4) for item in selected)
    estimated_input = query_tokens + len(selected) * min(corpus_tokens, 4096)
    estimated_output = len(selected) * 512
    pricing, pricing_status = load_pricing(pricing_config, GENERATION_MODEL)
    projected_cost = None
    if pricing:
        projected_cost = round(
            estimated_input / 1_000_000 * pricing["input_per_million"]
            + estimated_output / 1_000_000 * pricing["output_per_million"],
            8,
        )
    config = ReadinessConfig(provider=provider)
    return {
        "status": READINESS_STATUS,
        "provider": provider,
        "network_called": False,
        "case_count": len(selected),
        "available_case_count": len(queries),
        "estimated_input_tokens": estimated_input,
        "estimated_output_tokens": estimated_output,
        "token_estimate_method": "UTF-8 character count divided by four plus fixed 512-token output budget per case",
        "projected_cost": projected_cost,
        "pricing_status": pricing_status,
        "fixed_config": asdict(config) | {"config_hash": config.config_hash},
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _estimated_tokens(text: str) -> int:
    """Transparent local character estimate; never represented as provider usage."""

    return max(1, (len(text) + 3) // 4)


def _pdf_text(path: Path) -> tuple[str, int]:
    import fitz

    with fitz.open(path) as document:
        pages = [page.get_text("text", sort=True) for page in document]
    return "\n".join(pages), len(pages)


def _pre_freeze_scope(
    *, dataset_manifest_path: Path, gold_queries_path: Path, source_manifest_path: Path,
) -> dict[str, Any]:
    manifest = _read_json(dataset_manifest_path)
    query_payload = _read_json(gold_queries_path)
    source_payload = _read_json(source_manifest_path)
    all_queries = query_payload.get("queries")
    source_rows = source_payload.get("files")
    if not isinstance(all_queries, list) or not isinstance(source_rows, list):
        raise ValueError("Pre-freeze query/source manifests have an invalid shape")
    if int(manifest.get("gold_query_count", -1)) != len(all_queries):
        raise ValueError("dataset_manifest gold_query_count does not match gold_queries.json")

    holdout_packages = set(manifest.get("split_report", {}).get("candidate_holdout_packages", []))
    queries = [item for item in all_queries if item.get("split") == "candidate_holdout"]
    documents = [item for item in source_rows if item.get("split") == "candidate_holdout"]
    if not queries or not documents or not holdout_packages:
        raise ValueError("Candidate-holdout scope is empty or missing")
    if {item.get("document_package") for item in queries} != holdout_packages:
        raise ValueError("Candidate-holdout query packages disagree with dataset_manifest")
    if {item.get("package_id") for item in documents} != holdout_packages:
        raise ValueError("Candidate-holdout source packages disagree with dataset_manifest")

    query_texts: list[str] = []
    for item in queries:
        text = item.get("query")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Candidate-holdout query text is missing")
        query_texts.append(text)

    corpus_parts: list[str] = []
    page_count = 0
    source_root = Path(source_manifest_path).parent
    for item in documents:
        relative_path = item.get("relative_path")
        if not isinstance(relative_path, str):
            raise ValueError("Candidate-holdout source relative_path is missing")
        pdf_path = source_root / relative_path
        if not pdf_path.is_file():
            raise FileNotFoundError(pdf_path)
        if _file_sha256(pdf_path) != item.get("sha256"):
            raise ValueError(f"Candidate-holdout source hash mismatch: {relative_path}")
        text, observed_pages = _pdf_text(pdf_path)
        if observed_pages != int(item.get("page_count", -1)):
            raise ValueError(f"Candidate-holdout page count mismatch: {relative_path}")
        corpus_parts.append(text)
        page_count += observed_pages

    return {
        "dataset_version": manifest.get("dataset_version"),
        "query_count": len(queries),
        "document_count": len(documents),
        "page_count": page_count,
        "query_token_estimate": sum(_estimated_tokens(text) for text in query_texts),
        "corpus_token_estimate": _estimated_tokens("\n".join(corpus_parts)),
        "dataset_manifest_sha256": _file_sha256(dataset_manifest_path),
        "gold_queries_sha256": _file_sha256(gold_queries_path),
        "source_manifest_sha256": _file_sha256(source_manifest_path),
        "candidate_holdout_packages": sorted(holdout_packages),
    }


def _scale_scope(scale_manifest_path: Path) -> dict[str, Any]:
    manifest = _read_json(scale_manifest_path)
    if manifest.get("privacy_safe") is not True or manifest.get("synthetic") is not True:
        raise ValueError("Scale subset must be marked privacy-safe and synthetic")
    document_count = int(manifest.get("document_count", 0))
    query_count = int(manifest.get("query_count", 0))
    documents = manifest.get("documents")
    query_ids = manifest.get("config", {}).get("gold_query_ids")
    if not isinstance(documents, list) or len(documents) != document_count:
        raise ValueError("Scale manifest document count is inconsistent")
    if not isinstance(query_ids, list) or len(query_ids) != query_count:
        raise ValueError("Scale manifest query count is inconsistent")

    # Reconstruct only from versioned local source code and verify it against the
    # supplied manifest.  This is deterministic and makes no provider call.
    from .a_gate_phase2 import QUERIES
    from .c_gate import build_scale_documents, scale_manifest

    reconstructed_manifest = scale_manifest(document_count)
    if reconstructed_manifest["corpus_hash"] != manifest.get("corpus_hash"):
        raise ValueError("Scale manifest corpus hash disagrees with the local deterministic builder")
    query_lookup = {item.id: item for item in QUERIES}
    if any(item not in query_lookup for item in query_ids):
        raise ValueError("Scale manifest references an unknown local query")
    scale_documents = build_scale_documents(document_count)
    query_texts = [query_lookup[item].text for item in query_ids]
    corpus_text = "\n".join(page for document in scale_documents for page in document.pages)
    return {
        "dataset_version": manifest.get("schema_version"),
        "query_count": query_count,
        "document_count": document_count,
        "page_count": sum(len(item.pages) for item in scale_documents),
        "query_token_estimate": sum(_estimated_tokens(text) for text in query_texts),
        "corpus_token_estimate": _estimated_tokens(corpus_text),
        "scale_manifest_sha256": _file_sha256(scale_manifest_path),
        "corpus_hash": manifest.get("corpus_hash"),
        "development_only": manifest.get("development_only"),
    }


def _load_e1_pricing(path: Path | None) -> tuple[dict[str, float] | None, str, str | None]:
    if path is None:
        return None, "NO_LOCAL_PRICING_CONFIG", None
    payload = _read_json(path)
    generation = payload.get(GENERATION_MODEL)
    embedding = payload.get(EMBEDDING_MODEL)
    if not isinstance(generation, dict) or not {"input_per_million", "output_per_million"} <= set(generation):
        raise ValueError(f"Local pricing configuration has no complete entry for {GENERATION_MODEL}")
    if not isinstance(embedding, dict) or "input_per_million" not in embedding:
        raise ValueError(f"Local pricing configuration has no input price for {EMBEDDING_MODEL}")
    return {
        "generation_input_per_million": float(generation["input_per_million"]),
        "generation_output_per_million": float(generation["output_per_million"]),
        "embedding_input_per_million": float(embedding["input_per_million"]),
    }, "LOCAL_PRICING_CONFIG", _file_sha256(path)


def _scenario_estimate(
    *, name: str, scope: dict[str, Any], modes: Sequence[str], repeats: int,
    pricing: dict[str, float] | None, average_provider_latency_ms: float | None,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be at least one")
    if not modes or len(set(modes)) != len(modes):
        raise ValueError("modes must be non-empty and unique")
    query_count = int(scope["query_count"])
    mode_count = len(modes)
    cases_per_repeat = query_count * mode_count
    case_count = cases_per_repeat * repeats
    context_tokens_per_case = min(int(scope["corpus_token_estimate"]), MAX_CONTEXT_TOKEN_BUDGET_PER_CASE)
    estimated_input_tokens = repeats * mode_count * (
        int(scope["query_token_estimate"]) + query_count * context_tokens_per_case
    )
    estimated_output_tokens = case_count * OUTPUT_TOKEN_BUDGET_PER_CASE
    estimated_embedding_input_tokens = repeats * (
        int(scope["corpus_token_estimate"]) + mode_count * int(scope["query_token_estimate"])
    )

    # The corpus is one batch call. Query vectors have identical cache identity
    # across modes within a repeat, so later modes are expected cache hits. Each
    # repeat uses a separate cache root to preserve independent-run semantics.
    embedding_operations = repeats * (1 + cases_per_repeat)
    embedding_cache_misses = repeats * (1 + query_count)
    embedding_cache_hits = repeats * query_count * max(0, mode_count - 1)
    keyword_operations = case_count
    generation_operations = case_count
    keyword_cache_misses = keyword_operations
    generation_cache_misses = generation_operations
    expected_cache_hits = embedding_cache_hits
    expected_cache_misses = embedding_cache_misses + keyword_cache_misses + generation_cache_misses
    request_count = expected_cache_misses
    retry_budget = generation_operations * MAX_GENERATION_RETRIES_PER_CASE

    projected_cost = None
    if pricing is not None:
        projected_cost = round(
            estimated_input_tokens / 1_000_000 * pricing["generation_input_per_million"]
            + estimated_output_tokens / 1_000_000 * pricing["generation_output_per_million"]
            + estimated_embedding_input_tokens / 1_000_000 * pricing["embedding_input_per_million"],
            8,
        )
    estimated_artifact_size_bytes = (
        case_count * 2048
        + estimated_input_tokens * 4
        + estimated_output_tokens * 4
        + request_count * 512
    )
    if average_provider_latency_ms is None:
        provider_runtime_estimate = "UNKNOWN"
        estimated_provider_wall_clock_ms = None
    else:
        provider_runtime_estimate = "LOCAL_LATENCY_ASSUMPTION"
        estimated_provider_wall_clock_ms = round(request_count * average_provider_latency_ms, 3)

    return {
        "scenario": name,
        "query_count": query_count,
        "mode_count": mode_count,
        "modes": list(modes),
        "repeats": repeats,
        "total_case_count": case_count,
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_total_tokens": estimated_input_tokens + estimated_output_tokens,
        "estimated_embedding_input_tokens": estimated_embedding_input_tokens,
        "embedding_operations": embedding_operations,
        "embedding_input_count": repeats * (int(scope["page_count"]) + cases_per_repeat),
        "keyword_operations": keyword_operations,
        "generation_operations": generation_operations,
        "operation_count_semantics": "cold-cache upper bound; controlled failures may skip generation",
        "expected_cache_hits": expected_cache_hits,
        "expected_cache_misses": expected_cache_misses,
        "cache_breakdown": {
            "embedding_hits": embedding_cache_hits,
            "embedding_misses": embedding_cache_misses,
            "keyword_hits": 0,
            "keyword_misses": keyword_cache_misses,
            "generation_hits": 0,
            "generation_misses": generation_cache_misses,
        },
        "provider_request_count": request_count,
        "generation_retry_budget": retry_budget,
        "estimated_artifact_size_bytes": estimated_artifact_size_bytes,
        "estimated_artifact_size_mib": round(estimated_artifact_size_bytes / (1024 * 1024), 3),
        "provider_runtime_estimate": provider_runtime_estimate,
        "estimated_provider_wall_clock_ms": estimated_provider_wall_clock_ms,
        "projected_cost": projected_cost,
    }


def estimate_full_e1(
    *, dataset_manifest_path: Path, gold_queries_path: Path, source_manifest_path: Path,
    repeats: int, modes: Sequence[str] = E1_MODES, include_scale_subset: bool = False,
    scale_manifest_path: Path | None = None, pricing_config: Path | None = None,
    average_provider_latency_ms: float | None = None,
) -> dict[str, Any]:
    """Estimate the planned full E1 entirely from local, pre-freeze inputs."""

    selected_modes = tuple(modes)
    unknown_modes = sorted(set(selected_modes) - set(E1_MODES))
    if unknown_modes:
        raise ValueError(f"Unsupported E1 modes: {', '.join(unknown_modes)}")
    if average_provider_latency_ms is not None and average_provider_latency_ms < 0:
        raise ValueError("average_provider_latency_ms cannot be negative")
    pricing, pricing_status, pricing_sha256 = _load_e1_pricing(pricing_config)
    base_scope = _pre_freeze_scope(
        dataset_manifest_path=dataset_manifest_path,
        gold_queries_path=gold_queries_path,
        source_manifest_path=source_manifest_path,
    )
    base = _scenario_estimate(
        name=f"BASE_E1_{repeats}_REPEAT" if repeats == 1 else f"BASE_E1_{repeats}_REPEATS",
        scope=base_scope,
        modes=selected_modes,
        repeats=repeats,
        pricing=pricing,
        average_provider_latency_ms=average_provider_latency_ms,
    )
    scale = None
    if include_scale_subset:
        if scale_manifest_path is None:
            raise ValueError("scale_manifest_path is required when include_scale_subset is true")
        scale_scope = _scale_scope(scale_manifest_path)
        scale = _scenario_estimate(
            name="OPTIONAL_PROVIDER_BACKED_SCALE_SUBSET",
            scope=scale_scope,
            modes=SCALE_SUBSET_MODES,
            repeats=1,
            pricing=pricing,
            average_provider_latency_ms=average_provider_latency_ms,
        )
        scale["separate_from_base_e1"] = True
        scale["development_only"] = scale_scope["development_only"]
        scale["document_count"] = scale_scope["document_count"]
        scale["scale_manifest_sha256"] = scale_scope["scale_manifest_sha256"]
        scale["corpus_hash"] = scale_scope["corpus_hash"]

    combined_cost = None
    if base["projected_cost"] is not None:
        combined_cost = round(base["projected_cost"] + (scale["projected_cost"] if scale else 0.0), 8)
    config = ReadinessConfig(provider="openai")
    return {
        "schema_version": E1_ESTIMATE_SCHEMA_VERSION,
        "status": READINESS_STATUS,
        "authorization_status": "DO_NOT_RUN_FINAL_E1_YET",
        "estimate_only": True,
        "network_called": False,
        "api_key_read": False,
        "provider": "openai",
        "fixed_config": asdict(config) | {"config_hash": config.config_hash},
        "source_scope": base_scope,
        "base_e1": base,
        "optional_scale_subset": scale,
        "pricing_status": pricing_status,
        "pricing_config_sha256": pricing_sha256,
        "combined_projected_cost": combined_cost,
        "token_estimate_method": (
            "local Unicode character count divided by four; 4096-token maximum context and "
            "512-token output budget per case; not provider-billed usage"
        ),
        "cache_policy": (
            "operation/input/provider/model/prompt/config keyed cache; separate cache root per repeat; "
            "resume only the same sealed run identity"
        ),
        "artifact_size_method": (
            "2048 bytes per case plus four bytes per estimated input/output token and 512 bytes per provider request"
        ),
    }


def write_e1_estimate_bundle(estimate: dict[str, Any], output_path: Path) -> tuple[Path, Path]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(estimate, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    rows: list[dict[str, Any]] = []
    for scenario in (estimate["base_e1"], estimate.get("optional_scale_subset")):
        if scenario is None:
            continue
        rows.append({
            "scenario": scenario["scenario"],
            "query_count": scenario["query_count"],
            "mode_count": scenario["mode_count"],
            "modes": ";".join(scenario["modes"]),
            "repeats": scenario["repeats"],
            "total_case_count": scenario["total_case_count"],
            "estimated_input_tokens": scenario["estimated_input_tokens"],
            "estimated_output_tokens": scenario["estimated_output_tokens"],
            "estimated_total_tokens": scenario["estimated_total_tokens"],
            "estimated_embedding_input_tokens": scenario["estimated_embedding_input_tokens"],
            "embedding_operations": scenario["embedding_operations"],
            "generation_operations": scenario["generation_operations"],
            "expected_cache_hits": scenario["expected_cache_hits"],
            "expected_cache_misses": scenario["expected_cache_misses"],
            "provider_request_count": scenario["provider_request_count"],
            "generation_retry_budget": scenario["generation_retry_budget"],
            "estimated_artifact_size_bytes": scenario["estimated_artifact_size_bytes"],
            "provider_runtime_estimate": scenario["provider_runtime_estimate"],
            "estimated_provider_wall_clock_ms": scenario["estimated_provider_wall_clock_ms"],
            "pricing_status": estimate["pricing_status"],
            "projected_cost": scenario["projected_cost"],
            "network_called": estimate["network_called"],
        })
    csv_path = output_path.with_suffix(".csv")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    csv_path.write_text(buffer.getvalue(), encoding="utf-8", newline="")
    return output_path, csv_path
