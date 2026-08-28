"""Async SQLAlchemy engine and session management."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from backend.config import settings
from backend.db.base import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def normalize_database_url(url: str) -> str:
    """Normalize raw database URLs to their async driver equivalents."""
    cleaned = url.strip()
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql+asyncpg://" + cleaned[len("postgres://") :]
    elif cleaned.startswith("postgresql://") and not cleaned.startswith("postgresql+asyncpg://"):
        cleaned = "postgresql+asyncpg://" + cleaned[len("postgresql://") :]
    elif cleaned.startswith("sqlite://") and not cleaned.startswith("sqlite+aiosqlite://"):
        cleaned = "sqlite+aiosqlite://" + cleaned[len("sqlite://") :]
    return cleaned


def create_engine_for_url(
    url: str | None = None,
    *,
    echo: bool = False,
    pool_override: Any = None,
) -> AsyncEngine:
    """Create a configured AsyncEngine for PostgreSQL or SQLite."""
    db_url = normalize_database_url(url or settings.database_url)
    engine_kwargs: dict[str, Any] = {"echo": echo}

    if "sqlite" in db_url:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in db_url:
            engine_kwargs["poolclass"] = StaticPool
        elif pool_override is not None:
            engine_kwargs["poolclass"] = pool_override
    else:
        # PostgreSQL / asyncpg connection pool tuning
        if pool_override is not None:
            engine_kwargs["poolclass"] = pool_override
        else:
            engine_kwargs["pool_size"] = 10
            engine_kwargs["max_overflow"] = 20
            engine_kwargs["pool_pre_ping"] = True
            engine_kwargs["pool_recycle"] = 300

    engine = create_async_engine(db_url, **engine_kwargs)

    if "sqlite" in db_url:
        # Enable foreign key constraint enforcement in SQLite
        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_engine() -> AsyncEngine:
    """Get or lazily initialize the singleton application AsyncEngine."""
    global _engine
    if _engine is None:
        _engine = create_engine_for_url()
    return _engine


def async_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Get or create an async sessionmaker bound to the given or singleton engine."""
    global _session_factory
    active_engine = engine or get_engine()
    if _session_factory is None or engine is not None:
        factory = async_sessionmaker(
            bind=active_engine,
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
        )
        if engine is None:
            _session_factory = factory
        return factory
    return _session_factory


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Initialize database tables defined on Base metadata."""
    active_engine = engine or get_engine()
    async with active_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/initialized successfully.")


async def close_db() -> None:
    """Close the global database connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine connection pool closed.")


def reset_engine() -> None:
    """Synchronously reset singleton references (primarily for testing)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an isolated AsyncSession.

    Automatically rolls back on any uncaught exception.
    """
    session_maker = async_session_factory()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
