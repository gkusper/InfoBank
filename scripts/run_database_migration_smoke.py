"""Exercise current migrations twice against an isolated representative R1 database."""

from __future__ import annotations

import argparse
import inspect as python_inspect
import json
import os
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend_python"
for path in (str(REPOSITORY_ROOT), str(BACKEND_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

LEGACY_SCHEMA = """
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL, password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, full_name VARCHAR(255), avatar_url VARCHAR(1024)
) ENGINE=InnoDB;
CREATE TABLE documents (
    id VARCHAR(255) PRIMARY KEY, file_path VARCHAR(512) NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, visibility VARCHAR(50) DEFAULT 'Private'
) ENGINE=InnoDB;
CREATE TABLE keywords (
    id INT AUTO_INCREMENT PRIMARY KEY, word VARCHAR(100) UNIQUE NOT NULL
) ENGINE=InnoDB;
CREATE TABLE document_keywords (
    document_id VARCHAR(255) NOT NULL, keyword_id INT NOT NULL,
    PRIMARY KEY (document_id, keyword_id),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE document_chunks (
    id VARCHAR(36) PRIMARY KEY, document_id VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL, text_content TEXT NOT NULL, vector_id VARCHAR(255) NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE user_document_permission (
    id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL, document_id VARCHAR(255) NOT NULL,
    permission_type ENUM('Owner','Reader','Aggregate') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    UNIQUE(user_id, document_id)
) ENGINE=InnoDB;
CREATE TABLE audit_logs (
    id VARCHAR(50) PRIMARY KEY, user_id VARCHAR(50), action VARCHAR(50),
    target_id VARCHAR(50), details TEXT, timestamp DATETIME
) ENGINE=InnoDB;
"""


def _execute_script(engine, script: str) -> None:
    for statement in (item.strip() for item in script.split(";") if item.strip()):
        with engine.begin() as connection:
            connection.execute(text(statement))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-database-url", default=os.getenv("INFOBANK_MIGRATION_SMOKE_ADMIN_DATABASE_URL"))
    parser.add_argument("--configured-env-file", type=Path, help="Load DATABASE_URL without printing credentials.")
    parser.add_argument("--database-name", default="infobank_migration_smoke_3385364")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.admin_database_url and args.configured_env_file:
        args.admin_database_url = dotenv_values(args.configured_env_file).get("DATABASE_URL")
    if not args.admin_database_url:
        raise SystemExit("--admin-database-url or INFOBANK_MIGRATION_SMOKE_ADMIN_DATABASE_URL is required")
    if not args.database_name.startswith("infobank_migration_smoke_"):
        raise SystemExit("Refusing non-isolated migration smoke database name")

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
        _execute_script(target_engine, LEGACY_SCHEMA)
        from passlib.context import CryptContext

        password_hash = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("runtime-smoke-password")
        with target_engine.begin() as connection:
            connection.execute(
                text("INSERT INTO users (id,email,username,password_hash) VALUES ('legacy-user','legacy-runtime@example.invalid','legacy-runtime',:hash)"),
                {"hash": password_hash},
            )
            connection.execute(text("INSERT INTO documents (id,file_path,visibility) VALUES ('legacy-doc','legacy-tv-manual.pdf','Private')"))
            connection.execute(text("INSERT INTO keywords (id,word) VALUES (1,'tvx-900'),(2,'warranty')"))
            connection.execute(text("INSERT INTO document_keywords (document_id,keyword_id) VALUES ('legacy-doc',1),('legacy-doc',2)"))
            connection.execute(text("INSERT INTO document_chunks (id,document_id,chunk_index,text_content,vector_id) VALUES ('legacy-chunk','legacy-doc',0,'TVX-900 warranty is twenty-four months.','legacy-vector')"))
            connection.execute(text("INSERT INTO user_document_permission (id,user_id,document_id,permission_type) VALUES ('legacy-perm','legacy-user','legacy-doc','Owner')"))
            connection.execute(text("INSERT INTO audit_logs (id,user_id,action,target_id,details) VALUES ('legacy-audit','legacy-user','LEGACY','legacy-doc','preserve')"))

        pre = check_database_schema(target_engine)
        first = apply_database_migrations(target_engine)
        second = apply_database_migrations(target_engine)
        post = check_database_schema(target_engine)
        if pre["status"] == SCHEMA_COMPATIBLE or post["status"] != SCHEMA_COMPATIBLE:
            raise RuntimeError("Legacy/current schema classification failed")
        if not first["existing_table_fingerprints_preserved"] or second["applied_now"]:
            raise RuntimeError("Migration preservation or idempotence failed")

        os.environ.update(
            {
                "DATABASE_URL": target_url.render_as_string(hide_password=False),
                "JWT_SECRET_KEY": "isolated-migration-smoke-secret",
                "AI_PROVIDER": "deterministic-mock",
                "CHROMA_PERSIST_DIR": str(Path(tempfile.mkdtemp(prefix="infobank-migration-smoke-chroma-"))),
                "SOURCE_STORAGE_DIR": str(Path(tempfile.mkdtemp(prefix="infobank-migration-smoke-source-"))),
                "AGGREGATE_K_THRESHOLD": "3",
            }
        )
        os.environ.pop("OPENAI_API_KEY", None)
        import httpx
        from fastapi.testclient import TestClient
        import main
        import models
        from sqlalchemy.orm import Session

        with Session(target_engine) as session:
            document = session.query(models.Document).filter(models.Document.id == "legacy-doc").one()
            chunk = session.query(models.DocumentChunk).filter(models.DocumentChunk.id == "legacy-chunk").one()
            orm = {
                "document_original_filename": document.original_filename,
                "document_source_status": document.source_status,
                "chunk_page_number": chunk.page_number,
                "chunk_config_hash": chunk.chunk_config_hash,
            }

        if "app" not in python_inspect.signature(httpx.Client.__init__).parameters:
            original_client_init = httpx.Client.__init__

            def compatible_client_init(self, *client_args, app=None, **client_kwargs):
                del app
                original_client_init(self, *client_args, **client_kwargs)

            httpx.Client.__init__ = compatible_client_init

        with TestClient(main.app) as client:
            login = client.post(
                "/api/login",
                json={"email": "legacy-runtime@example.invalid", "password": "runtime-smoke-password"},
            )
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            endpoint_results = {}
            for name, method, path, payload in (
                ("documents", "get", "/api/documents/me", None),
                ("ask", "post", "/api/ask", {"question": "What is the TVX-900 warranty term?"}),
                ("knowledge_map", "get", "/api/knowledge-map/me", None),
                ("semantic_graph", "get", "/api/semantic-cooccurrence-graph/me", None),
            ):
                request_kwargs = {"headers": headers}
                if payload is not None:
                    request_kwargs["data" if name == "ask" else "json"] = payload
                response = getattr(client, method)(path, **request_kwargs)
                endpoint_results[name] = {
                    "status": response.status_code,
                    "schema": sorted(response.json().keys()),
                    "raw_sql_present": any(
                        marker in response.text.lower()
                        for marker in ("select documents", "from documents", "pymysql", "sqlalchemy", "operationalerror")
                    ),
                }
            if any(item["status"] >= 500 or item["raw_sql_present"] for item in endpoint_results.values()):
                raise RuntimeError("Legacy-upgrade endpoint regression failed")

        output.update(
            {
                "status": "PASS",
                "pre_status": pre["status"],
                "post_status": post["status"],
                "first_applied": first["applied_now"],
                "rerun_applied": second["applied_now"],
                "preserved": first["existing_table_fingerprints_preserved"],
                "orm": orm,
                "endpoints": endpoint_results,
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
