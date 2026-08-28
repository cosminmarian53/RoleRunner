"""Storage service for private resumes and generated CV document assets."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID, uuid4

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Manages secure file uploads and signed URLs via Supabase Storage or local filesystem fallback."""

    def __init__(self) -> None:
        self.bucket = settings.supabase_storage_bucket
        self.supabase_url = str(settings.supabase_url or "").rstrip("/")
        self.anon_key = settings.supabase_anon_key
        self.local_resumes_dir = settings.data_dir / "resumes"
        self.local_resumes_dir.mkdir(parents=True, exist_ok=True)

    async def upload_resume(
        self,
        user_id: str | UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/pdf",
    ) -> str:
        """
        Upload resume document into isolated storage.

        Returns storage key path: `resumes/{user_id}/{file_id}_{clean_filename}`
        """
        uid = str(user_id)
        file_id = str(uuid4())
        clean_name = Path(filename).name.replace(" ", "_")
        storage_path = f"resumes/{uid}/{file_id}_{clean_name}"

        # If Supabase storage is configured, upload via Supabase Storage REST API
        if self.supabase_url and self.anon_key:
            url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{storage_path}"
            headers = {
                "Authorization": f"Bearer {self.anon_key}",
                "Content-Type": content_type,
            }
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, content=file_bytes, headers=headers)
                    if resp.status_code not in (200, 201):
                        logger.warning(
                            "Supabase storage upload failed (%d), falling back to local: %s",
                            resp.status_code,
                            resp.text,
                        )
                        self._save_local(storage_path, file_bytes)
            except Exception as exc:
                logger.warning("Supabase storage upload error (%s), saving locally", exc)
                self._save_local(storage_path, file_bytes)
        else:
            self._save_local(storage_path, file_bytes)

        return storage_path

    def _save_local(self, storage_path: str, file_bytes: bytes) -> Path:
        """Save file locally for offline / testing development."""
        target_path = settings.data_dir / storage_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(file_bytes)
        return target_path

    async def create_signed_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """Create a signed download URL for private storage assets."""
        if self.supabase_url and self.anon_key:
            url = f"{self.supabase_url}/storage/v1/object/sign/{self.bucket}/{storage_path}"
            headers = {
                "Authorization": f"Bearer {self.anon_key}",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json={"expiresIn": expires_in}, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        signed_url = data.get("signedURL")
                        if signed_url:
                            return f"{self.supabase_url}/storage/v1{signed_url}"
            except Exception as exc:
                logger.warning("Supabase create_signed_url error (%s), using local route", exc)

        # Local fallback URL
        return f"{settings.public_base_url}/api/storage/{storage_path}"
