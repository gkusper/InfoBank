from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

import ai_service


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend_python"


def test_core_modules_import_without_openai_key(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment.update(
        {
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "JWT_SECRET_KEY": "r1b-subprocess-test-secret",
            "CHROMA_PERSIST_DIR": str(tmp_path / "chroma"),
        }
    )
    code = (
        "from unittest.mock import patch; "
        "guard=patch('dotenv.load_dotenv', return_value=False); guard.start(); "
        "import ai_service, evidence_service, routers.evidence; "
        "print('R1B_IMPORT_OK'); guard.stop()"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "R1B_IMPORT_OK" in completed.stdout


def test_openapi_schema_builds_with_unique_operation_models() -> None:
    from main import app

    schema = app.openapi()
    assert "/api/policy/documents/{doc_id}/permissions" in schema["paths"]
    assert "/api/documents/transfer" in schema["paths"]


def test_openai_client_fails_clearly_only_when_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(ai_service, "_openai_client", None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        ai_service.get_openai_client()


def test_environment_paths_are_deterministic() -> None:
    assert ai_service.ENV_PATH == Path(ai_service.__file__).resolve().parent / ".env"
    assert ai_service.CHROMA_PERSIST_DIR == os.environ["CHROMA_PERSIST_DIR"]


def test_no_gemini_import_or_dependency_remains() -> None:
    forbidden_modules = {"google.generativeai", "google.genai"}
    for path in BACKEND_DIR.rglob("*.py"):
        if "tests" in path.parts or any(part.startswith(".venv") or part == "venv" for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name in forbidden_modules for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden_modules
                assert not (node.module == "google" and any(alias.name == "genai" for alias in node.names))
    requirements = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8-sig").lower()
    assert "google-generativeai" not in requirements


def test_chunk_text_defaults_preserve_order_overlap_and_content() -> None:
    text = "".join(str(index % 10) for index in range(1800))
    chunks = ai_service.chunk_text(text)
    assert [len(chunk) for chunk in chunks] == [1000, 1000, 200]
    assert chunks[0][-200:] == chunks[1][:200]
    assert chunks[1][-200:] == chunks[2]
    reconstructed = chunks[0] + "".join(chunk[200:] for chunk in chunks[1:])
    assert reconstructed == text


def test_chunk_text_short_and_empty_inputs_are_explicit() -> None:
    assert ai_service.chunk_text("short") == ["short"]
    assert ai_service.chunk_text("") == []


@pytest.mark.parametrize(
    ("chunk_size", "overlap", "message"),
    [
        (0, 0, "chunk_size"),
        (-1, 0, "chunk_size"),
        (100, -1, "overlap"),
        (100, 100, "smaller"),
        (100, 101, "smaller"),
    ],
)
def test_chunk_text_rejects_non_progressing_configuration(chunk_size: int, overlap: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ai_service.chunk_text("content", chunk_size=chunk_size, overlap=overlap)
