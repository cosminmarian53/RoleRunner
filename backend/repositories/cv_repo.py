"""Tenant-scoped repository for generated CV records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import GeneratedCVRecord
from backend.repositories.base import BaseTenantRepository


class CVRepository(BaseTenantRepository[GeneratedCVRecord]):
    """Tenant-isolated repository for generated CV documents."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        super().__init__(GeneratedCVRecord, session, user_id)

    async def list_by_job(self, job_id: UUID) -> list[GeneratedCVRecord]:
        """Fetch all CVs generated for a specific job target."""
        stmt = (
            select(GeneratedCVRecord)
            .where(
                GeneratedCVRecord.user_id == self.user_id,
                GeneratedCVRecord.job_id == job_id,
            )
            .order_by(GeneratedCVRecord.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
