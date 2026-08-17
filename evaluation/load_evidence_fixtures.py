from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from .backend import BACKEND_DIR, REPO_ROOT, ensure_backend_path


SCORER_ONLY_FIELDS = {
    "expected_status",
    "expected_presence",
    "gold_role",
    "primary_evidence_ids",
    "contextual_evidence_ids",
    "contrastive_evidence_ids",
    "closure_type",
    "action_description",
}
PURPOSE = "action_reconstruction"


@dataclass
class EvidenceBenchmark:
    cases: list[dict[str, Any]]
    gold: list[dict[str, Any]]
    source_manifest: dict[str, Any]
    root: Path

    @property
    def gold_by_case(self) -> dict[str, dict[str, Any]]:
        return {row["case_id"]: row for row in self.gold}


@dataclass
class LoadedEvidenceCase:
    case_id: str
    user_id: str
    benchmark_user: str
    inserted_evidence_ids: list[str]
    excluded_future_evidence_ids: list[str]
    policy_rule_ids: list[str]
    benchmark_to_database_evidence_ids: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "user_id": self.user_id,
            "benchmark_user": self.benchmark_user,
            "inserted_evidence_ids": self.inserted_evidence_ids,
            "excluded_future_evidence_ids": self.excluded_future_evidence_ids,
            "policy_rule_ids": self.policy_rule_ids,
            "benchmark_to_database_evidence_ids": self.benchmark_to_database_evidence_ids,
        }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_benchmark(root: str | Path) -> EvidenceBenchmark:
    root = Path(root)
    cases = read_jsonl(root / "cases.jsonl")
    gold = read_jsonl(root / "gold.jsonl")
    source_manifest = json.loads((root / "source_manifest.json").read_text(encoding="utf-8"))
    validate_runtime_cases(cases)
    return EvidenceBenchmark(cases=cases, gold=gold, source_manifest=source_manifest, root=root)


def validate_runtime_cases(cases: list[dict[str, Any]]) -> None:
    case_ids = set()
    for case in cases:
        case_id = case.get("case_id")
        if not case_id or case_id in case_ids:
            raise ValueError(f"Invalid or duplicate case_id: {case_id!r}")
        case_ids.add(case_id)
        leaked = SCORER_ONLY_FIELDS & set(case)
        if leaked:
            raise ValueError(f"Runtime case {case_id} contains scorer-only fields: {sorted(leaked)}")
        for unit in case.get("evidence_units") or []:
            unit_leaked = SCORER_ONLY_FIELDS & set(unit)
            if unit_leaked:
                raise ValueError(f"Runtime unit in {case_id} contains scorer-only fields: {sorted(unit_leaked)}")
            if not unit.get("evidence_id"):
                raise ValueError(f"Runtime unit in {case_id} is missing evidence_id")
            if not unit.get("timestamp"):
                raise ValueError(f"Runtime unit {unit.get('evidence_id')} is missing timestamp")
            parse_timestamp(unit["timestamp"])


def parse_timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def configure_database_from_env_file(env_file: str | Path) -> tuple[Engine, sessionmaker[Session], dict[str, Any]]:
    env_file = Path(env_file)
    values = read_env_file(env_file)
    database_url = values.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured for EvidenceUnit evaluation loading.")
    url = make_url(database_url)
    if url.database != "infobank_eval":
        raise RuntimeError(f"EvidenceUnit evaluation must use infobank_eval, not {url.database!r}.")
    os.environ["DATABASE_URL"] = database_url
    ensure_backend_path()
    import models

    engine = create_engine(database_url)
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal, {
        "database_host": url.host,
        "database_port": url.port,
        "database_name": url.database,
        "drivername": url.drivername,
    }


def deterministic_user_id(case_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"infobank:d1-d8-evidence:{case_id}"))


def cleanup_case(db: Session, user_id: str) -> None:
    ensure_backend_path()
    import models

    unit_ids = [row[0] for row in db.query(models.EvidenceUnit.id).filter(models.EvidenceUnit.user_id == user_id).all()]
    if unit_ids:
        db.query(models.PolicyRule).filter(
            models.PolicyRule.owner_user_id == user_id,
            models.PolicyRule.target_type == "EvidenceUnit",
            models.PolicyRule.target_id.in_(unit_ids),
        ).delete(synchronize_session=False)
        db.query(models.EvidenceUnit).filter(models.EvidenceUnit.user_id == user_id).delete(synchronize_session=False)
    db.query(models.PolicyRule).filter(models.PolicyRule.owner_user_id == user_id).delete(synchronize_session=False)
    db.query(models.User).filter(models.User.id == user_id).delete(synchronize_session=False)
    db.commit()


def load_case(db: Session, case: dict[str, Any], *, cleanup_first: bool = True) -> LoadedEvidenceCase:
    ensure_backend_path()
    import models
    import policy_engine

    case_id = case["case_id"]
    user_id = deterministic_user_id(case_id)
    if cleanup_first:
        cleanup_case(db, user_id)

    user = models.User(
        id=user_id,
        email=f"{case_id.lower()}@benchmark.example.test",
        username=f"d1d8_{case_id.lower()}",
        password_hash="evaluation-only-not-a-real-login",
        full_name=f"D1-D8 evaluation user {case_id}",
    )
    db.add(user)
    db.flush()

    query_time = parse_timestamp(case.get("query_time"))
    inserted: list[str] = []
    excluded_future: list[str] = []
    mapping: dict[str, str] = {}
    policy_rule_ids: list[str] = []
    for unit in case.get("evidence_units") or []:
        benchmark_id = unit["evidence_id"]
        source_time = parse_timestamp(unit.get("timestamp"))
        if query_time and source_time and source_time > query_time:
            excluded_future.append(benchmark_id)
            continue
        metadata = {
            key: value
            for key, value in dict(unit.get("provenance") or {}).items()
            if key not in SCORER_ONLY_FIELDS
        }
        metadata.update(
            {
                "benchmark_case_id": case_id,
                "benchmark_evidence_id": benchmark_id,
                "benchmark_user": case.get("benchmark_user"),
                "sender": unit.get("sender"),
                "recipients": unit.get("recipients") or [],
                "owner": unit.get("owner"),
                "access_mode": unit.get("access_mode"),
            }
        )
        row = models.EvidenceUnit(
            id=benchmark_id,
            user_id=user_id,
            source_type=models.EvidenceSourceType(unit.get("source_type", "Other")),
            title=unit.get("title") or "Untitled evidence unit",
            content=unit.get("content") or "",
            source_timestamp=source_time,
            thread_id=unit.get("thread_id"),
            relation_key=unit.get("relation_key"),
            metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        )
        db.add(row)
        inserted.append(benchmark_id)
        mapping[benchmark_id] = benchmark_id
    db.flush()

    for evidence_id in inserted:
        source_unit = next(unit for unit in case["evidence_units"] if unit["evidence_id"] == evidence_id)
        access_mode = str(source_unit.get("access_mode") or "full").strip().lower()
        mode = {
            "full": "Full",
            "aggregate": "Aggregate",
            "metadata": "Metadata",
            "deny": "Deny",
        }.get(access_mode)
        if not mode:
            raise ValueError(f"Unknown access_mode for {evidence_id}: {source_unit.get('access_mode')!r}")
        rule = policy_engine.create_policy_rule(
            db=db,
            owner_user_id=user_id,
            target_type="EvidenceUnit",
            target_id=evidence_id,
            purpose=PURPOSE,
            access_mode=mode,
        )
        policy_rule_ids.append(rule.id)

    db.commit()
    return LoadedEvidenceCase(
        case_id=case_id,
        user_id=user_id,
        benchmark_user=case.get("benchmark_user") or "benchmark_user",
        inserted_evidence_ids=inserted,
        excluded_future_evidence_ids=excluded_future,
        policy_rule_ids=policy_rule_ids,
        benchmark_to_database_evidence_ids=mapping,
    )


def load_all_cases(db: Session, benchmark: EvidenceBenchmark) -> list[LoadedEvidenceCase]:
    return [load_case(db, case) for case in benchmark.cases]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load EvidenceUnit benchmark cases into infobank_eval.")
    parser.add_argument("--benchmark", default=str(REPO_ROOT / "data" / "benchmarks" / "evidence_unit_v1"))
    parser.add_argument("--env-file", default=str(BACKEND_DIR / ".env.eval"))
    parser.add_argument("--case-id")
    parser.add_argument("--manifest-out")
    args = parser.parse_args(argv)

    benchmark = load_benchmark(args.benchmark)
    _, SessionLocal, database = configure_database_from_env_file(args.env_file)
    selected = [case for case in benchmark.cases if not args.case_id or case["case_id"] == args.case_id]
    if args.case_id and not selected:
        raise SystemExit(f"Unknown case_id: {args.case_id}")
    with SessionLocal() as db:
        loaded = [load_case(db, case) for case in selected]
    manifest = {
        "benchmark": str(Path(args.benchmark).resolve()),
        "database": database,
        "loaded_cases": [item.to_dict() for item in loaded],
        "case_isolation_strategy": "deterministic evaluation user per case",
    }
    if args.manifest_out:
        write_json(Path(args.manifest_out), manifest)
    print(f"EVIDENCE LOAD: PASS cases={len(loaded)} evidence_units={sum(len(item.inserted_evidence_ids) for item in loaded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
