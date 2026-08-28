"""Standardized error handlers and response envelopes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.scrapers.ssrf import SSRFProtectionError

logger = logging.getLogger(__name__)


def make_error_response(code: str, detail: Any, request_id: str = "", status_code: int = 400) -> JSONResponse:
    """Construct a standardized JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "detail": detail,
            "request_id": request_id,
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all global error handlers on the FastAPI application."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "")
        code_map = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            422: "UNPROCESSABLE_ENTITY",
        }
        err_code = code_map.get(exc.status_code, "HTTP_ERROR")
        return make_error_response(
            code=err_code,
            detail=exc.detail,
            request_id=req_id,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "")
        return make_error_response(
            code="VALIDATION_ERROR",
            detail=exc.errors(),
            request_id=req_id,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(SSRFProtectionError)
    async def ssrf_exception_handler(request: Request, exc: SSRFProtectionError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "")
        return make_error_response(
            code="SSRF_BLOCKED",
            detail=exc.message,
            request_id=req_id,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "")
        logger.exception("Unhandled server error [request_id=%s]: %s", req_id, exc)
        return make_error_response(
            code="INTERNAL_SERVER_ERROR",
            detail="An unexpected error occurred. Please try again or contact support.",
            request_id=req_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
