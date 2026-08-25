"""Run isolated, deterministic FastAPI W1/W2/W3 reviewer workflows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.api_workflows import run_api_workflows  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database-url", default=os.getenv("INFOBANK_API_EVAL_DATABASE_URL"), required=os.getenv("INFOBANK_API_EVAL_DATABASE_URL") is None)
    parser.add_argument("--admin-database-url", default=os.getenv("INFOBANK_EVAL_ADMIN_DATABASE_URL"))
    parser.add_argument("--chroma-dir", type=Path, required=True)
    parser.add_argument("--source-storage-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_api_workflows(
        output_dir=args.output,
        database_url=args.database_url,
        admin_database_url=args.admin_database_url,
        chroma_dir=args.chroma_dir,
        source_storage_dir=args.source_storage_dir,
    )
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
