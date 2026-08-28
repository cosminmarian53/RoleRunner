"""Tenant-scoped repository for job listing search and deduplication."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import JobRecord
from backend.repositories.base import BaseTenantRepository


class JobRepository(BaseTenantRepository[JobRecord]):
    """Tenant-isolated repository for discovered jobs."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        super().__init__(JobRecord, session, user_id)

    async def get_by_url_hash(self, url_hash: str) -> JobRecord | None:
        """Find a job by url_hash scoped to the current user."""
        stmt = select(JobRecord).where(
            JobRecord.user_id == self.user_id,
            JobRecord.url_hash == url_hash,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_relevance(self, limit: int = 50) -> list[JobRecord]:
        """List jobs ordered by relevance_score descending."""
        stmt = (
            select(JobRecord)
            .where(JobRecord.user_id == self.user_id)
            .order_by(JobRecord.relevance_score.desc().nullslast(), JobRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create(self, jobs: list[JobRecord]) -> list[JobRecord]:
        """Persist multiple job records attached to the current user."""
        await self.ensure_user_exists()
        for job in jobs:
            job.user_id = self.user_id
            self.session.add(job)
        await self.session.flush()
        return jobs
