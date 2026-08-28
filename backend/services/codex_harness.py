"""Codex CLI harness for per-user ChatGPT device authentication."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_MS = 20 * 60 * 1000
DEVICE_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4,5}\b")
AUTH_URL_PATTERN = re.compile(r"https://[^\s<>\"']+")


@dataclass
class DeviceAuthInfo:
    """Info returned during the device-auth flow for user to complete."""

    authorization_url: str | None = None
    device_code: str | None = None
    raw_output: str = ""
    expires_at: float | None = None


@dataclass
class CodexSession:
    """Tracks the state of a Codex session."""

    auth_path: Path | None = None
    is_authenticated: bool = False
    last_used: float = 0.0
    codex_home: str = ""


class CodexHarness:
    """
    Manages the Codex CLI interaction for ChatGPT access.

    Uses `codex` CLI subprocess for both authentication and prompt execution.
    No API keys needed — leverages ChatGPT subscription via device auth.
    """

    def __init__(self, codex_home: str | None = None) -> None:
        self.codex_home = str(Path(codex_home or "~/.codex").expanduser())
        self.session = CodexSession(codex_home=self.codex_home)
        self._login_proc: asyncio.subprocess.Process | None = None
        self._login_output: list[str] = []
        self._login_started_at: float = 0.0
        self._check_existing_session()

    def _env(self) -> dict[str, str]:
        """Return a CLI environment with terminal decoration disabled."""
        Path(self.codex_home).mkdir(parents=True, exist_ok=True)
        return {
            **os.environ,
            "NO_COLOR": "1",
            "TERM": "dumb",
            "CODEX_HOME": self.codex_home,
        }

    def _check_existing_session(self) -> None:
        """Check the current CLI login state without reading token contents."""
        auth_path = Path(self.codex_home) / "auth.json"
        authenticated, output = self._login_status_sync()
        self.session.auth_path = auth_path if auth_path.exists() else None
        self.session.is_authenticated = authenticated
        if authenticated:
            self.session.last_used = time.time()
            logger.info("Codex login is active")
        elif output:
            logger.debug("Codex login status: %s", output)

    def _login_status_sync(self) -> tuple[bool, str]:
        """Run `codex login status` synchronously for status endpoints."""
        import subprocess

        try:
            result = subprocess.run(
                ["codex", "login", "status"],
                capture_output=True,
                check=False,
                env=self._env(),
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            return False, "Codex CLI not found"
        except subprocess.TimeoutExpired:
            return False, "Codex login status timed out"

        output = self._strip_terminal_formatting(f"{result.stdout}\n{result.stderr}").strip()
        return result.returncode == 0 and "not logged in" not in output.lower(), output

    async def refresh_auth_status(self) -> bool:
        """Refresh auth status through the Codex CLI."""
        authenticated, _ = await asyncio.to_thread(self._login_status_sync)
        auth_path = Path(self.codex_home) / "auth.json"
        self.session.auth_path = auth_path if auth_path.exists() else None
        self.session.is_authenticated = authenticated
        if authenticated:
            self.session.last_used = time.time()
        return authenticated

    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid session."""
        return self.session.is_authenticated

    def _strip_terminal_formatting(self, text: str) -> str:
        """Strip ANSI escape codes and terminal formatting (from open·kritt)."""
        escape = chr(27)
        bell = chr(7)
        # Operating system commands
        text = re.sub(rf"{escape}\][^{bell}]*(?:{bell}|{escape}\\)", "", text)
        # Control sequences
        text = re.sub(rf"{escape}\[[0-?]*[ -/]*[@-~]", "", text)
        return text.replace("\r", "")

    def parse_login_output(self, raw_output: str) -> DeviceAuthInfo:
        """Parse the output of `codex login` for URL and device code."""
        output = self._strip_terminal_formatting(raw_output)
        url_match = AUTH_URL_PATTERN.search(output)
        code_match = DEVICE_CODE_PATTERN.search(output)

        return DeviceAuthInfo(
            authorization_url=url_match.group(0).rstrip("),.;") if url_match else None,
            device_code=code_match.group(0) if code_match else None,
            raw_output=output,
            expires_at=(self._login_started_at + SESSION_TIMEOUT_MS / 1000) if self._login_started_at else None,
        )

    async def start_login(self) -> DeviceAuthInfo:
        """
        Initiate the Codex device-auth login flow.

        Returns the URL and device code for the user to complete in their browser.
        """
        if self._login_proc and self._login_proc.returncode is None:
            existing = self.parse_login_output("".join(self._login_output))
            if existing.authorization_url and existing.device_code:
                return existing
            self._login_proc.terminate()
            await self._login_proc.wait()

        try:
            self._login_started_at = time.time()
            self._login_output = []
            proc = await asyncio.create_subprocess_exec(
                "codex",
                "login",
                "--device-auth",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=self._env(),
            )
            self._login_proc = proc

            auth_info = DeviceAuthInfo()
            assert proc.stdout is not None  # guaranteed by PIPE

            # Read output until we get the URL + code, or process exits
            while True:
                try:
                    chunk = await asyncio.wait_for(proc.stdout.read(4096), timeout=30)
                except asyncio.TimeoutError:
                    break

                if not chunk:
                    break

                text = chunk.decode("utf-8", errors="replace")
                self._login_output.append(text)
                combined = "".join(self._login_output)

                auth_info = self.parse_login_output(combined)
                if auth_info.authorization_url and auth_info.device_code:
                    break

            if proc.returncode not in (None, 0) and not auth_info.authorization_url:
                raise RuntimeError(self._strip_terminal_formatting("".join(self._login_output)).strip())

            return auth_info

        except FileNotFoundError:
            raise RuntimeError("Codex CLI not found. Install it before starting provider login.")

    async def wait_for_auth(self, timeout: int = 300) -> bool:
        """
        Wait for the user to complete the device-auth flow.

        Polls the Codex CLI status until auth is complete or timeout expires.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await self.refresh_auth_status():
                logger.info("Codex authentication successful")
                return True
            await asyncio.sleep(2)

        return False

    async def ask(self, prompt: str, *, system_prompt: str = "") -> str:
        """
        Send a prompt to ChatGPT via the Codex CLI.

        Uses `codex exec` in non-interactive mode to get a response.
        The Codex CLI handles all auth token management internally.
        """
        if not self.is_authenticated and not await self.refresh_auth_status():
            raise RuntimeError("Not authenticated. Run login first.")

        # Build the full prompt with system context
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"<instructions>\n{system_prompt}\n</instructions>\n\n{prompt}"

        try:
            with tempfile.TemporaryDirectory(prefix="jobbot-codex-") as workdir:
                proc = await asyncio.create_subprocess_exec(
                    "codex",
                    "exec",
                    "--ephemeral",
                    "--sandbox",
                    "read-only",
                    "--skip-git-repo-check",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--color",
                    "never",
                    "--cd",
                    workdir,
                    "-",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=self._env(),
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(full_prompt.encode("utf-8")),
                        timeout=120,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.communicate()
                    raise

            output = stdout.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                err_text = stderr.decode("utf-8", errors="replace").strip()
                logger.error("Codex CLI error (code %d): %s", proc.returncode, err_text)
                raise RuntimeError(f"Codex CLI error: {err_text}")

            self.session.last_used = time.time()
            # Strip any thinking blocks
            output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()
            return output

        except asyncio.TimeoutError:
            raise RuntimeError("Codex CLI timed out after 120 seconds")
        except FileNotFoundError:
            raise RuntimeError("Codex CLI not found")

    def get_status(self) -> dict:
        """Get current harness status for the frontend."""
        return {
            "provider": "codex",
            "authenticated": self.is_authenticated,
            "codex_home": self.codex_home,
            "auth_file_exists": Path(self.codex_home, "auth.json").exists(),
            "login_in_progress": bool(self._login_proc and self._login_proc.returncode is None),
            "last_used": self.session.last_used,
        }
