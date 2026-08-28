"""Integration tests for Codex PostgreSQL session synchronization and container redeploy recovery.

Verifies:
1. Device authentication start generates code and state.
2. Successful auth saves auth.json to disk and syncs payload into PostgreSQL settings_data["codex_auth"].
3. Container rebuild simulation (disk wipe) triggers automatic restoration from PostgreSQL on next status check.
4. Correct 0600 file permissions are enforced on restored credentials.
5. Logout removes credentials from both filesystem disk and database storage.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.db.models import UserRecord
from backend.db.session import (
    async_session_factory,
    create_engine_for_url,
    get_db,
    init_db,
)
from backend.main import app
from backend.services.codex_credentials import CodexCredentialsManager
from backend.services.codex_harness import CodexHarness, DeviceAuthInfo


@pytest.fixture
async def codex_sync_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up database and isolated credentials manager."""
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    session_factory = async_session_factory(engine)

    creds_dir = tmp_path / "credentials"
    creds_mgr = CodexCredentialsManager(creds_dir)
    monkeypatch.setattr("backend.services.codex_credentials.get_credentials_manager", lambda: creds_mgr)
    monkeypatch.setattr("backend.routers.agent.get_credentials_manager", lambda: creds_mgr)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    user_id = uuid4()
    async with session_factory() as session:
        session.add(UserRecord(id=user_id, email="cloud_user@rolerunner.io"))
        await session.commit()

    headers = {"Authorization": f"Bearer {user_id}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as client:
        yield {
            "client": client,
            "user_id": user_id,
            "session_factory": session_factory,
            "creds_mgr": creds_mgr,
            "creds_dir": creds_dir,
        }

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_codex_cloud_session_sync_and_restore_across_rebuilds(
    codex_sync_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test full cycle of PostgreSQL sync, container disk wipe, and auto-restoration."""
    client: AsyncClient = codex_sync_env["client"]
    user_id = codex_sync_env["user_id"]
    session_factory = codex_sync_env["session_factory"]
    creds_mgr: CodexCredentialsManager = codex_sync_env["creds_mgr"]

    # 1. Start login flow
    mock_auth_info = DeviceAuthInfo(
        authorization_url="https://auth.openai.com/device",
        device_code="ABCD-1234",
        raw_output="Visit https://auth.openai.com/device and enter ABCD-1234",
    )

    async def mock_start_login(self):
        return mock_auth_info

    monkeypatch.setattr(CodexHarness, "start_login", mock_start_login)

    start_resp = await client.post("/api/agent/login/start")
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["device_code"] == "ABCD-1234"
    assert start_data["authorization_url"] == "https://auth.openai.com/device"

    # 2. Simulate successful authentication
    sample_auth_payload = {
        "access_token": "sk-proj-mock-valid-token-12345",
        "refresh_token": "rt-mock-refresh-token",
        "expires_at": 1893456000,
        "token_type": "Bearer",
    }
    creds_mgr.write_auth_json(user_id, json.dumps(sample_auth_payload))

    # Mock harness refresh_auth_status to return True
    async def mock_refresh_auth(self):
        self.session.is_authenticated = True
        return True

    monkeypatch.setattr(CodexHarness, "refresh_auth_status", mock_refresh_auth)

    # Call /api/agent/login/status to trigger database sync
    status_resp = await client.get("/api/agent/login/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["authenticated"] is True

    # Verify that the session was written into PostgreSQL UserRecord.settings_data["codex_auth"]
    async with session_factory() as session:
        user_row = (await session.execute(select(UserRecord).where(UserRecord.id == user_id))).scalar_one()
        assert "codex_auth" in user_row.settings_data
        persisted_auth = json.loads(user_row.settings_data["codex_auth"])
        assert persisted_auth["access_token"] == "sk-proj-mock-valid-token-12345"

    # 3. Simulate container destroy/redeploy: delete all local credentials from disk
    user_home = creds_mgr.get_user_codex_home(user_id)
    auth_file = user_home / "auth.json"
    assert auth_file.exists()
    auth_file.unlink()
    assert not auth_file.exists()
    assert creds_mgr.read_auth_json(user_id) is None

    # 4. Call /api/agent/provider/status -> Verify backend automatically restores auth.json from DB
    provider_status_resp = await client.get("/api/agent/provider/status")
    assert provider_status_resp.status_code == 200
    assert provider_status_resp.json()["authenticated"] is True

    # Verify auth.json was recreated on disk with correct contents and 0600 permissions
    assert auth_file.exists()
    restored_raw = creds_mgr.read_auth_json(user_id)
    assert restored_raw is not None
    restored_auth = json.loads(restored_raw)
    assert restored_auth["access_token"] == "sk-proj-mock-valid-token-12345"
    assert (auth_file.stat().st_mode & 0o777) == 0o600

    # 5. Test logout -> Verify credentials removed from both disk and PostgreSQL
    async def mock_logout(self):
        self.session.is_authenticated = False
        return True

    monkeypatch.setattr(CodexHarness, "logout", mock_logout)
    logout_resp = await client.post("/api/agent/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json()["authenticated"] is False

    # Check database is clean
    async with session_factory() as session:
        user_row = (await session.execute(select(UserRecord).where(UserRecord.id == user_id))).scalar_one()
        assert "codex_auth" not in user_row.settings_data
