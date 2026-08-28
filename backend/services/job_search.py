"""Job search orchestration and aggregation service with multi-board scrapers."""

from __future__ import annotations

import asyncio
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
from backend.scrapers.job_feeds import ArbeitnowFeed, JobicyFeed, RemotiveFeed
from backend.scrapers.lever import LEVER_BOARD_URL_PATTERN, LeverScraper
from backend.scrapers.page_inspector import DeepPageInspector

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
    """Aggregates job searches from direct career APIs, HTML pages, web engines, and public feeds."""

    def __init__(self, session: AsyncSession, user_id: UUID | str) -> None:
        self.session = session
        self.user_id = UUID(user_id) if not isinstance(user_id, UUID) else user_id
        self.repo = JobRepository(session, self.user_id)
        self.greenhouse = GreenhouseScraper()
        self.lever = LeverScraper()
        self.generic = GenericCareerScraper()
        self.ddg = DDGJobSearcher()
        self.remotive = RemotiveFeed()
        self.jobicy = JobicyFeed()
        self.arbeitnow = ArbeitnowFeed()
        self.inspector = DeepPageInspector()

    async def _search_target_companies(self, request: JobSearchRequest) -> list[JobListing]:
        """Search direct target company career pages."""
        found: list[JobListing] = []
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
                jobs = await self.greenhouse.fetch_jobs(target_str)
                if not jobs:
                    jobs = await self.lever.fetch_jobs(target_str)

            found.extend(jobs)
        return found

    async def _search_ddg(self, request: JobSearchRequest) -> list[JobListing]:
        """Run DuckDuckGo ATS web search."""
        return await self.ddg.search(
            request.query,
            site_filters=request.site_filters or request.board_urls,
            location=request.location_filter,
            date_filter=request.date_posted_filter,
            remote_only=request.remote_only,
            limit=request.limit,
        )

    async def _search_feeds(self, query: str, limit: int) -> list[JobListing]:
        """Run all public job feed searches concurrently."""
        results = await asyncio.gather(
            self.remotive.search(query, limit=limit),
            self.jobicy.search(query, limit=limit),
            self.arbeitnow.search(query, limit=limit),
            return_exceptions=True,
        )

        combined: list[JobListing] = []
        feed_names = ["Remotive", "Jobicy", "Arbeitnow"]
        for feed_name, result in zip(feed_names, results):
            if isinstance(result, Exception):
                logger.warning("%s feed error: %s", feed_name, result)
            elif isinstance(result, list):
                combined.extend(result)
        return combined

    async def _enrich_with_deep_inspection(self, listings: list[JobListing]) -> list[JobListing]:
        """Enrich listings missing location or date by fetching and inspecting their pages."""
        urls_to_inspect: list[str] = []
        url_to_idx: dict[str, list[int]] = {}

        for idx, listing in enumerate(listings):
            needs_location = not listing.location or listing.location.lower() in ("", "location not listed")
            needs_date = not listing.date_posted
            if (needs_location or needs_date) and listing.link:
                url = listing.link
                urls_to_inspect.append(url)
                url_to_idx.setdefault(url, []).append(idx)

        if not urls_to_inspect:
            return listings

        # Deduplicate URLs for inspection
        unique_urls = list(dict.fromkeys(urls_to_inspect))
        # Cap at 20 inspections per search to keep response time reasonable
        unique_urls = unique_urls[:20]

        inspection_results = await self.inspector.inspect_many(unique_urls)

        enriched = list(listings)
        expired_indices: set[int] = set()

        for url, meta in inspection_results.items():
            if url not in url_to_idx:
                continue

            for idx in url_to_idx[url]:
                if meta.is_expired:
                    expired_indices.add(idx)
                    continue

                listing = enriched[idx]

                # Enrich location
                if meta.location and (not listing.location or listing.location.lower() in ("", "location not listed")):
                    listing.location = meta.location

                # Enrich date_posted
                if meta.date_posted and not listing.date_posted:
                    listing.date_posted = meta.date_posted

                # Enrich salary
                if meta.salary and not listing.salary:
                    listing.salary = meta.salary

                # Enrich employment type
                if meta.employment_type and not listing.employment_type:
                    listing.employment_type = meta.employment_type

                # Enrich company name
                if meta.company and not listing.company:
                    listing.company = meta.company

                # Enrich logo
                if meta.logo_url and not listing.logo_url:
                    listing.logo_url = meta.logo_url

                # Enrich expiry
                if meta.valid_through and not listing.expires:
                    listing.expires = meta.valid_through

        # Remove confirmed expired listings
        if expired_indices:
            enriched = [listing for idx, listing in enumerate(enriched) if idx not in expired_indices]
            logger.info("Removed %d expired listings via deep inspection", len(expired_indices))

        return enriched

    async def search_and_persist(self, request: JobSearchRequest) -> JobSearchResults:
        """
        Execute search across all configured sources concurrently,
        enrich with deep page inspection, deduplicate, and persist.
        """
        # Run all search lanes concurrently
        company_task = asyncio.create_task(self._search_target_companies(request))
        ddg_task = asyncio.create_task(self._search_ddg(request))
        feeds_task = asyncio.create_task(self._search_feeds(request.query, request.limit))

        company_results, ddg_results, feed_results = await asyncio.gather(
            company_task,
            ddg_task,
            feeds_task,
            return_exceptions=True,
        )

        found_listings: list[JobListing] = []
        for label, result in [("Companies", company_results), ("DDG", ddg_results), ("Feeds", feed_results)]:
            if isinstance(result, Exception):
                logger.warning("Search lane %s error: %s", label, result)
            elif isinstance(result, list):
                found_listings.extend(result)

        # Deduplicate in-memory by url_hash
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

        # Enrich DDG/web results with deep page inspection (location, date, salary)
        unique_listings = await self._enrich_with_deep_inspection(unique_listings)

        # Persist new jobs to database
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
