"""Tests for environment-backed application settings."""

from pathlib import Path

from backend.config import PROJECT_ROOT, Settings


def test_relative_data_paths_are_rooted_at_project() -> None:
    configured = Settings(
        _env_file=None,
        data_dir="var/data",
        profile_path="var/profile.json",
        credentials_dir="var/credentials",
        ai_credentials_root="var/credentials/codex",
        jobs_dir="var/jobs",
        exports_dir="var/exports",
        applications_dir="var/applications",
        operations_dir="var/operations",
    )

    assert configured.data_dir == PROJECT_ROOT / "var/data"
    assert configured.profile_path == PROJECT_ROOT / "var/profile.json"


def test_home_paths_expand_and_cors_origins_are_normalized(monkeypatch: object, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))  # type: ignore[attr-defined]
    configured = Settings(_env_file=None, data_dir="~/jobbot", cors_origins=" http://localhost:5173,https://app.test, ")

    assert configured.data_dir == tmp_path / "jobbot"
    assert configured.cors_origin_list() == ["http://localhost:5173", "https://app.test"]


def test_ensure_dirs_creates_all_runtime_directories(tmp_path: Path) -> None:
    configured = Settings(
        _env_file=None,
        data_dir=tmp_path,
        profile_path=tmp_path / "profiles/profile.json",
        credentials_dir=tmp_path / "credentials",
        ai_credentials_root=tmp_path / "credentials/codex",
        jobs_dir=tmp_path / "jobs",
        exports_dir=tmp_path / "exports",
        applications_dir=tmp_path / "applications",
        operations_dir=tmp_path / "operations",
    )

    configured.ensure_dirs()

    assert configured.profile_path.parent.is_dir()
    assert configured.ai_credentials_root.is_dir()
    assert configured.jobs_dir.is_dir()
    assert configured.exports_dir.is_dir()
    assert configured.applications_dir.is_dir()
    assert configured.operations_dir.is_dir()
