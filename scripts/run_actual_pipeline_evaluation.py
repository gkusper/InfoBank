"""Build, run twice, seal, and post-score the actual development B0-B3 evaluation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.actual_pipeline_dataset import build_development_dataset  # noqa: E402
from evaluation.actual_pipeline_runner import (  # noqa: E402
    ActualPipelineConfig,
    run_actual_pipeline,
)
from evaluation.actual_pipeline_scorer import score_sealed_run  # noqa: E402


def _prepare_mysql_database(database_url: str, admin_database_url: str | None = None) -> None:
    from sqlalchemy.engine import make_url

    parsed = make_url(database_url)
    if not parsed.drivername.startswith("mysql"):
        return
    database = parsed.database or ""
    if not database.startswith("infobank_eval_"):
        raise ValueError("MySQL evaluation database name must start with infobank_eval_")
    import pymysql

    admin = make_url(admin_database_url) if admin_database_url else parsed
    if admin_database_url:
        connection = pymysql.connect(
            host=admin.host or parsed.host or "127.0.0.1",
            port=admin.port or parsed.port or 3306,
            user=admin.username or "",
            password=admin.password or "",
            autocommit=True,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                if admin.username != parsed.username and parsed.username:
                    cursor.execute(f"GRANT ALL PRIVILEGES ON `{database}`.* TO %s@'%%'", (parsed.username,))
        finally:
            connection.close()
    schema_text = (REPOSITORY_ROOT / "infobank_db.sql").read_text(encoding="utf-8")
    statements = [item.strip() for item in schema_text.split(";") if item.strip()]
    schema_connection = pymysql.connect(
        host=admin.host or parsed.host or "127.0.0.1",
        port=admin.port or parsed.port or 3306,
        user=admin.username or "",
        password=admin.password or "",
        database=database,
        autocommit=True,
    )
    try:
        with schema_connection.cursor() as cursor:
            for statement in statements:
                if statement.upper().startswith("CREATE DATABASE") or statement.upper().startswith("USE "):
                    continue
                cursor.execute(statement)
    finally:
        schema_connection.close()


def _run_one(
    *,
    root: Path,
    label: str,
    database_url: str,
    dataset_dir: Path,
    config: ActualPipelineConfig,
    modes: list[str],
) -> dict:
    run_dir = root / label
    seal = run_actual_pipeline(
        query_input_path=dataset_dir / "query_inputs.jsonl",
        corpus_fixture_path=dataset_dir / "corpus_fixture.json",
        output_dir=run_dir / "raw",
        database_url=database_url,
        chroma_dir=run_dir / "runtime" / "chroma",
        source_storage_dir=run_dir / "runtime" / "source_storage",
        run_id=label,
        modes=modes,
        config=config,
    )
    score = score_sealed_run(
        raw_run_path=run_dir / "raw" / "raw_records.jsonl",
        seal_path=run_dir / "raw" / "run_seal.json",
        gold_annotation_path=dataset_dir / "gold_annotations.jsonl",
        output_dir=run_dir / "scores",
    )
    return {"seal": seal, "score": score}


def execute(output: Path, database_url: str, admin_database_url: str | None = None) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to mix evaluation output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    _prepare_mysql_database(database_url, admin_database_url)
    dataset_dir = output / "dataset"
    dataset = build_development_dataset(dataset_dir)

    calibration_configs = [
        ActualPipelineConfig(top_k=4, minimum_support_score=0.35),
        ActualPipelineConfig(top_k=6, minimum_support_score=0.45),
    ]
    calibration_rows = []
    for index, config in enumerate(calibration_configs, start=1):
        result = _run_one(
            root=output / "calibration",
            label=f"config-{index:02d}",
            database_url=database_url,
            dataset_dir=dataset_dir,
            config=config,
            modes=["B3_FULL_ROLE_AWARE"],
        )
        metrics = result["score"]["modes"]["B3_FULL_ROLE_AWARE"]
        calibration_rows.append(
            {
                "label": f"config-{index:02d}",
                "config": asdict(config),
                "config_hash": config.config_hash,
                "metrics": metrics,
                "raw_run_sha256": result["seal"]["raw_run_sha256"],
            }
        )
    eligible = [row for row in calibration_rows if row["metrics"]["safety_error_total"] == 0]
    if not eligible:
        raise RuntimeError("No calibration configuration satisfied hard safety")
    selected = max(
        eligible,
        key=lambda row: (
            row["metrics"]["permitted_answer_accuracy"] or 0.0,
            row["metrics"]["output_class_accuracy"],
            -row["config"]["top_k"],
        ),
    )
    selected_config = ActualPipelineConfig(**selected["config"])
    calibration = {
        "status": "DEVELOPMENT_ONLY_NOT_FROZEN",
        "selection_rule": "zero safety errors, then permitted-answer accuracy, output-class accuracy, then lower top-k",
        "candidate_holdout_accessed": False,
        "all_configurations": calibration_rows,
        "selected_config_hash": selected_config.config_hash,
    }
    (output / "calibration_results.json").write_text(json.dumps(calibration, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    repeated = []
    for index in (1, 2):
        repeated.append(
            _run_one(
                root=output,
                label=f"development-run-{index:02d}",
                database_url=database_url,
                dataset_dir=dataset_dir,
                config=selected_config,
                modes=["B0_VECTOR_ONLY", "B1_VECTOR_ROUTING", "B2_PERMISSION_FILTERED", "B3_FULL_ROLE_AWARE"],
            )
        )
    deterministic_match = (
        repeated[0]["seal"]["deterministic_content_sha256"]
        == repeated[1]["seal"]["deterministic_content_sha256"]
    )
    reproducibility = {
        "status": "PASS" if deterministic_match else "FAIL",
        "deterministic_content_hash_match": deterministic_match,
        "run_1_deterministic_content_sha256": repeated[0]["seal"]["deterministic_content_sha256"],
        "run_2_deterministic_content_sha256": repeated[1]["seal"]["deterministic_content_sha256"],
        "run_1_raw_sha256": repeated[0]["seal"]["raw_run_sha256"],
        "run_2_raw_sha256": repeated[1]["seal"]["raw_run_sha256"],
        "wall_clock_timings_separate": True,
        "candidate_holdout_accessed": False,
    }
    (output / "reproducibility.json").write_text(json.dumps(reproducibility, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if not deterministic_match:
        raise RuntimeError("Deterministic actual-pipeline content hashes differ")
    return {
        "status": "ACTUAL_PIPELINE_DEVELOPMENT_EVALUATION",
        "dataset": dataset,
        "calibration": calibration,
        "reproducibility": reproducibility,
        "selected_summary": repeated[0]["score"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--database-url",
        default=os.getenv("INFOBANK_EVAL_DATABASE_URL"),
        required=os.getenv("INFOBANK_EVAL_DATABASE_URL") is None,
        help="Isolated evaluation database URL; may also be set with INFOBANK_EVAL_DATABASE_URL.",
    )
    parser.add_argument(
        "--admin-database-url",
        default=os.getenv("INFOBANK_EVAL_ADMIN_DATABASE_URL"),
        help="Local database bootstrap URL; never written to evaluation artifacts.",
    )
    args = parser.parse_args()
    result = execute(args.output, args.database_url, args.admin_database_url)
    public = {
        "status": result["status"],
        "query_count": result["dataset"]["query_count"],
        "document_count": result["dataset"]["document_count"],
        "selected_config_hash": result["calibration"]["selected_config_hash"],
        "reproducibility": result["reproducibility"]["status"],
        "b3": result["selected_summary"]["modes"]["B3_FULL_ROLE_AWARE"],
    }
    print(json.dumps(public, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
