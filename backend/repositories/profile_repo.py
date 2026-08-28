"""Tenant-scoped repository for master candidate profile records."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ProfileRecord
from backend.repositories.base import BaseTenantRepository


class ProfileRepository(BaseTenantRepository[ProfileRecord]):
    """Tenant-isolated repository for candidate profiles."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        super().__init__(ProfileRecord, session, user_id)

    async def get_profile(self) -> ProfileRecord | None:
        """Fetch the single master profile for the current user."""
        stmt = select(ProfileRecord).where(ProfileRecord.user_id == self.user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_profile(self, data: dict[str, Any]) -> ProfileRecord:
        """Create or update the master profile for the current user."""
        await self.ensure_user_exists()
        profile = await self.get_profile()
        if profile is None:
            profile = ProfileRecord(user_id=self.user_id, data=data)
            self.session.add(profile)
        else:
            profile.data = data
        await self.session.flush()
        return profile

    async def delete_profile(self) -> bool:
        """Delete the master profile for the current user."""
        profile = await self.get_profile()
        if profile is not None:
            await self.session.delete(profile)
            await self.session.flush()
            return True
        return False
