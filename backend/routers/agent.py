"""Router for agent status, SSE streaming, and Codex authentication."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser
from backend.services.ai_client import get_harness, get_provider_status
from backend.services.redis_service import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


async def sse_event_generator(user_id: str, request: Request) -> AsyncGenerator[str, None]:
    """Generate SSE events for a specific user's operation channel."""
    pubsub = None
    channel_name = f"user:{user_id}:operations"

    try:
        client = get_redis_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel_name)
    except Exception as exc:
        logger.debug("Redis pubsub unavailable for SSE (local dev fallback): %s", exc)
        pubsub = None

    try:
        while True:
            if await request.is_disconnected():
                break

            if pubsub is not None:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                    if message is not None:
                        data = message["data"]
                        if isinstance(data, bytes):
                            data = data.decode("utf-8")
                        yield f"data: {data}\n\n"
                    else:
                        yield ": heartbeat\n\n"
                except Exception as exc:
                    logger.debug("Redis pubsub read error during stream: %s", exc)
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(5.0)
            else:
                yield ": heartbeat\n\n"
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
    harness = get_harness(user_id=current_user.id)
    auth_info = await harness.start_login()
    return {
        "authorization_url": auth_info.authorization_url,
        "device_code": auth_info.device_code,
        "raw_output": auth_info.raw_output,
        "expires_at": auth_info.expires_at,
    }


@router.get("/login/status")
async def get_agent_login_status(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Check whether user's Codex harness is currently authenticated."""
    harness = get_harness(user_id=current_user.id)
    is_authenticated = await harness.refresh_auth_status()
    return {
        "authenticated": is_authenticated,
        "provider": "codex",
    }


@router.get("/provider/status")
async def get_agent_provider_status(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get provider details and credential state for UI indicator."""
    return get_provider_status(user_id=current_user.id)
