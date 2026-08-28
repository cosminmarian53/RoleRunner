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

    async def fetch_job_page_content(self, job_url: str) -> str:
        """Fetch full job posting page HTML and extract clean readable description text."""
        if not job_url or not job_url.startswith(("http://", "https://")):
            return ""
        try:
            resp = await self.client.get(job_url)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. Try JSON-LD JobPosting schema first (handles Ashby, Greenhouse, Lever, etc.)
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    import json

                    raw_json = script.string or ""
                    if not raw_json.strip():
                        continue
                    data = json.loads(raw_json)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            raw_desc = item.get("description", "")
                            if raw_desc and len(raw_desc.strip()) > 100:
                                s_desc = BeautifulSoup(raw_desc, "html.parser")
                                desc_text = s_desc.get_text(separator="\n").strip()
                                lines = [line.strip() for line in desc_text.split("\n") if line.strip()]
                                if lines:
                                    return "\n\n".join(lines[:200])
                except Exception:
                    pass

            # 2. Fallback to HTML container extraction
            for el in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "button"]):
                el.decompose()
            text = soup.get_text(separator="\n").strip()
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n\n".join(lines[:120])
        except Exception as exc:
            logger.debug("Failed to fetch full job page content for %s: %s", job_url, exc)
            return ""
