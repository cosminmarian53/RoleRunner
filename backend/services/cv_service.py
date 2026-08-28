"""Orchestration service for generating, scoring, rendering, and persisting tailored CVs."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import GeneratedCVRecord
from backend.models.cv import CVGenerateRequest, ExportFormat, GeneratedCV
from backend.repositories.cv_repo import CVRepository
from backend.services.cv_generator import CVGenerator
from backend.services.docx_renderer import CVDocxRenderer
from backend.services.job_scorer import JobScorer
from backend.services.pdf_renderer import CVReportLabRenderer
from backend.services.profile_service import ProfileService
from backend.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class CVService:
    """End-to-end service for CV generation, scoring, document rendering, and persistence."""

    def __init__(
        self,
        session: AsyncSession,
        user_id: UUID | str,
        storage_service: StorageService | None = None,
    ) -> None:
        self.session = session
        self.user_id = UUID(user_id) if not isinstance(user_id, UUID) else user_id
        self.repo = CVRepository(session, self.user_id)
        self.profile_service = ProfileService(session, self.user_id)
        self.cv_generator = CVGenerator(user_id=self.user_id)
        self.pdf_renderer = CVReportLabRenderer()
        self.docx_renderer = CVDocxRenderer()
        self.storage = storage_service or StorageService()

    async def generate_and_save_cv(
        self,
        request: CVGenerateRequest,
        job_id: UUID | None = None,
    ) -> GeneratedCV:
        """
        Generate tailored CV markdown, compute ATS score, render requested document formats,
        store artifacts, and persist record in PostgreSQL.
        """
        # 1. Load candidate profile
        profile = await self.profile_service.get_profile()

        # 2. Generate Tailored Markdown
        markdown_content = await self.cv_generator.generate_markdown(
            profile=profile,
            job_description=request.job_description,
            job_title=request.job_title,
            company=request.company,
            use_ai=request.use_ai,
        )

        # 3. Score CV against job description
        ats_score = JobScorer.score_cv_against_job(markdown_content, request.job_description)

        # 4. Render and store document exports
        export_paths: dict[str, str] = {}

        # Render PDF
        pdf_bytes = self.pdf_renderer.render_markdown_to_pdf_bytes(markdown_content)
        pdf_filename = f"cv_{request.job_title or 'custom'}.pdf".replace(" ", "_")
        pdf_storage_path = await self.storage.upload_resume(
            self.user_id,
            pdf_bytes,
            pdf_filename,
            content_type="application/pdf",
        )
        export_paths[ExportFormat.PDF.value] = pdf_storage_path

        # Render DOCX if requested
        if request.export_format == ExportFormat.DOCX:
            docx_bytes = self.docx_renderer.render_markdown_to_docx_bytes(markdown_content)
            docx_filename = f"cv_{request.job_title or 'custom'}.docx".replace(" ", "_")
            docx_storage_path = await self.storage.upload_resume(
                self.user_id,
                docx_bytes,
                docx_filename,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            export_paths[ExportFormat.DOCX.value] = docx_storage_path

        export_paths[ExportFormat.MARKDOWN.value] = "inline"

        # 5. Persist record in Postgres
        cv_record = GeneratedCVRecord(
            user_id=self.user_id,
            job_id=job_id,
            job_title=request.job_title,
            company=request.company,
            markdown_content=markdown_content,
            ats_score=ats_score.model_dump(mode="json"),
            storage_paths=export_paths,
        )
        saved_record = await self.repo.create(cv_record)

        return GeneratedCV(
            id=str(saved_record.id),
            markdown_content=markdown_content,
            job_title=request.job_title,
            company=request.company,
            created_at=saved_record.created_at.isoformat() if saved_record.created_at else "",
            export_paths=export_paths,
            ats_score=ats_score,
        )

    async def get_cv_by_id(self, cv_id: UUID | str) -> GeneratedCV | None:
        """Retrieve a generated CV record by primary key."""
        rec = await self.repo.get_by_id(cv_id)
        if rec is None:
            return None

        from backend.models.cv import CVScoreResult

        score_res = CVScoreResult(**rec.ats_score) if rec.ats_score else None
        export_paths = rec.storage_paths or {}
        if ExportFormat.MARKDOWN.value not in export_paths:
            export_paths[ExportFormat.MARKDOWN.value] = "inline"

        return GeneratedCV(
            id=str(rec.id),
            markdown_content=rec.markdown_content,
            job_title=rec.job_title,
            company=rec.company,
            created_at=rec.created_at.isoformat() if rec.created_at else "",
            export_paths=export_paths,
            ats_score=score_res,
        )
