"""Central safe HTTP handling for database and unexpected server errors."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


LOGGER = logging.getLogger("infobank.database_errors")
DATABASE_ERROR_MARKERS = re.compile(
    r"(select\s+.+from|from\s+documents|pymysql|sqlalchemy|operationalerror|programmingerror|"
    r"unknown column|table .+ doesn't exist|\(10(?:45|49|54),|database credentials|[a-z]:\\)",
    re.IGNORECASE | re.DOTALL,
)


def public_error(code: str, message: str, *, status_code: int, error_id: str | None = None) -> JSONResponse:
    identifier = error_id or str(uuid.uuid4())
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error": {
                "code": code,
                "message": message,
                "error_id": identifier,
            },
        },
    )


def _looks_like_database_detail(detail: Any) -> bool:
    return bool(DATABASE_ERROR_MARKERS.search(str(detail)))


def install_database_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(_request, exc: SQLAlchemyError):
        error_id = str(uuid.uuid4())
        LOGGER.error(
            "Database operation failed; error_id=%s",
            error_id,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        unavailable = isinstance(exc, OperationalError) and bool(getattr(exc, "connection_invalidated", False))
        code = "DATABASE_UNAVAILABLE" if unavailable else "DATABASE_OPERATION_FAILED"
        message = (
            "The database is temporarily unavailable. Try again after the backend database is restored."
            if unavailable
            else "The database operation could not be completed. Use the error ID to inspect the server log."
        )
        return public_error(code, message, status_code=503 if unavailable else 500, error_id=error_id)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request, exc: StarletteHTTPException):
        if exc.status_code < 500:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
        error_id = str(uuid.uuid4())
        LOGGER.error(
            "Server HTTP exception; error_id=%s; detail=%r",
            error_id,
            exc.detail,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        if _looks_like_database_detail(exc.detail):
            return public_error(
                "DATABASE_OPERATION_FAILED",
                "The database operation could not be completed. Use the error ID to inspect the server log.",
                status_code=500,
                error_id=error_id,
            )
        return public_error(
            "INTERNAL_SERVER_ERROR",
            "The request could not be completed. Use the error ID to inspect the server log.",
            status_code=500,
            error_id=error_id,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request, exc: Exception):
        error_id = str(uuid.uuid4())
        LOGGER.error(
            "Unhandled server exception; error_id=%s",
            error_id,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        if isinstance(exc, (DBAPIError, SQLAlchemyError)):
            return public_error(
                "DATABASE_OPERATION_FAILED",
                "The database operation could not be completed. Use the error ID to inspect the server log.",
                status_code=500,
                error_id=error_id,
            )
        return public_error(
            "INTERNAL_SERVER_ERROR",
            "The request could not be completed. Use the error ID to inspect the server log.",
            status_code=500,
            error_id=error_id,
        )
