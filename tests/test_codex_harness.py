"""Contract tests for the Codex CLI harness without invoking the real CLI."""

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import pytest

from backend.services.codex_harness import CodexHarness, CodexSession


class FakeStream:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = iter(chunks)

    async def read(self, _size: int) -> bytes:
        return next(self.chunks, b"")


class FakeProcess:
    def __init__(
        self,
        *,
        stdout_chunks: list[bytes] | None = None,
        communicate_result: tuple[bytes, bytes] = (b"", b""),
        returncode: int | None = 0,
    ) -> None:
        self.stdout = FakeStream(stdout_chunks or [])
        self._communicate_result = communicate_result
        self.returncode = returncode
        self.input: bytes | None = None
        self.killed = False
        self.terminated = False

    async def communicate(self, value: bytes | None = None) -> tuple[bytes, bytes]:
        self.input = value
        return self._communicate_result

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    async def wait(self) -> int:
        return self.returncode or 0


def make_harness(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, authenticated: bool = False) -> CodexHarness:
    monkeypatch.setattr(CodexHarness, "_login_status_sync", lambda _self: (authenticated, "status"))
    return CodexHarness(str(tmp_path / "codex-home"))


def test_parse_login_output_strips_ansi_and_requires_no_token_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = make_harness(monkeypatch, tmp_path)
    harness._login_started_at = 100.0

    result = harness.parse_login_output(
        "\x1b[32mOpen https://auth.openai.com/device), then enter ABCD-12345\x1b[0m\r\n"
    )

    assert result.authorization_url == "https://auth.openai.com/device"
    assert result.device_code == "ABCD-12345"
    assert result.expires_at == 1300.0
    assert "\x1b" not in result.raw_output


def test_login_status_uses_cli_status_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="Logged in using ChatGPT", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    harness = object.__new__(CodexHarness)
    harness.codex_home = str(tmp_path / "codex-home")
    harness.session = CodexSession(codex_home=harness.codex_home)

    authenticated, output = harness._login_status_sync()

    assert authenticated is True
    assert output == "Logged in using ChatGPT"
    assert calls[0][0] == ["codex", "login", "status"]
    assert calls[0][1]["timeout"] == 10
    assert calls[0][1]["env"]["CODEX_HOME"] == harness.codex_home


@pytest.mark.asyncio
async def test_start_login_uses_device_auth_and_combines_split_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = make_harness(monkeypatch, tmp_path)
    process = FakeProcess(
        stdout_chunks=[b"Open https://auth.openai.com/device\n", b"Enter code ABCD-1234\n"],
        returncode=None,
    )
    calls: list[tuple[str, ...]] = []

    async def fake_create(*args: str, **_kwargs: Any) -> FakeProcess:
        calls.append(args)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    result = await harness.start_login()

    assert calls == [("codex", "login", "--device-auth")]
    assert result.authorization_url == "https://auth.openai.com/device"
    assert result.device_code == "ABCD-1234"
    assert harness._login_proc is process


@pytest.mark.asyncio
async def test_ask_uses_ephemeral_read_only_exec_and_stdin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    harness = make_harness(monkeypatch, tmp_path, authenticated=True)
    process = FakeProcess(communicate_result=(b"<think>hidden</think>\nFinal answer\n", b""))
    calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []

    async def fake_create(*args: str, **kwargs: Any) -> FakeProcess:
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    answer = await harness.ask("candidate text", system_prompt="Return JSON")

    command = calls[0][0]
    assert command[:2] == ("codex", "exec")
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[-1] == "-"
    assert process.input == b"<instructions>\nReturn JSON\n</instructions>\n\ncandidate text"
    assert answer == "Final answer"


@pytest.mark.asyncio
async def test_ask_surfaces_cli_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    harness = make_harness(monkeypatch, tmp_path, authenticated=True)
    process = FakeProcess(communicate_result=(b"", b"invalid option"), returncode=2)

    async def fake_create(*_args: str, **_kwargs: Any) -> FakeProcess:
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    with pytest.raises(RuntimeError, match="Codex CLI error: invalid option"):
        await harness.ask("prompt")
