"""Router for job search, discovery aggregation, and relevance scoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
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
    Recommendation,
)
from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser
from backend.services.job_intelligence import JobIntelligenceService
from backend.services.job_scorer import JobScorer
from backend.services.job_search import JobSearchService, compute_url_hash
from backend.services.profile_service import ProfileService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/search", response_model=JobSearchResults)
async def search_jobs(
    request: JobSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobSearchResults:
    """Execute multi-board and web job search with deduplication and persistence."""
    service = JobSearchService(session, current_user.id)
    return await service.search_and_persist(request)


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
    """Score a list of job postings against current user's profile."""
    prof_svc = ProfileService(session, current_user.id)
    profile = await prof_svc.get_profile()

    # Form profile text
    skills_text = " ".join([", ".join(v) for v in profile.skills.values()])
    cv_summary_text = f"{profile.summary} {skills_text}"

    scored_jobs: list[JobListing] = []
    for job in request.jobs:
        job_text = f"{job.title} {job.summary} {job.description}"
        score_res = JobScorer.score_cv_against_job(cv_summary_text, job_text)

        job_copy = job.model_copy()
        job_copy.relevance_score = float(score_res.overall_score)
        job_copy.match_reasons = score_res.matched_keywords[:5]
        job_copy.gaps = score_res.missing_keywords[:5]

        if score_res.overall_score >= 80:
            job_copy.recommendation = Recommendation.STRONG_MATCH
        elif score_res.overall_score >= 60:
            job_copy.recommendation = Recommendation.GOOD_MATCH
        elif score_res.overall_score >= 40:
            job_copy.recommendation = Recommendation.PARTIAL_MATCH
        else:
            job_copy.recommendation = Recommendation.WEAK_MATCH

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
    """Score all jobs against current user's profile and persist score updates."""
    prof_svc = ProfileService(session, current_user.id)
    profile = await prof_svc.get_profile()

    skills_text = " ".join([", ".join(v) for v in profile.skills.values()])
    cv_summary_text = f"{profile.personal_info.name} {profile.summary} {skills_text}".strip()

    job_service = JobSearchService(session, current_user.id)
    jobs_to_score: list[JobListing] = []

    if request and request.jobs:
        jobs_to_score = request.jobs
    else:
        jobs_to_score = await job_service.list_saved_jobs(limit=100)

    scored_jobs: list[JobListing] = []
    for job in jobs_to_score:
        job_text = f"{job.title} {job.company} {job.summary} {job.description}"
        score_res = JobScorer.score_cv_against_job(cv_summary_text, job_text)

        job_copy = job.model_copy()
        job_copy.relevance_score = float(score_res.overall_score)
        job_copy.match_reasons = score_res.matched_keywords[:5]
        job_copy.gaps = score_res.missing_keywords[:5]

        if score_res.overall_score >= 80:
            job_copy.recommendation = Recommendation.STRONG_MATCH
        elif score_res.overall_score >= 60:
            job_copy.recommendation = Recommendation.GOOD_MATCH
        elif score_res.overall_score >= 40:
            job_copy.recommendation = Recommendation.PARTIAL_MATCH
        else:
            job_copy.recommendation = Recommendation.WEAK_MATCH

        scored_jobs.append(job_copy)

        # Update in database if url exists
        if job_copy.link:
            h = compute_url_hash(job_copy.link)
            existing_rec = await job_service.repo.get_by_url_hash(h)
            if existing_rec:
                existing_rec.relevance_score = job_copy.relevance_score
                existing_rec.recommendation = str(job_copy.recommendation.value) if job_copy.recommendation else None
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
