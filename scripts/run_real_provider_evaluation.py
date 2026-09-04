"""Estimate or explicitly execute a cached OpenAI/Anthropic actual-pipeline evaluation.

The default path is network-free.  A real run requires both ``--provider
openai`` or ``--provider anthropic`` and ``--allow-network-provider``; it never
falls back to a mock. Anthropic runs still use OpenAI embeddings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.provider_readiness import (  # noqa: E402
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


def _required(path: Path | None, flag: str) -> Path:
    if path is None:
        raise ValueError(f"{flag} is required for an actual provider run")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["deterministic-mock", "openai", "anthropic"], default="deterministic-mock")
    parser.add_argument("--allow-network-provider", action="store_true")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--estimate-only", "--estimated-cost-only", dest="estimate_only", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--modes", nargs="+", choices=E1_MODES)
    parser.add_argument("--include-scale-subset", action="store_true")
    parser.add_argument("--max-estimated-cost", type=float)
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
