"""Exercise current migrations twice against an isolated empty MariaDB database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend_python"
for path in (str(REPOSITORY_ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-database-url", default=os.getenv("INFOBANK_MIGRATION_SMOKE_ADMIN_DATABASE_URL"))
    parser.add_argument("--configured-env-file", type=Path, help="Load DATABASE_URL without printing credentials.")
    parser.add_argument("--database-name", default="infobank_migration_smoke_clean_3385364")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.admin_database_url and args.configured_env_file:
        args.admin_database_url = dotenv_values(args.configured_env_file).get("DATABASE_URL")
    if not args.admin_database_url:
        raise SystemExit("--admin-database-url or INFOBANK_MIGRATION_SMOKE_ADMIN_DATABASE_URL is required")
    if not args.database_name.startswith("infobank_migration_smoke_clean_"):
        raise SystemExit("Refusing non-isolated clean migration smoke database name")

    admin_url = make_url(args.admin_database_url).set(database=None)
    admin_engine = create_engine(admin_url, pool_pre_ping=True)
    database = args.database_name
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS `{database}`"))
        connection.execute(text(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))

    target_url = admin_url.set(database=database)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    os.environ["DATABASE_URL"] = target_url.render_as_string(hide_password=False)
    from database_schema import SCHEMA_COMPATIBLE, apply_database_migrations, check_database_schema

    output: dict[str, object] = {"database": database, "volume_deleted": False}
    try:
        pre = check_database_schema(target_engine)
        first = apply_database_migrations(target_engine)
        second = apply_database_migrations(target_engine)
        post = check_database_schema(target_engine)
        tables = sorted(inspect(target_engine).get_table_names())
        if pre["status"] == SCHEMA_COMPATIBLE or post["status"] != SCHEMA_COMPATIBLE:
            raise RuntimeError("Empty/current schema classification failed")
        if not first["existing_table_fingerprints_preserved"] or second["applied_now"]:
            raise RuntimeError("Clean migration preservation or idempotence failed")
        if "schema_migrations" not in tables:
            raise RuntimeError("Migration tracking table was not created")
        output.update(
            {
                "status": "PASS",
                "pre_status": pre["status"],
                "post_status": post["status"],
                "first_applied": first["applied_now"],
                "rerun_applied": second["applied_now"],
                "preserved": first["existing_table_fingerprints_preserved"],
                "tables": tables,
            }
        )
    finally:
        target_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS `{database}`"))
        admin_engine.dispose()
        output["isolated_database_removed"] = True

    rendered = json.dumps(output, sort_keys=True, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
