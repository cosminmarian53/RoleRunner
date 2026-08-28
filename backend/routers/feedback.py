"""Router for submitting, storing, and viewing user feedback."""

from __future__ import annotations

import logging
import os
from typing import Sequence
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.feedback import (
    FeedbackCategory,
    FeedbackCreateRequest,
    FeedbackResponse,
)
from backend.repositories.feedback import FeedbackRepository
from backend.security.auth import get_optional_user
from backend.security.jwt import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


async def forward_feedback_to_webhook(payload: FeedbackCreateRequest, feedback_id: UUID) -> None:
    """Optionally forward user feedback to Discord, Slack, or Telegram webhook."""
    webhook_url = os.getenv("FEEDBACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return

    stars = "⭐" * payload.rating
    category_labels = {
        "general": "💬 General Feedback",
        "job_search": "🔍 Job Search Feedback",
        "cv_generator": "📄 CV Generator Feedback",
        "bug_report": "🐛 Bug Report",
        "feature_request": "💡 Feature Request",
    }
    cat_title = category_labels.get(str(payload.category), "💬 Feedback")

    # Format for Discord / Slack webhook
    embed_data = {
        "title": f"{cat_title} ({stars})",
        "description": payload.message,
        "color": 65280 if payload.rating >= 4 else (16776960 if payload.rating == 3 else 16711680),
        "fields": [
            {"name": "Feedback ID", "value": str(feedback_id), "inline": True},
            {"name": "Page URL", "value": payload.page_url or "N/A", "inline": True},
            {"name": "User Email", "value": payload.email or "Anonymous", "inline": True},
        ],
    }

    body = {
        "username": "RoleRunner Feedback",
        "embeds": [embed_data],
        "content": f"New feedback received on **RoleRunner**: {cat_title}",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, json=body)
            if resp.status_code >= 400:
                logger.warning("Feedback webhook returned status %d: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.warning("Failed to forward feedback to webhook: %s", exc)


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    request: FeedbackCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser | None = Depends(get_optional_user),
) -> FeedbackResponse:
    """Submit user feedback, rating, or bug report and persist in database."""
    user_id = current_user.id if current_user else None

    # 1. Persist feedback directly into database
    repo = FeedbackRepository(session)
    record = await repo.create(request, user_id=user_id)

    logger.info(
        "Feedback saved (id=%s, rating=%d, category=%s, user=%s)",
        record.id,
        record.rating,
        record.category,
        user_id or "anonymous",
    )

    # 2. Trigger webhook alert if configured
    background_tasks.add_task(forward_feedback_to_webhook, request, record.id)

    return FeedbackResponse(
        id=record.id,
        rating=record.rating,
        category=FeedbackCategory(record.category),
        message=record.message,
        status="received",
        created_at=record.created_at,
    )


@router.get("", response_model=list[FeedbackResponse])
async def list_feedback(
    category: FeedbackCategory | None = Query(None, description="Filter by feedback category"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> Sequence[FeedbackResponse]:
    """Retrieve feedback submissions for review."""
    repo = FeedbackRepository(session)
    records = await repo.list_all(category=category, limit=limit, offset=offset)
    return [
        FeedbackResponse(
            id=rec.id,
            rating=rec.rating,
            category=FeedbackCategory(rec.category),
            message=rec.message,
            status="received",
            created_at=rec.created_at,
        )
        for rec in records
    ]
