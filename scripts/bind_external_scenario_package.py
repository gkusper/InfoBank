"""Bind an external ScenarioPack package to actual-pipeline input artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.external_scenario_corpus import write_external_scenario_actual_inputs  # noqa: E402


def _source_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise ValueError("--source-filename-map must point to a JSON object of source_id keys and filename values")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario-id", action="append", dest="scenario_ids")
    parser.add_argument("--source-filename-map", type=Path)
    parser.add_argument("--package-sha256")
    args = parser.parse_args()
    result = write_external_scenario_actual_inputs(
        args.package_root,
        args.output,
        scenario_ids=tuple(args.scenario_ids) if args.scenario_ids else None,
        source_filename_map=_source_map(args.source_filename_map),
        package_sha256=args.package_sha256,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
