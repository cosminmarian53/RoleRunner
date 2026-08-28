"""Router for job search, discovery aggregation, and relevance scoring."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.job import (
    JobIntelligenceRequest,
    JobIntelligenceResponse,
    JobListing,
    JobScoreRequest,
    JobScoreResponse,
    JobSearchRequest,
    JobSearchResults,
)
from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser
from backend.services.job_intelligence import JobIntelligenceService
from backend.services.job_scorer import JobScorer, extract_dynamic_profile_keywords
from backend.services.job_search import JobSearchService, compute_url_hash
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/search", response_model=JobSearchResults)
async def search_jobs(
    request: JobSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobSearchResults:
    """Execute multi-board and web job search with deduplication, query filtering, and profile scoring."""
    service = JobSearchService(session, current_user.id)
    results = await service.search_and_persist(request)

    # Auto-score search results against profile if user has skills defined
    try:
        prof_svc = ProfileService(session, current_user.id)
        profile = await prof_svc.get_profile()
        cv_keywords, title_keywords = extract_dynamic_profile_keywords(profile)

        if cv_keywords or title_keywords:
            for job in results.jobs:
                job_text = f"{job.title} {job.company} {job.summary} {job.description} {' '.join(job.tags)}"
                score_res = JobScorer.score_job_fast(
                    cv_keywords,
                    job_text,
                    job_title=job.title,
                    candidate_title_keywords=title_keywords,
                )
                job.relevance_score = score_res.score
                job.match_reasons = score_res.matched_keywords[:5]
                job.gaps = score_res.missing_keywords[:5]
                job.recommendation = score_res.recommendation
    except Exception as exc:
        logger.debug("Auto profile scoring skipped: %s", exc)

    return results


@router.get("", response_model=list[JobListing])
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[JobListing]:
    """List saved job opportunities for the tenant."""
    service = JobSearchService(session, current_user.id)
    return await service.list_saved_jobs(limit=limit)


@router.post("/score", response_model=JobScoreResponse)
async def score_jobs(
    request: JobScoreRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobScoreResponse:
    """Score a list of job postings against current user's profile with high-speed dynamic keyword matching."""
    prof_svc = ProfileService(session, current_user.id)
    profile = await prof_svc.get_profile()

    # Dynamically extract target candidate skills & title tokens directly from candidate's profile
    cv_keywords, title_keywords = extract_dynamic_profile_keywords(profile)

    scored_jobs: list[JobListing] = []
    for job in request.jobs:
        job_text = f"{job.title} {job.company} {job.summary} {job.description} {' '.join(job.tags)}"
        score_res = JobScorer.score_job_fast(
            cv_keywords,
            job_text,
            job_title=job.title,
            candidate_title_keywords=title_keywords,
        )

        job_copy = job.model_copy()
        job_copy.relevance_score = score_res.score
        job_copy.match_reasons = score_res.matched_keywords[:5]
        job_copy.gaps = score_res.missing_keywords[:5]
        job_copy.recommendation = score_res.recommendation

        scored_jobs.append(job_copy)

    # Sort descending by relevance score
    scored_jobs.sort(key=lambda j: j.relevance_score or 0.0, reverse=True)
    return JobScoreResponse(jobs=scored_jobs)


@router.post("/score-all", response_model=JobSearchResults)
async def score_all_jobs(
    request: JobScoreRequest | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobSearchResults:
    """Score all jobs against current user's profile and persist score updates efficiently."""
    prof_svc = ProfileService(session, current_user.id)
    profile = await prof_svc.get_profile()

    cv_keywords, title_keywords = extract_dynamic_profile_keywords(profile)

    job_service = JobSearchService(session, current_user.id)
    jobs_to_score: list[JobListing] = []

    if request and request.jobs:
        jobs_to_score = request.jobs
    else:
        jobs_to_score = await job_service.list_saved_jobs(limit=100)

    scored_jobs: list[JobListing] = []
    has_db_updates = False

    for job in jobs_to_score:
        job_text = f"{job.title} {job.company} {job.summary} {job.description} {' '.join(job.tags)}"
        score_res = JobScorer.score_job_fast(
            cv_keywords,
            job_text,
            job_title=job.title,
            candidate_title_keywords=title_keywords,
        )

        job_copy = job.model_copy()
        job_copy.relevance_score = score_res.score
        job_copy.match_reasons = score_res.matched_keywords[:5]
        job_copy.gaps = score_res.missing_keywords[:5]
        job_copy.recommendation = score_res.recommendation

        scored_jobs.append(job_copy)

        # Update in database if url exists
        if job_copy.link:
            h = compute_url_hash(job_copy.link)
            existing_rec = await job_service.repo.get_by_url_hash(h)
            if existing_rec:
                existing_rec.relevance_score = job_copy.relevance_score
                existing_rec.recommendation = str(job_copy.recommendation.value) if job_copy.recommendation else None
                has_db_updates = True

    if has_db_updates:
        await session.flush()

    scored_jobs.sort(key=lambda j: j.relevance_score or 0.0, reverse=True)
    return JobSearchResults(
        query=f"Profile match for {profile.personal_info.name}" if profile.personal_info.name else "Profile match",
        jobs=scored_jobs,
        total_found=len(scored_jobs),
    )


@router.post("/intelligence", response_model=JobIntelligenceResponse)
async def get_job_intelligence(
    request: JobIntelligenceRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobIntelligenceResponse:
    """Generate strategic framing, interview process phases, and company intel for a job."""
    prof_svc = ProfileService(session, current_user.id)
    profile = await prof_svc.get_profile()

    intel_svc = JobIntelligenceService(user_id=current_user.id)
    return await intel_svc.generate_intelligence(request, profile)


class FetchJobDescriptionRequest(BaseModel):
    url: str


class FetchJobDescriptionResponse(BaseModel):
    url: str
    description: str
    character_count: int


@router.post("/fetch-description", response_model=FetchJobDescriptionResponse)
async def fetch_job_description(
    request: FetchJobDescriptionRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> FetchJobDescriptionResponse:
    """Fetch and extract full text requirements for any live job posting URL."""
    from backend.scrapers.generic import GenericCareerScraper

    scraper = GenericCareerScraper()
    description = await scraper.fetch_job_page_content(request.url)
    return FetchJobDescriptionResponse(
        url=request.url,
        description=description,
        character_count=len(description),
    )
