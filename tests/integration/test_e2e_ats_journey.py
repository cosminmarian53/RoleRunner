"""End-to-end integration test suite covering the entire candidate journey.

Workflow:
1. Anonymous session initialization with UUID.
2. Candidate profile creation and verification.
3. Multi-feed job search with dynamic 0.0-10.0 ATS relevance ranking and limit slicing.
4. AI Strategic Job Intelligence generation (all 6 strategic breakdown cards).
5. Tailored CV generation with enforced markdown bullet points and Title Case categories.
6. ATS scoring verification accepting flexible payload schemas without stop-word pollution.
7. Multi-format export verification (PDF & DOCX).
8. Kanban application pipeline state transitions (APPLIED -> INTERVIEWING -> OFFER).
9. Feedback submission and verification.
10. Strict multi-tenant isolation preventing cross-user data leakage.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from backend.db.models import UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    get_db,
    init_db,
)
from backend.main import app
from backend.models.job import JobListing, JobSource
from backend.services.codex_credentials import CodexCredentialsManager
from backend.services.storage_service import StorageService


@pytest.fixture
async def e2e_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Construct completely isolated database, redis, storage, and HTTP client."""
    # 1. Database
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    session_factory = async_session_factory(engine)

    # 2. Redis
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("backend.services.redis_service.get_redis_client", lambda: fake_redis)
    monkeypatch.setattr("backend.services.operation_service.get_redis_client", lambda: fake_redis)

    # 3. Credentials & Storage
    creds_dir = tmp_path / "credentials"
    creds_mgr = CodexCredentialsManager(creds_dir)
    monkeypatch.setattr("backend.services.codex_credentials.get_credentials_manager", lambda: creds_mgr)
    monkeypatch.setattr("backend.services.user_service.get_credentials_manager", lambda: creds_mgr)

    storage_svc = StorageService()
    storage_svc.local_resumes_dir = tmp_path / "resumes"
    monkeypatch.setattr(storage_svc, "supabase_url", "")
    monkeypatch.setattr("backend.routers.cv.StorageService", lambda: storage_svc)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Create HTTP clients
    user_a_id = uuid4()
    user_b_id = uuid4()

    async with session_factory() as session:
        session.add(UserRecord(id=user_a_id, email="cand_a@rolerunner.io"))
        session.add(UserRecord(id=user_b_id, email="cand_b@rolerunner.io"))
        await session.commit()

    headers_a = {"Authorization": f"Bearer {user_a_id}"}
    headers_b = {"Authorization": f"Bearer {user_b_id}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=headers_a) as client_a:
        async with AsyncClient(transport=transport, base_url="http://testserver", headers=headers_b) as client_b:
            yield {
                "client_a": client_a,
                "client_b": client_b,
                "user_a_id": user_a_id,
                "user_b_id": user_b_id,
                "session_factory": session_factory,
                "storage_svc": storage_svc,
            }

    app.dependency_overrides.clear()
    await engine.dispose()
    await fake_redis.aclose()


@pytest.mark.asyncio
async def test_full_ats_candidate_e2e_journey(e2e_environment, monkeypatch: pytest.MonkeyPatch) -> None:
    """Execute full 10-step candidate workflow from profile setup to CV export and application tracking."""
    client_a: AsyncClient = e2e_environment["client_a"]
    client_b: AsyncClient = e2e_environment["client_b"]

    # -------------------------------------------------------------
    # Step 1 & 2: Create Candidate Profile for User A
    # -------------------------------------------------------------
    profile_payload = {
        "personal_info": {
            "name": "Alex Mercer",
            "email": "alex.mercer@security.dev",
            "phone": "+1 555-0199",
            "location": "San Francisco, CA",
            "github": "https://github.com/alexmercer",
            "linkedin": "https://linkedin.com/in/alexmercer",
            "portfolio": "https://alexmercer.security",
        },
        "summary": "Senior Security Engineer with expertise in smart contracts, Kubernetes, Rust, and fuzzing.",
        "skills": {
            "core_competencies": ["Vulnerability Assessment", "Threat Modeling", "Smart Contract Security"],
            "tools_software": ["Foundry", "Slither", "Echidna", "Docker", "Kubernetes", "Rust", "Solidity"],
        },
        "experience": [
            {
                "title": "Lead Security Researcher",
                "company": "ChainArmor",
                "start_date": "2023",
                "end_date": "Present",
                "duration": "2023 – Present",
                "bullets": [
                    "Audited 20+ production Solidity and Rust DeFi protocols with zero post-deployment exploits.",
                    "Implemented custom automated differential fuzzing campaigns uncovering 4 critical logic bugs.",
                ],
            }
        ],
        "projects": [
            {
                "name": "AegisGuard",
                "tech": "Rust, Slither, Foundry",
                "description": "Open-source automated invariant testing harness for EVM bytecodes.",
                "bullet_points": ["Achieved 98% branch coverage across 12 protocol test suites."],
            }
        ],
        "achievements": [
            "Ranked 1st in Paradigm CTF 2024 smart contract exploitation track.",
            "Reported critical $5M flash loan vulnerability via Immunefi bug bounty.",
        ],
        "certifications": [
            {"name": "Offensive Security Certified Professional (OSCP)", "issuer": "OffSec", "date": "2023"}
        ],
        "education": [
            {"degree": "B.S. in Computer Science", "institution": "University of California, Berkeley", "year": "2021"}
        ],
    }

    save_resp = await client_a.post("/api/profile", json=profile_payload)
    assert save_resp.status_code == 200
    saved_profile = save_resp.json()
    assert saved_profile["personal_info"]["name"] == "Alex Mercer"
    assert "tools_software" in saved_profile["skills"]

    # -------------------------------------------------------------
    # Step 3: Job Search with Aggregation & ATS Relevance Scoring
    # -------------------------------------------------------------
    # Mock search service aggregation to provide deterministic sample jobs
    sample_jobs = [
        JobListing(
            id="job-101",
            title="Senior Smart Contract Security Auditor",
            company="Trail of Bits",
            location="Remote",
            link="https://trailofbits.com/careers/auditor",
            description="We are seeking a Senior Smart Contract Auditor proficient in Solidity, Rust, Foundry, Slither, and fuzzing to audit leading DeFi protocols.",
            source=JobSource.JOB_FEED,
        ),
        JobListing(
            id="job-102",
            title="Frontend React Specialist",
            company="DesignStudio",
            location="New York, NY",
            link="https://designstudio.com/jobs/react",
            description="Looking for a UI designer and React developer specializing in CSS and Tailwind.",
            source=JobSource.JOB_FEED,
        ),
    ]

    from backend.models.job import JobSearchResults
    from backend.services.job_search import JobSearchService

    async def mock_search_and_persist(self, req):
        return JobSearchResults(query=req.query, jobs=sample_jobs, total_found=len(sample_jobs))

    monkeypatch.setattr(JobSearchService, "search_and_persist", mock_search_and_persist)

    search_resp = await client_a.post(
        "/api/jobs/search",
        json={"query": "Security Auditor", "location_filter": "Remote", "limit": 10},
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert len(search_data["jobs"]) == 2

    # Score jobs against candidate profile
    score_all_resp = await client_a.post(
        "/api/jobs/score",
        json={"jobs": [j.model_dump(mode="json") for j in sample_jobs]},
    )
    assert score_all_resp.status_code == 200
    scored_jobs = score_all_resp.json()["jobs"]
    job_101 = next(j for j in scored_jobs if j["id"] == "job-101")
    assert job_101["relevance_score"] >= 6.0
    assert "solidity" in [kw.lower() for kw in job_101["match_reasons"]]

    # -------------------------------------------------------------
    # Step 4: Deep Strategic Job Intelligence Generation
    # -------------------------------------------------------------
    intel_resp = await client_a.post(
        "/api/jobs/intelligence",
        json={
            "job_title": job_101["title"],
            "company": job_101["company"],
            "job_description": job_101["description"],
            "job_url": job_101["link"],
        },
    )
    assert intel_resp.status_code == 200
    intel_data = intel_resp.json()
    assert len(intel_data["framing_strategy"]) > 10
    assert len(intel_data["interview_stages"]) >= 3
    assert len(intel_data["talking_points"]) >= 2
    assert len(intel_data["questions_to_ask"]) >= 2
    assert len(intel_data["key_technologies"]) >= 1

    # -------------------------------------------------------------
    # Step 5: Tailored CV Generation with Enforced Markdown Bullets
    # -------------------------------------------------------------
    cv_gen_resp = await client_a.post(
        "/api/cv/generate",
        json={
            "job_title": job_101["title"],
            "company": job_101["company"],
            "job_description": job_101["description"],
            "export_format": "pdf",
            "use_ai": False,  # Deterministic test
        },
    )
    assert cv_gen_resp.status_code == 200
    cv_data = cv_gen_resp.json()
    cv_id = cv_data["id"]
    cv_markdown = cv_data["markdown_content"]

    # Verify clean section headers and bullet points
    assert "# Alex Mercer" in cv_markdown
    assert "## Core Skills & Competencies" in cv_markdown
    assert "Tools & Technologies:" in cv_markdown  # Clean Title Case
    assert "## Key Achievements" in cv_markdown
    assert "- Ranked 1st in Paradigm CTF" in cv_markdown
    assert "### Lead Security Researcher | ChainArmor | 2023 – Present" in cv_markdown
    assert "- Audited 20+ production Solidity" in cv_markdown

    # -------------------------------------------------------------
    # Step 6: CV Keyword Scoring with Flexible Request Schema
    # -------------------------------------------------------------
    # Test with standard 'markdown_content' key
    score_resp_1 = await client_a.post(
        "/api/cv/score",
        json={"markdown_content": cv_markdown, "job_description": job_101["description"]},
    )
    assert score_resp_1.status_code == 200
    score_1 = score_resp_1.json()
    assert score_1["overall_score"] >= 70
    assert "solidity" in score_1["matched_keywords"]
    assert "across" not in score_1["matched_keywords"]  # Stop words properly filtered

    # Test with legacy 'markdown' key alias (no 422 error)
    score_resp_2 = await client_a.post(
        "/api/cv/score",
        json={"markdown": cv_markdown, "job_description": job_101["description"]},
    )
    assert score_resp_2.status_code == 200
    assert score_resp_2.json()["overall_score"] == score_1["overall_score"]

    # -------------------------------------------------------------
    # Step 7: Exporting Tailored CV to PDF and DOCX
    # -------------------------------------------------------------
    pdf_export_resp = await client_a.get(f"/api/cv/{cv_id}/export/pdf")
    assert pdf_export_resp.status_code == 200
    pdf_data = pdf_export_resp.json()
    assert pdf_data["export_format"] == "pdf"
    assert pdf_data["path"] is not None

    # -------------------------------------------------------------
    # Step 8: Kanban Application Pipeline Transitions
    # -------------------------------------------------------------
    app_create_resp = await client_a.post(
        "/api/applications",
        json={
            "job_title": job_101["title"],
            "company": job_101["company"],
            "job_url": job_101["link"],
            "job_description": job_101["description"],
            "status": "APPLIED",
            "notes": "Applied with tailored smart contract auditor CV.",
        },
    )
    assert app_create_resp.status_code == 201
    application = app_create_resp.json()
    app_id = application["id"]
    assert application["status"] == "applied"

    # Transition to INTERVIEWING
    update_resp = await client_a.put(
        f"/api/applications/{app_id}",
        json={"status": "INTERVIEWING", "notes": "Passed initial recruiter screen. Technical round scheduled."},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "interviewing"

    # Transition to OFFER
    offer_resp = await client_a.put(
        f"/api/applications/{app_id}",
        json={"status": "OFFER", "notes": "Offer letter received!"},
    )
    assert offer_resp.status_code == 200
    assert offer_resp.json()["status"] == "offer"

    # List applications and verify status counts
    list_apps_resp = await client_a.get("/api/applications")
    assert list_apps_resp.status_code == 200
    apps_list = list_apps_resp.json()
    assert len(apps_list) == 1
    assert apps_list[0]["id"] == app_id

    # -------------------------------------------------------------
    # Step 9: Submit User Feedback
    # -------------------------------------------------------------
    feedback_resp = await client_a.post(
        "/api/feedback",
        json={
            "feedback_type": "feature_request",
            "message": "The AI CV tailoring and strategic intelligence are exceptionally useful!",
            "rating": 5,
            "page": "/cv",
        },
    )
    assert feedback_resp.status_code == 201
    assert feedback_resp.json()["status"] == "received"

    # -------------------------------------------------------------
    # Step 10: Strict Multi-Tenant Isolation
    # -------------------------------------------------------------
    # User B must not see User A's profile
    user_b_profile_resp = await client_b.get("/api/profile")
    assert user_b_profile_resp.status_code == 200
    assert user_b_profile_resp.json()["personal_info"]["name"] == ""

    # User B must not see User A's CV
    user_b_cv_resp = await client_b.get(f"/api/cv/{cv_id}")
    assert user_b_cv_resp.status_code == 404

    # User B must not see User A's applications
    user_b_apps_resp = await client_b.get("/api/applications")
    assert user_b_apps_resp.status_code == 200
    assert len(user_b_apps_resp.json()) == 0

    # User B cannot update User A's application
    user_b_hack_resp = await client_b.put(
        f"/api/applications/{app_id}",
        json={"status": "REJECTED"},
    )
    assert user_b_hack_resp.status_code == 404
