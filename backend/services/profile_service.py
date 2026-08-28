"""Profile parsing and persistence service."""

from __future__ import annotations

import json
import re
from io import BytesIO
from typing import Any

from pydantic import ValidationError

from backend.models.profile import (
    CandidateProfile,
    Certification,
    Education,
    Experience,
    Language,
    PersonalInfo,
    ProfileUploadResponse,
    Project,
)
from backend.services.storage import JsonUserRepository

PROFILE_FILENAME = "profile.json"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"https?://[^\s,)]+|(?:linkedin|github)\.com/[^\s,)]+", re.IGNORECASE)
SECTION_ALIASES = {
    "summary": {"summary", "profile", "objective", "about"},
    "skills": {"skills", "technical skills", "core skills", "technologies", "technology"},
    "experience": {"experience", "work experience", "professional experience", "employment"},
    "education": {"education"},
    "certifications": {"certifications", "certificates", "licenses"},
    "projects": {"projects", "selected projects"},
    "languages": {"languages"},
    "achievements": {"achievements", "awards"},
}


class ProfileService:
    """User-scoped profile service backed by local JSON files."""

    def __init__(self, repository: JsonUserRepository | None = None) -> None:
        self.repository = repository or JsonUserRepository()

    def get_profile(self, user_id: str) -> CandidateProfile:
        return self.repository.read_model(user_id, PROFILE_FILENAME, CandidateProfile) or CandidateProfile()

    def save_profile(self, user_id: str, profile: CandidateProfile) -> CandidateProfile:
        self.repository.write_model(user_id, PROFILE_FILENAME, profile)
        return profile

    def parse_profile_text(self, user_id: str, text: str, *, merge_existing: bool = True) -> ProfileUploadResponse:
        warnings: list[str] = []
        profile: CandidateProfile

        try:
            profile = self.parse_json_profile(text)
        except ValueError:
            profile = self.parse_resume_text(text)
            if not text.strip():
                warnings.append("No text content was found to parse.")
            elif not profile.personal_info.name and not profile.summary and not profile.skills:
                warnings.append("Only limited structured profile data could be inferred from the text.")

        if merge_existing:
            profile = merge_profiles(self.get_profile(user_id), profile)

        self.save_profile(user_id, profile)
        return ProfileUploadResponse(profile=profile, extracted_text=text, warnings=warnings)

    async def parse_upload(self, user_id: str, upload: Any, *, merge_existing: bool = True) -> ProfileUploadResponse:
        filename = getattr(upload, "filename", "") or "upload"
        content = await upload.read()
        text, warnings = extract_text_from_upload(filename, content)

        if filename.lower().endswith(".json"):
            try:
                profile = self.parse_json_profile(text)
            except ValueError as exc:
                raise ValueError(f"Invalid profile JSON: {exc}") from exc
            if merge_existing:
                profile = merge_profiles(self.get_profile(user_id), profile)
            self.save_profile(user_id, profile)
            return ProfileUploadResponse(
                profile=profile,
                extracted_text=text,
                source_filename=filename,
                warnings=warnings,
            )

        response = self.parse_profile_text(user_id, text, merge_existing=merge_existing)
        response.source_filename = filename
        response.warnings.extend(warnings)
        return response

    def parse_json_profile(self, raw: str) -> CandidateProfile:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("not JSON") from exc

        if isinstance(payload, dict) and isinstance(payload.get("profile"), dict):
            payload = payload["profile"]
        if not isinstance(payload, dict):
            raise ValueError("profile JSON must be an object")

        try:
            return CandidateProfile.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    def parse_resume_text(self, text: str) -> CandidateProfile:
        clean = normalize_text(text)
        lines = [line.strip(" \t-•") for line in clean.splitlines() if line.strip()]
        sections = split_sections(lines)

        personal_info = parse_personal_info(lines, clean)
        summary = "\n".join(sections.get("summary", [])).strip()
        skills = parse_skills(sections.get("skills", []), clean)
        experience = parse_experience(sections.get("experience", []))
        education = parse_education(sections.get("education", []))
        certifications = parse_certifications(sections.get("certifications", []))
        projects = parse_projects(sections.get("projects", []))
        languages = parse_languages(sections.get("languages", []))
        achievements = parse_bullet_lines(sections.get("achievements", []))

        return CandidateProfile(
            personal_info=personal_info,
            summary=summary,
            skills=skills,
            experience=experience,
            education=education,
            certifications=certifications,
            projects=projects,
            languages=languages,
            achievements=achievements,
        )


def extract_text_from_upload(filename: str, content: bytes) -> tuple[str, list[str]]:
    """Extract readable text from supported upload formats."""

    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    warnings: list[str] = []

    if suffix == "pdf":
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text.strip(), warnings
        except Exception as exc:  # pragma: no cover - depends on third-party parser internals.
            warnings.append(f"PDF text extraction failed: {exc}")

    if suffix == "docx":
        try:
            from docx import Document

            document = Document(BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            return text.strip(), warnings
        except Exception as exc:  # pragma: no cover - depends on third-party parser internals.
            warnings.append(f"DOCX text extraction failed: {exc}")

    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding).strip(), warnings
        except UnicodeDecodeError:
            continue

    warnings.append("Could not decode upload as text.")
    return "", warnings


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "summary"

    for line in lines:
        key = section_key(line)
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)

    return sections


def section_key(line: str) -> str | None:
    normalized = re.sub(r"[^a-z ]+", "", line.lower()).strip()
    if len(normalized.split()) > 4:
        return None
    for key, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return key
    return None


def parse_personal_info(lines: list[str], full_text: str) -> PersonalInfo:
    email = first_match(EMAIL_RE, full_text)
    phone = first_match(PHONE_RE, full_text)
    urls = URL_RE.findall(full_text)
    linkedin = first_url(urls, "linkedin")
    github = first_url(urls, "github")
    portfolio = next((url for url in urls if "linkedin" not in url.lower() and "github" not in url.lower()), "")
    name = ""

    for line in lines[:6]:
        lower = line.lower()
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or "linkedin" in lower or "github" in lower:
            continue
        if 1 <= len(line.split()) <= 5 and not section_key(line):
            name = line
            break

    return PersonalInfo(name=name, email=email, phone=phone, linkedin=linkedin, github=github, portfolio=portfolio)


def parse_skills(lines: list[str], full_text: str) -> dict[str, list[str]]:
    if not lines:
        return {}
    grouped: dict[str, list[str]] = {}
    for line in lines:
        if ":" in line:
            category, raw_values = line.split(":", 1)
            values = split_inline_values(raw_values)
            if values:
                grouped[category.strip().lower().replace(" ", "_")] = values
        else:
            grouped.setdefault("general", []).extend(split_inline_values(line))

    if grouped:
        return {key: unique_strings(values) for key, values in grouped.items() if values}

    common_skills = [
        "python",
        "typescript",
        "javascript",
        "react",
        "node",
        "fastapi",
        "django",
        "postgres",
        "sql",
        "aws",
        "docker",
        "kubernetes",
        "solidity",
        "rust",
        "go",
    ]
    matches = [skill for skill in common_skills if re.search(rf"\b{re.escape(skill)}\b", full_text, re.IGNORECASE)]
    return {"general": matches} if matches else {}


def parse_experience(lines: list[str]) -> list[Experience]:
    entries = split_entries(lines)
    experience: list[Experience] = []
    for entry in entries:
        if not entry:
            continue
        heading = entry[0]
        title = heading
        company = ""
        duration = ""
        if " at " in heading.lower():
            parts = re.split(r"\s+at\s+", heading, maxsplit=1, flags=re.IGNORECASE)
            title, company = parts[0].strip(), parts[1].strip()
        elif " - " in heading:
            parts = [part.strip() for part in heading.split(" - ", 1)]
            title, company = parts[0], parts[1]
        for line in entry[:3]:
            if re.search(r"\b(20\d{2}|19\d{2}|present|current)\b", line, re.IGNORECASE):
                duration = line
                break
        bullets = parse_bullet_lines(entry[1:])
        experience.append(Experience(company=company, title=title, duration=duration, bullets=bullets))
    return experience


def parse_education(lines: list[str]) -> list[Education]:
    education: list[Education] = []
    for entry in split_entries(lines):
        if not entry:
            continue
        institution = entry[0]
        degree = entry[1] if len(entry) > 1 else ""
        year = ""
        for line in entry:
            match = re.search(r"\b(19\d{2}|20\d{2})\b", line)
            if match:
                year = match.group(1)
                break
        education.append(Education(institution=institution, degree=degree, year=year, details="\n".join(entry[2:])))
    return education


def parse_certifications(lines: list[str]) -> list[Certification]:
    return [Certification(name=line) for line in parse_bullet_lines(lines)]


def parse_projects(lines: list[str]) -> list[Project]:
    projects: list[Project] = []
    for entry in split_entries(lines):
        if not entry:
            continue
        projects.append(Project(name=entry[0], description="\n".join(entry[1:])))
    return projects


def parse_languages(lines: list[str]) -> list[Language]:
    languages: list[Language] = []
    for line in parse_bullet_lines(lines):
        if ":" in line:
            language, level = line.split(":", 1)
        elif " - " in line:
            language, level = line.split(" - ", 1)
        else:
            language, level = line, ""
        languages.append(Language(language=language.strip(), level=level.strip()))
    return languages


def split_entries(lines: list[str]) -> list[list[str]]:
    entries: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        starts_new = bool(current) and not line.startswith(("-", "•", "*")) and len(current) >= 3
        if starts_new:
            entries.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append(current)
    return entries


def parse_bullet_lines(lines: list[str]) -> list[str]:
    values: list[str] = []
    for line in lines:
        parts = [part.strip(" \t-•*") for part in re.split(r"\s+[•]\s+|\n", line)]
        values.extend(part for part in parts if part)
    return unique_strings(values)


def split_inline_values(text: str) -> list[str]:
    parts = re.split(r"[,;|/]| {2,}", text)
    return [part.strip(" \t-•*") for part in parts if part.strip(" \t-•*")]


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


def first_url(urls: list[str], needle: str) -> str:
    return next((url for url in urls if needle in url.lower()), "")


def merge_profiles(existing: CandidateProfile, incoming: CandidateProfile) -> CandidateProfile:
    """Merge newly parsed profile data into an existing profile without erasing useful fields."""

    personal = PersonalInfo(
        **{
            key: incoming_value or existing_value
            for key, existing_value in existing.personal_info.model_dump().items()
            for incoming_value in [getattr(incoming.personal_info, key)]
        }
    )
    personal.extra_links = {**existing.personal_info.extra_links, **incoming.personal_info.extra_links}

    skills = {key: list(values) for key, values in existing.skills.items()}
    for category, values in incoming.skills.items():
        skills[category] = unique_strings(skills.get(category, []) + values)

    return CandidateProfile(
        personal_info=personal,
        summary=incoming.summary or existing.summary,
        skills=skills,
        experience=merge_model_lists(existing.experience, incoming.experience),
        education=merge_model_lists(existing.education, incoming.education),
        certifications=merge_model_lists(existing.certifications, incoming.certifications),
        projects=merge_model_lists(existing.projects, incoming.projects),
        languages=merge_model_lists(existing.languages, incoming.languages),
        achievements=unique_strings(existing.achievements + incoming.achievements),
    )


def merge_model_lists(existing: list[Any], incoming: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for item in existing + incoming:
        if isinstance(item, str):
            key = item.lower()
        else:
            key = json.dumps(item.model_dump(mode="json"), sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
