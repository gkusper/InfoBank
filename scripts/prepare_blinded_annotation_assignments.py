#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.human_qa_tools import anonymized_annotator_id, prepare_assignments, read_csv, write_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare deterministic blinded assignments; no human field is populated.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--id-field", required=True)
    parser.add_argument("--primary", action="append", required=True)
    parser.add_argument("--secondary", action="append", required=True)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = read_csv(args.input)
    primary = [anonymized_annotator_id(value, salt=args.salt) for value in args.primary]
    secondary = [anonymized_annotator_id(value, salt=args.salt) for value in args.secondary]
    rows = prepare_assignments([row[args.id_field] for row in source], primary_annotators=primary, secondary_annotators=secondary, seed=args.seed)
    write_csv(args.output, rows)
    print(f"PENDING_HUMAN_REVIEW assignments={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
