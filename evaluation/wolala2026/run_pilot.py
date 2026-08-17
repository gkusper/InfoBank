from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .adapters import ALL_MODES, run_adapters_for_case
from .common import read_json, read_jsonl, sha256_file, write_checksums, write_json, write_jsonl
from .pilot_data import DATA_DIR, DEV_DATASET, HELDOUT_DATASET
from .retrieval import build_retrieval_snapshot
from .run_manifest import build_manifest, now_utc, write_schema
from .score_pilot import write_score_outputs


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PACKAGE_DIR / "development_run"


def run_pilot(
    *,
    dataset: str,
    modes: list[str],
    repetitions: int,
    output_dir: str | Path,
    max_mode_executions: int,
    max_embedding_calls: int,
    max_generation_calls: int,
    max_total_external_calls: int,
    allow_real_api: bool = False,
    allow_heldout: bool = False,
) -> dict[str, Any]:
    if dataset == HELDOUT_DATASET and not allow_heldout:
        raise RuntimeError("Held-out pilot execution refused: supply an explicit held-out approval flag for a future run.")
    dataset_dir = DATA_DIR / dataset
    cases = read_jsonl(dataset_dir / "cases.jsonl")
    dataset_manifest = read_json(dataset_dir / "manifest.json")
    mode_executions = len(cases) * len(modes) * repetitions
    estimated_embedding_calls = len(cases) if allow_real_api else 0
    estimated_generation_calls = mode_executions if allow_real_api else 0
    estimated_total = estimated_embedding_calls + estimated_generation_calls
    if mode_executions > max_mode_executions:
        raise RuntimeError(f"Mode execution cap exceeded: requested {mode_executions}, cap {max_mode_executions}.")
    if estimated_embedding_calls > max_embedding_calls:
        raise RuntimeError(f"Embedding call cap exceeded: requested {estimated_embedding_calls}, cap {max_embedding_calls}.")
    if estimated_generation_calls > max_generation_calls:
        raise RuntimeError(f"Generation call cap exceeded: requested {estimated_generation_calls}, cap {max_generation_calls}.")
    if estimated_total > max_total_external_calls:
        raise RuntimeError(f"Total external call cap exceeded: requested {estimated_total}, cap {max_total_external_calls}.")
    if allow_real_api and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --allow-real-api and is not visible in the environment.")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    protocol_checksum = sha256_file(PACKAGE_DIR / "WOLALA2026_PILOT_PROTOCOL_v1.md")
    start_time = now_utc()
    run_id = f"{dataset}_deterministic_v1"
    manifest = build_manifest(
        run_id=run_id,
        run_type="development_integration_pilot_v1" if dataset == DEV_DATASET else "heldout_pilot_v1",
        development_or_heldout="development" if dataset == DEV_DATASET else "heldout",
        dataset_name=dataset,
        dataset_checksum=dataset_manifest["dataset_checksum"],
        protocol_checksum=protocol_checksum,
        case_ids=[case["case_id"] for case in cases],
        modes=modes,
        repetitions=repetitions,
        max_mode_executions=max_mode_executions,
        max_embedding_calls=max_embedding_calls,
        max_generation_calls=max_generation_calls,
        max_total_external_calls=max_total_external_calls,
        start_time_utc=start_time,
        allow_real_api=allow_real_api,
    )
    results: list[dict[str, Any]] = []
    retrieval_snapshots = []
    errors: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        for case in cases:
            snapshot, case_results = run_adapters_for_case(case, modes, run_id=run_id, repetition=repetition)
            retrieval_snapshots.append(snapshot)
            results.extend(case_results)
    write_jsonl(out / "raw_results.jsonl", results)
    write_jsonl(out / "shared_retrieval_snapshots.jsonl", retrieval_snapshots)
    scores = write_score_outputs(cases, results, out)
    latency_payload = {
        "diagnostic_only": True,
        "not_publication_ready": True,
        "latency_summaries": scores["latency_summaries"],
        "mode_execution_count": mode_executions,
    }
    write_json(out / "latency_diagnostics.json", latency_payload)
    write_jsonl(out / "errors.jsonl", errors)
    manifest["end_time_utc"] = now_utc()
    manifest["actual_embedding_calls"] = 0
    manifest["actual_generation_calls"] = 0
    manifest["actual_total_external_calls"] = 0
    manifest["mode_execution_count"] = mode_executions
    manifest["heldout_mode_execution_count"] = 0 if dataset == DEV_DATASET else mode_executions
    manifest["completion_status"] = "COMPLETED"
    manifest["errors"] = errors
    write_json(out / "run_manifest.json", manifest)
    write_schema(PACKAGE_DIR / "run_manifest_schema.json")
    write_checksums(
        out / "checksums.sha256",
        [
            out / "run_manifest.json",
            out / "raw_results.jsonl",
            out / "case_scores.jsonl",
            out / "pair_scores.jsonl",
            out / "summary.json",
            out / "summary.csv",
            out / "summary_table.tex",
            out / "latency_diagnostics.json",
            out / "errors.jsonl",
            out / "shared_retrieval_snapshots.jsonl",
        ],
        root=out,
    )
    return manifest


def parse_modes(value: str) -> list[str]:
    modes = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [mode for mode in modes if mode not in ALL_MODES]
    if unknown:
        raise ValueError(f"Unknown mode(s): {unknown}")
    return modes


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a capped WoLaLa 2026 development integration pilot.")
    parser.add_argument("--dataset", choices=[DEV_DATASET, HELDOUT_DATASET], required=True)
    parser.add_argument("--modes", default=",".join(ALL_MODES))
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-mode-executions", type=int, required=True)
    parser.add_argument("--max-embedding-calls", type=int, required=True)
    parser.add_argument("--max-generation-calls", type=int, required=True)
    parser.add_argument("--max-total-external-calls", type=int, required=True)
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--allow-heldout", action="store_true")
    args = parser.parse_args()
    manifest = run_pilot(
        dataset=args.dataset,
        modes=parse_modes(args.modes),
        repetitions=args.repetitions,
        output_dir=args.output_dir,
        max_mode_executions=args.max_mode_executions,
        max_embedding_calls=args.max_embedding_calls,
        max_generation_calls=args.max_generation_calls,
        max_total_external_calls=args.max_total_external_calls,
        allow_real_api=args.allow_real_api,
        allow_heldout=args.allow_heldout,
    )
    print(json.dumps({"completion_status": manifest["completion_status"], "mode_execution_count": manifest["mode_execution_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
