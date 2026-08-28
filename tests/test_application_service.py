"""Unit tests for ApplicationService pipeline management and Kanban stage tracking."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    init_db,
)
from backend.models.application import (
    ApplicationCreateRequest,
    ApplicationStatus,
    ApplicationUpdateRequest,
)
from backend.services.application_service import ApplicationService


@pytest.fixture
async def in_memory_db_session():
    """Provide an isolated in-memory SQLite database session."""
    test_engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(test_engine)

    session_maker = async_session_factory(test_engine)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_application_lifecycle_and_state_transitions(in_memory_db_session: AsyncSession) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="tracker@apply.test"))
    await session.flush()

    service = ApplicationService(session, user_id)

    # 1. Create in SAVED status
    create_req = ApplicationCreateRequest(
        title="Lead Smart Contract Auditor",
        company="Spearbit",
        job_url="https://spearbit.com/careers/1",
        status=ApplicationStatus.SAVED,
        notes="Referred by colleague",
    )
    app = await service.create_application(create_req)

    assert app.title == "Lead Smart Contract Auditor"
    assert app.company == "Spearbit"
    assert app.status == ApplicationStatus.SAVED
    assert not app.applied_at

    # 2. Update to APPLIED -> should automatically timestamp applied_at
    update_req = ApplicationUpdateRequest(
        status=ApplicationStatus.APPLIED,
        next_step="Await response on recruiter screening",
    )
    updated = await service.update_application(app.id, update_req)
    assert updated is not None
    assert updated.status == ApplicationStatus.APPLIED
    assert updated.applied_at != ""
    assert updated.next_step == "Await response on recruiter screening"

    # 3. Create second application in INTERVIEWING
    await service.create_application(
        ApplicationCreateRequest(
            title="Senior Solana Engineer",
            company="Anza",
            status=ApplicationStatus.INTERVIEWING,
        )
    )

    # 4. Check Pipeline Stats
    stats = await service.get_pipeline_stats()
    assert stats[ApplicationStatus.APPLIED.value] == 1
    assert stats[ApplicationStatus.INTERVIEWING.value] == 1
    assert stats[ApplicationStatus.SAVED.value] == 0
    assert stats[ApplicationStatus.OFFER.value] == 0

    # 5. List with filter
    applied_list = await service.list_applications(status=ApplicationStatus.APPLIED.value)
    assert len(applied_list) == 1
    assert applied_list[0].company == "Spearbit"

    # 6. Delete
    deleted = await service.delete_application(app.id)
    assert deleted is True

    # Confirm deleted
    check = await service.get_application(app.id)
    assert check is None
