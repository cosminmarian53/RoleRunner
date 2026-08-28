"""Pydantic models for CV generation and export."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class ExportFormat(StrEnum):
    """Supported CV export formats."""

    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"


class CVGenerateRequest(BaseModel):
    """Request to generate a tailored CV."""

    model_config = ConfigDict(extra="ignore")

    job_description: str = ""
    job_title: str = ""
    company: str = ""
    job_url: str = ""
    export_format: ExportFormat = ExportFormat.PDF
    use_ai: bool = True

    @model_validator(mode="after")
    def _has_job_context(self) -> "CVGenerateRequest":
        if not self.job_description.strip() and not self.job_url.strip():
            raise ValueError("job_description or job_url is required")
        return self


class CVScoreResult(BaseModel):
    """ATS scoring result for a generated CV."""

    model_config = ConfigDict(extra="ignore")

    overall_score: int = 0
    keyword_match_pct: float = 0.0
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)


class GeneratedCV(BaseModel):
    """A generated, tailored CV."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid4().hex)
    markdown_content: str = ""
    job_title: str = ""
    company: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    export_paths: dict[str, str] = Field(default_factory=dict)
    ats_score: CVScoreResult | None = None


class CVScoreRequest(BaseModel):
    """Request to score existing CV markdown against a job description."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    markdown_content: str = Field(
        default="",
        validation_alias=AliasChoices("markdown_content", "markdown"),
    )
    job_description: str = Field(
        default="",
        validation_alias=AliasChoices("job_description", "description"),
    )
    job_url: str = Field(
        default="",
        validation_alias=AliasChoices("job_url", "url", "link"),
    )


class CVExportResponse(BaseModel):
    """A generated export file path."""

    model_config = ConfigDict(extra="ignore")

    cv_id: str
    export_format: ExportFormat
    path: str
