"""Build pending owned-object, citation, mail, and no-health human work sheets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.human_qa import build_human_qa_package  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--actual-gold", type=Path, required=True)
    parser.add_argument("--actual-raw-run", type=Path, action="append", required=True)
    parser.add_argument("--mailex-candidate", type=Path, required=True)
    args = parser.parse_args()
    result = build_human_qa_package(
        output_dir=args.output,
        actual_gold_path=args.actual_gold,
        actual_raw_run_paths=args.actual_raw_run,
        mailex_candidate_dir=args.mailex_candidate,
    )
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
