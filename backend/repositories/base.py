"""Base tenant-scoped repository with mandatory user_id filtering."""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseTenantRepository(Generic[ModelT]):
    """
    Generic repository enforcing tenant isolation on every database interaction.

    All SELECT, UPDATE, DELETE queries automatically append `WHERE user_id = self.user_id`.
    """

    def __init__(self, model_class: type[ModelT], session: AsyncSession, user_id: UUID | str) -> None:
        self.model_class = model_class
        self.session = session
        self.user_id = UUID(user_id) if not isinstance(user_id, UUID) else user_id

    async def get_by_id(self, entity_id: UUID | str) -> ModelT | None:
        """Fetch a single record by primary key, isolated to the current user."""
        uid = UUID(entity_id) if not isinstance(entity_id, UUID) else entity_id
        stmt = select(self.model_class).where(
            self.model_class.id == uid,  # type: ignore[attr-defined]
            self.model_class.user_id == self.user_id,  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """List records owned by the current tenant, ordered by created_at descending."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.user_id == self.user_id)  # type: ignore[attr-defined]
            .order_by(self.model_class.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: ModelT) -> ModelT:
        """Persist a new entity attached to the current user."""
        entity.user_id = self.user_id  # type: ignore[attr-defined]
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete_by_id(self, entity_id: UUID | str) -> bool:
        """Delete an entity by id, ensuring it belongs to the current user."""
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True
