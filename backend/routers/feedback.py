"""Router for receiving and alerting on user feedback."""

from __future__ import annotations

import logging
import os
from uuid import uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, status

from backend.models.feedback import FeedbackCreateRequest, FeedbackResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


async def forward_feedback_to_webhook(payload: FeedbackCreateRequest) -> None:
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
            {"name": "Page URL", "value": payload.page_url or "N/A", "inline": True},
            {"name": "User Email", "value": payload.email or "Anonymous", "inline": True},
        ],
    }

    body = {
        "username": "RoleRunner Feedback Bot",
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
) -> FeedbackResponse:
    """Submit user feedback, rating, or bug report."""
    logger.info(
        "User feedback received: rating=%d category=%s email=%s",
        request.rating,
        request.category,
        request.email or "anonymous",
    )

    # Trigger background webhook alert if configured
    background_tasks.add_task(forward_feedback_to_webhook, request)

    return FeedbackResponse(
        id=uuid4(),
        rating=request.rating,
        category=request.category,
        message=request.message,
        status="received",
    )
