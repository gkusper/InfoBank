"""Estimate or explicitly execute a cached OpenAI actual-pipeline evaluation.

The default path is network-free.  A real run requires both ``--provider
openai`` and ``--allow-network-provider``; it never falls back to a mock.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.actual_pipeline_runner import ActualPipelineConfig, run_actual_pipeline  # noqa: E402
from evaluation.actual_pipeline_scorer import score_sealed_run  # noqa: E402
from evaluation.provider_readiness import (  # noqa: E402
    EMBEDDING_MODEL,
    GENERATION_MODEL,
    READINESS_STATUS,
    estimate_evaluation,
    validate_provider_request,
)
from scripts.run_actual_pipeline_evaluation import _prepare_mysql_database  # noqa: E402


def _required(path: Path | None, flag: str) -> Path:
    if path is None:
        raise ValueError(f"{flag} is required for an actual provider run")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["deterministic-mock", "openai"], default="deterministic-mock")
    parser.add_argument("--allow-network-provider", action="store_true")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--estimated-cost-only", action="store_true")
    parser.add_argument("--max-estimated-cost", type=float)
    parser.add_argument("--pricing-config", type=Path)
    parser.add_argument("--query-input", type=Path, required=True)
    parser.add_argument("--corpus-fixture", type=Path, required=True)
    parser.add_argument("--gold-annotations", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--chroma-dir", type=Path)
    parser.add_argument("--source-storage-dir", type=Path)
    parser.add_argument("--database-url", default=os.getenv("INFOBANK_EVAL_DATABASE_URL"))
    parser.add_argument("--admin-database-url", default=os.getenv("INFOBANK_EVAL_ADMIN_DATABASE_URL"))
    args = parser.parse_args()

    estimate = estimate_evaluation(
        query_input_path=args.query_input,
        corpus_fixture_path=args.corpus_fixture,
        max_cases=args.max_cases,
        provider=args.provider,
        pricing_config=args.pricing_config,
    )
    if args.max_estimated_cost is not None:
        if estimate["projected_cost"] is None:
            raise RuntimeError("--max-estimated-cost cannot be enforced without a matching local --pricing-config entry")
        if estimate["projected_cost"] > args.max_estimated_cost:
            raise RuntimeError(
                f"Projected cost {estimate['projected_cost']} exceeds --max-estimated-cost {args.max_estimated_cost}"
            )
    if args.estimated_cost_only:
        print(json.dumps(estimate, sort_keys=True, indent=2))
        return

    validate_provider_request(args.provider, args.allow_network_provider)
    output = _required(args.output, "--output")
    cache_dir = _required(args.cache_dir, "--cache-dir")
    chroma_dir = _required(args.chroma_dir, "--chroma-dir")
    source_dir = _required(args.source_storage_dir, "--source-storage-dir")
    gold_path = _required(args.gold_annotations, "--gold-annotations")
    if not args.database_url:
        raise ValueError("--database-url or INFOBANK_EVAL_DATABASE_URL is required for an actual provider run")
    _prepare_mysql_database(args.database_url, args.admin_database_url)
    config = ActualPipelineConfig(
        generation_model=GENERATION_MODEL if args.provider == "openai" else "infobank-deterministic-extractive-v1",
        embedding_model=EMBEDDING_MODEL if args.provider == "openai" else "infobank-deterministic-embedding-v1",
    )
    seal = run_actual_pipeline(
        query_input_path=args.query_input,
        corpus_fixture_path=args.corpus_fixture,
        output_dir=output / "raw",
        database_url=args.database_url,
        chroma_dir=chroma_dir,
        source_storage_dir=source_dir,
        run_id=f"actual-provider-{args.provider}",
        modes=["B3_FULL_ROLE_AWARE"],
        config=config,
        provider_name=args.provider,
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
