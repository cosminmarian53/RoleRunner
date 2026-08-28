"""Service for tracking long-running operations and broadcasting SSE updates via Redis."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.operation_repo import OperationRepository
from backend.services.redis_service import get_redis_client


class OperationService:
    """Service to manage operation lifecycle and broadcast real-time updates."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.repo = OperationRepository(session, user_id)
        self.user_id = user_id
        self.channel_name = f"user:{self.user_id}:operations"

    async def _publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to the user's Redis PubSub channel."""
        client = get_redis_client()
        payload = json.dumps({"event": event_type, "data": data})
        await client.publish(self.channel_name, payload)

    def _to_dict(self, op: Any) -> dict[str, Any]:
        """Convert OperationRecord to a standard dictionary payload."""
        return {
            "id": str(op.id),
            "type": op.type,
            "status": op.status,
            "progress": op.progress,
            "message": op.message,
            "result_ref": op.result_ref,
            "error": op.error,
        }

    async def create_operation(self, op_type: str, message: str = "") -> dict[str, Any]:
        """Create a new operation and broadcast its creation."""
        from backend.db.models import OperationRecord

        op = OperationRecord(type=op_type, message=message, status="queued")
        op = await self.repo.create(op)
        op_data = self._to_dict(op)
        await self._publish("operation_created", op_data)
        return op_data

    async def update_progress(
        self, op_id: UUID, progress: int, message: str = "", status: str | None = None
    ) -> dict[str, Any] | None:
        """Update operation progress/status and broadcast the update."""
        op = await self.repo.update_progress(op_id, progress, message, status)
        if not op:
            return None
        op_data = self._to_dict(op)
        await self._publish("operation_updated", op_data)
        return op_data

    async def mark_succeeded(self, op_id: UUID, result_ref: str = "") -> dict[str, Any] | None:
        """Mark operation as succeeded and broadcast."""
        op = await self.repo.mark_succeeded(op_id, result_ref)
        if not op:
            return None
        op_data = self._to_dict(op)
        await self._publish("operation_succeeded", op_data)
        return op_data

    async def mark_failed(self, op_id: UUID, error: str) -> dict[str, Any] | None:
        """Mark operation as failed and broadcast."""
        op = await self.repo.mark_failed(op_id, error)
        if not op:
            return None
        op_data = self._to_dict(op)
        await self._publish("operation_failed", op_data)
        return op_data

    async def get_operation(self, op_id: UUID) -> dict[str, Any] | None:
        """Retrieve an operation without broadcasting."""
        op = await self.repo.get_by_id(op_id)
        if not op:
            return None
        return self._to_dict(op)

    async def list_active(self) -> list[dict[str, Any]]:
        """List active operations for the user."""
        ops = await self.repo.list_active()
        return [self._to_dict(op) for op in ops]
