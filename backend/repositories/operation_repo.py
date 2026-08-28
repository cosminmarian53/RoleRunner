"""Tenant-scoped repository for async operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import OperationRecord
from backend.repositories.base import BaseTenantRepository


class OperationRepository(BaseTenantRepository[OperationRecord]):
    """Tenant-isolated repository for background operation lifecycle."""

    def __init__(self, session: AsyncSession, user_id: UUID | str) -> None:
        super().__init__(OperationRecord, session, user_id)

    async def create_operation(
        self,
        type: str,
        message: str = "",
        status: str = "queued",
        result_ref: str = "",
        error: str = "",
    ) -> OperationRecord:
        """Create and persist a new operation record for the tenant."""
        op = OperationRecord(
            type=type,
            message=message,
            status=status,
            result_ref=result_ref,
            error=error,
        )
        return await self.create(op)

    async def update_progress(
        self,
        op_id: UUID | str,
        progress: int,
        message: str = "",
        status: str | None = None,
    ) -> OperationRecord | None:
        """Update progress and status on an active operation."""
        op = await self.get_by_id(op_id)
        if op is None:
            return None

        op.progress = max(0, min(100, progress))
        if message:
            op.message = message
        if status:
            op.status = status
        await self.session.flush()
        return op

    async def mark_succeeded(self, op_id: UUID | str, result_ref: str = "") -> OperationRecord | None:
        """Mark operation as succeeded with 100% progress."""
        op = await self.get_by_id(op_id)
        if op is None:
            return None

        op.status = "succeeded"
        op.progress = 100
        if result_ref:
            op.result_ref = result_ref
        await self.session.flush()
        return op

    async def mark_failed(self, op_id: UUID | str, error: str) -> OperationRecord | None:
        """Mark operation as failed with error details."""
        op = await self.get_by_id(op_id)
        if op is None:
            return None

        op.status = "failed"
        op.error = error
        await self.session.flush()
        return op

    async def list_active(self) -> list[OperationRecord]:
        """List ongoing operations (queued or running)."""
        stmt = (
            select(OperationRecord)
            .where(
                OperationRecord.user_id == self.user_id,
                OperationRecord.status.in_(["queued", "running"]),
            )
            .order_by(OperationRecord.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
