"""
AI client — provider-agnostic wrapper.

Supports tenant-isolated Codex harnesses (ChatGPT via device auth).
Provides a unified async `ask()` interface for all services to use.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from backend.services.codex_harness import CodexHarness

logger = logging.getLogger(__name__)

# Registry of user-scoped harness instances
_user_harnesses: dict[str, CodexHarness] = {}
_global_harness: CodexHarness | None = None


def get_harness(user_id: str | UUID | None = None) -> CodexHarness:
    """Get or create a tenant-scoped or global CodexHarness instance."""
    global _global_harness
    if user_id is not None:
        key = str(user_id)
        if key not in _user_harnesses:
            _user_harnesses[key] = CodexHarness(user_id=key)
        return _user_harnesses[key]

    if _global_harness is None:
        from backend.config import settings

        _global_harness = CodexHarness(codex_home=settings.codex_home)
    return _global_harness


async def ask(
    prompt: str,
    *,
    user_id: str | UUID | None = None,
    system_prompt: str = "",
) -> str:
    """
    Send a prompt to the AI and get a response.

    Uses the user's isolated Codex harness (ChatGPT subscription) — no API keys needed.
    """
    harness = get_harness(user_id=user_id)
    return await harness.ask(prompt, system_prompt=system_prompt)


def get_provider_status(user_id: str | UUID | None = None) -> dict[str, Any]:
    """Get AI provider status for the frontend."""
    harness = get_harness(user_id=user_id)
    return harness.get_status()
