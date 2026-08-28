"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = job-bot/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """App settings from .env or environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RoleRunner"
    app_env: str = "development"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    # Hosted deployment / Supabase. Local development can run without these.
    public_base_url: str = "http://localhost:8000"
    database_url: str = "sqlite+aiosqlite:///./data/rolerunner.db"
    redis_url: str = "redis://localhost:6379/0"
    supabase_url: AnyHttpUrl | None = None
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_storage_bucket: str = "rolerunner"

    # Codex harness
    codex_home: str = os.path.expanduser("~/.codex")
    codex_timeout_seconds: int = 120

    # Data paths
    data_dir: Path = PROJECT_ROOT / "data"
    profile_path: Path = PROJECT_ROOT / "data" / "profiles" / "profile.json"
    credentials_dir: Path = PROJECT_ROOT / "data" / "credentials"
    ai_credentials_root: Path = PROJECT_ROOT / "data" / "credentials" / "codex"
    jobs_dir: Path = PROJECT_ROOT / "data" / "jobs"
    exports_dir: Path = PROJECT_ROOT / "data" / "exports"
    applications_dir: Path = PROJECT_ROOT / "data" / "applications"
    operations_dir: Path = PROJECT_ROOT / "data" / "operations"

    # Runtime bounds
    max_upload_size_mb: int = 8
    default_search_limit: int = 20
    max_search_limit: int = 50
    ai_score_limit: int = 10

    @field_validator(
        "data_dir",
        "profile_path",
        "credentials_dir",
        "ai_credentials_root",
        "jobs_dir",
        "exports_dir",
        "applications_dir",
        "operations_dir",
        mode="before",
    )
    @classmethod
    def _expand_path(cls, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    def ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        for d in [
            self.data_dir,
            self.profile_path.parent,
            self.credentials_dir,
            self.ai_credentials_root,
            self.jobs_dir,
            self.exports_dir,
            self.applications_dir,
            self.operations_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def cors_origin_list(self) -> list[str]:
        """Return normalized CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
settings.ensure_dirs()
