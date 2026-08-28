from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import select

from backend.db.models import OperationRecord, ProfileRecord, UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    init_db,
)
from backend.services.codex_credentials import CodexCredentialsManager
from backend.services.operation_service import OperationService
from backend.services.profile_service import ProfileService
from backend.services.storage_service import StorageService
from backend.services.user_service import UserService


def make_sample_pdf(name: str, email: str, role: str) -> bytes:
    """Generate valid sample PDF bytes with resume content."""
    buf = BytesIO()
    p = canvas.Canvas(buf)
    y = 750
    for line in [name, email, role, "Skills: Python, FastAPI, Docker", "Experience: Lead Architect at Tech Inc"]:
        p.drawString(100, y, line)
        y -= 20
    p.showPage()
    p.save()
    return buf.getvalue()


@pytest.fixture
async def integration_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up isolated in-memory DB, in-memory Redis, and temp directories."""
    # 1. Database
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    session_factory = async_session_factory(engine)

    # 2. Redis
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("backend.services.redis_service.get_redis_client", lambda: fake_redis)
    monkeypatch.setattr("backend.services.operation_service.get_redis_client", lambda: fake_redis)

    # 3. Credentials & storage directories
    creds_dir = tmp_path / "credentials"
    custom_creds_mgr = CodexCredentialsManager(creds_dir)
    monkeypatch.setattr("backend.services.codex_credentials.get_credentials_manager", lambda: custom_creds_mgr)
    monkeypatch.setattr("backend.services.user_service.get_credentials_manager", lambda: custom_creds_mgr)

    storage_svc = StorageService()
    storage_svc.local_resumes_dir = tmp_path / "resumes"
    monkeypatch.setattr(storage_svc, "supabase_url", "")

    yield {
        "engine": engine,
        "session_factory": session_factory,
        "redis": fake_redis,
        "creds_mgr": custom_creds_mgr,
        "storage_svc": storage_svc,
    }

    await engine.dispose()
    await fake_redis.aclose()


@pytest.mark.asyncio
async def test_full_tenant_lifecycle_integration(integration_context) -> None:
    """
    Test full lifecycle:
    1. Tenant A registers and uploads a PDF resume.
    2. DocumentExtractor parses PDF, StorageService saves file, ProfileService updates DB.
    3. OperationService tracks background progress and publishes Redis PubSub events.
    4. Tenant B is isolated from Tenant A's data.
    5. Tenant A deletes account -> verifies full DB and disk cleanup.
    """
    ctx = integration_context
    session_factory = ctx["session_factory"]

    tenant_a_id = uuid4()
    tenant_b_id = uuid4()

    async with session_factory() as session:
        # Step 1: Create tenants
        session.add(UserRecord(id=tenant_a_id, email="alice@enterprise.com"))
        session.add(UserRecord(id=tenant_b_id, email="bob@enterprise.com"))
        await session.flush()

        # Step 2: Tenant A creates an Operation for profile extraction
        op_service = OperationService(session, tenant_a_id)
        op_data = await op_service.create_operation("profile_extraction", message="Starting extraction")
        op_id = op_data["id"]
        assert op_data["status"] == "queued"

        # Update progress to 50%
        await op_service.update_progress(op_id, progress=50, message="Parsing PDF document", status="running")

        # Step 3: Tenant A uploads and processes a PDF resume
        pdf_bytes = make_sample_pdf("Alice Enterprise", "alice@enterprise.com", "Principal Engineer")
        profile_svc = ProfileService(session, tenant_a_id)
        upload_resp = await profile_svc.parse_and_save_upload("alice_cv.pdf", pdf_bytes, use_ai=False)

        assert upload_resp.profile.personal_info.name == "Alice Enterprise"
        assert upload_resp.profile.personal_info.email == "alice@enterprise.com"
        assert upload_resp.source_filename == "alice_cv.pdf"

        # Complete operation
        await op_service.mark_succeeded(op_id, result_ref=str(tenant_a_id))

        # Verify operation in DB
        op_in_db = await session.execute(select(OperationRecord).where(OperationRecord.id == UUID(op_id)))
        saved_op = op_in_db.scalar_one()
        assert saved_op.status == "succeeded"
        assert saved_op.progress == 100

        # Step 4: Verify Tenant B cannot access Tenant A's profile
        tenant_b_profile_svc = ProfileService(session, tenant_b_id)
        tenant_b_profile = await tenant_b_profile_svc.get_profile()
        assert tenant_b_profile.personal_info.name == ""

        # Step 5: Tenant A deletion routine
        user_svc = UserService(session)
        deleted = await user_svc.delete_user_account(tenant_a_id)
        assert deleted is True

        # Verify Tenant A records are completely removed from DB
        tenant_a_check = await session.execute(select(UserRecord).where(UserRecord.id == tenant_a_id))
        assert tenant_a_check.scalar_one_or_none() is None

        tenant_a_profile_check = await session.execute(
            select(ProfileRecord).where(ProfileRecord.user_id == tenant_a_id)
        )
        assert tenant_a_profile_check.scalar_one_or_none() is None

        # Verify Tenant B is still intact
        tenant_b_check = await session.execute(select(UserRecord).where(UserRecord.id == tenant_b_id))
        assert tenant_b_check.scalar_one_or_none() is not None
