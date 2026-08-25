"""Build and verify the non-frozen reviewer-v2 pre-freeze candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.reviewer_v2_candidate import build_candidate, validate_candidate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/pre_freeze/reviewer_v2_candidate"))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    result = validate_candidate(args.output) if args.validate_only else build_candidate(args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
