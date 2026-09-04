"""Estimate or explicitly execute a cached OpenAI/Anthropic actual-pipeline evaluation.

The default path is network-free.  A real run requires both ``--provider
openai`` or ``--provider anthropic`` and ``--allow-network-provider``; it never
falls back to a mock. Anthropic runs still use OpenAI embeddings.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.provider_readiness import (  # noqa: E402
    MAX_CONTEXT_TOKEN_BUDGET_PER_CASE,
    OUTPUT_TOKEN_BUDGET_PER_CASE,
    READINESS_STATUS,
    E1_MODES,
    embedding_model_for_provider,
    embedding_provider_for_provider,
    estimate_evaluation,
    estimate_full_e1,
    generation_model_for_provider,
    validate_provider_request,
    write_e1_estimate_bundle,
)


FULL_EXPERIMENT_MODES = (
    "C0_VECTOR_ONLY",
    "C1_VECTOR_ROUTING",
    "P1_PROMPT_ONLY_GOVERNANCE",
    "C2_PERMISSION_FILTERED",
    "C3_FULL_ROLE_AWARE",
)
S1_S6_INPUT_DIR = REPOSITORY_ROOT / "artifacts/s1_s6_publication_experiment_v2/combined_input"
DEFAULT_FULL_QUERY_INPUT = S1_S6_INPUT_DIR / "combined_query_inputs.jsonl"
DEFAULT_FULL_CORPUS_FIXTURE = S1_S6_INPUT_DIR / "combined_corpus_fixture.json"
DEFAULT_FULL_GOLD_ANNOTATIONS = S1_S6_INPUT_DIR / "combined_reference_annotations.jsonl"
HAIKU_45_INPUT_PER_MILLION = 1.0
HAIKU_45_OUTPUT_PER_MILLION = 5.0
DEFAULT_MAX_PROVIDER_REQUEST_ATTEMPTS = 70
DEFAULT_MAX_ANTHROPIC_ESTIMATED_COST = 6.0
DEFAULT_MAX_PROVIDER_OUTPUT_TOKENS = 1024
DEFAULT_MAX_PROVIDER_RETRIES = 1


def _required(path: Path | None, flag: str) -> Path:
    if path is None:
        raise ValueError(f"{flag} is required for an actual provider run")
    return path


def _jsonl_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _load_json_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _token_estimate(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _token_estimate_from_char_count(character_count: int) -> int:
    return max(1, math.ceil(character_count / 4))


def _full_corpus_summary(corpus_path: Path) -> dict:
    corpus = _load_json_object(corpus_path)
    documents = corpus.get("documents", [])
    if not isinstance(documents, list):
        raise ValueError(f"Expected documents[] in {corpus_path}")
    page_count = 0
    text_chars = 0
    for document in documents:
        pages = document.get("pages") if isinstance(document, dict) else None
        if not isinstance(pages, list):
            raise ValueError(f"Expected document pages[] in {corpus_path}")
        page_count += len(pages)
        text_chars += sum(len(str(page)) for page in pages)
    return {
        "document_count": len(documents),
        "page_count": page_count,
        "text_character_count": text_chars,
        "corpus_token_estimate": _token_estimate_from_char_count(text_chars),
    }


def _full_query_token_estimate(query_input_path: Path) -> int:
    total = 0
    for line in query_input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = row.get("query_text") or row.get("question") or row.get("query") or ""
        total += _token_estimate(str(text))
    return total


def full_experiment_preflight_plan(
    *,
    provider: str,
    generation_model: str | None,
    embedding_provider: str | None,
    embedding_model: str | None,
    repeats: int,
    modes: tuple[str, ...],
    query_input_path: Path,
    corpus_fixture_path: Path,
    gold_annotations_path: Path,
    anthropic_cost_cap: float,
) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be at least one")
    if not modes or len(set(modes)) != len(modes):
        raise ValueError("full experiment modes must be non-empty and unique")
    unknown_modes = sorted(set(modes) - set(FULL_EXPERIMENT_MODES))
    if unknown_modes:
        raise ValueError(f"Unsupported full-experiment modes: {', '.join(unknown_modes)}")

    normalized_provider = provider if provider != "deterministic-mock" else "openai"
    generation_model = generation_model or generation_model_for_provider(normalized_provider)
    embedding_provider = embedding_provider or embedding_provider_for_provider(normalized_provider)
    embedding_model = embedding_model or embedding_model_for_provider(normalized_provider)
    query_count = _jsonl_count(query_input_path)
    gold_count = _jsonl_count(gold_annotations_path)
    corpus = _full_corpus_summary(corpus_fixture_path)
    query_tokens = _full_query_token_estimate(query_input_path)
    mode_count = len(modes)
    planned_records = query_count * mode_count * repeats
    routing_keyword_modes = {
        "C1_VECTOR_ROUTING",
        "P1_PROMPT_ONLY_GOVERNANCE",
        "C3_FULL_ROLE_AWARE",
    }
    keyword_operations = query_count * repeats * sum(1 for mode in modes if mode in routing_keyword_modes)
    generation_operations_upper_bound = planned_records
    estimated_input_tokens = repeats * mode_count * (
        query_tokens + query_count * min(int(corpus["corpus_token_estimate"]), MAX_CONTEXT_TOKEN_BUDGET_PER_CASE)
    )
    estimated_output_tokens = planned_records * OUTPUT_TOKEN_BUDGET_PER_CASE
    estimated_anthropic_cost = round(
        estimated_input_tokens / 1_000_000 * HAIKU_45_INPUT_PER_MILLION
        + estimated_output_tokens / 1_000_000 * HAIKU_45_OUTPUT_PER_MILLION,
        8,
    )
    return {
        "status": READINESS_STATUS,
        "preflight_only": True,
        "network_called": False,
        "api_key_read": False,
        "do_not_run_yet": True,
        "provider": normalized_provider,
        "generation_model": generation_model,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "modes": list(modes),
        "repeats": repeats,
        "query_count": query_count,
        "gold_annotation_count": gold_count,
        "planned_records": planned_records,
        "expected_records_for_default_s1_s6": 630,
        "keyword_selection_operations": keyword_operations,
        "generation_operations_upper_bound": generation_operations_upper_bound,
        "anthropic_request_upper_bound": keyword_operations + generation_operations_upper_bound,
        "openai_query_embedding_operations_upper_bound": planned_records,
        "openai_document_embedding_reuse_required": True,
        "prepared_corpus_mode_available": False,
        "document_embeddings_reused_without_provider_calls": False,
        "stored_corpus_integrity_blocker": (
            "The legacy seeded runner creates an isolated corpus and Chroma index for provider runs; "
            "full Claude execution must use --query-only with an approved prepared manifest."
        ),
        "corpus": corpus,
        "token_estimate_method": (
            "local Unicode character count divided by four; 4096-token maximum context and "
            "512-token output budget per case; not provider-billed usage"
        ),
        "haiku_45_preliminary_pricing_usd_per_million_tokens": {
            "input": HAIKU_45_INPUT_PER_MILLION,
            "output": HAIKU_45_OUTPUT_PER_MILLION,
        },
        "estimated_anthropic_input_tokens": estimated_input_tokens,
        "estimated_anthropic_output_tokens": estimated_output_tokens,
        "estimated_anthropic_cost_usd": estimated_anthropic_cost,
        "estimated_anthropic_cost_with_25_percent_margin_usd": round(estimated_anthropic_cost * 1.25, 8),
        "anthropic_cost_cap_usd": anthropic_cost_cap,
        "anthropic_cost_cap_status": "WITHIN_CAP" if estimated_anthropic_cost * 1.25 <= anthropic_cost_cap else "EXCEEDS_CAP",
        "confirmation_guard": (
            "Full seeded execution is disabled; use --query-only with --prepared-manifest and explicit "
            "full-experiment confirmation for the prepared-corpus path."
        ),
        "requires_confirm_full_experiment": True,
        "current_execution_limit": "preflight-only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["deterministic-mock", "openai", "anthropic"], default="deterministic-mock")
    parser.add_argument("--allow-network-provider", action="store_true")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--estimate-only", "--estimated-cost-only", dest="estimate_only", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--modes", nargs="+", choices=FULL_EXPERIMENT_MODES)
    parser.add_argument("--full-experiment-preflight", action="store_true")
    parser.add_argument("--full-experiment-modes", nargs="+", choices=FULL_EXPERIMENT_MODES)
    parser.add_argument("--confirm-full-experiment", action="store_true")
    parser.add_argument("--confirm-readiness-pilot", action="store_true")
    parser.add_argument("--prepared-manifest", type=Path)
    parser.add_argument("--query-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--case-ids-file", type=Path)
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument("--selection-plan-kind", choices=["two-case-smoke", "six-case-readiness"])
    parser.add_argument("--selection-plan-output", type=Path)
    parser.add_argument("--case-ids-output", type=Path)
    parser.add_argument("--include-scale-subset", action="store_true")
    parser.add_argument("--max-estimated-cost", type=float)
    parser.add_argument("--max-anthropic-estimated-cost", type=float, default=DEFAULT_MAX_ANTHROPIC_ESTIMATED_COST)
    parser.add_argument("--max-provider-request-attempts", type=int, default=DEFAULT_MAX_PROVIDER_REQUEST_ATTEMPTS)
    parser.add_argument("--max-provider-output-tokens", type=int, default=DEFAULT_MAX_PROVIDER_OUTPUT_TOKENS)
    parser.add_argument("--max-provider-retries", type=int, default=DEFAULT_MAX_PROVIDER_RETRIES)
    parser.add_argument("--pricing-config", type=Path)
    parser.add_argument("--average-provider-latency-ms", type=float)
    parser.add_argument("--generation-model")
    parser.add_argument("--embedding-provider")
    parser.add_argument("--embedding-model")
    parser.add_argument("--pre-freeze-manifest", type=Path, default=REPOSITORY_ROOT / "artifacts/pre_freeze/reviewer_v2_candidate/dataset_manifest.json")
    parser.add_argument("--gold-queries", type=Path, default=REPOSITORY_ROOT / "artifacts/pre_freeze/reviewer_v2_candidate/gold_queries.json")
    parser.add_argument("--source-manifest", type=Path, default=REPOSITORY_ROOT / "artifacts/pre_freeze/reviewer_v2_candidate/source_manifest.json")
    parser.add_argument("--scale-manifest", type=Path, default=REPOSITORY_ROOT / "artifacts/c_gate/scale/1000/manifest.json")
    parser.add_argument("--query-input", type=Path)
    parser.add_argument("--corpus-fixture", type=Path)
    parser.add_argument("--gold-annotations", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--chroma-dir", type=Path)
    parser.add_argument("--source-storage-dir", type=Path)
    parser.add_argument("--database-url")
    parser.add_argument("--admin-database-url")
    args = parser.parse_args()

    if args.selection_plan_kind:
        from evaluation.prepared_corpus_query_only import (
            make_readiness_selection_plan,
            make_two_case_smoke_selection_plan,
            write_case_id_file,
        )

        gold_annotations = args.gold_annotations or DEFAULT_FULL_GOLD_ANNOTATIONS
        query_input = args.query_input or DEFAULT_FULL_QUERY_INPUT
        if args.selection_plan_kind == "two-case-smoke":
            plan = make_two_case_smoke_selection_plan(
                query_input_path=query_input,
                gold_annotation_path=gold_annotations,
                output_path=args.selection_plan_output,
            )
        else:
            plan = make_readiness_selection_plan(
                query_input_path=query_input,
                gold_annotation_path=gold_annotations,
                output_path=args.selection_plan_output,
            )
        if args.case_ids_output is not None:
            write_case_id_file(plan["selected_case_ids"], args.case_ids_output)
            plan["case_ids_file"] = str(args.case_ids_output)
        print(json.dumps(plan, sort_keys=True, indent=2))
        return

    if args.query_only or args.prepared_manifest is not None:
        if args.prepared_manifest is None:
            raise ValueError("--prepared-manifest is required for --query-only")
        import os

        from evaluation.prepared_corpus_query_only import query_only_dry_run_plan, run_prepared_query_only

        repetitions = args.repetitions if args.repetitions is not None else args.repeats
        resolved_modes = tuple(args.full_experiment_modes or args.modes or FULL_EXPERIMENT_MODES)
        database_url = args.database_url or os.getenv("INFOBANK_EVAL_DATABASE_URL")
        admin_database_url = args.admin_database_url or os.getenv("INFOBANK_EVAL_ADMIN_DATABASE_URL")
        generation_model = args.generation_model or generation_model_for_provider(args.provider)
        embedding_provider = args.embedding_provider or embedding_provider_for_provider(args.provider)
        embedding_model = args.embedding_model or embedding_model_for_provider(args.provider)
        if args.dry_run or args.full_experiment_preflight:
            plan = query_only_dry_run_plan(
                prepared_manifest_path=args.prepared_manifest,
                database_url=database_url,
                case_ids_file=args.case_ids_file,
                modes=resolved_modes,
                repetitions=repetitions,
                output_dir=args.output,
                cache_dir=args.cache_dir,
                max_provider_output_tokens=args.max_provider_output_tokens,
                max_anthropic_estimated_cost=args.max_anthropic_estimated_cost,
            )
            print(json.dumps(plan, sort_keys=True, indent=2))
            return
        if not database_url:
            raise ValueError("--database-url or INFOBANK_EVAL_DATABASE_URL is required for query-only execution")
        result = run_prepared_query_only(
            prepared_manifest_path=args.prepared_manifest,
            output_dir=_required(args.output, "--output"),
            database_url=database_url,
            admin_database_url=admin_database_url,
            provider_name=args.provider,
            generation_model=generation_model,
            embedding_provider_name=embedding_provider,
            embedding_model=embedding_model,
            modes=resolved_modes,
            repetitions=repetitions,
            case_ids_file=args.case_ids_file,
            gold_annotation_path=args.gold_annotations or DEFAULT_FULL_GOLD_ANNOTATIONS,
            allow_network_provider=args.allow_network_provider,
            cache_dir=args.cache_dir,
            pricing_config_path=args.pricing_config,
            confirm_readiness_pilot=args.confirm_readiness_pilot,
            confirm_full_experiment=args.confirm_full_experiment,
            keep_workspaces=args.keep_workspaces,
            max_provider_request_attempts=args.max_provider_request_attempts,
            max_provider_output_tokens=args.max_provider_output_tokens,
            max_provider_retries=args.max_provider_retries,
            max_anthropic_estimated_cost=args.max_anthropic_estimated_cost,
        )
        print(json.dumps(result, sort_keys=True, indent=2))
        return

    if args.full_experiment_preflight:
        plan = full_experiment_preflight_plan(
            provider=args.provider,
            generation_model=args.generation_model,
            embedding_provider=args.embedding_provider,
            embedding_model=args.embedding_model,
            repeats=args.repeats,
            modes=tuple(args.full_experiment_modes or FULL_EXPERIMENT_MODES),
            query_input_path=args.query_input or DEFAULT_FULL_QUERY_INPUT,
            corpus_fixture_path=args.corpus_fixture or DEFAULT_FULL_CORPUS_FIXTURE,
            gold_annotations_path=args.gold_annotations or DEFAULT_FULL_GOLD_ANNOTATIONS,
            anthropic_cost_cap=args.max_anthropic_estimated_cost,
        )
        print(json.dumps(plan, sort_keys=True, indent=2))
        return

    if args.confirm_full_experiment:
        raise RuntimeError(
            "Full experiment execution remains disabled on the legacy seeded path; use --query-only "
            "with --prepared-manifest for prepared-corpus execution."
        )

    if args.estimate_only:
        estimate_provider = args.provider if args.provider != "deterministic-mock" else "openai"
        estimate = estimate_full_e1(
            dataset_manifest_path=args.pre_freeze_manifest,
            gold_queries_path=args.gold_queries,
            source_manifest_path=args.source_manifest,
            repeats=args.repeats,
            modes=args.modes or E1_MODES,
            include_scale_subset=args.include_scale_subset,
            scale_manifest_path=args.scale_manifest,
            pricing_config=args.pricing_config,
            average_provider_latency_ms=args.average_provider_latency_ms,
            provider=estimate_provider,
            generation_model=args.generation_model,
            embedding_provider=args.embedding_provider,
            embedding_model=args.embedding_model,
        )
        if args.max_estimated_cost is not None:
            if estimate["combined_projected_cost"] is None:
                raise RuntimeError("--max-estimated-cost cannot be enforced without a complete local --pricing-config")
            if estimate["combined_projected_cost"] > args.max_estimated_cost:
                raise RuntimeError(
                    f"Projected cost {estimate['combined_projected_cost']} exceeds --max-estimated-cost "
                    f"{args.max_estimated_cost}"
                )
        if args.output is not None:
            json_path, csv_path = write_e1_estimate_bundle(estimate, args.output)
            estimate["written_bundle"] = {"json": str(json_path), "csv": str(csv_path)}
        print(json.dumps(estimate, sort_keys=True, indent=2))
        return

    # Keep all runtime/provider imports below the estimate-only return. The
    # estimate path cannot read an API key or initialize a network adapter.
    if args.repeats != 1 or args.modes is not None or args.include_scale_subset or args.average_provider_latency_ms is not None:
        raise ValueError(
            "--repeats, --modes, --include-scale-subset and --average-provider-latency-ms are estimate-only; "
            "final multi-mode provider execution is not authorized"
        )
    import os

    from evaluation.actual_pipeline_runner import ActualPipelineConfig, run_actual_pipeline
    from evaluation.actual_pipeline_scorer import score_sealed_run
    from scripts.run_actual_pipeline_evaluation import _prepare_mysql_database

    query_input = _required(args.query_input, "--query-input")
    corpus_fixture = _required(args.corpus_fixture, "--corpus-fixture")
    estimate = estimate_evaluation(
        query_input_path=query_input,
        corpus_fixture_path=corpus_fixture,
        max_cases=args.max_cases,
        provider=args.provider,
        pricing_config=args.pricing_config,
        generation_model=args.generation_model,
        embedding_provider=args.embedding_provider,
        embedding_model=args.embedding_model,
    )
    if args.max_estimated_cost is not None:
        if estimate["projected_cost"] is None:
            raise RuntimeError("--max-estimated-cost cannot be enforced without a matching local --pricing-config entry")
        if estimate["projected_cost"] > args.max_estimated_cost:
            raise RuntimeError(
                f"Projected cost {estimate['projected_cost']} exceeds --max-estimated-cost {args.max_estimated_cost}"
            )
    if args.provider == "anthropic":
        if args.max_provider_output_tokens < 1:
            raise RuntimeError("--max-provider-output-tokens must be positive")
        if args.max_provider_retries < 0:
            raise RuntimeError("--max-provider-retries must not be negative")
        preliminary_anthropic_cost = round(
            estimate["estimated_input_tokens"] / 1_000_000 * HAIKU_45_INPUT_PER_MILLION
            + estimate["estimated_output_tokens"] / 1_000_000 * HAIKU_45_OUTPUT_PER_MILLION,
            8,
        )
        if preliminary_anthropic_cost > args.max_anthropic_estimated_cost:
            raise RuntimeError(
                f"Projected preliminary Anthropic cost {preliminary_anthropic_cost} exceeds "
                f"--max-anthropic-estimated-cost {args.max_anthropic_estimated_cost}"
            )
        if estimate["projected_cost"] is not None and estimate["projected_cost"] > args.max_anthropic_estimated_cost:
            raise RuntimeError(
                f"Projected Anthropic cost {estimate['projected_cost']} exceeds --max-anthropic-estimated-cost "
                f"{args.max_anthropic_estimated_cost}"
            )
        configured_max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "512"))
        configured_retries = int(os.getenv("ANTHROPIC_MAX_RETRIES", "1"))
        retry_attempts = 1 + args.max_provider_retries
        provider_operations_upper_bound = int(estimate["case_count"]) * 2
        request_attempts_upper_bound = provider_operations_upper_bound * retry_attempts
        if request_attempts_upper_bound > args.max_provider_request_attempts:
            raise RuntimeError(
                f"Provider request attempts upper bound {request_attempts_upper_bound} exceeds "
                f"--max-provider-request-attempts {args.max_provider_request_attempts}"
            )
        if args.max_provider_output_tokens > DEFAULT_MAX_PROVIDER_OUTPUT_TOKENS:
            raise RuntimeError("--max-provider-output-tokens must be 1024 or lower for the Anthropic smoke guard")
        if args.max_provider_retries > DEFAULT_MAX_PROVIDER_RETRIES:
            raise RuntimeError("--max-provider-retries must be 1 or lower for the Anthropic smoke guard")
        if configured_max_tokens > args.max_provider_output_tokens:
            raise RuntimeError(
                f"ANTHROPIC_MAX_TOKENS={configured_max_tokens} exceeds --max-provider-output-tokens "
                f"{args.max_provider_output_tokens}"
            )
        if configured_retries > args.max_provider_retries:
            raise RuntimeError(
                f"ANTHROPIC_MAX_RETRIES={configured_retries} exceeds --max-provider-retries {args.max_provider_retries}"
            )
        os.environ.setdefault("ANTHROPIC_MAX_TOKENS", str(configured_max_tokens))
        os.environ.setdefault("ANTHROPIC_MAX_RETRIES", str(configured_retries))
    validate_provider_request(args.provider, args.allow_network_provider)
    output = _required(args.output, "--output")
    cache_dir = _required(args.cache_dir, "--cache-dir")
    chroma_dir = _required(args.chroma_dir, "--chroma-dir")
    source_dir = _required(args.source_storage_dir, "--source-storage-dir")
    gold_path = _required(args.gold_annotations, "--gold-annotations")
    database_url = args.database_url or os.getenv("INFOBANK_EVAL_DATABASE_URL")
    admin_database_url = args.admin_database_url or os.getenv("INFOBANK_EVAL_ADMIN_DATABASE_URL")
    if not database_url:
        raise ValueError("--database-url or INFOBANK_EVAL_DATABASE_URL is required for an actual provider run")
    _prepare_mysql_database(database_url, admin_database_url)
    config = ActualPipelineConfig(
        generation_model=args.generation_model or generation_model_for_provider(args.provider),
        embedding_model=args.embedding_model or embedding_model_for_provider(args.provider),
    )
    embedding_provider = args.embedding_provider or embedding_provider_for_provider(args.provider)
    seal = run_actual_pipeline(
        query_input_path=query_input,
        corpus_fixture_path=corpus_fixture,
        output_dir=output / "raw",
        database_url=database_url,
        chroma_dir=chroma_dir,
        source_storage_dir=source_dir,
        run_id=f"actual-provider-{args.provider}",
        modes=["C3_FULL_ROLE_AWARE"],
        config=config,
        provider_name=args.provider,
        embedding_provider_name=embedding_provider,
        allow_network_provider=args.allow_network_provider,
        cache_dir=cache_dir,
        max_cases=args.max_cases,
        pricing_config_path=args.pricing_config,
    )
    scores = score_sealed_run(
        raw_run_path=output / "raw" / "raw_records.jsonl",
        seal_path=output / "raw" / "run_seal.json",
        gold_annotation_path=gold_path,
        output_dir=output / "scores",
    )
    print(json.dumps({"status": READINESS_STATUS, "seal": seal, "scores": scores}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
