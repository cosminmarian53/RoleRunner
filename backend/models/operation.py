"""Models for long-running backend operations."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class OperationStatus(StrEnum):
    """Lifecycle state for async work."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Operation(BaseModel):
    """Status payload emitted over polling/SSE."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid4().hex)
    type: str
    status: OperationStatus = OperationStatus.QUEUED
    message: str = ""
    progress: int = Field(default=0, ge=0, le=100)
    result_id: str = ""
    error: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
