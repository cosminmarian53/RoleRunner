"""Repository for storing and retrieving user feedback records."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import FeedbackRecord
from backend.models.feedback import FeedbackCategory, FeedbackCreateRequest


class FeedbackRepository:
    """Handles feedback persistence in PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        request: FeedbackCreateRequest,
        user_id: UUID | None = None,
    ) -> FeedbackRecord:
        """Persist a new feedback entry."""
        record = FeedbackRecord(
            user_id=user_id,
            rating=request.rating,
            category=str(request.category),
            message=request.message,
            email=request.email,
            page_url=request.page_url,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def list_all(
        self,
        category: FeedbackCategory | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[FeedbackRecord]:
        """List feedback submissions, ordered newest first."""
        stmt = select(FeedbackRecord).order_by(FeedbackRecord.created_at.desc())
        if category:
            stmt = stmt.where(FeedbackRecord.category == str(category))
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()
