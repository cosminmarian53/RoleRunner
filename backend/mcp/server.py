"""Official Python Model Context Protocol (MCP) server for job scouting."""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from backend.scrapers.ddg_search import DDGJobSearcher
from backend.scrapers.generic import GenericCareerScraper
from backend.scrapers.greenhouse import GreenhouseScraper
from backend.scrapers.http_client import safe_fetch_text
from backend.scrapers.lever import LeverScraper

logger = logging.getLogger(__name__)

mcp = MCPServer("JobBot")

_greenhouse = GreenhouseScraper()
_lever = LeverScraper()
_generic = GenericCareerScraper()
_ddg = DDGJobSearcher()


@mcp.tool()
async def search_company_careers(target: str, company_name: str = "") -> list[dict[str, Any]]:
    """
    Search direct company career pages or job board slugs (Greenhouse, Lever, or generic URL).

    Args:
        target: Company slug (e.g. 'stripe', 'vercel') or full careers URL.
        company_name: Optional display name for company.
    """
    jobs = await _greenhouse.fetch_jobs(target, company_name=company_name)
    if not jobs:
        jobs = await _lever.fetch_jobs(target, company_name=company_name)
    if not jobs and target.startswith(("http://", "https://")):
        jobs = await _generic.fetch_jobs(target, company_name=company_name)

    return [j.model_dump(mode="json") for j in jobs]


@mcp.tool()
async def search_job_boards(query: str, board_urls: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Search across major ATS job boards (Greenhouse, Lever, Ashby) for specific queries.

    Args:
        query: Search keywords (e.g. 'Senior Python Engineer').
        board_urls: Optional specific board domain filters.
    """
    default_boards = ["boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com"]
    filters = board_urls or default_boards
    jobs = await _ddg.search(query, site_filters=filters)
    return [j.model_dump(mode="json") for j in jobs]


@mcp.tool()
async def web_search_jobs(query: str, location: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """
    Perform an open web search for job listings via DuckDuckGo.

    Args:
        query: Search keywords or role title.
        location: Geographic or remote location filter.
        limit: Max results (1-50).
    """
    jobs = await _ddg.search(query, location=location, limit=limit)
    return [j.model_dump(mode="json") for j in jobs]


@mcp.tool()
async def fetch_job_posting(url: str) -> str:
    """
    Safely fetch the HTML or plain text of a job posting URL with SSRF protection.

    Args:
        url: Absolute HTTP/HTTPS job posting URL.
    """
    return await safe_fetch_text(url)


def run_stdio_server() -> None:
    """Run the MCP server over standard input/output."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio_server()
