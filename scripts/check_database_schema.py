"""Check the configured InfoBank database against the current model contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend_python"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env", override=False)

from database_schema import SCHEMA_COMPATIBLE, check_database_schema, redacted_database_target  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the detailed developer report as JSON.")
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not configured.")
    engine = create_engine(database_url, pool_pre_ping=True)
    report = check_database_schema(engine)
    engine.dispose()
    output = {"target": redacted_database_target(database_url), **report}
    if args.json:
        print(json.dumps(output, sort_keys=True, indent=2, default=str))
    else:
        print(f"TARGET={output['target']}")
        print(f"SCHEMA_STATUS={report['status']}")
        if report["missing_tables"]:
            print("MISSING_TABLES=" + ",".join(report["missing_tables"]))
        for table, columns in report["missing_columns"].items():
            print(f"MISSING_COLUMNS[{table}]=" + ",".join(columns))
        print("MIGRATION_TRACKING=" + report["migration_tracking"]["state"])
    raise SystemExit(0 if report["status"] == SCHEMA_COMPATIBLE else 2)


if __name__ == "__main__":
    main()
