"""Router for candidate profile ingestion, text parsing, and file uploads."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.profile import (
    CandidateProfile,
    ProfileTextParseRequest,
    ProfileUploadResponse,
)
from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser
from backend.services.profile_service import ProfileService

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=CandidateProfile)
async def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    """Fetch current user's master candidate profile."""
    service = ProfileService(session, current_user.id)
    return await service.get_profile()


@router.post("", response_model=CandidateProfile)
@router.post("/form", response_model=CandidateProfile)
async def save_profile(
    profile: CandidateProfile,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CandidateProfile:
    """Save or update current user's master candidate profile."""
    service = ProfileService(session, current_user.id)
    return await service.save_profile(profile)


@router.delete("", response_model=dict[str, str])
async def delete_profile(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete current user's master candidate profile."""
    service = ProfileService(session, current_user.id)
    await service.delete_profile()
    return {"status": "deleted", "message": "Profile successfully deleted."}


@router.post("/parse-text", response_model=ProfileUploadResponse)
async def parse_profile_text(
    request: ProfileTextParseRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProfileUploadResponse:
    """Parse raw resume or LinkedIn text into structured profile."""
    service = ProfileService(session, current_user.id)
    return await service.parse_and_save_text(request.text, merge_existing=request.merge_existing)


@router.post("/upload", response_model=ProfileUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProfileUploadResponse:
    """Upload resume document (PDF, DOCX, TXT) and extract candidate profile."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    service = ProfileService(session, current_user.id)
    return await service.parse_and_save_upload(file.filename, file_bytes)
