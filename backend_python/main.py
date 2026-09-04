import logging
import os
import uuid

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import models
import ai_service
from database import engine, get_db
from database_errors import install_database_exception_handlers
from database_schema import (
    PUBLIC_MIGRATION_MESSAGE,
    PUBLIC_UNAVAILABLE_MESSAGE,
    SCHEMA_COMPATIBLE,
    SCHEMA_UNAVAILABLE,
    check_database_schema,
    safe_public_schema_report,
)

# IMPORTÁLÁS A ROUTERS MAPPÁBÓL:
from routers import auth, profile, analytics, documents, chat, admin, evidence, policy, citds_eval, classifier, connectors
import security

load_dotenv()

app = FastAPI(title="InfoBank API", version="3.4.0")
app.state.database_schema = {
    "status": "NOT_CHECKED",
    "compatible": False,
    "migration_tracking": {"state": "NOT_CHECKED"},
}
install_database_exception_handlers(app)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://127.0.0.1:8765,http://localhost:8765",
    ).split(",")
    if origin.strip()
]
if "*" in allowed_origins:
    raise RuntimeError("CORS_ALLOWED_ORIGINS cannot contain '*' when credentials are enabled.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def verify_database_schema_on_startup() -> None:
    provider_config = ai_service.effective_provider_configuration()
    logging.getLogger("infobank.startup").info(
        "InfoBank AI configuration: LLM provider=%s; LLM model=%s; Embedding provider=%s; Embedding model=%s",
        provider_config["llm_provider"],
        provider_config["llm_model"],
        provider_config["embedding_provider"],
        provider_config["embedding_model"],
    )
    report = check_database_schema(engine)
    app.state.database_schema = report
    if report["status"] != SCHEMA_COMPATIBLE:
        logging.getLogger("infobank.startup").error(
            "InfoBank database schema is not ready: %s",
            report,
        )


@app.middleware("http")
async def require_compatible_database(request: Request, call_next):
    safe_paths = {"/docs", "/openapi.json", "/redoc", "/api/health/schema"}
    if request.url.path in safe_paths or not request.url.path.startswith("/api/"):
        return await call_next(request)
    report = app.state.database_schema
    if report.get("status") == SCHEMA_COMPATIBLE:
        return await call_next(request)
    error_id = str(uuid.uuid4())
    unavailable = report.get("status") == SCHEMA_UNAVAILABLE
    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "error": {
                "code": "DATABASE_UNAVAILABLE" if unavailable else "DATABASE_MIGRATION_REQUIRED",
                "message": PUBLIC_UNAVAILABLE_MESSAGE if unavailable else PUBLIC_MIGRATION_MESSAGE,
                "error_id": error_id,
            },
        },
    )

# ROUTEREK BEKÖTÉSE
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(analytics.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(evidence.router)
app.include_router(policy.router)
app.include_router(citds_eval.router)
app.include_router(classifier.router)
app.include_router(connectors.router)


@app.get("/api/health/schema", tags=["Diagnostics"])
def database_schema_health():
    return safe_public_schema_report(app.state.database_schema)

@app.get("/api/test-db")
def test_db_connection(
    _user_id: str = Depends(security.get_current_user_id),
    db: Session = Depends(get_db),
):
    db.query(models.User.id).limit(1).all()
    return {"status": "success"}
