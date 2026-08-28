"""Main entrypoint for Job Bot FastAPI backend application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.config import settings
from backend.db.session import close_db, get_engine, init_db
from backend.middleware.errors import register_error_handlers
from backend.middleware.request_id import RequestIDMiddleware
from backend.routers import agent, applications, cv, jobs, profile
from backend.services.redis_service import get_redis_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    settings.ensure_dirs()
    try:
        await init_db()
        logger.info("Database schemas initialized.")
    except Exception as exc:
        logger.warning("Database init failed during lifespan startup: %s", exc)

    yield

    try:
        await close_db()
    except Exception as exc:
        logger.warning("Database disposal error: %s", exc)


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="Job Bot API",
        version="1.0.0",
        description="Multi-tenant ATS application packager, job discovery, and resume tailoring agent.",
        lifespan=lifespan,
    )

    # 1. Middlewares
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # 2. Global Error Envelopes
    register_error_handlers(app)

    # 3. Health & Readiness Probes
    @app.get("/healthz", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    async def readiness() -> JSONResponse:
        db_ready = False
        details: dict[str, Any] = {}

        # Check DB
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ready = True
            details["database"] = "ok"
        except Exception as exc:
            details["database"] = str(exc)

        # Check Redis
        try:
            client = get_redis_client()
            await client.ping()
            details["redis"] = "ok"
        except Exception as exc:
            details["redis"] = str(exc)

        if db_ready:  # Soft-fail Redis in single-host local test environments if needed
            return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready", "details": details})

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "details": details},
        )

    # 4. Include Routers
    app.include_router(profile.router)
    app.include_router(jobs.router)
    app.include_router(cv.router)
    app.include_router(applications.router)
    app.include_router(agent.router)

    return app


app = create_app()
