"""User management and tenant deletion cleanup service."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import UserRecord
from backend.services.codex_credentials import get_credentials_manager

logger = logging.getLogger(__name__)


class UserService:
    """Handles tenant account lifecycle and cascading resource deletion."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.credentials_manager = get_credentials_manager()

    async def delete_user_account(self, user_id: UUID | str) -> bool:
        """
        Completely delete a tenant account.

        Deletes:
        1. All database rows associated with user (via foreign key cascades).
        2. Isolated Codex credentials and auth files on disk.
        """
        uid = UUID(str(user_id))
        stmt = select(UserRecord).where(UserRecord.id == uid)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return False

        await self.session.delete(user)
        await self.session.flush()

        # Delete isolated directory on disk
        self.credentials_manager.delete_user_credentials(uid)

        logger.info("Deleted user account %s", uid)
        return True
