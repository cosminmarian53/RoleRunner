"""SQLAlchemy relational models for multi-tenant SaaS persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Dialect-agnostic JSON column (uses JSONB on Postgres, standard JSON on SQLite)
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class UserRecord(Base, TimestampMixin):
    """User account record mapped to Supabase auth user."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    settings_data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    # Relationships with cascade deletion
    profile: Mapped[ProfileRecord | None] = relationship(
        "ProfileRecord",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list[JobRecord]] = relationship(
        "JobRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    cvs: Mapped[list[GeneratedCVRecord]] = relationship(
        "GeneratedCVRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    applications: Mapped[list[ApplicationRecord]] = relationship(
        "ApplicationRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    operations: Mapped[list[OperationRecord]] = relationship(
        "OperationRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class ProfileRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single master candidate profile containing full candidate data."""

    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    user: Mapped[UserRecord] = relationship("UserRecord", back_populates="profile")


class JobRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Discovered or tracked job listings."""

    __tablename__ = "jobs"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), index=True, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="web_search", nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    user: Mapped[UserRecord] = relationship("UserRecord", back_populates="jobs")

    __table_args__ = (
        Index("ix_jobs_user_created", "user_id", "created_at"),
        Index("ix_jobs_user_score", "user_id", "relevance_score"),
    )


class GeneratedCVRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tailored CV generated for a target job."""

    __tablename__ = "generated_cvs"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    company: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ats_score: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    storage_paths: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict, nullable=False)

    user: Mapped[UserRecord] = relationship("UserRecord", back_populates="cvs")
    job: Mapped[JobRecord | None] = relationship("JobRecord")


class ApplicationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Application pipeline record (saved -> applied -> interviewing -> offer/rejected)."""

    __tablename__ = "applications"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cv_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("generated_cvs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    job_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="saved", index=True, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    next_step: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserRecord] = relationship("UserRecord", back_populates="applications")
    job: Mapped[JobRecord | None] = relationship("JobRecord")
    cv: Mapped[GeneratedCVRecord | None] = relationship("GeneratedCVRecord")

    __table_args__ = (
        Index("ix_applications_user_status", "user_id", "status"),
        Index("ix_applications_user_created", "user_id", "created_at"),
    )


class OperationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Long-running async operation status tracking."""

    __tablename__ = "operations"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    result_ref: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)

    user: Mapped[UserRecord] = relationship("UserRecord", back_populates="operations")

    __table_args__ = (
        Index("ix_operations_user_status", "user_id", "status"),
        Index("ix_operations_user_created", "user_id", "created_at"),
    )
