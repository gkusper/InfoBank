from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend_python"
for path in (str(REPO_ROOT), str(BACKEND_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

TEST_CHROMA_DIR = Path(tempfile.mkdtemp(prefix="infobank-r1b-chroma-"))
TEST_SOURCE_DIR = Path(tempfile.mkdtemp(prefix="infobank-a1-source-"))
atexit.register(shutil.rmtree, TEST_CHROMA_DIR, True)
atexit.register(shutil.rmtree, TEST_SOURCE_DIR, True)

# Prevent tests from reading or depending on real local environment values.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "r1b-isolated-test-secret"
os.environ["OPENAI_API_KEY"] = "r1b-placeholder-no-provider-calls"
os.environ["AI_PROVIDER"] = "deterministic-mock"
os.environ["AI_EMBEDDING_MODEL"] = "deterministic-test-v1"
os.environ.pop("AI_EMBEDDING_DIMENSIONS", None)
os.environ["CHROMA_PERSIST_DIR"] = str(TEST_CHROMA_DIR)
os.environ["SOURCE_STORAGE_DIR"] = str(TEST_SOURCE_DIR)

import models  # noqa: E402


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()
