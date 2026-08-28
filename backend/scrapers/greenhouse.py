"""Greenhouse API scraper for company job boards."""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from backend.models.job import JobListing, JobSource
from backend.scrapers.http_client import SafeAsyncClient

logger = logging.getLogger(__name__)

GREENHOUSE_BOARD_URL_PATTERN = re.compile(
    r"(?:boards\.greenhouse\.io|job-boards\.greenhouse\.io|boards-api\.greenhouse\.io/v1/boards)/([a-zA-Z0-9_-]+)"
)


def extract_greenhouse_slug(target: str) -> str | None:
    """Extract greenhouse company slug from URL or clean slug input."""
    target_clean = target.strip()
    match = GREENHOUSE_BOARD_URL_PATTERN.search(target_clean)
    if match:
        return match.group(1)

    if "/" not in target_clean and "." not in target_clean and target_clean:
        return target_clean
    return None


class GreenhouseScraper:
    """Fetches job listings directly from Greenhouse board JSON API."""

    def __init__(self, client: SafeAsyncClient | None = None) -> None:
        self.client = client or SafeAsyncClient()

    async def fetch_jobs(self, board_slug_or_url: str, *, company_name: str = "") -> list[JobListing]:
        """Fetch and parse all active jobs for a company from Greenhouse."""
        slug = extract_greenhouse_slug(board_slug_or_url)
        if not slug:
            logger.warning("Could not determine Greenhouse slug from: %s", board_slug_or_url)
            return []

        company = company_name or slug.replace("-", " ").replace("_", " ").title()
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

        try:
            resp = await self.client.get(api_url)
            if resp.status_code != 200:
                logger.info("Greenhouse board %s returned status %d", slug, resp.status_code)
                return []
            data: dict[str, Any] = resp.json()
        except Exception as exc:
            logger.warning("Error fetching Greenhouse board %s: %s", slug, exc)
            return []

        raw_jobs = data.get("jobs", [])
        listings: list[JobListing] = []

        for item in raw_jobs:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            job_id = str(item.get("id") or "")
            link = item.get("absolute_url") or f"https://boards.greenhouse.io/{slug}/jobs/{job_id}"
            location = (item.get("location") or {}).get("name", "")

            # Parse description
            raw_content = item.get("content") or ""
            soup = BeautifulSoup(raw_content, "html.parser")
            plain_description = soup.get_text(separator="\n").strip()
            summary = plain_description[:300].strip() if plain_description else title

            # Tags / Departments
            departments = [d.get("name") for d in item.get("departments", []) if d.get("name")]

            listing = JobListing(
                title=title,
                company=company,
                link=link,
                summary=summary,
                description=plain_description,
                source=JobSource.COMPANY_CAREER,
                location=location,
                source_platform="greenhouse",
                source_url=link,
                tags=departments,
            )
            listings.append(listing)

        return listings
