"""Job search orchestration and aggregation service with multi-board scrapers."""

from __future__ import annotations

import hashlib
import logging
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import JobRecord
from backend.models.job import JobListing, JobSearchRequest, JobSearchResults, JobSource
from backend.repositories.job_repo import JobRepository
from backend.scrapers.ddg_search import DDGJobSearcher
from backend.scrapers.generic import GenericCareerScraper
from backend.scrapers.greenhouse import (
    GREENHOUSE_BOARD_URL_PATTERN,
    GreenhouseScraper,
)
from backend.scrapers.lever import LEVER_BOARD_URL_PATTERN, LeverScraper

logger = logging.getLogger(__name__)


def compute_url_hash(url: str) -> str:
    """Compute a deterministic SHA256 hash of a normalized URL for deduplication."""
    parsed = urlparse(url.strip())
    # Canonicalize: ignore fragments and trailing slashes
    canonical = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    if parsed.query:
        canonical = f"{canonical}?{parsed.query}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class JobSearchService:
    """Aggregates job searches from direct career APIs, HTML pages, and web engines."""

    def __init__(self, session: AsyncSession, user_id: UUID | str) -> None:
        self.session = session
        self.user_id = UUID(user_id) if not isinstance(user_id, UUID) else user_id
        self.repo = JobRepository(session, self.user_id)
        self.greenhouse = GreenhouseScraper()
        self.lever = LeverScraper()
        self.generic = GenericCareerScraper()
        self.ddg = DDGJobSearcher()

    async def search_and_persist(self, request: JobSearchRequest) -> JobSearchResults:
        """
        Execute search across configured company boards and web search,
        deduplicating against existing tenant database records.
        """
        found_listings: list[JobListing] = []

        # 1. Direct Target Companies
        for target in request.target_companies:
            target_str = target.strip()
            if not target_str:
                continue

            if GREENHOUSE_BOARD_URL_PATTERN.search(target_str):
                jobs = await self.greenhouse.fetch_jobs(target_str)
            elif LEVER_BOARD_URL_PATTERN.search(target_str):
                jobs = await self.lever.fetch_jobs(target_str)
            elif target_str.startswith(("http://", "https://")):
                jobs = await self.generic.fetch_jobs(target_str)
            else:
                # Try greenhouse first, then lever
                jobs = await self.greenhouse.fetch_jobs(target_str)
                if not jobs:
                    jobs = await self.lever.fetch_jobs(target_str)

            found_listings.extend(jobs)

        # 2. Web Search Aggregation (DDG)
        ddg_jobs = await self.ddg.search(
            request.query,
            site_filters=request.site_filters or request.board_urls,
            location=request.location_filter,
            date_filter=request.date_posted_filter,
            remote_only=request.remote_only,
            limit=request.limit,
        )
        found_listings.extend(ddg_jobs)

        # 3. Deduplicate in-memory by url_hash
        unique_listings: list[JobListing] = []
        seen_hashes: set[str] = set()

        for listing in found_listings:
            url = listing.link or listing.source_url
            if not url:
                continue
            h = compute_url_hash(url)
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_listings.append(listing)

        # 4. Filter against existing jobs in Postgres and persist new ones
        records_to_create: list[JobRecord] = []
        for listing in unique_listings:
            url = listing.link or listing.source_url
            url_h = compute_url_hash(url)
            existing = await self.repo.get_by_url_hash(url_h)
            if existing is None:
                record = JobRecord(
                    user_id=self.user_id,
                    title=listing.title,
                    company=listing.company,
                    url=url,
                    url_hash=url_h,
                    summary=listing.summary,
                    description=listing.description,
                    source=str(listing.source.value if isinstance(listing.source, JobSource) else listing.source),
                    location=listing.location,
                    raw_data=listing.model_dump(mode="json"),
                )
                records_to_create.append(record)

        if records_to_create:
            await self.repo.bulk_create(records_to_create)

        # Return aggregated search results limited to request limit
        limited_listings = unique_listings[: request.limit]
        return JobSearchResults(
            query=request.query,
            jobs=limited_listings,
            total_found=len(unique_listings),
        )

    async def list_saved_jobs(self, limit: int = 50) -> list[JobListing]:
        """List jobs saved in the database for the current tenant."""
        records = await self.repo.list_by_relevance(limit=limit)
        listings: list[JobListing] = []
        for rec in records:
            listing = JobListing(
                id=str(rec.id),
                title=rec.title,
                company=rec.company,
                link=rec.url,
                summary=rec.summary,
                description=rec.description,
                source=JobSource(rec.source) if rec.source in JobSource.__members__.values() else JobSource.WEB_SEARCH,
                location=rec.location,
                relevance_score=rec.relevance_score,
                recommendation=rec.recommendation,  # type: ignore[arg-type]
            )
            listings.append(listing)
        return listings
