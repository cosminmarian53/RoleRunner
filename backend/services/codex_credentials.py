"""Per-user isolated credential storage directory manager for Codex CLI."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from uuid import UUID

from backend.config import settings

logger = logging.getLogger(__name__)

SAFE_USER_ID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


class CredentialSecurityError(Exception):
    """Raised when an invalid user ID or path traversal attempt is detected."""


class CodexCredentialsManager:
    """Manages secure, tenant-isolated directories for Codex CLI device authentication."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or settings.ai_credentials_root).resolve()
        self._ensure_root()

    def _ensure_root(self) -> None:
        """Create the root directory with secure 0700 permissions."""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.root_dir.chmod(0o700)
        except OSError as exc:
            logger.warning("Could not set 0700 permissions on root credentials dir: %s", exc)

    def sanitize_user_id(self, user_id: str | UUID) -> str:
        """Validate and return normalized user_id string, rejecting path traversal."""
        user_str = str(user_id).strip().lower()
        if not SAFE_USER_ID_RE.match(user_str):
            raise CredentialSecurityError(f"Invalid tenant UUID identifier: {user_id!r}")
        return user_str

    def get_user_codex_home(self, user_id: str | UUID) -> Path:
        """
        Get the secure isolated CODEX_HOME directory for a tenant.

        Ensures 0700 permissions on the user directory.
        """
        sanitized = self.sanitize_user_id(user_id)
        user_dir = (self.root_dir / sanitized).resolve()

        # Prevent traversal outside root
        if not user_dir.is_relative_to(self.root_dir):
            raise CredentialSecurityError("Path traversal detected outside credentials root")

        user_dir.mkdir(parents=True, exist_ok=True)
        try:
            user_dir.chmod(0o700)
        except OSError as exc:
            logger.warning("Could not set 0700 on %s: %s", user_dir, exc)

        return user_dir

    def enforce_file_permissions(self, user_id: str | UUID) -> None:
        """Enforce 0600 on any existing files (e.g. auth.json) in the user's directory."""
        user_dir = self.get_user_codex_home(user_id)
        for item in user_dir.iterdir():
            if item.is_file():
                try:
                    item.chmod(0o600)
                except OSError as exc:
                    logger.warning("Could not set 0600 on %s: %s", item, exc)

    def delete_user_credentials(self, user_id: str | UUID) -> bool:
        """Completely wipe a user's isolated credential directory."""
        sanitized = self.sanitize_user_id(user_id)
        user_dir = (self.root_dir / sanitized).resolve()

        if not user_dir.is_relative_to(self.root_dir):
            raise CredentialSecurityError("Path traversal detected outside credentials root")

        if user_dir.exists() and user_dir.is_dir():
            shutil.rmtree(user_dir, ignore_errors=True)
            logger.info("Deleted Codex credentials directory for user %s", sanitized)
            return True
        return False


_credentials_manager: CodexCredentialsManager | None = None


def get_credentials_manager() -> CodexCredentialsManager:
    """Get the global credential manager instance."""
    global _credentials_manager
    if _credentials_manager is None:
        _credentials_manager = CodexCredentialsManager()
    return _credentials_manager
