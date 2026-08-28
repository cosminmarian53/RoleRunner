"""Tests for local, user-scoped JSON persistence."""

from pathlib import Path

from backend.models.profile import CandidateProfile, PersonalInfo
from backend.services.storage import LOCAL_DEV_USER_ID, JsonUserRepository, normalize_user_id


def test_normalize_user_id_has_safe_fallback_and_removes_path_characters() -> None:
    assert normalize_user_id(None) == LOCAL_DEV_USER_ID
    assert normalize_user_id("../../user/name") == ".._.._user_name"


def test_model_round_trip_is_scoped_by_user(tmp_path: Path) -> None:
    repository = JsonUserRepository(tmp_path)
    profile = CandidateProfile(personal_info=PersonalInfo(name="Ada"))

    path = repository.write_model("user@example.com", "profile.json", profile)

    assert path == tmp_path / "user@example.com" / "profile.json"
    assert repository.read_model("user@example.com", "profile.json", CandidateProfile) == profile
    assert repository.read_model("other-user", "profile.json", CandidateProfile) is None


def test_malformed_json_returns_default(tmp_path: Path) -> None:
    repository = JsonUserRepository(tmp_path)
    path = repository.path_for("user", "profile.json")
    path.write_text("{not-json", encoding="utf-8")

    assert repository.read_raw("user", "profile.json", {"fallback": True}) == {"fallback": True}
