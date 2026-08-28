"""DuckDuckGo web search aggregator for job discovery across multiple boards."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ddgs import DDGS

from backend.models.job import JobListing, JobSource

logger = logging.getLogger(__name__)

DEFAULT_JOB_SITES = [
    "boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
]


class DDGJobSearcher:
    """Discovers job postings across the web using DuckDuckGo search."""

    def __init__(self, max_results: int = 25) -> None:
        self.max_results = max_results

    def _sync_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Run blocking DDGS query in background thread."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return results
        except Exception as exc:
            logger.warning("DuckDuckGo search error for query %r: %s", query, exc)
            return []

    async def search(
        self,
        query: str,
        *,
        site_filters: list[str] | None = None,
        location: str = "",
        limit: int | None = None,
    ) -> list[JobListing]:
        """Search DuckDuckGo for matching job opportunities."""
        max_res = limit or self.max_results
        search_query = query.strip()

        # Append site filters if requested
        sites = site_filters or []
        if sites:
            site_query = " OR ".join(f"site:{s.strip()}" for s in sites if s.strip())
            search_query = f"({site_query}) {search_query}"

        if location.strip():
            search_query = f"{search_query} {location.strip()}"

        raw_results = await asyncio.to_thread(self._sync_search, search_query, max_res)
        listings: list[JobListing] = []

        for item in raw_results:
            title = (item.get("title") or "").strip()
            href = (item.get("href") or "").strip()
            body = (item.get("body") or "").strip()

            if not title or not href:
                continue

            # Attempt to infer company from title (e.g. "Software Engineer at Company")
            company = ""
            if " at " in title:
                company = title.split(" at ")[-1].split(" - ")[0].strip()
            elif " - " in title:
                parts = title.split(" - ")
                if len(parts) >= 2:
                    company = parts[1].strip()

            listing = JobListing(
                title=title,
                company=company,
                link=href,
                summary=body,
                description=body,
                source=JobSource.WEB_SEARCH,
                source_url=href,
            )
            listings.append(listing)

        return listings
