"""Comprehensive tests for FastAPI app, middleware, and all API routers."""

from pathlib import Path
from typing import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    get_db,
    init_db,
)
from backend.main import create_app
from backend.models.application import ApplicationStatus
from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser


@pytest.fixture
async def test_app_and_session(tmp_path: Path):
    """Provide a test FastAPI client connected to an in-memory SQLite DB and mock user."""
    test_engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(test_engine)

    session_maker = async_session_factory(test_engine)
    user_id = uuid4()

    async with session_maker() as session:
        session.add(UserRecord(id=user_id, email="router_test@apply.test"))
        await session.commit()

    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    async def override_get_current_user() -> CurrentUser:
        return CurrentUser(id=user_id, email="router_test@apply.test")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, user_id

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_health_and_readyz_probes(test_app_and_session):
    client, _ = test_app_and_session

    resp_health = await client.get("/healthz")
    assert resp_health.status_code == 200
    assert resp_health.json() == {"status": "ok"}
    assert "x-request-id" in resp_health.headers


@pytest.mark.asyncio
async def test_profile_endpoints(test_app_and_session):
    client, _ = test_app_and_session

    # 1. Get profile (initial empty default)
    resp = await client.get("/api/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "personal_info" in data

    # 2. Save profile
    save_payload = {
        "personal_info": {"name": "Bob Tester", "email": "bob@test.com"},
        "summary": "Experienced Rust & Python engineer",
        "skills": {"Languages": ["Rust", "Python", "Solidity"]},
    }
    resp_save = await client.post("/api/profile", json=save_payload)
    assert resp_save.status_code == 200
    saved_data = resp_save.json()
    assert saved_data["personal_info"]["name"] == "Bob Tester"
    assert "Rust" in saved_data["skills"]["Languages"]

    # 3. Parse text
    resp_parse = await client.post(
        "/api/profile/parse-text",
        json={"text": "Email: alice@web3.io. Skills: Move, Go, Solidity."},
    )
    assert resp_parse.status_code == 200
    parse_data = resp_parse.json()
    assert "profile" in parse_data
    assert "Solidity" in str(parse_data["profile"]["skills"])


@pytest.mark.asyncio
async def test_job_search_and_scoring_endpoints(test_app_and_session, monkeypatch):
    client, _ = test_app_and_session

    # Mock DDG scraper and feeds so search is deterministic
    from backend.models.job import JobListing, JobSource
    from backend.scrapers.ddg_search import DDGJobSearcher
    from backend.scrapers.job_feeds import ArbeitnowFeed, JobicyFeed, RemotiveFeed

    async def mock_search(self, query: str, **kwargs):
        return [
            JobListing(
                title="Smart Contract Security Auditor",
                company="OpenZeppelin",
                link="https://openzeppelin.com/jobs/1",
                summary="Audit Ethereum smart contracts and DeFi protocols.",
                source=JobSource.WEB_SEARCH,
                location="Remote",
            )
        ]

    async def mock_feed_search(self, query: str, **kwargs):
        return []

    monkeypatch.setattr(DDGJobSearcher, "search", mock_search)
    monkeypatch.setattr(RemotiveFeed, "search", mock_feed_search)
    monkeypatch.setattr(JobicyFeed, "search", mock_feed_search)
    monkeypatch.setattr(ArbeitnowFeed, "search", mock_feed_search)

    # 1. POST /api/jobs/search
    search_resp = await client.post(
        "/api/jobs/search",
        json={"query": "smart contract auditor", "limit": 10},
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total_found"] >= 1
    assert search_data["jobs"][0]["company"] == "OpenZeppelin"

    # 2. GET /api/jobs
    list_resp = await client.get("/api/jobs")
    assert list_resp.status_code == 200
    saved_jobs = list_resp.json()
    assert len(saved_jobs) >= 1

    # 3. POST /api/jobs/score
    score_resp = await client.post(
        "/api/jobs/score",
        json={"jobs": [saved_jobs[0]]},
    )
    assert score_resp.status_code == 200
    scored_data = score_resp.json()
    assert len(scored_data["jobs"]) == 1
    assert scored_data["jobs"][0]["relevance_score"] is not None


@pytest.mark.asyncio
async def test_cv_generation_and_export_endpoints(test_app_and_session, monkeypatch, tmp_path):
    client, _ = test_app_and_session

    # Set storage fallback dir
    from backend.services.storage_service import StorageService

    storage = StorageService()
    storage.local_resumes_dir = tmp_path / "resumes"
    monkeypatch.setattr(storage, "supabase_url", "")

    # Save profile first
    await client.post(
        "/api/profile",
        json={
            "personal_info": {"name": "Alice Candidate", "email": "alice@cv.test"},
            "summary": "Rust, Kubernetes, and Solidity security specialist.",
            "skills": {"Languages": ["Rust", "Python", "Solidity"]},
        },
    )

    # 1. POST /api/cv/generate
    gen_resp = await client.post(
        "/api/cv/generate",
        json={
            "job_title": "Lead Security Auditor",
            "company": "Trail of Bits",
            "job_description": "We need an auditor proficient in Rust, Solidity, and security verification.",
            "export_format": "pdf",
            "use_ai": False,
        },
    )
    assert gen_resp.status_code == 200
    cv_data = gen_resp.json()
    cv_id = cv_data["id"]
    assert "Alice Candidate" in cv_data["markdown_content"]
    assert cv_data["ats_score"]["overall_score"] > 50

    # 2. GET /api/cv/{cv_id}
    get_resp = await client.get(f"/api/cv/{cv_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == cv_id

    # 3. POST /api/cv/score
    score_resp = await client.post(
        "/api/cv/score",
        json={
            "markdown_content": cv_data["markdown_content"],
            "job_description": "Looking for Solidity and Rust auditor.",
        },
    )
    assert score_resp.status_code == 200
    assert score_resp.json()["overall_score"] > 60


@pytest.mark.asyncio
async def test_application_crud_endpoints(test_app_and_session):
    client, _ = test_app_and_session

    # 1. Create application
    create_resp = await client.post(
        "/api/applications",
        json={
            "title": "Senior Rust Engineer",
            "company": "Paradigm",
            "job_url": "https://paradigm.xyz/careers/1",
            "status": "saved",
            "notes": "Met at Devcon",
        },
    )
    assert create_resp.status_code == 201
    app_data = create_resp.json()
    app_id = app_data["id"]
    assert app_data["title"] == "Senior Rust Engineer"
    assert app_data["status"] == "saved"

    # 2. Update status -> applied
    patch_resp = await client.patch(
        f"/api/applications/{app_id}",
        json={"status": "applied", "next_step": "Phone screen"},
    )
    assert patch_resp.status_code == 200
    updated_data = patch_resp.json()
    assert updated_data["status"] == "applied"
    assert updated_data["applied_at"] != ""

    # 3. Get Stats
    stats_resp = await client.get("/api/applications/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats[ApplicationStatus.APPLIED.value] == 1

    # 4. List
    list_resp = await client.get("/api/applications")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # 5. Delete
    del_resp = await client.delete(f"/api/applications/{app_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"success": True}

    # 6. Verify 404 after deletion
    check_resp = await client.get(f"/api/applications/{app_id}")
    assert check_resp.status_code == 404
    err_json = check_resp.json()
    assert err_json["code"] == "NOT_FOUND"
    assert "request_id" in err_json


@pytest.mark.asyncio
async def test_feedback_endpoint(test_app_and_session) -> None:
    client, _ = test_app_and_session
    payload = {
        "rating": 5,
        "category": "feature_request",
        "message": "Love the universal job matching! Please add Discord alerts.",
        "email": "tester@rolerunner.app",
        "page_url": "http://test/jobs",
    }
    resp = await client.post("/api/feedback", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "received"
    assert data["rating"] == 5
    assert data["category"] == "feature_request"
    assert data["message"] == payload["message"]
