#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.human_qa_tools import read_csv, validate_assignments, validate_citation_audit, validate_gold_qa, validate_no_health_signoff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignments", type=Path)
    parser.add_argument("--citation-audit", type=Path)
    parser.add_argument("--gold-qa", type=Path)
    parser.add_argument("--no-health-signoff", type=Path)
    args = parser.parse_args()
    result = {}
    if args.assignments:
        result["assignments"] = validate_assignments(read_csv(args.assignments))
    if args.citation_audit:
        result["citation_audit"] = validate_citation_audit(read_csv(args.citation_audit))
    if args.gold_qa:
        result["gold_qa"] = validate_gold_qa(read_csv(args.gold_qa))
    if args.no_health_signoff:
        result["no_health_signoff"] = validate_no_health_signoff(read_csv(args.no_health_signoff))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if any(value.get("status") == "FAIL" for value in result.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
