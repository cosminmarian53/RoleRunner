"""Unit tests for Supabase JWT validation and FastAPI auth dependencies."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from backend.config import settings
from backend.security.auth import DEV_FALLBACK_USER, get_current_user, get_optional_user
from backend.security.jwt import AuthError, CurrentUser, decode_supabase_jwt

TEST_SECRET = "test-supabase-jwt-secret-very-secure-32-chars-long"


def create_test_jwt(
    sub: str | None = None,
    email: str = "alice@example.com",
    expired: bool = False,
    secret: str = TEST_SECRET,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    payload = {
        "sub": sub if sub is not None else str(uuid4()),
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    assert isinstance(token, str)
    return token


def test_decode_valid_jwt_with_secret() -> None:
    user_id = uuid4()
    token = create_test_jwt(sub=str(user_id), email="bob@example.com")

    user = decode_supabase_jwt(token, secret=TEST_SECRET)
    assert isinstance(user, CurrentUser)
    assert user.id == user_id
    assert user.email == "bob@example.com"
    assert user.role == "authenticated"


def test_decode_expired_jwt_raises_auth_error() -> None:
    token = create_test_jwt(expired=True)

    with pytest.raises(AuthError) as exc_info:
        decode_supabase_jwt(token, secret=TEST_SECRET)

    assert exc_info.value.code == "TOKEN_EXPIRED"


def test_decode_invalid_signature_raises_auth_error() -> None:
    token = create_test_jwt(secret="wrong-secret-12345678901234567890")

    with pytest.raises(AuthError) as exc_info:
        decode_supabase_jwt(token, secret=TEST_SECRET)

    assert exc_info.value.code == "UNAUTHORIZED"


def test_decode_non_uuid_sub_raises_auth_error() -> None:
    token = create_test_jwt(sub="not-a-valid-uuid")

    with pytest.raises(AuthError) as exc_info:
        decode_supabase_jwt(token, secret=TEST_SECRET)

    assert exc_info.value.code == "UNAUTHORIZED"


def create_mock_request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({"type": "http", "headers": headers or []})


@pytest.mark.asyncio
async def test_get_current_user_dev_fallback() -> None:
    req = create_mock_request()
    user = await get_current_user(req, None)
    assert user.id == DEV_FALLBACK_USER.id
    assert user.email == DEV_FALLBACK_USER.email


@pytest.mark.asyncio
async def test_get_current_user_with_valid_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_SECRET)

    req = create_mock_request()
    user_id = uuid4()
    token = create_test_jwt(sub=str(user_id), email="carol@example.com")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = await get_current_user(req, credentials=credentials)
    assert user.id == user_id
    assert user.email == "carol@example.com"


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_SECRET)

    req = create_mock_request()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(req, None)

    assert exc_info.value.status_code == 401
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_optional_user_returns_none_when_header_absent() -> None:
    req = create_mock_request()
    assert await get_optional_user(req, None) is None


@pytest.mark.asyncio
async def test_get_current_user_with_anonymous_session_uuid() -> None:
    req = create_mock_request()
    session_id = uuid4()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=str(session_id))
    user = await get_current_user(req, credentials=credentials)
    assert user.id == session_id
    assert user.role == "anonymous"
    assert user.claims.get("is_anonymous") is True
