"""Router for agent status, SSE streaming, and Codex authentication."""

from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser
from backend.services.redis_service import get_redis_client

router = APIRouter(prefix="/api/agent", tags=["agent"])


async def sse_event_generator(user_id: str, request: Request) -> AsyncGenerator[str, None]:
    """Generate SSE events for a specific user's operation channel."""
    client = get_redis_client()
    pubsub = client.pubsub()
    channel_name = f"user:{user_id}:operations"
    await pubsub.subscribe(channel_name)

    try:
        while True:
            if await request.is_disconnected():
                break

            # Use get_message with timeout to allow heartbeats
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)

            if message is not None:
                # message["data"] contains the JSON payload from operation_service
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield f"data: {data}\n\n"
            else:
                # Heartbeat to keep connection alive
                yield ": heartbeat\n\n"
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()


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
            "X-Accel-Buffering": "no",  # Needed for NGINX to stream immediately
        },
    )
