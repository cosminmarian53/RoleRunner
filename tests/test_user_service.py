"""Tests for user service and account deletion cascades."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import JobRecord, ProfileRecord, UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    init_db,
)
from backend.services.codex_credentials import CodexCredentialsManager
from backend.services.user_service import UserService


@pytest.fixture
async def in_memory_db_session():
    """Provide an isolated, ephemeral in-memory SQLite database session for testing."""
    test_engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(test_engine)

    session_maker = async_session_factory(test_engine)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_user_service_delete_user_account(
    in_memory_db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = in_memory_db_session
    user_id = uuid4()

    # Configure custom creds root
    custom_manager = CodexCredentialsManager(tmp_path)
    monkeypatch.setattr("backend.services.user_service.get_credentials_manager", lambda: custom_manager)

    # Create user and credentials directory
    user_home = custom_manager.get_user_codex_home(user_id)
    (user_home / "auth.json").write_text("dummy token")

    user = UserRecord(id=user_id, email="tenant@example.com")
    session.add(user)
    await session.flush()

    # Add related records
    profile = ProfileRecord(user_id=user_id, data={"name": "Tenant"})
    job = JobRecord(user_id=user_id, title="Engineer")
    session.add_all([profile, job])
    await session.flush()

    service = UserService(session)
    deleted = await service.delete_user_account(user_id)

    assert deleted is True
    assert not user_home.exists()

    # Verify user record is gone
    user_res = await session.execute(select(UserRecord).where(UserRecord.id == user_id))
    assert user_res.scalar_one_or_none() is None
