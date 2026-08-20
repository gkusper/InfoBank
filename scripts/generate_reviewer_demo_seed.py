#!/usr/bin/env python3
"""Generate an ignored reviewer screenshot seed from an actual API trace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for module_root in (REPOSITORY_ROOT, REPOSITORY_ROOT / "backend_python"):
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))

from evaluation.reviewer_demo_seed import write_reviewer_demo_seed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    seed = write_reviewer_demo_seed(args.trace, args.output)
    print(json.dumps({
        "status": "PASS",
        "demo_seed_version": seed["demo_seed_version"],
        "privacy_safe": seed["privacy_safe"],
        "source_trace_sha256": seed["source_trace_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
