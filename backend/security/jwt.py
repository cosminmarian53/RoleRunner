"""Supabase JWT validation and CurrentUser identity model."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import jwt
from pydantic import BaseModel, ConfigDict, Field

from backend.config import settings

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Domain exception raised when token validation fails."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class CurrentUser(BaseModel):
    """Authenticated tenant identity extracted from Supabase JWT."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    email: str = ""
    role: str = "authenticated"
    claims: dict[str, Any] = Field(default_factory=dict)


def decode_supabase_jwt(token: str, secret: str | None = None) -> CurrentUser:
    """
    Decode and validate a Supabase Auth JWT token.

    Verifies signature and claims if secret is configured.
    """
    jwt_secret = secret if secret is not None else settings.supabase_jwt_secret

    try:
        if jwt_secret:
            # Full cryptographically verified token decoding
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256", "RS256"],
                options={"verify_aud": False},  # Supabase uses 'authenticated' or project ref
            )
        else:
            # Development-only fallback when no secret is configured
            if settings.app_env != "development":
                raise AuthError("UNAUTHORIZED", "Supabase JWT secret is required in non-development environments.")
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True},
            )

        sub = payload.get("sub")
        if not sub:
            raise AuthError("UNAUTHORIZED", "Token missing subject 'sub' claim.")

        try:
            user_id = UUID(str(sub))
        except ValueError as exc:
            raise AuthError("UNAUTHORIZED", f"Subject '{sub}' is not a valid UUID.") from exc

        email = payload.get("email") or payload.get("user_metadata", {}).get("email", "")
        role = payload.get("role", "authenticated")

        return CurrentUser(id=user_id, email=str(email), role=str(role), claims=payload)

    except jwt.ExpiredSignatureError as exc:
        raise AuthError("TOKEN_EXPIRED", "Authentication token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("UNAUTHORIZED", f"Invalid authentication token: {exc}") from exc
