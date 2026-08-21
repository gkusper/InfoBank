from __future__ import annotations

import datetime

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import schemas
import security
from main import app


USER_ID = "00000000-0000-0000-0000-000000000401"


def test_access_token_has_required_bounded_claims(monkeypatch) -> None:
    monkeypatch.setenv("JWT_ACCESS_TOKEN_TTL_SECONDS", "900")
    token = security.create_access_token({"sub": USER_ID, "email": "user@example.invalid"})
    payload = jwt.decode(
        token,
        security.SECRET_KEY,
        algorithms=[security.ALGORITHM],
        issuer=security.TOKEN_ISSUER,
        audience=security.TOKEN_AUDIENCE,
    )
    assert payload["sub"] == USER_ID
    assert payload["exp"] - payload["iat"] == 900
    assert payload["nbf"] == payload["iat"]
    assert payload["jti"]
    assert security.get_current_user_id(token) == USER_ID


def test_expired_or_wrong_audience_token_is_rejected() -> None:
    now = datetime.datetime.now(datetime.UTC)
    base = {
        "sub": USER_ID,
        "iat": now - datetime.timedelta(hours=2),
        "nbf": now - datetime.timedelta(hours=2),
        "exp": now - datetime.timedelta(hours=1),
        "iss": security.TOKEN_ISSUER,
        "aud": security.TOKEN_AUDIENCE,
        "jti": "expired-token",
    }
    expired = jwt.encode(base, security.SECRET_KEY, algorithm=security.ALGORITHM)
    wrong_audience = jwt.encode(
        {**base, "exp": now + datetime.timedelta(hours=1), "aud": "other-client"},
        security.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    for token in (expired, wrong_audience):
        with pytest.raises(HTTPException) as exc:
            security.get_current_user_id(token)
        assert exc.value.status_code == 401


def test_registration_schema_rejects_weak_or_malformed_identity() -> None:
    with pytest.raises(ValidationError):
        schemas.UserRegister(email="not-an-email", username="x", password="short")
    valid = schemas.UserRegister(
        email="  USER@Example.Invalid ",
        username="valid-user_1",
        password="correct-horse-battery-staple",
    )
    assert valid.email == "user@example.invalid"


def test_cors_and_database_diagnostic_are_not_public_wildcards() -> None:
    cors = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")
    assert "*" not in cors.options["allow_origins"]
    route = next(route for route in app.routes if route.path == "/api/test-db")
    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
    assert security.get_current_user_id in dependency_calls
