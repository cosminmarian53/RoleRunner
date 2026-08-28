"""Pydantic models for job listings and search results."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobSource(StrEnum):
    """Where the job was found."""

    COMPANY_CAREER = "company_career"
    JOB_BOARD = "job_board"
    JOB_FEED = "job_feed"
    WEB_SEARCH = "web_search"
    MANUAL = "manual"


class Recommendation(StrEnum):
    """Match quality recommendation."""

    STRONG_MATCH = "strong_match"
    GOOD_MATCH = "good_match"
    PARTIAL_MATCH = "partial_match"
    WEAK_MATCH = "weak_match"


class JobListing(BaseModel):
    """A single job listing found by the search engine."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    company: str = ""
    link: str = ""
    summary: str = ""
    description: str = ""
    source: JobSource = JobSource.WEB_SEARCH
    location: str = ""
    date_posted: str = ""
    date_seen: str = Field(default_factory=lambda: datetime.now().isoformat())
    source_platform: str = ""
    source_url: str = ""
    employment_type: str = ""
    salary: str = ""
    logo_url: str = ""
    expires: str = ""
    tags: list[str] = Field(default_factory=list)

    # Scoring fields (populated after relevance scoring)
    relevance_score: float | None = None
    match_reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendation: Recommendation | None = None


class JobSearchRequest(BaseModel):
    """Request body for job search."""

    model_config = ConfigDict(extra="ignore")

    query: str
    target_companies: list[str] = Field(default_factory=list, description="Company career URLs or company names.")
    board_urls: list[str] = Field(default_factory=list)
    site_filters: list[str] = Field(default_factory=list)
    location_filter: str = ""
    date_posted_filter: str = ""
    remote_only: bool = False
    limit: int = Field(default=30, ge=1, le=150)

    @field_validator("query")
    @classmethod
    def _query_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query is required")
        return value


class JobSearchResults(BaseModel):
    """Response for a job search operation."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid4().hex)
    query: str
    jobs: list[JobListing] = Field(default_factory=list)
    total_found: int = 0
    search_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SearchSettings(BaseModel):
    """Persisted user search targets."""

    model_config = ConfigDict(extra="ignore")

    target_companies: list[str] = Field(default_factory=list)
    board_urls: list[str] = Field(default_factory=list)
    site_filters: list[str] = Field(default_factory=list)


class JobScoreRequest(BaseModel):
    """Request to score one or more jobs against the user's saved profile."""

    model_config = ConfigDict(extra="ignore")

    jobs: list[JobListing] = Field(default_factory=list)
    use_ai: bool = False


class JobScoreResponse(BaseModel):
    """Scored job list."""

    model_config = ConfigDict(extra="ignore")

    jobs: list[JobListing] = Field(default_factory=list)
    scored_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class JobIntelligenceRequest(BaseModel):
    """Request for deep AI analysis and interview/company framing of a job."""

    model_config = ConfigDict(extra="ignore")

    job_title: str
    company: str = ""
    description: str = ""
    summary: str = ""
    link: str = ""


class JobIntelligenceResponse(BaseModel):
    """Deep AI analysis, strategic framing, and interview process intelligence."""

    model_config = ConfigDict(extra="ignore")

    role_summary: str = ""
    framing_strategy: str = ""
    company_insights: str = ""
    interview_stages: list[str] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    key_technologies: list[str] = Field(default_factory=list)
    culture_notes: str = ""
    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
