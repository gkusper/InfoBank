"""Export one complete ScenarioPack into separated runtime and scorer files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.scenario_pack import write_scenario_pack_projection  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-version", default="scenario-pack-development-v1")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace only known projection files when their deterministic content differs.",
    )
    args = parser.parse_args()
    pack = json.loads(args.scenario_pack.read_text(encoding="utf-8"))
    result = write_scenario_pack_projection(
        pack,
        args.output,
        dataset_version=args.dataset_version,
        replace=args.replace,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
