"""Unit tests for official MCP server tools."""

import pytest

from backend.mcp.server import (
    fetch_job_posting,
    search_company_careers,
    search_job_boards,
    web_search_jobs,
)
from backend.models.job import JobListing, JobSource


@pytest.mark.asyncio
async def test_mcp_search_company_careers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(*args, **kwargs):
        return [
            JobListing(
                title="Lead Rust Engineer",
                company="Stripe",
                link="https://boards.greenhouse.io/stripe/jobs/1",
                source=JobSource.COMPANY_CAREER,
            )
        ]

    monkeypatch.setattr("backend.mcp.server._greenhouse.fetch_jobs", fake_fetch)

    results = await search_company_careers("stripe")
    assert len(results) == 1
    assert results[0]["title"] == "Lead Rust Engineer"
    assert results[0]["company"] == "Stripe"


@pytest.mark.asyncio
async def test_mcp_web_search_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(*args, **kwargs):
        return [
            JobListing(
                title="Fullstack Typescript",
                link="https://jobs.lever.co/vercel/2",
                source=JobSource.WEB_SEARCH,
            )
        ]

    monkeypatch.setattr("backend.mcp.server._ddg.search", fake_search)

    results = await web_search_jobs("Typescript", location="Remote", limit=5)
    assert len(results) == 1
    assert results[0]["title"] == "Fullstack Typescript"


@pytest.mark.asyncio
async def test_mcp_search_job_boards(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_ddg_search(*args, **kwargs):
        return [
            JobListing(
                title="Staff Engineer",
                link="https://jobs.ashbyhq.com/org/3",
                source=JobSource.JOB_BOARD,
            )
        ]

    monkeypatch.setattr("backend.mcp.server._ddg.search", fake_ddg_search)

    results = await search_job_boards("Staff Engineer")
    assert len(results) == 1
    assert results[0]["title"] == "Staff Engineer"


@pytest.mark.asyncio
async def test_mcp_fetch_job_posting(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_safe_fetch(url: str, **kwargs):
        return "<html><body><h1>Principal Architect</h1></body></html>"

    monkeypatch.setattr("backend.mcp.server.safe_fetch_text", fake_safe_fetch)

    content = await fetch_job_posting("https://boards.greenhouse.io/acme/jobs/123")
    assert "Principal Architect" in content
