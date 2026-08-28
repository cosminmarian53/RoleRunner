"""Router for agent status, SSE streaming, and persistent Codex authentication."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import UserRecord
from backend.db.session import get_db
from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser
from backend.services.ai_client import (
    disconnect_harness,
    get_harness,
    get_provider_status,
)
from backend.services.codex_credentials import get_credentials_manager
from backend.services.redis_service import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


async def _restore_codex_auth_from_db(user_id: UUID, session: AsyncSession) -> None:
    """Restore cached auth.json from persistent database if local disk was wiped upon redeploy."""
    manager = get_credentials_manager()
    if manager.read_auth_json(user_id) is not None:
        return

    result = await session.execute(select(UserRecord).where(UserRecord.id == user_id))
    user_rec = result.scalar_one_or_none()
    if user_rec and user_rec.settings_data and "codex_auth" in user_rec.settings_data:
        saved_auth = user_rec.settings_data["codex_auth"]
        if isinstance(saved_auth, str) and saved_auth.strip():
            manager.write_auth_json(user_id, saved_auth)
            logger.info("Restored persistent Codex credentials from PostgreSQL for user %s", user_id)


async def _persist_codex_auth_to_db(user_id: UUID, session: AsyncSession) -> None:
    """Save newly authenticated auth.json into PostgreSQL for persistence across container redeploys."""
    manager = get_credentials_manager()
    auth_str = manager.read_auth_json(user_id)
    if not auth_str:
        return

    result = await session.execute(select(UserRecord).where(UserRecord.id == user_id))
    user_rec = result.scalar_one_or_none()

    if user_rec is None:
        user_rec = UserRecord(
            id=user_id,
            email=f"{user_id}@session.local",
            settings_data={"codex_auth": auth_str},
        )
        session.add(user_rec)
    else:
        new_settings = dict(user_rec.settings_data or {})
        new_settings["codex_auth"] = auth_str
        user_rec.settings_data = new_settings
        session.add(user_rec)

    await session.flush()
    logger.info("Synchronized persistent Codex credentials to PostgreSQL for user %s", user_id)


async def _clear_codex_auth_from_db(user_id: UUID, session: AsyncSession) -> None:
    """Clear stored Codex credentials from PostgreSQL upon logout."""
    result = await session.execute(select(UserRecord).where(UserRecord.id == user_id))
    user_rec = result.scalar_one_or_none()
    if user_rec and user_rec.settings_data and "codex_auth" in user_rec.settings_data:
        new_settings = dict(user_rec.settings_data)
        new_settings.pop("codex_auth", None)
        user_rec.settings_data = new_settings
        session.add(user_rec)
        await session.flush()


async def sse_event_generator(user_id: str, request: Request) -> AsyncGenerator[str, None]:
    """Generate SSE events for a specific user's operation channel."""
    pubsub = None
    channel_name = f"user:{user_id}:operations"

    try:
        redis = get_redis_client()
        if redis is not None:
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel_name)

        yield "event: connected\ndata: {}\n\n"

        while True:
            if await request.is_disconnected():
                break

            if pubsub is not None:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    yield f"data: {message['data']}\n\n"
            else:
                await asyncio.sleep(5.0)
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(channel_name)
                await pubsub.close()
            except Exception:
                pass


@router.get("/status")
async def stream_agent_status(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Stream real-time background operation updates via Server-Sent Events (SSE)."""
    return StreamingResponse(
        sse_event_generator(str(current_user.id), request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/login/start")
async def start_agent_login(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Initiate ChatGPT device auth login for the user's isolated Codex harness."""
    try:
        harness = get_harness(user_id=current_user.id)
        auth_info = await harness.start_login()
        return {
            "authorization_url": auth_info.authorization_url,
            "device_code": auth_info.device_code,
            "raw_output": auth_info.raw_output,
            "expires_at": auth_info.expires_at,
        }
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CLI_UNAVAILABLE", "detail": str(exc)},
        ) from exc
    except Exception as exc:
        logger.warning("Agent login start error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "LOGIN_FAILED", "detail": f"Failed to start device login: {exc}"},
        ) from exc


@router.get("/login/status")
async def get_agent_login_status(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Check whether user's Codex harness is currently authenticated, syncing with PostgreSQL."""
    await _restore_codex_auth_from_db(current_user.id, session)
    harness = get_harness(user_id=current_user.id)
    is_authenticated = await harness.refresh_auth_status()

    if is_authenticated:
        await _persist_codex_auth_to_db(current_user.id, session)

    return {
        "authenticated": is_authenticated,
        "provider": "codex",
    }


@router.get("/provider/status")
async def get_agent_provider_status(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get provider details and credential state for UI indicator, restoring from DB if needed."""
    await _restore_codex_auth_from_db(current_user.id, session)
    harness = get_harness(user_id=current_user.id)
    await harness.refresh_auth_status()
    return get_provider_status(user_id=current_user.id)


@router.post("/disconnect")
@router.post("/logout")
async def disconnect_agent(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Disconnect and wipe the user's active Codex CLI session from disk and PostgreSQL."""
    success = await disconnect_harness(user_id=current_user.id)
    await _clear_codex_auth_from_db(current_user.id, session)
    return {
        "success": success,
        "authenticated": False,
        "message": "Codex session disconnected successfully.",
    }
