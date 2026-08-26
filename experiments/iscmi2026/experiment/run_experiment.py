from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from experiment_core import (
    BENCHMARK_DIR,
    CONDITIONS,
    EXPERIMENT_DIR,
    append_jsonl,
    build_oracle_documents,
    build_prompt,
    contexts_for_condition,
    deterministic_mock_embedding,
    ensure_no_forbidden_fields,
    inference_question,
    load_benchmark,
    load_configs,
    mock_model_output,
    parse_corrected_packet,
    parse_model_output,
    read_jsonl,
    resolve_packet_dir,
    sha256_file,
    sha256_text,
    write_json,
)


DRY_RUN_FAMILIES = ("OPEN_TASKS", "TASK_HISTORY", "NO_TASK_CONTROL", "DEADLINE")
MAX_API_RETRIES = 12
TRANSIENT_API_ERROR_TYPES = {
    "APIConnectionError",
    "APITimeoutError",
    "InternalServerError",
    "RateLimitError",
}


def utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=EXPERIMENT_DIR, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def select_questions(questions: list[dict[str, Any]], *, real_api: bool, limit: int | None) -> list[dict[str, Any]]:
    if real_api:
        selected = list(questions)
    else:
        selected = []
        for family in DRY_RUN_FAMILIES:
            match = next((row for row in questions if row["question_family"] == family), None)
            if match is not None:
                selected.append(match)
        if not selected:
            raise ValueError("No dry-run question families are available in this benchmark")
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be positive")
        selected = selected[:limit]
    return selected


def empty_usage() -> dict[str, Any]:
    return {
        "embedding_calls": 0,
        "generation_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "retries": 0,
    }


def sanitize_error_message(value: str) -> str:
    sanitized = re.sub(r"\borg-[A-Za-z0-9_-]+\b", "org-[redacted]", value)
    sanitized = re.sub(r"\bproj_[A-Za-z0-9_-]+\b", "proj_[redacted]", sanitized)
    return re.sub(r"\bsk-[A-Za-z0-9_-]+\b", "sk-[redacted]", sanitized)


def is_retryable_api_error(exc: Exception) -> bool:
    if type(exc).__name__ in TRANSIENT_API_ERROR_TYPES:
        return True
    status_code = getattr(exc, "status_code", None)
    return isinstance(status_code, int) and status_code >= 500


def retry_delay_seconds(exc: Exception, retry_number: int) -> float:
    delay: float | None = None
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    try:
        if headers.get("retry-after-ms") is not None:
            delay = float(headers["retry-after-ms"]) / 1000.0
        elif headers.get("retry-after") is not None:
            delay = float(headers["retry-after"])
    except (TypeError, ValueError):
        delay = None
    if delay is None:
        match = re.search(
            r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s)",
            str(exc),
            flags=re.IGNORECASE,
        )
        if match:
            delay = float(match.group(1)) / (1000.0 if match.group(2).lower() == "ms" else 1.0)
    fallback = min(30.0, float(2 * retry_number))
    if type(exc).__name__ == "RateLimitError":
        return max(delay or 0.0, fallback)
    return max(delay or 0.0, min(30.0, float(2 ** min(retry_number, 5))))


def add_usage(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in target:
        target[key] += int(source.get(key) or 0)


def usage_from_response(response: Any, *, generation_calls: int = 0, embedding_calls: int = 0) -> dict[str, Any]:
    usage = empty_usage()
    usage["generation_calls"] = generation_calls
    usage["embedding_calls"] = embedding_calls
    raw = getattr(response, "usage", None)
    if raw:
        usage["input_tokens"] = int(
            getattr(raw, "prompt_tokens", None) or getattr(raw, "input_tokens", None) or 0
        )
        usage["output_tokens"] = int(
            getattr(raw, "completion_tokens", None) or getattr(raw, "output_tokens", None) or 0
        )
        usage["total_tokens"] = int(getattr(raw, "total_tokens", None) or 0)
    return usage


def embed_texts(client: Any, texts: list[str], model: str, batch_size: int = 100) -> tuple[list[list[float]], dict[str, Any]]:
    embeddings: list[list[float]] = []
    usage = empty_usage()
    for start in range(0, len(texts), batch_size):
        response = client.embeddings.create(input=texts[start : start + batch_size], model=model)
        embeddings.extend(item.embedding for item in response.data)
        add_usage(usage, usage_from_response(response, embedding_calls=1))
    if len(embeddings) != len(texts):
        raise RuntimeError("Embedding API returned an unexpected number of vectors")
    return embeddings, usage


def generate_real(
    client: Any,
    *,
    system_prompt: str,
    user_prompt: str,
    config: dict[str, Any],
) -> tuple[str, dict[str, Any], str, int, str | None]:
    retries = 0
    while True:
        try:
            kwargs: dict[str, Any] = {
                "model": config["generator_model"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": config["temperature"],
                "max_tokens": config["max_output_tokens"],
                "response_format": {"type": "json_object"},
            }
            if config.get("top_p") is not None:
                kwargs["top_p"] = config["top_p"]
            if config.get("seed") is not None:
                kwargs["seed"] = config["seed"]
            response = client.chat.completions.create(**kwargs)
            raw = response.choices[0].message.content or ""
            finish_reason = getattr(response.choices[0], "finish_reason", None)
            usage = usage_from_response(response, generation_calls=1)
            usage["retries"] = retries
            return raw, usage, str(response.model), retries, finish_reason
        except Exception as exc:
            if not is_retryable_api_error(exc) or retries >= MAX_API_RETRIES:
                raise
            retries += 1
            time.sleep(retry_delay_seconds(exc, retries))


def existing_pairs(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    rows = read_jsonl(path)
    pairs = [(row["question_id"], row["condition"]) for row in rows]
    if len(pairs) != len(set(pairs)):
        raise ValueError(f"Duplicate result records already exist in {path}")
    return set(pairs)


def execute_generation_job(job: dict[str, Any], client: Any, real_api: bool) -> dict[str, Any]:
    started = time.perf_counter()
    error: dict[str, str] | None = None
    actual_model = "unavailable" if real_api else "deterministic-mock"
    generation_usage = empty_usage()
    finish_reason: str | None = None if real_api else "mock"
    output_status = "unparsable"
    parser_recovery_applied = False
    try:
        if real_api:
            raw_output, generation_usage, actual_model, _retries, finish_reason = generate_real(
                client,
                system_prompt=job["system_prompt"],
                user_prompt=job["user_prompt"],
                config=job["config"],
            )
        else:
            raw_output = mock_model_output(job["question"]["question"], job["contexts"])
        parsed_output, parser_error = parse_model_output(raw_output)
        parser_recovery_applied = bool(parsed_output.get("_parser_recovery"))
        if parser_error:
            error = {"type": "parser_error", "message": parser_error}
        if finish_reason == "length":
            output_status = "truncated_by_output_limit"
        elif parser_error or parser_recovery_applied:
            output_status = "invalid_json"
        elif finish_reason in {"stop", "mock"}:
            output_status = "complete"
    except Exception as exc:
        raw_output = ""
        parsed_output, _ = parse_model_output("{}")
        error = {"type": type(exc).__name__, "message": sanitize_error_message(str(exc))}
        output_status = "unparsable"
    question = job["question"]
    contexts = job["contexts"]
    config = job["config"]
    return {
        "schema_version": "1.0",
        "run_id": job["run_id"],
        "run_mode": job["run_mode"],
        "question_id": question["question_id"],
        "question_family": question["question_family"],
        "pilot_id": question["pilot_id"],
        "thread_id": question["thread_id"],
        "condition": job["condition"],
        "question": question["question"],
        "retrieved_context_ids": [row["document_id"] for row in contexts],
        "retrieved_message_ids": [
            row["message_id"] for row in contexts if row["document_type"] == "original_email_message"
        ],
        "retrieval_scores": job["retrieval_scores"],
        "raw_model_output": raw_output,
        "parsed_output": parsed_output,
        "system_prompt_sha256": sha256_text(job["system_prompt"]),
        "user_prompt_sha256": sha256_text(job["user_prompt"]),
        "latency_seconds": round(time.perf_counter() - started, 6),
        "input_tokens": generation_usage["input_tokens"],
        "output_tokens": generation_usage["output_tokens"],
        "total_tokens": generation_usage["total_tokens"],
        "api_calls": generation_usage["generation_calls"],
        "retries": generation_usage["retries"],
        "configured_generator_model": config["generator_model"],
        "actual_generator_model": actual_model,
        "finish_reason": finish_reason,
        "output_status": output_status,
        "parser_recovery_applied": parser_recovery_applied,
        "error": error,
    }


def build_manifest(
    *,
    run_id: str,
    mode: str,
    benchmark: dict[str, Any],
    configs: dict[str, dict[str, Any]],
    selected_questions: list[dict[str, Any]],
    packet_dir: Path,
    output_path: Path,
    config_dir: Path,
    generator_model_override: str | None,
) -> dict[str, Any]:
    shared = configs[CONDITIONS[0]]
    config_hashes = {
        condition: sha256_file(config_dir / config["config_file"])
        for condition, config in configs.items()
    }
    benchmark_dir = Path(benchmark["benchmark_dir"])
    benchmark_manifest_hash = sha256_file(benchmark_dir / "benchmark_manifest.json")
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "status": "running",
        "run_mode": mode,
        "git_commit": git_commit(),
        "timestamp_utc": utc_timestamp(),
        "conditions": list(CONDITIONS),
        "condition_manifests": [
            {
                "condition": condition,
                "generator_model": config["generator_model"],
                "embedding_model": config["embedding_model"],
                "temperature": config["temperature"],
                "top_p": config.get("top_p"),
                "seed": config.get("seed"),
                "max_output_tokens": config["max_output_tokens"],
                "retrieval_top_k": config["retrieval_top_k"],
                "chunking": config["chunking"],
                "similarity_metric": config["similarity_metric"],
                "thread_scope": config["thread_scope"],
                "question_count": len(selected_questions),
                "benchmark_manifest_hash": benchmark_manifest_hash,
                "task_representation_mode": config["task_representation_mode"],
                "config_sha256": config_hashes[condition],
            }
            for condition, config in configs.items()
        ],
        "generator_model": shared["generator_model"],
        "embedding_model": shared["embedding_model"],
        "temperature": shared["temperature"],
        "max_output_tokens": shared["max_output_tokens"],
        "question_count": len(selected_questions),
        "benchmark_dir": str(benchmark_dir),
        "benchmark_manifest_hash": benchmark_manifest_hash,
        "benchmark_question_count": len(benchmark["questions"]),
        "full_benchmark_question_count": 271,
        "expected_condition_question_pairs": len(selected_questions) * len(CONDITIONS),
        "question_ids_sha256": sha256_text(
            "\n".join(row["question_id"] for row in selected_questions)
        ),
        "corrected_packet": {
            "path": str(packet_dir),
            "aggregate_sha256": benchmark["manifest"]["pilot_packet"]["aggregate_sha256"],
            "raw_content_committed": False,
        },
        "generator_model_override": generator_model_override,
        "output_file": str(output_path),
        "prompt_sha256": sha256_text(__import__("experiment_core").SYSTEM_PROMPT),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "openai": package_version("openai"),
        },
        "gold_joined_during_inference": False,
        "oracle_interpretation": (
            "Oracle task-state representation only; automatic task-state extraction is not evaluated."
        ),
    }


def run(args: argparse.Namespace) -> int:
    benchmark_dir = Path(args.benchmark_dir).resolve() if args.benchmark_dir else BENCHMARK_DIR
    benchmark = load_benchmark(
        benchmark_dir,
        expected_question_count=None if args.benchmark_dir else 271,
    )
    config_dir = Path(args.config_dir).resolve() if args.config_dir else EXPERIMENT_DIR / "configs"
    configs = load_configs(config_dir, generator_model=args.generator_model)
    packet_dir = resolve_packet_dir(args.packet_dir)
    email_documents = parse_corrected_packet(packet_dir, benchmark["evidence"])
    oracle_documents = build_oracle_documents(benchmark["histories"], benchmark["snapshots"])
    ensure_no_forbidden_fields(email_documents, "email_corpus")
    ensure_no_forbidden_fields(oracle_documents, "oracle_corpus")

    selected_questions = select_questions(
        benchmark["questions"], real_api=args.real_api, limit=args.limit
    )
    mode = "real_api_smoke" if args.real_api and args.limit is not None else "real_api" if args.real_api else "mock_dry_run"
    run_id = args.run_id or f"iscmi2026-{mode}-{utc_timestamp().replace(':', '').replace('-', '')}"
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    inference_path = output_dir / "inference_results.jsonl"
    manifest_path = output_dir / "run_manifest.json"
    if inference_path.exists() and not args.resume:
        raise FileExistsError(f"{inference_path} exists; choose another output directory or pass --resume")
    done = existing_pairs(inference_path) if args.resume else set()

    manifest = build_manifest(
        run_id=run_id,
        mode=mode,
        benchmark=benchmark,
        configs=configs,
        selected_questions=selected_questions,
        packet_dir=packet_dir,
        output_path=inference_path,
        config_dir=config_dir,
        generator_model_override=args.generator_model,
    )
    manifest["max_parallel_generations"] = args.max_workers if args.real_api else 1
    write_json(manifest_path, manifest)

    client = None
    embedding_usage = empty_usage()
    shared = configs[CONDITIONS[0]]
    email_texts = [row["text"] for row in email_documents]
    question_texts = [row["question"] for row in selected_questions]
    if args.real_api:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set in the process environment")
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        email_vectors, email_usage = embed_texts(client, email_texts, shared["embedding_model"])
        question_vectors, question_usage = embed_texts(client, question_texts, shared["embedding_model"])
        add_usage(embedding_usage, email_usage)
        add_usage(embedding_usage, question_usage)
    else:
        email_vectors = [deterministic_mock_embedding(text) for text in email_texts]
        question_vectors = [deterministic_mock_embedding(text) for text in question_texts]
    document_embeddings = {
        row["document_id"]: vector for row, vector in zip(email_documents, email_vectors)
    }

    jobs: list[dict[str, Any]] = []
    for question_index, raw_question in enumerate(selected_questions):
        question = inference_question(raw_question)
        for condition in CONDITIONS:
            pair = (question["question_id"], condition)
            if pair in done:
                continue
            config = configs[condition]
            contexts, retrieval_scores = contexts_for_condition(
                condition=condition,
                question=question,
                email_documents=email_documents,
                oracle_documents=oracle_documents,
                question_embedding=question_vectors[question_index],
                document_embeddings=document_embeddings,
                config=config,
            )
            ensure_no_forbidden_fields(contexts, f"{condition}.contexts")
            system_prompt, user_prompt = build_prompt(question["question"], contexts)
            ensure_no_forbidden_fields(
                {"system_prompt": system_prompt, "user_prompt": user_prompt}, f"{condition}.prompt"
            )
            jobs.append({
                "run_id": run_id,
                "run_mode": mode,
                "question": question,
                "condition": condition,
                "config": config,
                "contexts": contexts,
                "retrieval_scores": retrieval_scores,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            })

    written = 0
    if args.real_api:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            generated = executor.map(lambda job: execute_generation_job(job, client, True), jobs)
            for result in generated:
                ensure_no_forbidden_fields(
                    result, f"result.{result['question_id']}.{result['condition']}"
                )
                append_jsonl(inference_path, result)
                written += 1
                if written % 25 == 0:
                    print(f"Wrote {written} new condition-question records", flush=True)
    else:
        for job in jobs:
            result = execute_generation_job(job, client, False)
            ensure_no_forbidden_fields(result, f"result.{result['question_id']}.{result['condition']}")
            append_jsonl(inference_path, result)
            written += 1

    rows = read_jsonl(inference_path)
    pairs = [(row["question_id"], row["condition"]) for row in rows]
    if len(pairs) != len(set(pairs)):
        raise ValueError("Duplicate condition-question result pair detected")
    expected_ids = {row["question_id"] for row in selected_questions}
    for condition in CONDITIONS:
        condition_ids = {row["question_id"] for row in rows if row["condition"] == condition}
        if condition_ids != expected_ids:
            raise ValueError(f"Question ID mismatch for {condition}")
    manifest["status"] = "complete"
    manifest["completed_timestamp_utc"] = utc_timestamp()
    manifest["condition_question_pairs"] = len(rows)
    manifest["embedding_usage"] = embedding_usage
    manifest["observed_generator_models"] = sorted(
        {row["actual_generator_model"] for row in rows}
    )
    api_errors = [
        row
        for row in rows
        if row.get("error") and (row.get("error") or {}).get("type") != "parser_error"
    ]
    expected_models = {config["generator_model"] for config in configs.values()}
    observed_models = set(manifest["observed_generator_models"])
    if args.real_api and (api_errors or observed_models != expected_models):
        manifest["status"] = "failed_api_validation"
        manifest["api_error_records"] = len(api_errors)
        write_json(manifest_path, manifest)
        raise RuntimeError(
            f"Run rejected: api_errors={len(api_errors)}, "
            f"expected_models={sorted(expected_models)}, observed_models={sorted(observed_models)}"
        )
    write_json(manifest_path, manifest)
    print(f"Completed {len(rows)} pairs in {mode}; results: {inference_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the three-condition ISCMI 2026 oracle task-state RAG experiment."
    )
    parser.add_argument(
        "--real-api",
        action="store_true",
        help="Run all loaded benchmark questions with the configured OpenAI model.",
    )
    parser.add_argument(
        "--benchmark-dir",
        help="Benchmark directory to load; defaults to the frozen 271-question benchmark.",
    )
    parser.add_argument(
        "--config-dir",
        help="Condition config directory; defaults to experiments/iscmi2026/experiment/configs.",
    )
    parser.add_argument(
        "--generator-model",
        help="Pinned generator snapshot to apply to all three condition configs.",
    )
    parser.add_argument(
        "--packet-dir",
        help="Corrected external MailEx packet (defaults to MAILEX_PILOT_PACKET or work/mailex_pilot_external_packet).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(EXPERIMENT_DIR / "results"),
        help="Directory for generated inference artifacts.",
    )
    parser.add_argument("--run-id", help="Optional stable run identifier.")
    parser.add_argument("--limit", type=int, help="Debug-only limit; do not use for the reported full run.")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=6,
        help="Maximum concurrent real-API generations (recorded in the run manifest).",
    )
    parser.add_argument("--resume", action="store_true", help="Resume a partially written result file.")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
