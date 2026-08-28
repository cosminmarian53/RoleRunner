"""Router for job application lifecycle, pipeline state transitions, and Kanban analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.application import (
    ApplicationCreateRequest,
    ApplicationRecord,
    ApplicationUpdateRequest,
)
from backend.security.auth import get_current_user
from backend.security.jwt import CurrentUser
from backend.services.application_service import ApplicationService
from backend.services.ats_form_scanner import ApplicationPackResponse, ATSFormScanner

router = APIRouter(prefix="/api/applications", tags=["applications"])


class ScanFormRequest(BaseModel):
    """Payload to scan an employer form and draft reviewable answers."""

    job_url: str = ""
    job_title: str = ""
    company: str = ""
    notes: str = ""


@router.get("", response_model=list[ApplicationRecord])
async def list_applications(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ApplicationRecord]:
    """List tracked job applications with optional status filter."""
    service = ApplicationService(session, current_user.id)
    return await service.list_applications(status=status_filter, limit=limit, offset=offset)


@router.get("/stats", response_model=dict[str, int])
async def get_application_stats(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Get aggregate counts of applications in each pipeline stage."""
    service = ApplicationService(session, current_user.id)
    return await service.get_pipeline_stats()


@router.post("", response_model=ApplicationRecord, status_code=status.HTTP_201_CREATED)
async def create_application(
    request: ApplicationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApplicationRecord:
    """Create and start tracking a new job application."""
    service = ApplicationService(session, current_user.id)
    return await service.create_application(request)


@router.get("/{app_id}", response_model=ApplicationRecord)
async def get_application(
    app_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApplicationRecord:
    """Get a tracked application by ID."""
    service = ApplicationService(session, current_user.id)
    app = await service.get_application(app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return app


@router.patch("/{app_id}", response_model=ApplicationRecord)
@router.put("/{app_id}", response_model=ApplicationRecord)
async def update_application(
    app_id: str,
    request: ApplicationUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApplicationRecord:
    """Update fields or stage of an existing application."""
    service = ApplicationService(session, current_user.id)
    app = await service.update_application(app_id, request)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return app


@router.delete("/{app_id}")
async def delete_application(
    app_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Delete a tracked application."""
    service = ApplicationService(session, current_user.id)
    deleted = await service.delete_application(app_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return {"success": True}


@router.post("/scan-form", response_model=ApplicationPackResponse)
async def scan_application_form(
    request: ScanFormRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApplicationPackResponse:
    """Scan apply page, extract employer questions, and draft tailored answers."""
    from backend.services.profile_service import ProfileService

    profile_svc = ProfileService(session=session, user_id=current_user.id)
    profile = await profile_svc.get_profile()

    scanner = ATSFormScanner(user_id=current_user.id)
    return await scanner.generate_application_pack(
        profile=profile,
        job_title=request.job_title,
        company=request.company,
        job_description=request.notes or "",
        job_url=request.job_url,
    )
