"""Unit tests for CVService orchestration."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    init_db,
)
from backend.models.cv import CVGenerateRequest, ExportFormat
from backend.models.profile import CandidateProfile, PersonalInfo
from backend.services.cv_service import CVService
from backend.services.storage_service import StorageService


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
async def test_cv_service_generate_score_and_persist(
    in_memory_db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="candidate@cv.test"))
    await session.flush()

    storage_svc = StorageService()
    storage_svc.local_resumes_dir = tmp_path / "resumes"
    monkeypatch.setattr(storage_svc, "supabase_url", "")

    cv_service = CVService(session, user_id, storage_service=storage_svc)

    # Save a profile first
    profile = CandidateProfile(
        personal_info=PersonalInfo(
            name="Alice Candidate",
            email="alice@cv.test",
        ),
        summary="Experienced in Kubernetes, Terraform, and Python.",
        skills={"Infrastructure": ["Kubernetes", "Docker", "Terraform", "Python"]},
    )
    await cv_service.profile_service.save_profile(profile)

    # Generate CV
    req = CVGenerateRequest(
        job_description="Looking for Senior Platform Engineer skilled in Kubernetes, Terraform, and Python.",
        job_title="Senior Platform Engineer",
        company="CloudCorp",
        export_format=ExportFormat.PDF,
        use_ai=False,
    )

    generated = await cv_service.generate_and_save_cv(req)

    assert generated.job_title == "Senior Platform Engineer"
    assert generated.company == "CloudCorp"
    assert "Alice Candidate" in generated.markdown_content
    assert generated.ats_score is not None
    assert generated.ats_score.overall_score >= 80
    assert "kubernetes" in generated.ats_score.matched_keywords
    assert ExportFormat.PDF.value in generated.export_paths

    # Test retrieval from DB
    retrieved = await cv_service.get_cv_by_id(generated.id)
    assert retrieved is not None
    assert retrieved.job_title == "Senior Platform Engineer"
    assert retrieved.ats_score is not None
    assert retrieved.ats_score.overall_score == generated.ats_score.overall_score
