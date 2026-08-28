"""
AI client — provider-agnostic wrapper.

Currently only supports the Codex harness (ChatGPT via device auth).
Provides a unified async `ask()` interface for all services to use.
"""

from __future__ import annotations

import logging

from backend.services.codex_harness import CodexHarness

logger = logging.getLogger(__name__)

# Singleton harness instance
_harness: CodexHarness | None = None


def get_harness() -> CodexHarness:
    """Get or create the global CodexHarness instance."""
    global _harness
    if _harness is None:
        from backend.config import settings

        _harness = CodexHarness(codex_home=settings.codex_home)
    return _harness


async def ask(
    prompt: str,
    *,
    system_prompt: str = "",
) -> str:
    """
    Send a prompt to the AI and get a response.

    Uses the Codex harness (ChatGPT subscription) — no API keys needed.
    """
    harness = get_harness()
    return await harness.ask(prompt, system_prompt=system_prompt)


def get_provider_status() -> dict:
    """Get AI provider status for the frontend."""
    harness = get_harness()
    return harness.get_status()
