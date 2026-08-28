"""FastAPI authentication dependencies for tenant isolation."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import settings
from backend.security.jwt import AuthError, CurrentUser, decode_supabase_jwt

# Bearer token extractor (auto_error=False allows dev fallback)
bearer_scheme = HTTPBearer(auto_error=False)

DEV_FALLBACK_USER = CurrentUser(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    email="dev-user@example.com",
    role="authenticated",
    claims={"aud": "authenticated", "is_mock_dev": True},
)


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser | None:
    """Extract and validate the current user from Bearer header if present."""
    if credentials is None or not credentials.credentials:
        return None

    try:
        return decode_supabase_jwt(credentials.credentials)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": exc.code, "detail": exc.detail},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    """
    Enforce tenant authentication on protected API endpoints.

    In local development when no Supabase secret is set and no header is provided,
    falls back to DEV_FALLBACK_USER. In production, raises 401.
    """
    user = await get_optional_user(credentials)
    if user is not None:
        return user

    # Development-only fallback
    if settings.app_env == "development" and not settings.supabase_jwt_secret:
        return DEV_FALLBACK_USER

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "detail": "Missing authentication bearer token."},
        headers={"WWW-Authenticate": "Bearer"},
    )
