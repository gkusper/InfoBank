"""Build the roadmap v1.8 S1-S6 ScenarioPack authoring manifests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.scenario_pack import write_scenario_pack_bundle  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Non-repository dataset root in which scenario_packs/ and validation_reports/ are written.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace a known generated manifest if its content differs. Source documents are never removed.",
    )
    args = parser.parse_args()
    result = write_scenario_pack_bundle(args.output, replace=args.replace)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
