"""Explicit database-schema compatibility and migration support.

The application never upgrades a database during startup.  This module keeps
the detailed model/schema comparison on the developer side while exposing only
safe compatibility state to HTTP clients.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

import models


LOGGER = logging.getLogger("infobank.database_schema")

SCHEMA_COMPATIBLE = "COMPATIBLE"
SCHEMA_MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
SCHEMA_INCOMPLETE_MIGRATION = "INCOMPLETE_MIGRATION"
SCHEMA_UNSUPPORTED_NEWER = "UNSUPPORTED_NEWER_SCHEMA"
SCHEMA_UNAVAILABLE = "DATABASE_UNAVAILABLE"

PUBLIC_MIGRATION_MESSAGE = (
    "Database initialization is incomplete. Apply the documented InfoBank "
    "database migration and restart the backend."
)
PUBLIC_UNAVAILABLE_MESSAGE = "The database is temporarily unavailable. Try again after the backend database is restored."

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_FILES = (
    ("001_citds_11", REPOSITORY_ROOT / "backend_python" / "migrations" / "citds_11_mysql.sql"),
    (
        "002_infocom_a_gate_phase1",
        REPOSITORY_ROOT / "backend_python" / "migrations" / "infocom_a_gate_phase1_mysql.sql",
    ),
    (
        "003_permission_extensions_v1",
        REPOSITORY_ROOT / "backend_python" / "migrations" / "permission_extensions_v1_mysql.sql",
    ),
)


@dataclass(frozen=True)
class MigrationDefinition:
    version: str
    path: Path
    checksum: str


def migration_definitions() -> tuple[MigrationDefinition, ...]:
    return tuple(
        MigrationDefinition(version=version, path=path, checksum=hashlib.sha256(path.read_bytes()).hexdigest())
        for version, path in MIGRATION_FILES
    )


def redacted_database_target(database_url: str) -> str:
    parsed = make_url(database_url)
    host = parsed.host or "local"
    port = parsed.port or (3306 if parsed.get_backend_name() in {"mysql", "mariadb"} else None)
    authority = f"{host}:{port}" if port else host
    return f"{parsed.get_backend_name()}://{authority}/{parsed.database or '<unset>'}"


def current_model_contract() -> dict[str, set[str]]:
    return {
        table.name: {column.name for column in table.columns}
        for table in models.Base.metadata.sorted_tables
    }


def _migration_rows(connection, tables: set[str]) -> list[dict[str, Any]]:
    if "schema_migrations" not in tables:
        return []
    rows = connection.execute(
        text("SELECT version, checksum, description, applied_at FROM schema_migrations ORDER BY version")
    ).mappings()
    return [dict(row) for row in rows]


def check_database_schema(engine: Engine) -> dict[str, Any]:
    """Return a detailed developer-only compatibility report."""

    contract = current_model_contract()
    expected_migrations = {item.version: item for item in migration_definitions()}
    report: dict[str, Any] = {
        "schema_version": "infobank-database-compatibility-v1",
        "status": SCHEMA_UNAVAILABLE,
        "compatible": False,
        "dialect": engine.dialect.name,
        "missing_tables": [],
        "missing_columns": {},
        "migration_tracking": {
            "present": False,
            "state": "UNAVAILABLE",
            "applied": [],
            "unknown": [],
            "checksum_mismatches": [],
        },
    }
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            actual_tables = set(inspector.get_table_names())
            report["database_name"] = connection.execute(text("SELECT DATABASE()")).scalar_one() if engine.dialect.name in {"mysql", "mariadb"} else None
            report["server_version"] = str(connection.dialect.server_version_info or "")
            report["table_count"] = len(actual_tables)
            report["missing_tables"] = sorted(set(contract) - actual_tables)
            for table_name in sorted(set(contract) & actual_tables):
                actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
                missing = sorted(contract[table_name] - actual_columns)
                if missing:
                    report["missing_columns"][table_name] = missing

            tracking = report["migration_tracking"]
            tracking["present"] = "schema_migrations" in actual_tables
            rows = _migration_rows(connection, actual_tables)
            tracking["applied"] = [row["version"] for row in rows]
            for row in rows:
                expected = expected_migrations.get(row["version"])
                if expected is None:
                    tracking["unknown"].append(row["version"])
                elif row["checksum"] != expected.checksum:
                    tracking["checksum_mismatches"].append(row["version"])

            structural_missing = bool(report["missing_tables"] or report["missing_columns"])
            all_expected_marked = set(expected_migrations).issubset(set(tracking["applied"]))
            if tracking["unknown"]:
                report["status"] = SCHEMA_UNSUPPORTED_NEWER
                tracking["state"] = "UNKNOWN_VERSION_PRESENT"
            elif tracking["checksum_mismatches"] or (all_expected_marked and structural_missing):
                report["status"] = SCHEMA_INCOMPLETE_MIGRATION
                tracking["state"] = "INCOMPLETE_OR_CHECKSUM_MISMATCH"
            elif structural_missing:
                report["status"] = SCHEMA_MIGRATION_REQUIRED
                tracking["state"] = "MIGRATION_REQUIRED"
            else:
                report["status"] = SCHEMA_COMPATIBLE
                tracking["state"] = "TRACKED" if all_expected_marked else "STRUCTURALLY_COMPATIBLE_UNTRACKED"
                report["compatible"] = True
    except SQLAlchemyError:
        LOGGER.exception("Database schema compatibility check could not connect or inspect the database")
        report["status"] = SCHEMA_UNAVAILABLE
        report["migration_tracking"]["state"] = "UNAVAILABLE"
    return report


def safe_public_schema_report(report: dict[str, Any]) -> dict[str, Any]:
    status = str(report.get("status") or SCHEMA_UNAVAILABLE)
    compatible = status == SCHEMA_COMPATIBLE
    if compatible:
        message = "Database schema is compatible."
        code = "DATABASE_SCHEMA_COMPATIBLE"
    elif status == SCHEMA_UNAVAILABLE:
        message = PUBLIC_UNAVAILABLE_MESSAGE
        code = "DATABASE_UNAVAILABLE"
    else:
        message = PUBLIC_MIGRATION_MESSAGE
        code = "DATABASE_MIGRATION_REQUIRED"
    return {
        "status": "ok" if compatible else "error",
        "schema": {
            "compatible": compatible,
            "state": status,
            "code": code,
            "message": message,
        },
    }


def _split_mysql_script(path: Path) -> list[str]:
    lines = [
        line for line in path.read_text(encoding="utf-8-sig").splitlines()
        if not line.lstrip().startswith("--")
    ]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


def _ensure_tracking_table(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(100) NOT NULL PRIMARY KEY,
                    checksum CHAR(64) NOT NULL,
                    description VARCHAR(255) NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB
                """
            )
        )


def _table_fingerprints(engine: Engine, *, exclude_tables: set[str] | None = None) -> dict[str, dict[str, Any]]:
    excluded = exclude_tables or set()
    output: dict[str, dict[str, Any]] = {}
    with engine.connect() as connection:
        inspector = inspect(connection)
        for table_name in sorted(set(inspector.get_table_names()) - excluded):
            columns = [column["name"] for column in inspector.get_columns(table_name)]
            primary = inspector.get_pk_constraint(table_name).get("constrained_columns") or columns
            order = ", ".join(f"`{name}`" for name in primary)
            rows = connection.execute(text(f"SELECT * FROM `{table_name}` ORDER BY {order}")).mappings()
            digest = hashlib.sha256()
            count = 0
            for row in rows:
                digest.update(json.dumps(dict(row), sort_keys=True, default=str, ensure_ascii=False).encode("utf-8"))
                digest.update(b"\n")
                count += 1
            output[table_name] = {"columns": columns, "row_count": count, "sha256": digest.hexdigest()}
    return output


def _fingerprints_for_existing_columns(
    engine: Engine,
    before: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    with engine.connect() as connection:
        inspector = inspect(connection)
        actual_tables = set(inspector.get_table_names())
        for table_name, prior in sorted(before.items()):
            if table_name == "schema_migrations" or table_name not in actual_tables:
                continue
            columns = list(prior["columns"])
            primary = inspector.get_pk_constraint(table_name).get("constrained_columns") or columns
            projection = ", ".join(f"`{name}`" for name in columns)
            order = ", ".join(f"`{name}`" for name in primary if name in columns) or projection
            rows = connection.execute(
                text(f"SELECT {projection} FROM `{table_name}` ORDER BY {order}")
            ).mappings()
            digest = hashlib.sha256()
            count = 0
            for row in rows:
                digest.update(json.dumps(dict(row), sort_keys=True, default=str, ensure_ascii=False).encode("utf-8"))
                digest.update(b"\n")
                count += 1
            output[table_name] = {"columns": columns, "row_count": count, "sha256": digest.hexdigest()}
    return output


def apply_database_migrations(engine: Engine) -> dict[str, Any]:
    """Apply forward, rerunnable migrations and verify the current model contract."""

    if engine.dialect.name not in {"mysql", "mariadb"}:
        raise RuntimeError("The InfoBank migration runner supports MariaDB/MySQL targets only.")

    before = _table_fingerprints(engine)
    models.Base.metadata.create_all(bind=engine)
    _ensure_tracking_table(engine)
    applied_now: list[str] = []
    already_applied: list[str] = []

    for migration in migration_definitions():
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT checksum FROM schema_migrations WHERE version = :version"),
                {"version": migration.version},
            ).first()
        if row:
            if row[0] != migration.checksum:
                raise RuntimeError(f"Migration checksum mismatch for {migration.version}.")
            already_applied.append(migration.version)
            continue

        for statement in _split_mysql_script(migration.path):
            with engine.begin() as connection:
                connection.execute(text(statement))
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (version, checksum, description) "
                    "VALUES (:version, :checksum, :description)"
                ),
                {
                    "version": migration.version,
                    "checksum": migration.checksum,
                    "description": migration.path.name,
                },
            )
        applied_now.append(migration.version)

    report = check_database_schema(engine)
    if report["status"] != SCHEMA_COMPATIBLE:
        raise RuntimeError(f"Database remains incompatible after migration: {report['status']}")

    preservation_after = _fingerprints_for_existing_columns(engine, before)
    after = _table_fingerprints(engine, exclude_tables={"schema_migrations"})
    preserved = {
        table: before[table] == preservation_after.get(table)
        for table in before
        if table not in {"schema_migrations"} and table in preservation_after
    }
    changed_existing = sorted(table for table, unchanged in preserved.items() if not unchanged)
    return {
        "schema_version": "infobank-database-migration-result-v1",
        "status": "COMPATIBLE",
        "applied_now": applied_now,
        "already_applied": already_applied,
        "before": before,
        "after": after,
        "preservation_after": preservation_after,
        "existing_table_fingerprints_preserved": not changed_existing,
        "changed_existing_tables": changed_existing,
        "schema_report": report,
    }
