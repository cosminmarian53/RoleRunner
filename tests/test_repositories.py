"""Unit tests for tenant-scoped repositories using an isolated in-memory test database."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ApplicationRecord, JobRecord, OperationRecord, UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    init_db,
)
from backend.repositories.application_repo import ApplicationRepository
from backend.repositories.cv_repo import CVRepository
from backend.repositories.job_repo import JobRepository
from backend.repositories.operation_repo import OperationRepository
from backend.repositories.profile_repo import ProfileRepository


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
async def test_tenant_isolation_prevents_cross_user_access(
    in_memory_db_session: AsyncSession,
) -> None:
    session = in_memory_db_session

    user_a_id = uuid4()
    user_b_id = uuid4()

    # Create users
    session.add(UserRecord(id=user_a_id, email="alice@test.local"))
    session.add(UserRecord(id=user_b_id, email="bob@test.local"))
    await session.flush()

    repo_a = JobRepository(session, user_a_id)
    repo_b = JobRepository(session, user_b_id)

    # User A creates a job
    job_a = JobRecord(
        user_id=user_a_id,
        title="Smart Contract Auditor",
        company="CertiK",
        url="https://example.com/1",
        url_hash="hash_a",
    )
    await repo_a.create(job_a)
    await session.commit()

    # User A can retrieve it
    assert await repo_a.get_by_id(job_a.id) is not None
    assert await repo_a.get_by_url_hash("hash_a") is not None

    # User B CANNOT retrieve User A's job
    assert await repo_b.get_by_id(job_a.id) is None
    assert await repo_b.get_by_url_hash("hash_a") is None

    # User B CANNOT delete User A's job
    deleted = await repo_b.delete_by_id(job_a.id)
    assert deleted is False
    assert await repo_a.get_by_id(job_a.id) is not None


@pytest.mark.asyncio
async def test_profile_repository_upsert_and_isolation(
    in_memory_db_session: AsyncSession,
) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="carol@test.local"))
    await session.flush()

    repo = ProfileRepository(session, user_id)

    # Initial profile is None
    assert await repo.get_profile() is None

    # Upsert creates profile
    profile = await repo.upsert_profile({"name": "Carol", "skills": ["Rust", "Solidity"]})
    assert profile.data["name"] == "Carol"

    # Subsequent upsert updates existing profile
    updated = await repo.upsert_profile({"name": "Carol Marian", "skills": ["Rust"]})
    assert updated.id == profile.id
    assert updated.data["name"] == "Carol Marian"


@pytest.mark.asyncio
async def test_job_repository_ranking_and_bulk_create(
    in_memory_db_session: AsyncSession,
) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="dave@test.local"))
    await session.flush()

    repo = JobRepository(session, user_id)

    jobs = [
        JobRecord(user_id=user_id, title="Job Low", relevance_score=5.0, url_hash="1"),
        JobRecord(user_id=user_id, title="Job High", relevance_score=9.5, url_hash="2"),
        JobRecord(user_id=user_id, title="Job Mid", relevance_score=7.0, url_hash="3"),
    ]
    await repo.bulk_create(jobs)
    await session.commit()

    ranked = await repo.list_by_relevance()
    assert len(ranked) == 3
    assert ranked[0].title == "Job High"
    assert ranked[1].title == "Job Mid"
    assert ranked[2].title == "Job Low"


@pytest.mark.asyncio
async def test_application_repository_status_filtering_and_counts(
    in_memory_db_session: AsyncSession,
) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="eve@test.local"))
    await session.flush()

    repo = ApplicationRepository(session, user_id)

    app1 = ApplicationRecord(user_id=user_id, title="Role 1", status="applied")
    app2 = ApplicationRecord(user_id=user_id, title="Role 2", status="applied")
    app3 = ApplicationRecord(user_id=user_id, title="Role 3", status="interviewing")
    await repo.create(app1)
    await repo.create(app2)
    await repo.create(app3)
    await session.commit()

    applied = await repo.list_by_status("applied")
    assert len(applied) == 2

    counts = await repo.count_by_status()
    assert counts["applied"] == 2
    assert counts["interviewing"] == 1


@pytest.mark.asyncio
async def test_operation_repository_lifecycle(
    in_memory_db_session: AsyncSession,
) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="frank@test.local"))
    await session.flush()

    repo = OperationRepository(session, user_id)

    op = OperationRecord(user_id=user_id, type="cv_generation", status="queued")
    await repo.create(op)
    await session.commit()

    # Active operations
    active = await repo.list_active()
    assert len(active) == 1

    # Update progress
    await repo.update_progress(op.id, 50, message="Extracting keywords", status="running")
    updated = await repo.get_by_id(op.id)
    assert updated is not None
    assert updated.progress == 50
    assert updated.status == "running"

    # Mark succeeded
    await repo.mark_succeeded(op.id, result_ref="cv_123")
    succeeded = await repo.get_by_id(op.id)
    assert succeeded is not None
    assert succeeded.status == "succeeded"
    assert succeeded.progress == 100

    # No longer active
    assert len(await repo.list_active()) == 0


@pytest.mark.asyncio
async def test_cv_repository_job_filtering(
    in_memory_db_session: AsyncSession,
) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    job_id = uuid4()
    session.add(UserRecord(id=user_id, email="grace@test.local"))
    # Create job to satisfy foreign key constraint
    session.add(
        JobRecord(
            id=job_id,
            user_id=user_id,
            title="Lead Security Auditor",
            company="Immunefi",
            url="https://example.com/job/lead",
            url_hash="hash_lead",
        )
    )
    await session.flush()

    cv_repo = CVRepository(session, user_id)
    from backend.db.models import GeneratedCVRecord

    cv1 = GeneratedCVRecord(
        user_id=user_id,
        job_id=job_id,
        markdown_content="# CV for Job",
    )
    cv2 = GeneratedCVRecord(
        user_id=user_id,
        job_id=None,
        markdown_content="# General CV",
    )
    await cv_repo.create(cv1)
    await cv_repo.create(cv2)
    await session.commit()

    job_cvs = await cv_repo.list_by_job(job_id)
    assert len(job_cvs) == 1
    assert job_cvs[0].job_id == job_id
