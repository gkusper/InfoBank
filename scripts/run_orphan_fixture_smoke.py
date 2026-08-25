#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.orphan_repair import ConsistencySnapshot, TASK_OWNED_SCOPE, repair_snapshot, scan_snapshot, source_record


def fixture() -> ConsistencySnapshot:
    source = source_record(b"fixture-source")
    return ConsistencySnapshot(
        documents={"fixture-archived": {"source_sha256": source["sha256"], "source_status": "ARCHIVED", "scope": TASK_OWNED_SCOPE}},
        sources={"fixture-archived": source, "fixture-source-orphan": {**source_record(b"orphan"), "scope": TASK_OWNED_SCOPE}},
        chunks={"fixture-chunk": {"document_id": "fixture-archived", "vector_id": "fixture-vector", "scope": TASK_OWNED_SCOPE}, "fixture-missing-vector": {"document_id": "fixture-archived", "vector_id": "fixture-recreated", "scope": TASK_OWNED_SCOPE}},
        vectors={"fixture-vector": {"document_id": "fixture-archived", "chunk_id": "fixture-chunk", "active": True, "scope": TASK_OWNED_SCOPE}},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = fixture()
    dry_snapshot, dry_log = repair_snapshot(before)
    applied, apply_log = repair_snapshot(before, apply=True)
    second, idempotent_log = repair_snapshot(applied, apply=True)
    result = {
        "status": "PASS" if dry_snapshot == before and applied == second and apply_log["applied_count"] == 3 and idempotent_log["applied_count"] == 0 else "FAIL",
        "production_data_touched": False,
        "before_scan": scan_snapshot(before),
        "dry_run": dry_log,
        "apply": apply_log,
        "after_scan": scan_snapshot(applied),
        "idempotence": idempotent_log,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "dry_run_applied": dry_log["applied_count"], "fixture_apply_count": apply_log["applied_count"], "idempotent_apply_count": idempotent_log["applied_count"]}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
