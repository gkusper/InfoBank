"""Explicitly apply all current InfoBank MariaDB migrations after backup."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend_python"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env", override=False)

from database_schema import apply_database_migrations, redacted_database_target  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-database", required=True, help="Exact database name allowed for mutation.")
    parser.add_argument("--yes", action="store_true", help="Required explicit confirmation for forward migration.")
    parser.add_argument("--output", type=Path, help="Optional JSON result path (keep runtime outputs ignored).")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("Refusing migration without --yes.")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not configured.")
    parsed = make_url(database_url)
    if parsed.database != args.expected_database:
        raise SystemExit(
            f"Refusing migration: configured database does not match --expected-database {args.expected_database!r}."
        )
    target = redacted_database_target(database_url)
    print(f"MIGRATION_TARGET={target}")
    engine = create_engine(database_url, pool_pre_ping=True)
    result = apply_database_migrations(engine)
    engine.dispose()
    payload = {"target": target, **result}
    rendered = json.dumps(payload, sort_keys=True, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
