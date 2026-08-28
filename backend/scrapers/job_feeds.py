"""Public job feed integrations — Remotive, Jobicy, and Arbeitnow.

Zero API keys required.  Each adapter fetches structured JSON from a free
public API and converts results into ``JobListing`` models with exact
location, date, salary, and tags already populated.
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from backend.models.job import JobListing, JobSource
from backend.scrapers.http_client import SafeAsyncClient

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """Strip HTML tags and return plain text."""
    if not text or "<" not in text:
        return text.strip()
    soup = BeautifulSoup(text, "html.parser")
    return str(soup.get_text(separator="\n").strip())


# ---------------------------------------------------------------------------
# Remotive  —  https://remotive.com/api/remote-jobs
# ---------------------------------------------------------------------------


class RemotiveFeed:
    """Fetches remote job listings from the Remotive public API."""

    BASE_URL = "https://remotive.com/api/remote-jobs"

    def __init__(self, client: SafeAsyncClient | None = None) -> None:
        self.client = client or SafeAsyncClient(timeout=10.0)

    async def search(self, query: str, *, limit: int = 50) -> list[JobListing]:
        """Search Remotive for jobs matching *query*."""
        try:
            resp = await self.client.get(
                self.BASE_URL,
                params={"search": query, "limit": str(limit)},
            )
            if resp.status_code != 200:
                logger.info("Remotive returned status %d for query %r", resp.status_code, query)
                return []
            data: dict[str, Any] = resp.json()
        except Exception as exc:
            logger.warning("Remotive fetch error for %r: %s", query, exc)
            return []

        raw_jobs = data.get("jobs", [])
        listings: list[JobListing] = []

        for item in raw_jobs:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            company = (item.get("company_name") or "").strip()
            url = (item.get("url") or "").strip()
            location = (item.get("candidate_required_location") or "").strip()
            date_posted = (item.get("publication_date") or "").strip()
            salary = (item.get("salary") or "").strip()
            job_type = (item.get("job_type") or "").replace("_", " ").title()
            category = (item.get("category") or "").strip()
            logo = (item.get("company_logo") or item.get("company_logo_url") or "").strip()
            tags_raw: list[str] = item.get("tags") or []
            description_html = item.get("description") or ""

            description = _strip_html(description_html)
            summary = description[:300].strip() if description else title

            tags = [t for t in tags_raw[:10] if isinstance(t, str) and t.strip()]
            if category and category not in tags:
                tags.insert(0, category)

            listing = JobListing(
                title=title,
                company=company,
                link=url,
                summary=summary,
                description=description,
                source=JobSource.JOB_FEED,
                location=location,
                date_posted=date_posted[:10] if len(date_posted) >= 10 else date_posted,
                employment_type=job_type,
                salary=salary,
                logo_url=logo,
                source_platform="remotive",
                source_url=url,
                tags=tags,
            )
            listings.append(listing)

        return listings


# ---------------------------------------------------------------------------
# Jobicy  —  https://jobicy.com/api/v2/remote-jobs
# ---------------------------------------------------------------------------


class JobicyFeed:
    """Fetches remote job listings from the Jobicy public API."""

    BASE_URL = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, client: SafeAsyncClient | None = None) -> None:
        self.client = client or SafeAsyncClient(timeout=10.0)

    async def search(self, query: str, *, limit: int = 50) -> list[JobListing]:
        """Search Jobicy for jobs matching *query*."""
        try:
            resp = await self.client.get(
                self.BASE_URL,
                params={"tag": query, "count": str(limit)},
            )
            if resp.status_code != 200:
                logger.info("Jobicy returned status %d for query %r", resp.status_code, query)
                return []
            data: dict[str, Any] = resp.json()
        except Exception as exc:
            logger.warning("Jobicy fetch error for %r: %s", query, exc)
            return []

        raw_jobs = data.get("jobs", [])
        listings: list[JobListing] = []

        for item in raw_jobs:
            title = (item.get("jobTitle") or "").strip()
            if not title:
                continue

            company = (item.get("companyName") or "").strip()
            url = (item.get("url") or "").strip()
            location = (item.get("jobGeo") or "").strip() if isinstance(item.get("jobGeo"), str) else ""
            raw_date = item.get("pubDate", "")
            date_posted = str(raw_date).strip() if raw_date else ""
            raw_type = item.get("jobType", "")
            if isinstance(raw_type, list):
                job_type = ", ".join(str(t) for t in raw_type)
            else:
                job_type = str(raw_type).strip() if raw_type else ""
            logo = (item.get("companyLogo") or "").strip() if isinstance(item.get("companyLogo"), str) else ""

            salary_min = item.get("annualSalaryMin", "")
            salary_max = item.get("annualSalaryMax", "")
            salary_currency = str(item.get("salaryCurrency", ""))
            salary = ""
            if salary_min and salary_max:
                salary = f"{salary_currency} {salary_min}\u2013{salary_max}".strip()
            elif salary_min:
                salary = f"{salary_currency} {salary_min}+".strip()

            description_html = item.get("jobDescription") or item.get("jobExcerpt") or ""
            description = _strip_html(description_html)
            summary = description[:300].strip() if description else title

            industry = item.get("jobIndustry") or []
            tags = [str(ind) for ind in industry[:10]] if isinstance(industry, list) else []

            listing = JobListing(
                title=title,
                company=company,
                link=url,
                summary=summary,
                description=description,
                source=JobSource.JOB_FEED,
                location=location,
                date_posted=date_posted[:10] if len(date_posted) >= 10 else date_posted,
                employment_type=job_type,
                salary=salary,
                logo_url=logo,
                source_platform="jobicy",
                source_url=url,
                tags=tags,
            )
            listings.append(listing)

        return listings


# ---------------------------------------------------------------------------
# Arbeitnow  —  https://arbeitnow.com/api/job-board-api
# ---------------------------------------------------------------------------


class ArbeitnowFeed:
    """Fetches job listings from the Arbeitnow public API."""

    BASE_URL = "https://arbeitnow.com/api/job-board-api"

    def __init__(self, client: SafeAsyncClient | None = None) -> None:
        self.client = client or SafeAsyncClient(timeout=10.0)

    async def search(self, query: str, *, limit: int = 50) -> list[JobListing]:
        """Search Arbeitnow for jobs matching *query*."""
        try:
            resp = await self.client.get(
                self.BASE_URL,
                params={"search": query, "page": "1"},
            )
            if resp.status_code != 200:
                logger.info("Arbeitnow returned status %d for query %r", resp.status_code, query)
                return []
            data: dict[str, Any] = resp.json()
        except Exception as exc:
            logger.warning("Arbeitnow fetch error for %r: %s", query, exc)
            return []

        raw_jobs = data.get("data", [])
        listings: list[JobListing] = []

        for item in raw_jobs:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            company = (item.get("company_name") or "").strip()
            slug = (item.get("slug") or "").strip()
            url = (item.get("url") or f"https://arbeitnow.com/view/{slug}").strip()
            location = (item.get("location") or "").strip()
            remote = item.get("remote", False)
            if remote and location:
                location = f"{location} (Remote)"
            elif remote:
                location = "Remote"

            raw_created = item.get("created_at")
            date_posted = ""
            if raw_created:
                # Unix timestamp (int) or ISO string
                if isinstance(raw_created, (int, float)):
                    from datetime import datetime, timezone

                    date_posted = datetime.fromtimestamp(int(raw_created), tz=timezone.utc).strftime("%Y-%m-%d")
                else:
                    created_str = str(raw_created).strip()
                    date_posted = created_str[:10] if len(created_str) >= 10 else created_str

            description_html = item.get("description") or ""
            description = _strip_html(description_html)
            summary = description[:300].strip() if description else title

            tags_raw: list[str] = item.get("tags") or []
            tags = [t for t in tags_raw[:10] if isinstance(t, str) and t.strip()]

            visa_sponsorship = item.get("visa_sponsorship", False)
            if visa_sponsorship:
                tags.append("Visa Sponsorship")

            listing = JobListing(
                title=title,
                company=company,
                link=url,
                summary=summary,
                description=description,
                source=JobSource.JOB_FEED,
                location=location,
                date_posted=date_posted,
                source_platform="arbeitnow",
                source_url=url,
                tags=tags,
            )
            listings.append(listing)

            if len(listings) >= limit:
                break

        return listings
