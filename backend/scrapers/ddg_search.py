"""DuckDuckGo web search aggregator for job discovery across multiple boards."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from ddgs import DDGS

from backend.models.job import JobListing, JobSource

logger = logging.getLogger(__name__)

DEFAULT_ATS_SITES = [
    "boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "apply.workable.com",
    "jobs.smartrecruiters.com",
    "bamboohr.com",
    "breezy.hr",
    "jobs.jobvite.com",
    "workday.com",
    "wellfound.com",
    "remoteok.com",
    "weworkremotely.com",
]

BLOCKED_DOMAINS = {
    "wikipedia.org",
    "wikimedia.org",
    "wiktionary.org",
    "dictionary.com",
    "merriam-webster.com",
    "cambridge.org",
    "investopedia.com",
    "coursera.org",
    "udemy.com",
    "edx.org",
    "geeksforgeeks.org",
    "w3schools.com",
    "medium.com",
    "quora.com",
    "reddit.com",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "grokipedia.com",
    "thebalancecareers.com",
    "forbes.com",
    "businessinsider.com",
    "nytimes.com",
    "wsj.com",
}

BLOCKED_PREFIXES = (
    "what is ",
    "what is an ",
    "what is a ",
    "definition of ",
    "meaning of ",
    "how to become ",
    "guide to ",
    "tutorial:",
    "course:",
    "course -",
)

LOCATION_PATTERN = re.compile(
    r"\b(Remote|Hybrid|On-site|San Francisco|New York|London|Berlin|Toronto|Seattle|Austin|"
    r"Boston|Chicago|Los Angeles|Amsterdam|Dublin|Paris|Singapore|Sydney|Remote \(US\)|"
    r"Remote \(Europe\)|Remote \(Worldwide\)|Worldwide|United States|Europe|UK|Germany|"
    r"France|Romania|Poland|Netherlands|Canada)\b",
    re.IGNORECASE,
)


def clean_slug(slug: str) -> str:
    """Convert URL slug to readable company title."""
    slug = re.sub(r"[-_]", " ", slug)
    return slug.strip().title()


def unwrap_redirect_url(url: str) -> str:
    """Unwrap DuckDuckGo or search aggregator tracking URLs to direct target URLs."""
    if not url:
        return ""
    if "duckduckgo.com/l/?" in url or "uddg=" in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "uddg" in params and params["uddg"]:
            return unquote(params["uddg"][0])
    return url


def is_job_listing(title: str, url: str, snippet: str) -> bool:
    """Validate that the search result is an actual job opening and not an article or definition."""
    clean_url = unwrap_redirect_url(url)
    parsed = urlparse(clean_url)
    domain = parsed.netloc.lower()

    if not clean_url.startswith(("http://", "https://")):
        return False

    # Reject blocked informational domains
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            return False

    title_lower = title.lower()
    if any(title_lower.startswith(prefix) for prefix in BLOCKED_PREFIXES):
        return False

    # Known ATS job board URLs are inherently valid jobs
    if any(ats in domain for ats in DEFAULT_ATS_SITES):
        return True

    # General web pages must contain clear job opening indicators
    job_indicators = [
        "apply",
        "job",
        "hiring",
        "role",
        "responsibilities",
        "requirements",
        "qualifications",
        "salary",
        "career",
        "internship",
        "developer",
        "engineer",
        "position",
        "opening",
    ]
    combined_text = f"{title} {snippet}".lower()
    matches = sum(1 for indicator in job_indicators if indicator in combined_text)
    return matches >= 2


def parse_job_metadata(raw_title: str, url: str, snippet: str) -> tuple[str, str, str, JobSource]:
    """
    Extract clean job title, company name, location, and source from listing info.
    """
    clean_url = unwrap_redirect_url(url)
    parsed = urlparse(clean_url)
    domain = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    inferred_company = ""
    inferred_source = JobSource.WEB_SEARCH
    inferred_title = raw_title.strip()
    inferred_location = ""

    # 1. Infer ATS board source and company slug from URL
    if "greenhouse.io" in domain:
        inferred_source = JobSource.COMPANY_CAREER
        if path_parts:
            inferred_company = clean_slug(path_parts[0])
    elif "lever.co" in domain:
        inferred_source = JobSource.COMPANY_CAREER
        if path_parts:
            inferred_company = clean_slug(path_parts[0])
    elif "ashbyhq.com" in domain:
        inferred_source = JobSource.COMPANY_CAREER
        if path_parts:
            inferred_company = clean_slug(path_parts[0])
    elif "workable.com" in domain:
        inferred_source = JobSource.COMPANY_CAREER
        if path_parts:
            inferred_company = clean_slug(path_parts[0])
    elif "smartrecruiters.com" in domain:
        inferred_source = JobSource.JOB_BOARD
        if path_parts:
            inferred_company = clean_slug(path_parts[0])
    elif "bamboohr.com" in domain:
        inferred_source = JobSource.COMPANY_CAREER
        subdomain = domain.split(".bamboohr.com")[0]
        if subdomain:
            inferred_company = clean_slug(subdomain)
    elif "breezy.hr" in domain:
        inferred_source = JobSource.COMPANY_CAREER
        subdomain = domain.split(".breezy.hr")[0]
        if subdomain:
            inferred_company = clean_slug(subdomain)

    # 2. Extract and clean Title & Company from title text patterns
    if " @ " in raw_title:
        parts = raw_title.split(" @ ", 1)
        inferred_title = parts[0].strip()
        inferred_company = parts[1].strip()
    elif " | " in raw_title:
        parts = raw_title.split(" | ")
        if len(parts) >= 2:
            if inferred_company and inferred_company.lower() in parts[0].lower():
                inferred_company = parts[0].strip()
                inferred_title = " | ".join(parts[1:]).strip()
            else:
                inferred_title = parts[0].strip()
                if not inferred_company:
                    inferred_company = parts[1].strip()
    elif " - " in raw_title:
        parts = raw_title.split(" - ")
        if len(parts) >= 2:
            clean_part0 = parts[0].strip()
            clean_part1 = " - ".join(parts[1:]).strip()
            if inferred_company and inferred_company.lower() in clean_part0.lower().replace(" ", ""):
                inferred_company = clean_part0
                inferred_title = clean_part1
            elif any(w in clean_part0.lower() for w in ["technologies", "inc", "corp", "company", "labs", "studios"]):
                inferred_company = clean_part0
                inferred_title = clean_part1
            elif not inferred_company:
                inferred_company = clean_part0
                inferred_title = clean_part1

    # Remove board suffixes from title
    inferred_title = re.sub(
        r"\s*(\||-)\s*(Workable Jobs|Jobs By Workable|SmartRecruiters|Greenhouse|Lever|Ashby|Indeed|Handshake|LinkedIn).*$",
        "",
        inferred_title,
        flags=re.IGNORECASE,
    ).strip()
    if inferred_company:
        inferred_company = re.sub(
            r"\s*(\||-)\s*(Workable Jobs|Jobs By Workable|SmartRecruiters|Greenhouse|Lever|Ashby).*$",
            "",
            inferred_company,
            flags=re.IGNORECASE,
        ).strip()

    # 3. Detect location in snippet or title
    loc_matches = LOCATION_PATTERN.findall(f"{raw_title} {snippet}")
    if loc_matches:
        inferred_location = loc_matches[0].title()

    return inferred_title, inferred_company, inferred_location, inferred_source


class DDGJobSearcher:
    """Discovers high-quality, verified job postings using DuckDuckGo search."""

    def __init__(self, max_results: int = 25) -> None:
        self.max_results = max_results

    def _sync_search(
        self,
        query: str,
        max_results: int,
        timelimit: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run blocking DDGS query in background thread with optional timelimit."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results, timelimit=timelimit))
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
        date_filter: str = "",
        remote_only: bool = False,
        limit: int | None = None,
    ) -> list[JobListing]:
        """
        Search DuckDuckGo with targeted ATS filters, date filtering, and domain verification.
        """
        target_limit = limit or self.max_results
        clean_query = query.strip()
        if not clean_query:
            return []

        # Convert date_filter strings to DDGS timelimit codes
        timelimit: str | None = None
        date_lower = (date_filter or "").strip().lower()
        if date_lower in ("d", "day", "24h", "past_24h"):
            timelimit = "d"
        elif date_lower in ("w", "week", "past_week", "7d"):
            timelimit = "w"
        elif date_lower in ("m", "month", "past_month", "30d"):
            timelimit = "m"

        search_tasks: list[str] = []
        loc_str = location.strip()
        if remote_only and "remote" not in clean_query.lower() and "remote" not in loc_str.lower():
            loc_str = f"remote {loc_str}".strip()

        # 1. Targeted ATS Search
        sites = [s.strip() for s in (site_filters or DEFAULT_ATS_SITES) if s.strip()]
        if sites:
            site_query = " OR ".join(f"site:{s}" for s in sites[:10])
            ats_full_query = f"({site_query}) {clean_query}"
            if loc_str:
                ats_full_query = f"{ats_full_query} {loc_str}"
            search_tasks.append(ats_full_query)

        # 2. General Job Board Search
        gen_query = f'{clean_query} (job OR careers OR "apply now")'
        if loc_str:
            gen_query = f"{gen_query} {loc_str}"
        search_tasks.append(gen_query)

        # Execute searches concurrently
        raw_items: list[dict[str, Any]] = []
        for task_q in search_tasks:
            results = await asyncio.to_thread(self._sync_search, task_q, target_limit * 2, timelimit)
            raw_items.extend(results)
            if len(raw_items) >= target_limit * 2:
                break

        # Process, validate, and deduplicate results
        listings: list[JobListing] = []
        seen_urls: set[str] = set()

        for item in raw_items:
            raw_title = (item.get("title") or "").strip()
            href = (item.get("href") or "").strip()
            body = (item.get("body") or "").strip()

            if not raw_title or not href:
                continue

            clean_url = unwrap_redirect_url(href)
            url_key = clean_url.split("?")[0].rstrip("/")
            if url_key in seen_urls:
                continue

            if not is_job_listing(raw_title, clean_url, body):
                continue

            seen_urls.add(url_key)
            title, company, loc, source = parse_job_metadata(raw_title, clean_url, body)

            listing = JobListing(
                title=title or raw_title,
                company=company,
                link=clean_url,
                summary=body,
                description=body,
                source=source,
                location=loc or location,
                source_url=clean_url,
            )
            listings.append(listing)

            if len(listings) >= target_limit:
                break

        return listings
