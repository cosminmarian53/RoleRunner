from pathlib import Path
from uuid import uuid4

import pytest

from backend.services.codex_credentials import (
    CodexCredentialsManager,
    CredentialSecurityError,
)


def test_sanitize_user_id_accepts_valid_uuid(tmp_path: Path) -> None:
    manager = CodexCredentialsManager(tmp_path)
    uid = uuid4()
    sanitized = manager.sanitize_user_id(uid)
    assert sanitized == str(uid)


def test_sanitize_user_id_rejects_path_traversal(tmp_path: Path) -> None:
    manager = CodexCredentialsManager(tmp_path)
    with pytest.raises(CredentialSecurityError, match="Invalid tenant UUID"):
        manager.sanitize_user_id("../../etc/passwd")

    with pytest.raises(CredentialSecurityError, match="Invalid tenant UUID"):
        manager.sanitize_user_id("user/123")


def test_get_user_codex_home_creates_isolated_dir_with_permissions(tmp_path: Path) -> None:
    manager = CodexCredentialsManager(tmp_path)
    uid = uuid4()

    user_home = manager.get_user_codex_home(uid)
    assert user_home.exists()
    assert user_home.is_dir()
    assert user_home == tmp_path / str(uid)

    # Check directory permissions (0700)
    assert user_home.stat().st_mode & 0o777 == 0o700


def test_enforce_file_permissions(tmp_path: Path) -> None:
    manager = CodexCredentialsManager(tmp_path)
    uid = uuid4()
    user_home = manager.get_user_codex_home(uid)

    auth_file = user_home / "auth.json"
    auth_file.write_text('{"token": "secret"}')
    auth_file.chmod(0o644)

    manager.enforce_file_permissions(uid)
    assert auth_file.stat().st_mode & 0o777 == 0o600


def test_delete_user_credentials(tmp_path: Path) -> None:
    manager = CodexCredentialsManager(tmp_path)
    uid = uuid4()
    user_home = manager.get_user_codex_home(uid)
    (user_home / "auth.json").write_text("token")

    assert user_home.exists()
    deleted = manager.delete_user_credentials(uid)
    assert deleted is True
    assert not user_home.exists()

    # Second delete returns False
    assert manager.delete_user_credentials(uid) is False
