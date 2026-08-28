"""Service for job application pipeline management and Kanban stage tracking."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ApplicationRecord as DBApplicationRecord
from backend.models.application import (
    ApplicationCreateRequest,
    ApplicationRecord,
    ApplicationStatus,
    ApplicationUpdateRequest,
)
from backend.repositories.application_repo import ApplicationRepository

logger = logging.getLogger(__name__)


def _to_pydantic(db_app: DBApplicationRecord) -> ApplicationRecord:
    """Convert database ORM entity to Pydantic domain model."""
    status_val = (
        ApplicationStatus(db_app.status)
        if db_app.status in ApplicationStatus.__members__.values()
        else ApplicationStatus.SAVED
    )
    return ApplicationRecord(
        id=str(db_app.id),
        user_id=str(db_app.user_id),
        job_id=str(db_app.job_id) if db_app.job_id else "",
        cv_id=str(db_app.cv_id) if db_app.cv_id else "",
        title=db_app.title,
        company=db_app.company,
        job_url=db_app.job_url,
        status=status_val,
        notes=db_app.notes,
        contact_name=db_app.contact_name,
        contact_email=db_app.contact_email,
        next_step=db_app.next_step,
        applied_at=db_app.applied_at.isoformat() if db_app.applied_at else "",
        created_at=db_app.created_at.isoformat() if db_app.created_at else "",
        updated_at=db_app.updated_at.isoformat() if db_app.updated_at else "",
    )


class ApplicationService:
    """Business logic for tracking applications across hiring stages."""

    def __init__(self, session: AsyncSession, user_id: UUID | str) -> None:
        self.session = session
        self.user_id = UUID(user_id) if not isinstance(user_id, UUID) else user_id
        self.repo = ApplicationRepository(session, self.user_id)

    async def create_application(self, request: ApplicationCreateRequest) -> ApplicationRecord:
        """Create and track a new job application."""
        job_uuid = UUID(request.job_id) if request.job_id and request.job_id.strip() else None
        cv_uuid = UUID(request.cv_id) if request.cv_id and request.cv_id.strip() else None

        applied_datetime = None
        if request.status in (ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEWING, ApplicationStatus.OFFER):
            applied_datetime = datetime.now(timezone.utc)

        db_app = DBApplicationRecord(
            user_id=self.user_id,
            job_id=job_uuid,
            cv_id=cv_uuid,
            title=request.title.strip(),
            company=request.company.strip(),
            job_url=request.job_url.strip(),
            status=request.status.value,
            notes=request.notes.strip(),
            contact_name=request.contact_name.strip(),
            contact_email=request.contact_email.strip(),
            next_step=request.next_step.strip(),
            applied_at=applied_datetime,
        )
        saved = await self.repo.create(db_app)
        return _to_pydantic(saved)

    async def update_application(
        self,
        app_id: UUID | str,
        request: ApplicationUpdateRequest,
    ) -> ApplicationRecord | None:
        """Update fields or stage of an existing application."""
        db_app = await self.repo.get_by_id(app_id)
        if db_app is None:
            return None

        if request.title is not None:
            db_app.title = request.title.strip()
        if request.company is not None:
            db_app.company = request.company.strip()
        if request.job_url is not None:
            db_app.job_url = request.job_url.strip()
        if request.notes is not None:
            db_app.notes = request.notes.strip()
        if request.contact_name is not None:
            db_app.contact_name = request.contact_name.strip()
        if request.contact_email is not None:
            db_app.contact_email = request.contact_email.strip()
        if request.next_step is not None:
            db_app.next_step = request.next_step.strip()

        if request.job_id is not None:
            db_app.job_id = UUID(request.job_id) if request.job_id.strip() else None
        if request.cv_id is not None:
            db_app.cv_id = UUID(request.cv_id) if request.cv_id.strip() else None

        if request.status is not None:
            new_status = request.status.value
            db_app.status = new_status
            if (
                new_status in (ApplicationStatus.APPLIED.value, ApplicationStatus.INTERVIEWING.value)
                and not db_app.applied_at
            ):
                db_app.applied_at = datetime.now(timezone.utc)

        if request.applied_at is not None:
            if request.applied_at.strip():
                try:
                    db_app.applied_at = datetime.fromisoformat(request.applied_at)
                except ValueError:
                    pass
            else:
                db_app.applied_at = None

        await self.session.flush()
        return _to_pydantic(db_app)

    async def get_application(self, app_id: UUID | str) -> ApplicationRecord | None:
        """Get application by ID."""
        db_app = await self.repo.get_by_id(app_id)
        if db_app is None:
            return None
        return _to_pydantic(db_app)

    async def list_applications(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ApplicationRecord]:
        """List applications with optional status filter."""
        if status and status.strip():
            db_apps = await self.repo.list_by_status(status.strip())
        else:
            db_apps = await self.repo.list_all(limit=limit, offset=offset)
        return [_to_pydantic(app) for app in db_apps]

    async def delete_application(self, app_id: UUID | str) -> bool:
        """Delete an application."""
        return await self.repo.delete_by_id(app_id)

    async def get_pipeline_stats(self) -> dict[str, int]:
        """Get aggregate counts of applications per pipeline status."""
        counts = await self.repo.count_by_status()
        # Ensure all standard statuses exist in dict
        for s in ApplicationStatus:
            if s.value not in counts:
                counts[s.value] = 0
        return counts
