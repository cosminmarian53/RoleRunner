"""Pydantic models for tracked job applications."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class ApplicationStatus(StrEnum):
    """Lifecycle state for an application."""

    SAVED = "saved"
    DRAFTING = "drafting"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationCreateRequest(BaseModel):
    """Request to create a tracked application."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    job_id: str = ""
    cv_id: str = ""
    title: str = Field(default="", validation_alias=AliasChoices("title", "job_title"))
    company: str = ""
    job_url: str = ""
    status: ApplicationStatus = ApplicationStatus.SAVED
    notes: str = ""
    contact_name: str = ""
    contact_email: str = ""
    next_step: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_clean = v.strip().lower()
            try:
                return ApplicationStatus(v_clean)
            except ValueError:
                return v_clean
        return v


class ApplicationUpdateRequest(BaseModel):
    """Request to update a tracked application."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    job_id: str | None = None
    cv_id: str | None = None
    title: str | None = Field(default=None, validation_alias=AliasChoices("title", "job_title"))
    company: str | None = None
    job_url: str | None = None
    status: ApplicationStatus | None = None
    notes: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    next_step: str | None = None
    applied_at: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_clean = v.strip().lower()
            try:
                return ApplicationStatus(v_clean)
            except ValueError:
                return v_clean
        return v


class ApplicationRecord(BaseModel):
    """Persisted application record."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str = ""
    job_id: str = ""
    cv_id: str = ""
    title: str
    company: str = ""
    job_url: str = ""
    status: ApplicationStatus = ApplicationStatus.SAVED
    notes: str = ""
    contact_name: str = ""
    contact_email: str = ""
    next_step: str = ""
    applied_at: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ApplicationListResponse(BaseModel):
    """List response for tracked applications."""

    model_config = ConfigDict(extra="ignore")

    applications: list[ApplicationRecord] = Field(default_factory=list)
    total: int = 0


# Backwards-compatible shorter names used by the frontend and early service code.
Application = ApplicationRecord
ApplicationUpsert = ApplicationCreateRequest
ApplicationList = ApplicationListResponse
