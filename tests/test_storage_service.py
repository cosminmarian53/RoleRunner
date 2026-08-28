"""Unit tests for StorageService."""

from pathlib import Path
from uuid import uuid4

import pytest

from backend.config import settings
from backend.services.storage_service import StorageService


@pytest.mark.asyncio
async def test_storage_service_upload_local_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = StorageService()
    service.local_resumes_dir = tmp_path
    monkeypatch.setattr(service, "supabase_url", "")

    user_id = uuid4()
    content = b"%PDF-1.4 test resume"
    storage_path = await service.upload_resume(user_id, content, "my_resume.pdf")

    assert storage_path.startswith(f"resumes/{user_id}/")
    assert storage_path.endswith("_my_resume.pdf")

    saved_file = settings.data_dir / storage_path
    assert saved_file.exists()

    # check that create_signed_url returns valid local url
    signed_url = await service.create_signed_url(storage_path)
    assert f"/api/storage/{storage_path}" in signed_url
