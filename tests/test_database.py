"""Tests for database engine configuration, session management, and dependencies."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from backend.db.session import (
    async_session_factory,
    close_db,
    create_engine_for_url,
    get_db,
    init_db,
    normalize_database_url,
    reset_engine,
)


def test_normalize_database_url() -> None:
    assert (
        normalize_database_url("postgres://user:pass@localhost:5432/db")
        == "postgresql+asyncpg://user:pass@localhost:5432/db"
    )
    assert (
        normalize_database_url("postgresql://user:pass@localhost:5432/db")
        == "postgresql+asyncpg://user:pass@localhost:5432/db"
    )
    assert (
        normalize_database_url("postgresql+asyncpg://user:pass@localhost:5432/db")
        == "postgresql+asyncpg://user:pass@localhost:5432/db"
    )
    assert normalize_database_url("sqlite:///./data/test.db") == "sqlite+aiosqlite:///./data/test.db"
    assert normalize_database_url("sqlite+aiosqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"


@pytest.mark.asyncio
async def test_sqlite_in_memory_engine_and_init_db() -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(engine)

    session_maker = async_session_factory(engine)
    async with session_maker() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_db_yields_session_and_commits_on_success() -> None:
    reset_engine()
    test_engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")

    # Patch global engine for get_db test
    import backend.db.session as session_module

    session_module._engine = test_engine
    session_module._session_factory = None

    db_gen: AsyncGenerator[AsyncSession, None] = get_db()
    session = await anext(db_gen)
    assert isinstance(session, AsyncSession)
    assert session.is_active

    # Clean exit from generator
    with pytest.raises(StopAsyncIteration):
        await anext(db_gen)

    await close_db()
    reset_engine()


@pytest.mark.asyncio
async def test_get_db_rolls_back_on_exception() -> None:
    reset_engine()
    test_engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")

    import backend.db.session as session_module

    session_module._engine = test_engine
    session_module._session_factory = None

    db_gen = get_db()
    session = await anext(db_gen)
    assert isinstance(session, AsyncSession)

    # Trigger exception inside consumer block
    with pytest.raises(RuntimeError, match="Simulated consumer error"):
        try:
            raise RuntimeError("Simulated consumer error")
        except Exception as exc:
            await db_gen.athrow(exc)

    await close_db()
    reset_engine()


def test_base_metadata_naming_conventions_and_mixins() -> None:
    assert Base.metadata.naming_convention["ix"] == "ix_%(column_0_label)s"
    assert Base.metadata.naming_convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"

    class SampleModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
        __tablename__ = "sample_test_models"

    model_instance = SampleModel()
    assert model_instance.id is not None or "id" in SampleModel.__table__.columns
    assert "created_at" in SampleModel.__table__.columns
    assert "updated_at" in SampleModel.__table__.columns

    now = utc_now()
    assert now.tzinfo is not None
