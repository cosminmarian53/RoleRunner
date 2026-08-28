"""FastAPI authentication dependencies for tenant isolation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import settings
from backend.security.jwt import (
    AuthError,
    CurrentUser,
    resolve_user_from_token_or_session,
)

# Bearer token extractor (auto_error=False allows dev/anonymous fallback)
bearer_scheme = HTTPBearer(auto_error=False)

DEV_FALLBACK_USER = CurrentUser(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    email="dev-user@example.com",
    role="authenticated",
    claims={"aud": "authenticated", "is_mock_dev": True},
)


async def get_optional_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> CurrentUser | None:
    """Extract and validate the current user from Bearer token or X-Session-ID header."""
    token: str | None = None

    # 1. Authorization: Bearer <token_or_uuid>
    if credentials and credentials.credentials:
        token = credentials.credentials

    # 2. X-Session-ID header (anonymous client session)
    if not token:
        token = request.headers.get("X-Session-ID") or request.headers.get("x-session-id")

    if not token:
        return None

    try:
        return resolve_user_from_token_or_session(token)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": exc.code, "detail": exc.detail},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> CurrentUser:
    """
    Enforce tenant authentication on protected API endpoints.

    Supports:
    1. Anonymous sessions via client UUID (X-Session-ID or Bearer <uuid>)
    2. Supabase / JWT cryptographic bearer tokens
    3. Fallback to DEV_FALLBACK_USER if no token is passed and no secret is configured
    """
    user = await get_optional_user(request, credentials)
    if user is not None:
        return user

    # Strict enforcement only when Supabase secret is explicitly set and no session provided
    if settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "detail": "Missing authentication session or token."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fallback to dev user when no session or header is provided
    return DEV_FALLBACK_USER
