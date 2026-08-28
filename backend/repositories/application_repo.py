"""Tenant-scoped repository for tracked job applications."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ApplicationRecord
from backend.repositories.base import BaseTenantRepository


class ApplicationRepository(BaseTenantRepository[ApplicationRecord]):
    """Tenant-isolated repository for application pipeline tracking."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        super().__init__(ApplicationRecord, session, user_id)

    async def list_by_status(self, status: str) -> list[ApplicationRecord]:
        """List applications filtered by pipeline status."""
        stmt = (
            select(ApplicationRecord)
            .where(
                ApplicationRecord.user_id == self.user_id,
                ApplicationRecord.status == status,
            )
            .order_by(ApplicationRecord.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        """Aggregate counts per application status for Kanban overview."""
        stmt = (
            select(ApplicationRecord.status, func.count(ApplicationRecord.id))
            .where(ApplicationRecord.user_id == self.user_id)
            .group_by(ApplicationRecord.status)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
