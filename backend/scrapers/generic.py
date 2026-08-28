"""Generic career page scraper using HTML heuristic parsing."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from backend.models.job import JobListing, JobSource
from backend.scrapers.http_client import SafeAsyncClient

logger = logging.getLogger(__name__)

JOB_LINK_PATTERNS = [
    re.compile(r"/(?:jobs?|careers?|positions?|openings?|posting)/[a-zA-Z0-9_-]+", re.IGNORECASE),
    re.compile(r"gh_jid=\d+"),
]


class GenericCareerScraper:
    """Scrapes company HTML career pages for open roles."""

    def __init__(self, client: SafeAsyncClient | None = None) -> None:
        self.client = client or SafeAsyncClient()

    async def fetch_jobs(self, career_url: str, *, company_name: str = "") -> list[JobListing]:
        """Fetch and extract job listing links from an HTML career page."""
        parsed = urlparse(career_url)
        company = company_name or (parsed.netloc.split(".")[0].title() if parsed.netloc else "Company")

        try:
            resp = await self.client.get(career_url)
            if resp.status_code != 200:
                logger.info("Career page %s returned status %d", career_url, resp.status_code)
                return []
            html = resp.text
        except Exception as exc:
            logger.warning("Error fetching career page %s: %s", career_url, exc)
            return []

        soup = BeautifulSoup(html, "html.parser")
        listings: list[JobListing] = []
        seen_links: set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            raw_href = a_tag.get("href")
            if not raw_href:
                continue
            href = str(raw_href)
            full_url = urljoin(career_url, href)
            title = a_tag.get_text(separator=" ").strip()

            if not title or len(title) < 4 or len(title) > 120:
                continue

            # Check if link looks like a job link
            is_job = any(pat.search(full_url) for pat in JOB_LINK_PATTERNS)
            if is_job and full_url not in seen_links:
                seen_links.add(full_url)
                listing = JobListing(
                    title=title,
                    company=company,
                    link=full_url,
                    summary=f"{title} at {company}",
                    source=JobSource.COMPANY_CAREER,
                    source_platform="generic_html",
                    source_url=full_url,
                )
                listings.append(listing)

        return listings
