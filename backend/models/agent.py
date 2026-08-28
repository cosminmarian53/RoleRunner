"""Pydantic models for AI agent endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AgentAskRequest(BaseModel):
    """Request to ask the configured AI provider."""

    model_config = ConfigDict(extra="ignore")

    prompt: str
    system_prompt: str = ""


class AgentAskResponse(BaseModel):
    """Response from the configured AI provider."""

    model_config = ConfigDict(extra="ignore")

    answer: str


class AgentStatusResponse(BaseModel):
    """AI provider status."""

    model_config = ConfigDict(extra="ignore")

    provider: str = "codex"
    authenticated: bool = False
    codex_home: str = ""
    auth_file_exists: bool = False
    last_used: float = 0.0


class AgentLoginStartResponse(BaseModel):
    """Codex device-auth start response."""

    model_config = ConfigDict(extra="ignore")

    authorization_url: str | None = None
    device_code: str | None = None
    raw_output: str = ""


class AgentLoginWaitRequest(BaseModel):
    """Request to wait for Codex device-auth completion."""

    model_config = ConfigDict(extra="ignore")

    timeout_seconds: int = Field(default=300, ge=1, le=1200)


class AgentLoginWaitResponse(BaseModel):
    """Codex device-auth wait result."""

    model_config = ConfigDict(extra="ignore")

    authenticated: bool
