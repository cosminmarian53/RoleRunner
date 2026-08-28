"""Lever API scraper for company job boards."""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from backend.models.job import JobListing, JobSource
from backend.scrapers.http_client import SafeAsyncClient

logger = logging.getLogger(__name__)

LEVER_BOARD_URL_PATTERN = re.compile(r"(?:jobs\.lever\.co|api\.lever\.co/v0/postings)/([a-zA-Z0-9_-]+)")


def extract_lever_slug(target: str) -> str | None:
    """Extract lever company slug from URL or clean slug input."""
    target_clean = target.strip()
    match = LEVER_BOARD_URL_PATTERN.search(target_clean)
    if match:
        return match.group(1)

    if "/" not in target_clean and "." not in target_clean and target_clean:
        return target_clean
    return None


class LeverScraper:
    """Fetches job listings directly from Lever postings JSON API."""

    def __init__(self, client: SafeAsyncClient | None = None) -> None:
        self.client = client or SafeAsyncClient()

    async def fetch_jobs(self, board_slug_or_url: str, *, company_name: str = "") -> list[JobListing]:
        """Fetch and parse all active jobs for a company from Lever."""
        slug = extract_lever_slug(board_slug_or_url)
        if not slug:
            logger.warning("Could not determine Lever slug from: %s", board_slug_or_url)
            return []

        company = company_name or slug.replace("-", " ").replace("_", " ").title()
        api_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"

        try:
            resp = await self.client.get(api_url)
            if resp.status_code != 200:
                logger.info("Lever board %s returned status %d", slug, resp.status_code)
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
        except Exception as exc:
            logger.warning("Error fetching Lever board %s: %s", slug, exc)
            return []

        listings: list[JobListing] = []

        for item in data:
            title = (item.get("text") or "").strip()
            if not title:
                continue

            link = item.get("hostedUrl") or item.get("applyUrl") or ""
            categories: dict[str, Any] = item.get("categories") or {}
            location = categories.get("location") or ""
            commitment = categories.get("commitment") or ""
            team = categories.get("team") or ""

            # Description plain or HTML
            plain_description = item.get("descriptionPlain") or ""
            if not plain_description and item.get("description"):
                soup = BeautifulSoup(item["description"], "html.parser")
                plain_description = soup.get_text(separator="\n").strip()

            summary = plain_description[:300].strip() if plain_description else title

            tags = [t for t in [team, commitment] if t]

            listing = JobListing(
                title=title,
                company=company,
                link=link,
                summary=summary,
                description=plain_description,
                source=JobSource.COMPANY_CAREER,
                location=location,
                employment_type=commitment,
                source_platform="lever",
                source_url=link,
                tags=tags,
            )
            listings.append(listing)

        return listings
