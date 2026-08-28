"""Unit tests for ProfileService with PostgreSQL storage and AI fallback."""

from io import BytesIO
from uuid import uuid4

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    init_db,
)
from backend.services.profile_service import ProfileService


@pytest.fixture
async def in_memory_db_session():
    """Provide an isolated in-memory SQLite database session."""
    test_engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(test_engine)

    session_maker = async_session_factory(test_engine)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


def make_pdf_bytes(text: str = "Test resume text") -> bytes:
    buf = BytesIO()
    p = canvas.Canvas(buf)
    y = 750
    for line in text.splitlines():
        if line.strip():
            p.drawString(100, y, line.strip())
            y -= 20
    p.showPage()
    p.save()
    return buf.getvalue()


@pytest.mark.asyncio
async def test_profile_service_crud(in_memory_db_session: AsyncSession) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="alice@test.local"))
    await session.flush()

    service = ProfileService(session, user_id)

    # Initially empty
    profile = await service.get_profile()
    assert profile.personal_info.name == ""

    # Save
    profile.personal_info.name = "Alice Developer"
    profile.skills = {"languages": ["Python", "Go"]}
    await service.save_profile(profile)

    # Fetch back
    loaded = await service.get_profile()
    assert loaded.personal_info.name == "Alice Developer"
    assert "Python" in loaded.skills["languages"]


@pytest.mark.asyncio
async def test_profile_service_parse_and_save_text_regex_fallback(
    in_memory_db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="bob@test.local"))
    await session.flush()

    service = ProfileService(session, user_id)

    raw_text = """
    Bob Builder
    bob@example.com | +1 555-0199 | https://linkedin.com/in/bobbuilder

    SUMMARY
    Senior Software Engineer with 8 years experience in Python and FastAPI.

    EXPERIENCE
    Staff Engineer at Acme Corp
    2020 - Present
    - Designed distributed queue architecture
    - Led team of 5 backend engineers
    """

    # Force AI failure to test regex fallback
    async def fake_ask(*args, **kwargs):
        raise RuntimeError("AI unavailable")

    monkeypatch.setattr("backend.services.profile_service.ask", fake_ask)

    res = await service.parse_and_save_text(raw_text, use_ai=True)

    assert res.profile.personal_info.name == "Bob Builder"
    assert res.profile.personal_info.email == "bob@example.com"
    assert len(res.profile.experience) >= 1
    assert res.profile.experience[0].company == "Acme Corp"


@pytest.mark.asyncio
async def test_profile_service_parse_and_save_upload_pdf(in_memory_db_session: AsyncSession) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="carol@test.local"))
    await session.flush()

    service = ProfileService(session, user_id)

    pdf_content = make_pdf_bytes("Carol Danvers\ncarol@marvel.com\nPython Developer")
    res = await service.parse_and_save_upload("carol_resume.pdf", pdf_content, use_ai=False)

    assert res.profile.personal_info.name == "Carol Danvers"
    assert res.profile.personal_info.email == "carol@marvel.com"
    assert res.source_filename == "carol_resume.pdf"


@pytest.mark.asyncio
async def test_profile_service_extracts_complex_contact_formats(in_memory_db_session: AsyncSession) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="cosmin@test.local"))
    await session.flush()

    service = ProfileService(session, user_id)

    raw_text = """
    COSMIN -MARIAN LAVRIC
    Offensive Security & Blockchain Researcher
    Brașov, Romania (EET)  •  cosminlavric53@gmail.com  •  +40 749 -484-655
    linkedin.com/in/cosmin -lavric -827126331  •  github.com/cosminmarian53

    PROFESSIONAL SUMMARY
    Passionate Cybersecurity Consultant and Offensive Security Researcher.
    """

    res = await service.parse_and_save_text(raw_text, use_ai=False)

    assert res.profile.personal_info.name == "Cosmin-Marian Lavric"
    assert res.profile.personal_info.email == "cosminlavric53@gmail.com"
    assert "749" in res.profile.personal_info.phone and "484" in res.profile.personal_info.phone
    assert res.profile.personal_info.linkedin == "https://linkedin.com/in/cosmin-lavric-827126331"
    assert res.profile.personal_info.github == "https://github.com/cosminmarian53"
    assert "Brașov, Romania" in res.profile.personal_info.location
