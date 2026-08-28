"""Unit tests for Greenhouse, Lever, Generic scrapers, and JobSearchService."""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    init_db,
)
from backend.models.job import JobSearchRequest
from backend.scrapers.generic import GenericCareerScraper
from backend.scrapers.greenhouse import GreenhouseScraper
from backend.scrapers.http_client import SafeAsyncClient
from backend.scrapers.lever import LeverScraper
from backend.services.job_search import JobSearchService, compute_url_hash


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
async def test_greenhouse_scraper_parses_job_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_json = {
        "jobs": [
            {
                "id": 12345,
                "title": "Senior Backend Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
                "location": {"name": "Remote, US"},
                "departments": [{"name": "Engineering"}],
                "content": "<p>We are seeking a <strong>Python</strong> expert.</p>",
            }
        ]
    }

    async def fake_get(self, url, *args, **kwargs):
        return httpx.Response(200, json=fake_json, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    scraper = GreenhouseScraper()
    jobs = await scraper.fetch_jobs("https://boards.greenhouse.io/acme")

    assert len(jobs) == 1
    assert jobs[0].title == "Senior Backend Engineer"
    assert jobs[0].company == "Acme"
    assert jobs[0].location == "Remote, US"
    assert "Python" in jobs[0].description
    assert jobs[0].source_platform == "greenhouse"


@pytest.mark.asyncio
async def test_lever_scraper_parses_job_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_json = [
        {
            "id": "lever-99",
            "text": "Staff Data Engineer",
            "hostedUrl": "https://jobs.lever.co/initech/lever-99",
            "categories": {
                "location": "San Francisco, CA",
                "commitment": "Full-time",
                "team": "Data Platform",
            },
            "descriptionPlain": "Build real-time pipeline architecture.",
        }
    ]

    async def fake_get(self, url, *args, **kwargs):
        return httpx.Response(200, json=fake_json, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    scraper = LeverScraper()
    jobs = await scraper.fetch_jobs("initech")

    assert len(jobs) == 1
    assert jobs[0].title == "Staff Data Engineer"
    assert jobs[0].company == "Initech"
    assert jobs[0].employment_type == "Full-time"
    assert jobs[0].source_platform == "lever"


@pytest.mark.asyncio
async def test_generic_career_scraper_finds_job_links(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html>
        <body>
            <a href="/careers/frontend-lead">Frontend Lead</a>
            <a href="/about-us">About Us</a>
            <a href="https://example.com/jobs/1234">DevOps Architect</a>
        </body>
    </html>
    """

    async def fake_get(self, url, *args, **kwargs):
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    scraper = GenericCareerScraper()
    jobs = await scraper.fetch_jobs("https://mycompany.com/careers")

    assert len(jobs) == 2
    titles = [j.title for j in jobs]
    assert "Frontend Lead" in titles
    assert "DevOps Architect" in titles


@pytest.mark.asyncio
async def test_job_search_service_aggregation_and_deduplication(
    in_memory_db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = in_memory_db_session
    user_id = uuid4()
    session.add(UserRecord(id=user_id, email="searcher@test.local"))
    await session.flush()

    service = JobSearchService(session, user_id)

    # Mock scrapers to return duplicate URLs
    shared_link = "https://boards.greenhouse.io/acme/jobs/100"

    async def fake_gh_fetch(*args, **kwargs):
        from backend.models.job import JobListing, JobSource

        return [JobListing(title="Backend Dev", link=shared_link, source=JobSource.COMPANY_CAREER)]

    async def fake_ddg_search(*args, **kwargs):
        from backend.models.job import JobListing, JobSource

        return [
            JobListing(title="Backend Dev Dup", link=shared_link, source=JobSource.WEB_SEARCH),
            JobListing(title="Unique SRE Role", link="https://jobs.lever.co/acme/200", source=JobSource.WEB_SEARCH),
        ]

    async def empty_feed(*args, **kwargs):
        return []

    monkeypatch.setattr(service.greenhouse, "fetch_jobs", fake_gh_fetch)
    monkeypatch.setattr(service.ddg, "search", fake_ddg_search)
    monkeypatch.setattr(service.remotive, "search", empty_feed)
    monkeypatch.setattr(service.jobicy, "search", empty_feed)
    monkeypatch.setattr(service.arbeitnow, "search", empty_feed)

    req = JobSearchRequest(query="Backend", target_companies=["acme"])
    results = await service.search_and_persist(req)

    # Assert deduplicated to 2 unique jobs
    assert len(results.jobs) == 2
    links = [j.link for j in results.jobs]
    assert shared_link in links
    assert "https://jobs.lever.co/acme/200" in links

    # Verify saved jobs in Postgres
    saved = await service.list_saved_jobs()
    assert len(saved) == 2


def test_compute_url_hash() -> None:
    h1 = compute_url_hash("https://example.com/jobs/123/")
    h2 = compute_url_hash("https://example.com/jobs/123#overview")
    assert h1 == h2


@pytest.mark.asyncio
async def test_remotive_feed_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from backend.scrapers.job_feeds import RemotiveFeed

    feed = RemotiveFeed()

    async def fake_get(url, **kwargs):
        data = {
            "jobs": [
                {
                    "id": 123,
                    "url": "https://remotive.com/job/123",
                    "title": "Senior Security Auditor",
                    "company_name": "Trail of Bits",
                    "candidate_required_location": "Worldwide",
                    "publication_date": "2026-08-25T12:00:00",
                    "salary": "$150,000 - $180,000",
                    "job_type": "full_time",
                    "category": "Security",
                    "tags": ["solidity", "rust"],
                    "description": "<p>We are looking for a security researcher.</p>",
                }
            ]
        }
        return httpx.Response(200, json=data, request=httpx.Request("GET", url))

    monkeypatch.setattr(feed.client, "get", fake_get)
    jobs = await feed.search("security")
    assert len(jobs) == 1
    assert jobs[0].title == "Senior Security Auditor"
    assert jobs[0].company == "Trail of Bits"
    assert jobs[0].location == "Worldwide"
    assert jobs[0].salary == "$150,000 - $180,000"
    assert jobs[0].employment_type == "Full Time"
    assert jobs[0].source_platform == "remotive"


@pytest.mark.asyncio
async def test_jobicy_feed_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from backend.scrapers.job_feeds import JobicyFeed

    feed = JobicyFeed()

    async def fake_get(url, **kwargs):
        data = {
            "jobs": [
                {
                    "id": 456,
                    "url": "https://jobicy.com/job/456",
                    "jobTitle": "Lead AppSec Engineer",
                    "companyName": "Coinbase",
                    "jobGeo": "USA, Remote",
                    "pubDate": "2026-08-27",
                    "annualSalaryMin": "140000",
                    "annualSalaryMax": "190000",
                    "salaryCurrency": "USD",
                    "jobType": ["Full-Time"],
                    "jobIndustry": ["Crypto", "Security"],
                    "jobDescription": "<p>Protect digital assets.</p>",
                }
            ]
        }
        return httpx.Response(200, json=data, request=httpx.Request("GET", url))

    monkeypatch.setattr(feed.client, "get", fake_get)
    jobs = await feed.search("security")
    assert len(jobs) == 1
    assert jobs[0].title == "Lead AppSec Engineer"
    assert jobs[0].company == "Coinbase"
    assert "140000" in jobs[0].salary
    assert jobs[0].employment_type == "Full-Time"
    assert jobs[0].source_platform == "jobicy"


@pytest.mark.asyncio
async def test_deep_page_inspector_jsonld(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from backend.scrapers.page_inspector import DeepPageInspector

    inspector = DeepPageInspector()

    html_content = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org/",
          "@type": "JobPosting",
          "title": "Smart Contract Auditor",
          "hiringOrganization": {
            "@type": "Organization",
            "name": "CertiK"
          },
          "jobLocation": {
            "@type": "Place",
            "address": {
              "@type": "PostalAddress",
              "addressLocality": "New York",
              "addressCountry": "USA"
            }
          },
          "datePosted": "2026-08-20",
          "employmentType": "FULL_TIME"
        }
        </script>
      </head>
      <body>
        <h1>Smart Contract Auditor</h1>
      </body>
    </html>
    """

    async def fake_get(url, **kwargs):
        return httpx.Response(200, text=html_content, request=httpx.Request("GET", url))

    monkeypatch.setattr(inspector.client, "get", fake_get)
    meta = await inspector.inspect("https://example.com/jobs/99")
    assert not meta.is_dead
    assert not meta.is_expired
    assert meta.title == "Smart Contract Auditor"
    assert meta.company == "CertiK"
    assert "New York" in meta.location
    assert meta.date_posted == "2026-08-20"
    assert meta.employment_type == "Full-time"


@pytest.mark.asyncio
async def test_deep_page_inspector_detects_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from backend.scrapers.page_inspector import DeepPageInspector

    inspector = DeepPageInspector()

    html_content = """
    <html>
      <body>
        <h1>Position Closed</h1>
        <p>This job is no longer accepting applications.</p>
      </body>
    </html>
    """

    async def fake_get(url, **kwargs):
        return httpx.Response(200, text=html_content, request=httpx.Request("GET", url))

    monkeypatch.setattr(inspector.client, "get", fake_get)
    meta = await inspector.inspect("https://example.com/jobs/closed")
    assert meta.is_expired
