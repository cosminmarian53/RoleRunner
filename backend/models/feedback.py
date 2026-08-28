"""Pydantic schemas for user feedback submission and retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FeedbackCategory(StrEnum):
    """Category classification for user feedback."""

    GENERAL = "general"
    JOB_SEARCH = "job_search"
    CV_GENERATOR = "cv_generator"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"


class FeedbackCreateRequest(BaseModel):
    """Payload for submitting user feedback."""

    rating: int = Field(..., ge=1, le=5, description="1 to 5 satisfaction rating")
    category: FeedbackCategory = Field(
        default=FeedbackCategory.GENERAL,
        description="Category of feedback",
    )
    message: str = Field(..., min_length=3, max_length=2000, description="Feedback comment or bug details")
    email: str = Field(default="", max_length=255, description="Optional user email for follow up")
    page_url: str = Field(default="", max_length=500, description="URL of page where feedback was submitted")


class FeedbackResponse(BaseModel):
    """Response returned upon feedback submission."""

    id: UUID = Field(default_factory=uuid4)
    rating: int
    category: FeedbackCategory
    message: str
    status: str = "received"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
