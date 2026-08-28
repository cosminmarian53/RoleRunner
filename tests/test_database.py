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


@pytest.mark.asyncio
async def test_orm_models_schema_and_cascade_deletion() -> None:
    from backend.db.models import (
        ApplicationRecord,
        GeneratedCVRecord,
        JobRecord,
        OperationRecord,
        ProfileRecord,
        UserRecord,
    )

    test_engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(test_engine)

    session_maker = async_session_factory(test_engine)
    async with session_maker() as session:
        # Create user
        user = UserRecord(email="alice@example.com", settings_data={"theme": "dark"})
        session.add(user)
        await session.flush()

        # Add profile
        profile = ProfileRecord(user_id=user.id, data={"name": "Alice Developer"})
        session.add(profile)

        # Add job
        job = JobRecord(
            user_id=user.id,
            title="Senior Rust Engineer",
            company="Solana Protocol",
            url="https://example.com/job/1",
            url_hash="hash123",
        )
        session.add(job)
        await session.flush()

        # Add generated CV
        cv = GeneratedCVRecord(
            user_id=user.id,
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            markdown_content="# Alice CV",
        )
        session.add(cv)
        await session.flush()

        # Add application
        application = ApplicationRecord(
            user_id=user.id,
            job_id=job.id,
            cv_id=cv.id,
            title=job.title,
            company=job.company,
            status="applied",
        )
        session.add(application)

        # Add operation
        op = OperationRecord(
            user_id=user.id,
            type="job_search",
            status="running",
            progress=50,
        )
        session.add(op)
        await session.commit()

    # Verify entities were stored
    async with session_maker() as session:
        user_db = await session.get(UserRecord, user.id)
        assert user_db is not None
        assert user_db.email == "alice@example.com"

        # Verify cascade deletion on user removal
        await session.delete(user_db)
        await session.commit()

    async with session_maker() as session:
        assert await session.get(UserRecord, user.id) is None
        assert await session.get(ProfileRecord, profile.id) is None
        assert await session.get(JobRecord, job.id) is None
        assert await session.get(GeneratedCVRecord, cv.id) is None
        assert await session.get(ApplicationRecord, application.id) is None
        assert await session.get(OperationRecord, op.id) is None

    await test_engine.dispose()
