from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import pymysql

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from evaluation.actual_pipeline_runner import ActualPipelineConfig, run_actual_pipeline  # noqa: E402
from evaluation.actual_pipeline_scorer import score_sealed_run  # noqa: E402
from evaluation.provider_readiness import EMBEDDING_MODEL, GENERATION_MODEL  # noqa: E402
from scripts.run_actual_pipeline_evaluation import _prepare_mysql_database  # noqa: E402


SAFE_DIRECTORY = "C:/Users/EKKE/Documents/Codex/2026-08-24/files-pasted-by-the-user-you/work/InfoBank"
PREREG = BASE / "REAL_PROVIDER_PREREGISTRATION.json"
INPUTS = REPO / "artifacts" / "s1s2_freeze" / "S1_S2_JOURNAL_BENCHMARK_V2" / "actual_pipeline_inputs"
CONFIGS = [
    ("B0", "B0_VECTOR_ONLY"),
    ("B1", "B1_VECTOR_ROUTING"),
    ("B2", "B2_PERMISSION_FILTERED"),
    ("B3", "B3_FULL_ROLE_AWARE"),
]
DB_NAME_RE = re.compile(r"^infobank_eval_s1s2_openai_r[123]_b[0-3]_20260825$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={SAFE_DIRECTORY}", *args],
        cwd=REPO,
        stderr=subprocess.DEVNULL,
    ).decode().strip()


def read_compose_env(*names: str) -> str:
    text = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    for name in names:
        patterns = [
            rf"^\s*{name}:\s*([^\r\n#]+)",
            rf"^\s*-\s*{name}=([^\r\n#]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.M)
            if match:
                value = match.group(1).strip().strip('"').strip("'")
                if value:
                    return value
    return ""


def mysql_urls(database: str) -> tuple[str, str, dict[str, str]]:
    root_password = read_compose_env("MYSQL_ROOT_PASSWORD", "MARIADB_ROOT_PASSWORD")
    user = read_compose_env("MYSQL_USER", "MARIADB_USER")
    password = read_compose_env("MYSQL_PASSWORD", "MARIADB_PASSWORD")
    if not root_password or not user or not password:
        raise RuntimeError("MariaDB credentials are not fully available through docker-compose.yml")
    admin = f"mysql+pymysql://root:{quote_plus(root_password)}@127.0.0.1:3307/mysql"
    url = f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@127.0.0.1:3307/{database}"
    return url, admin, {"root_password": root_password, "user": user, "password": password}


def drop_eval_database(database: str, credentials: dict[str, str]) -> None:
    if not DB_NAME_RE.match(database):
        raise ValueError(f"Refusing to drop non-task database: {database}")
    connection = pymysql.connect(
        host="127.0.0.1",
        port=3307,
        user="root",
        password=credentials["root_password"],
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
    finally:
        connection.close()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sanitize_error(exc: BaseException) -> dict[str, str]:
    message = str(exc)
    for key in ("OPENAI_API_KEY",):
        secret = os.getenv(key)
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return {
        "type": type(exc).__name__,
        "message": message[:1000],
        "traceback": traceback.format_exc(limit=6)[:4000],
    }


def run_group(rep: int, label: str, mode: str, prereg_sha: str) -> dict:
    index = int(label[1])
    run_dir = BASE / f"R{rep}" / label
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite measured run group output: {run_dir}")

    database = f"infobank_eval_s1s2_openai_r{rep}_b{index}_20260825"
    database_url, admin_url, credentials = mysql_urls(database)
    config = ActualPipelineConfig(generation_model=GENERATION_MODEL, embedding_model=EMBEDDING_MODEL)
    run_id = f"s1s2-openai-r{rep}-{label.lower()}-20260825"
    manifest = {
        "schema_version": "infobank-s1s2-openai-run-config-v1",
        "preregistration_sha256": prereg_sha,
        "created_at": utc_now(),
        "branch": git("branch", "--show-current"),
        "head": git("rev-parse", "HEAD"),
        "repetition": rep,
        "config_label": label,
        "mode": mode,
        "run_id": run_id,
        "provider": "openai",
        "generation_model": GENERATION_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "provider_cache_enabled": False,
        "database_target": database,
        "raw_output_dir": str(run_dir / "raw"),
        "score_output_dir": str(run_dir / "scores"),
        "chroma_dir": str(run_dir / "runtime" / "chroma"),
        "source_storage_dir": str(run_dir / "runtime" / "source_storage"),
        "actual_pipeline_config": asdict(config) | {"config_hash": config.config_hash},
    }
    write_json(run_dir / "run_config_manifest.json", manifest)

    drop_eval_database(database, credentials)
    _prepare_mysql_database(database_url, admin_url)

    start = time.perf_counter()
    started_at = utc_now()
    seal = run_actual_pipeline(
        query_input_path=INPUTS / "query_inputs.jsonl",
        corpus_fixture_path=INPUTS / "corpus_fixture.json",
        output_dir=run_dir / "raw",
        database_url=database_url,
        chroma_dir=run_dir / "runtime" / "chroma",
        source_storage_dir=run_dir / "runtime" / "source_storage",
        run_id=run_id,
        modes=[mode],
        config=config,
        provider_name="openai",
        allow_network_provider=True,
        cache_dir=None,
        pricing_config_path=None,
    )
    scored = score_sealed_run(
        raw_run_path=run_dir / "raw" / "raw_records.jsonl",
        seal_path=run_dir / "raw" / "run_seal.json",
        gold_annotation_path=INPUTS / "gold_annotations.jsonl",
        output_dir=run_dir / "scores",
    )
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    summary = scored["modes"][mode]
    result_manifest = {
        "schema_version": "infobank-s1s2-openai-run-result-v1",
        "preregistration_sha256": prereg_sha,
        "started_at": started_at,
        "finished_at": utc_now(),
        "elapsed_ms": elapsed_ms,
        "repetition": rep,
        "config_label": label,
        "mode": mode,
        "run_id": run_id,
        "record_count": seal["record_count"],
        "raw_run_sha256": seal["raw_run_sha256"],
        "deterministic_content_sha256": seal["deterministic_content_sha256"],
        "timing_sidecar_sha256": seal["timing_sidecar_sha256"],
        "run_seal_sha256": sha256_file(run_dir / "raw" / "run_seal.json"),
        "score_summary_sha256": sha256_file(run_dir / "scores" / "summary.json"),
        "case_scores_sha256": sha256_file(run_dir / "scores" / "case_scores.jsonl"),
        "summary": summary,
    }
    write_json(run_dir / "run_result_manifest.json", result_manifest)
    print(
        json.dumps(
            {
                "status": "RUN_GROUP_COMPLETE",
                "rep": rep,
                "config": label,
                "mode": mode,
                "record_count": seal["record_count"],
                "output_class_accuracy": summary.get("output_class_accuracy"),
                "citation_support_precision": summary.get("citation_support_precision"),
                "safety_error_total": summary.get("safety_error_total"),
                "runtime_error_count": summary.get("runtime_error_count"),
                "elapsed_ms": elapsed_ms,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result_manifest


def main() -> int:
    if not PREREG.is_file():
        raise RuntimeError("Missing locked preregistration file")
    prereg_sha = sha256_file(PREREG)
    payload = json.loads(PREREG.read_text(encoding="utf-8"))
    if payload.get("preregistration_locked_before_measured_calls") is not True:
        raise RuntimeError("Preregistration is not marked locked")
    all_results = []
    try:
        for rep in (1, 2, 3):
            for label, mode in CONFIGS:
                print(json.dumps({"status": "RUN_GROUP_START", "rep": rep, "config": label, "mode": mode}, sort_keys=True), flush=True)
                all_results.append(run_group(rep, label, mode, prereg_sha))
                if sha256_file(PREREG) != prereg_sha:
                    raise RuntimeError("Preregistration file changed after measured execution started")
    except Exception as exc:
        interruption = {
            "schema_version": "infobank-s1s2-openai-interruption-v1",
            "status": "REAL_PROVIDER_EXPERIMENT_INTERRUPTED",
            "timestamp": utc_now(),
            "completed_run_groups": len(all_results),
            "preregistration_sha256": prereg_sha,
            "error": sanitize_error(exc),
        }
        write_json(BASE / "REAL_PROVIDER_INTERRUPTION.json", interruption)
        print(json.dumps({"status": "REAL_PROVIDER_EXPERIMENT_INTERRUPTED", "completed_run_groups": len(all_results), "error_type": type(exc).__name__}, sort_keys=True), flush=True)
        return 2
    write_json(
        BASE / "MEASURED_RUNS_COMPLETE.json",
        {
            "schema_version": "infobank-s1s2-openai-completion-v1",
            "status": "COMPLETE",
            "timestamp": utc_now(),
            "preregistration_sha256": prereg_sha,
            "completed_run_groups": len(all_results),
            "planned_run_groups": 12,
            "planned_records": 144,
            "completed_records": sum(item["record_count"] for item in all_results),
        },
    )
    print(json.dumps({"status": "ALL_RUN_GROUPS_COMPLETE", "completed_run_groups": len(all_results)}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
