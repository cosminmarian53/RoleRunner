"""Router for CV tailoring, ATS scoring, document rendering, and exports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.cv import (
    CVExportResponse,
    CVGenerateRequest,
    CVScoreRequest,
    CVScoreResult,
    ExportFormat,
    GeneratedCV,
)
from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser
from backend.services.cv_service import CVService
from backend.services.job_scorer import JobScorer
from backend.services.storage_service import StorageService

router = APIRouter(prefix="/api/cv", tags=["cv"])


@router.post("/generate", response_model=GeneratedCV)
async def generate_cv(
    request: CVGenerateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GeneratedCV:
    """Generate a tailored CV for a target job description and export formats."""
    service = CVService(session, current_user.id)
    return await service.generate_and_save_cv(request)


@router.get("/{cv_id}", response_model=GeneratedCV)
async def get_cv(
    cv_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GeneratedCV:
    """Retrieve a previously generated CV by ID."""
    service = CVService(session, current_user.id)
    cv = await service.get_cv_by_id(cv_id)
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")
    return cv


@router.post("/score", response_model=CVScoreResult)
async def score_cv_markdown(
    request: CVScoreRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> CVScoreResult:
    """Calculate deterministic ATS keyword match score for CV text."""
    return JobScorer.score_cv_against_job(request.markdown_content, request.job_description)


@router.get("/{cv_id}/export/{format}", response_model=CVExportResponse)
async def export_cv(
    cv_id: str,
    format: ExportFormat,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CVExportResponse:
    """Get download or signed URL for a specific CV export format."""
    service = CVService(session, current_user.id)
    cv = await service.get_cv_by_id(cv_id)
    if not cv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")

    storage_path = cv.export_paths.get(format.value)
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Format '{format.value}' not generated for this CV.",
        )

    storage = StorageService()
    signed_url = await storage.create_signed_url(storage_path)
    return CVExportResponse(cv_id=cv_id, export_format=format, path=signed_url)
