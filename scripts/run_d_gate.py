"""Run the complete non-frozen D-GATE development evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend_python"
for location in (str(REPOSITORY_ROOT), str(BACKEND_ROOT)):
    if location not in sys.path:
        sys.path.insert(0, location)

from evaluation.d_gate import run_d_gate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/d_gate"))
    args = parser.parse_args()
    print(json.dumps(run_d_gate(args.output), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
