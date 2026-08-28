"""Small user-scoped JSON persistence helpers.

TODO: Replace this module with Supabase/Postgres repositories before production
scale. The service interfaces already accept ``user_id`` so the API boundary can
stay stable when persistence moves out of local files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.config import settings

ModelT = TypeVar("ModelT", bound=BaseModel)

LOCAL_DEV_USER_ID = "local-dev-user"


def normalize_user_id(user_id: str | None) -> str:
    """Return a filesystem-safe user id with a local development fallback."""

    cleaned = (user_id or "").strip() or LOCAL_DEV_USER_ID
    return re.sub(r"[^A-Za-z0-9_.@-]+", "_", cleaned)[:160] or LOCAL_DEV_USER_ID


class JsonUserRepository:
    """Minimal JSON repository scoped by user id."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.data_dir / "users"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def user_dir(self, user_id: str | None) -> Path:
        path = self.base_dir / normalize_user_id(user_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path_for(self, user_id: str | None, filename: str) -> Path:
        return self.user_dir(user_id) / filename

    def read_raw(self, user_id: str | None, filename: str, default: Any) -> Any:
        path = self.path_for(user_id, filename)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def write_raw(self, user_id: str | None, filename: str, payload: Any) -> Path:
        path = self.path_for(user_id, filename)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(path)
        return path

    def read_model(self, user_id: str | None, filename: str, model_type: type[ModelT]) -> ModelT | None:
        payload = self.read_raw(user_id, filename, None)
        if payload is None:
            return None
        return model_type.model_validate(payload)

    def write_model(self, user_id: str | None, filename: str, model: BaseModel) -> Path:
        return self.write_raw(user_id, filename, model.model_dump(mode="json"))

    def read_collection(self, user_id: str | None, filename: str, model_type: type[ModelT]) -> list[ModelT]:
        payload = self.read_raw(user_id, filename, [])
        if isinstance(payload, dict) and "items" in payload:
            payload = payload["items"]
        if not isinstance(payload, list):
            return []
        return [model_type.model_validate(item) for item in payload if isinstance(item, dict)]

    def write_collection(self, user_id: str | None, filename: str, items: list[BaseModel]) -> Path:
        payload = [item.model_dump(mode="json") for item in items]
        return self.write_raw(user_id, filename, payload)
