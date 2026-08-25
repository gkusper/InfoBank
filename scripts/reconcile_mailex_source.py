from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evaluation.mailex_reconciliation import build_mailex_reconciliation


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile every thread-relevant record in the local MailEx ZIP.")
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path)
    args = parser.parse_args()
    result = build_mailex_reconciliation(args.source_zip, args.output, args.candidate_dir)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
