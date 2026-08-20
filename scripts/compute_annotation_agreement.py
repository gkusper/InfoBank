#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.human_qa_tools import agreement, export_adjudication, read_csv, write_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute descriptive agreement only when paired human labels are complete.")
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--adjudication-output", type=Path)
    args = parser.parse_args()
    rows = read_csv(args.assignments)
    result = agreement(rows)
    disagreements = export_adjudication(rows)
    if args.adjudication_output and disagreements:
        write_csv(args.adjudication_output, disagreements)
    result["unresolved_disagreement_count"] = len(disagreements)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "COMPUTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
