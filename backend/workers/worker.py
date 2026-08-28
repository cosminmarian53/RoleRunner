"""ARQ worker configuration and execution registry."""

import logging
from typing import Any

from arq.connections import RedisSettings

from backend.config import settings
from backend.services.redis_service import close_redis, get_redis_client
from backend.workers.tasks import (
    run_ai_scoring,
    run_cv_generation,
    run_job_search,
    run_profile_extraction,
)

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize resources on worker startup."""
    logger.info("Starting up ARQ worker...")
    ctx["redis"] = get_redis_client()


async def shutdown(ctx: dict[str, Any]) -> None:
    """Clean up resources on worker shutdown."""
    logger.info("Shutting down ARQ worker...")
    await close_redis()


class WorkerSettings:
    """ARQ Worker configuration class."""

    # Registered tasks
    functions = [
        run_profile_extraction,
        run_job_search,
        run_ai_scoring,
        run_cv_generation,
    ]

    # Connection settings from app config
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Worker bounds
    max_jobs = 10
    job_timeout = 300  # 5 minutes max per job
    keep_result = 3600  # Keep job results for 1 hour

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown
