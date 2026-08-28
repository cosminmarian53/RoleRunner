"""Deep Page Inspector — extracts structured metadata from job posting pages.

Fetches the actual HTML of a job URL and extracts Schema.org JobPosting
JSON-LD metadata (exact location, date posted, salary, employment type),
with OpenGraph fallback.  Also detects dead / expired listings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from backend.scrapers.http_client import SafeAsyncClient

logger = logging.getLogger(__name__)

# Phrases that indicate a job listing has been closed or expired
EXPIRED_PHRASES = [
    "no longer accepting applications",
    "position has been filled",
    "this job is no longer available",
    "this posting has expired",
    "job is closed",
    "this position is closed",
    "this role has been filled",
    "this listing is no longer active",
    "sorry, this job has been removed",
    "the page you requested was not found",
]


class PageMetadata:
    """Structured metadata extracted from a job posting page."""

    def __init__(self) -> None:
        self.location: str = ""
        self.country: str = ""
        self.city: str = ""
        self.date_posted: str = ""
        self.valid_through: str = ""
        self.salary: str = ""
        self.employment_type: str = ""
        self.company: str = ""
        self.title: str = ""
        self.description: str = ""
        self.logo_url: str = ""
        self.is_expired: bool = False
        self.is_dead: bool = False


def _extract_jsonld_job_posting(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Find and parse a Schema.org JobPosting JSON-LD block from the page."""
    for script_tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script_tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle both direct objects and arrays
        candidates = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                if "JobPosting" in item_type:
                    return item
            elif item_type == "JobPosting":
                return item

            # Check @graph arrays
            graph = item.get("@graph", [])
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict):
                        node_type = node.get("@type", "")
                        if node_type == "JobPosting" or (isinstance(node_type, list) and "JobPosting" in node_type):
                            return node
    return None


def _extract_location_from_jsonld(job: dict[str, Any]) -> tuple[str, str, str]:
    """Extract city, country, and combined location string from JSON-LD jobLocation."""
    job_location = job.get("jobLocation")
    if not job_location:
        return "", "", ""

    locations = job_location if isinstance(job_location, list) else [job_location]
    parts: list[str] = []
    city = ""
    country = ""

    for loc in locations:
        if not isinstance(loc, dict):
            continue
        address = loc.get("address", {})
        if isinstance(address, str):
            parts.append(address)
            continue
        if isinstance(address, dict):
            locality = address.get("addressLocality", "")
            region = address.get("addressRegion", "")
            addr_country = address.get("addressCountry", "")
            if isinstance(addr_country, dict):
                addr_country = addr_country.get("name", "") or addr_country.get("@value", "")

            if locality and not city:
                city = locality
            if addr_country and not country:
                country = addr_country

            loc_parts = [p for p in [locality, region, addr_country] if p]
            if loc_parts:
                parts.append(", ".join(loc_parts))

        # Some pages use name directly
        name = loc.get("name", "")
        if name and not parts:
            parts.append(name)

    location = " | ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")
    return city, country, location


def _extract_salary_from_jsonld(job: dict[str, Any]) -> str:
    """Extract salary info from JSON-LD baseSalary."""
    base_salary = job.get("baseSalary")
    if not base_salary or not isinstance(base_salary, dict):
        estimated = job.get("estimatedSalary")
        if isinstance(estimated, dict):
            base_salary = estimated
        elif isinstance(estimated, list) and estimated:
            base_salary = estimated[0]
        else:
            return ""

    currency = base_salary.get("currency", "")
    value = base_salary.get("value", {})
    if isinstance(value, dict):
        min_val = value.get("minValue", "")
        max_val = value.get("maxValue", "")
        unit = value.get("unitText", "")
        if min_val and max_val:
            return f"{currency} {min_val}–{max_val} {unit}".strip()
        elif min_val:
            return f"{currency} {min_val}+ {unit}".strip()
        val = value.get("value", "")
        if val:
            return f"{currency} {val} {unit}".strip()
    elif value:
        return f"{currency} {value}".strip()
    return ""


def _extract_employment_type(job: dict[str, Any]) -> str:
    """Normalize employment type from JSON-LD."""
    emp_type = job.get("employmentType", "")
    if isinstance(emp_type, list):
        emp_type = ", ".join(str(t) for t in emp_type)

    type_str = str(emp_type).upper().replace("_", " ")
    mapping = {
        "FULL TIME": "Full-time",
        "FULL-TIME": "Full-time",
        "PART TIME": "Part-time",
        "PART-TIME": "Part-time",
        "INTERN": "Internship",
        "INTERNSHIP": "Internship",
        "CONTRACT": "Contract",
        "CONTRACTOR": "Contract",
        "TEMPORARY": "Temporary",
        "VOLUNTEER": "Volunteer",
    }
    return mapping.get(type_str.strip(), type_str.title() if type_str else "")


def _parse_jsonld_metadata(job: dict[str, Any]) -> PageMetadata:
    """Parse a Schema.org JobPosting JSON-LD dict into PageMetadata."""
    meta = PageMetadata()

    meta.title = job.get("title", "")
    meta.date_posted = job.get("datePosted", "")
    meta.valid_through = job.get("validThrough", "")
    meta.employment_type = _extract_employment_type(job)
    meta.salary = _extract_salary_from_jsonld(job)

    # Company
    org = job.get("hiringOrganization", {})
    if isinstance(org, dict):
        meta.company = org.get("name", "")
        logo = org.get("logo", "")
        if isinstance(logo, dict):
            logo = logo.get("url", "") or logo.get("contentUrl", "")
        meta.logo_url = logo if isinstance(logo, str) else ""

    # Location
    meta.city, meta.country, meta.location = _extract_location_from_jsonld(job)

    # Description
    desc = job.get("description", "")
    if desc and "<" in desc:
        soup = BeautifulSoup(desc, "html.parser")
        meta.description = soup.get_text(separator="\n").strip()
    else:
        meta.description = desc

    return meta


def _extract_opengraph(soup: BeautifulSoup) -> dict[str, str]:
    """Extract OpenGraph meta tags as a dict."""
    og: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        prop = tag.get("property", "") or tag.get("name", "")
        content = tag.get("content", "")
        if prop and content:
            og[str(prop).lower()] = str(content)
    return og


def _check_expired(text: str) -> bool:
    """Check if the page text indicates the job has expired."""
    lower = text.lower()
    return any(phrase in lower for phrase in EXPIRED_PHRASES)


class DeepPageInspector:
    """Fetches job pages and extracts structured metadata via JSON-LD and OpenGraph."""

    def __init__(self, timeout: float = 5.0, max_concurrent: int = 10) -> None:
        self.client = SafeAsyncClient(timeout=timeout)
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def inspect(self, url: str) -> PageMetadata:
        """Fetch a single URL and extract structured metadata."""
        meta = PageMetadata()
        async with self.semaphore:
            try:
                resp = await self.client.get(url)
            except Exception as exc:
                logger.debug("DeepPageInspector failed to fetch %s: %s", url, exc)
                meta.is_dead = True
                return meta

        if resp.status_code == 404:
            meta.is_dead = True
            return meta

        if resp.status_code >= 400:
            meta.is_dead = True
            return meta

        html = resp.text
        if not html:
            meta.is_dead = True
            return meta

        # Check for expired markers in page text
        if _check_expired(html):
            meta.is_expired = True
            return meta

        soup = BeautifulSoup(html, "html.parser")

        # 1. Try JSON-LD extraction (highest quality)
        jsonld = _extract_jsonld_job_posting(soup)
        if jsonld:
            meta = _parse_jsonld_metadata(jsonld)
            # Re-check expired status
            if _check_expired(soup.get_text()):
                meta.is_expired = True
            return meta

        # 2. Fallback to OpenGraph
        og = _extract_opengraph(soup)
        if og.get("og:title"):
            meta.title = og["og:title"]
        if og.get("og:description"):
            meta.description = og["og:description"]

        # 3. Try to extract location from page text with regex
        page_text = soup.get_text(separator=" ")
        loc_match = re.search(
            r"(?:Location|Office|Based in)[:\s]+([A-Z][a-z]+(?:[\s,]+[A-Z][a-z]+){0,3})",
            page_text,
        )
        if loc_match:
            meta.location = loc_match.group(1).strip().rstrip(",")

        if _check_expired(page_text):
            meta.is_expired = True

        return meta

    async def inspect_many(self, urls: list[str]) -> dict[str, PageMetadata]:
        """Inspect multiple URLs concurrently and return a mapping of url → metadata."""
        if not urls:
            return {}

        tasks = {url: asyncio.create_task(self.inspect(url)) for url in urls}
        results: dict[str, PageMetadata] = {}
        for url, task in tasks.items():
            try:
                results[url] = await task
            except Exception as exc:
                logger.debug("DeepPageInspector error for %s: %s", url, exc)
                dead = PageMetadata()
                dead.is_dead = True
                results[url] = dead

        return results
