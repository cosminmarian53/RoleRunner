"""Profile parsing and persistence service with AI assistance and PostgreSQL storage."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

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
from backend.repositories.profile_repo import ProfileRepository
from backend.services.ai_client import ask
from backend.services.document_extractor import (
    DocumentExtractionError,
    extract_document_text,
)
from backend.services.storage_service import StorageService

logger = logging.getLogger(__name__)

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

AI_PROFILE_SYSTEM_PROMPT = """You are an expert resume parsing engine.
Convert the provided resume text into a strictly formatted JSON object matching the following structure:
{
  "personal_info": {
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1234567890",
    "linkedin": "https://linkedin.com/in/username",
    "github": "https://github.com/username",
    "portfolio": "https://example.com",
    "location": "City, Country"
  },
  "summary": "Professional summary...",
  "skills": {
    "languages": ["Python", "TypeScript"],
    "frameworks": ["FastAPI", "React"],
    "tools": ["Docker", "Git"]
  },
  "experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "duration": "2020 - Present",
      "location": "Remote",
      "bullets": ["Achievement 1", "Achievement 2"]
    }
  ],
  "education": [
    {
      "institution": "University Name",
      "degree": "B.S. in Computer Science",
      "year": "2019",
      "details": "Honors / GPA if mentioned"
    }
  ],
  "certifications": [
    {
      "name": "Cert Name",
      "issuer": "Issuer",
      "date": "2021"
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "tech": "Tech stack",
      "description": "Short description"
    }
  ],
  "languages": [
    {
      "language": "English",
      "level": "Fluent"
    }
  ],
  "achievements": ["Award or milestone 1"]
}
Output ONLY raw valid JSON with no markdown backticks, explanations, or think tags."""


class ProfileService:
    """Tenant-scoped profile service backed by PostgreSQL / Supabase."""

    def __init__(self, session: AsyncSession, user_id: UUID | str) -> None:
        self.session = session
        self.user_id = UUID(str(user_id))
        self.repo = ProfileRepository(session, self.user_id)
        self.storage = StorageService()

    async def get_profile(self) -> CandidateProfile:
        """Fetch candidate profile from the database."""
        record = await self.repo.get_profile()
        if record and record.data:
            try:
                return CandidateProfile.model_validate(record.data)
            except ValidationError as exc:
                logger.warning("Profile data validation failed: %s", exc)
        return CandidateProfile()

    async def save_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Persist profile model into PostgreSQL JSONB."""
        data = profile.model_dump(mode="json")
        await self.repo.upsert_profile(data)
        return profile

    async def parse_and_save_text(
        self,
        text: str,
        *,
        merge_existing: bool = True,
        use_ai: bool = True,
    ) -> ProfileUploadResponse:
        """Parse raw text into CandidateProfile using AI or regex fallback and persist."""
        warnings: list[str] = []
        profile: CandidateProfile | None = None

        # 1. Try parsing direct JSON
        try:
            profile = self.parse_json_profile(text)
        except ValueError:
            pass

        # 2. Try AI extraction if enabled
        if profile is None and use_ai:
            try:
                profile = await self.extract_profile_with_ai(text)
            except Exception as exc:
                logger.info("AI profile parsing skipped/failed (%s), using regex fallback", exc)
                warnings.append("AI extraction unavailable; extracted with deterministic heuristics.")

        # 3. Fallback to deterministic regex parser
        if profile is None:
            profile = self.parse_resume_text(text)
            if not text.strip():
                warnings.append("No text content was found to parse.")
            elif not profile.personal_info.name and not profile.summary and not profile.skills:
                warnings.append("Only limited structured profile data could be inferred from the text.")

        # 4. Merge if requested
        if merge_existing:
            existing = await self.get_profile()
            profile = merge_profiles(existing, profile)

        await self.save_profile(profile)
        return ProfileUploadResponse(profile=profile, extracted_text=text, warnings=warnings)

    async def parse_and_save_upload(
        self,
        filename: str,
        content: bytes,
        *,
        merge_existing: bool = True,
        use_ai: bool = True,
    ) -> ProfileUploadResponse:
        """Extract text from uploaded document, upload file to storage, parse and persist."""
        # 1. Validate & extract text
        try:
            text, detected_type = extract_document_text(filename, content)
        except DocumentExtractionError as exc:
            raise ValueError(exc.message) from exc

        # 2. Upload original document to secure storage
        try:
            await self.storage.upload_resume(
                user_id=self.user_id,
                file_bytes=content,
                filename=filename,
            )
        except Exception as exc:
            logger.warning("Failed to store resume document: %s", exc)

        # 3. Parse JSON or text
        if detected_type == "json":
            try:
                profile = self.parse_json_profile(text)
            except ValueError as exc:
                raise ValueError(f"Invalid profile JSON: {exc}") from exc
            if merge_existing:
                existing = await self.get_profile()
                profile = merge_profiles(existing, profile)
            await self.save_profile(profile)
            return ProfileUploadResponse(
                profile=profile,
                extracted_text=text,
                source_filename=filename,
                warnings=[],
            )

        response = await self.parse_and_save_text(
            text,
            merge_existing=merge_existing,
            use_ai=use_ai,
        )
        response.source_filename = filename
        return response

    async def extract_profile_with_ai(self, text: str) -> CandidateProfile:
        """Call Codex AI to extract structured JSON from raw resume text."""
        prompt = f"Resume text to parse:\n\n{text[:12000]}"
        raw_output = await ask(
            prompt,
            user_id=self.user_id,
            system_prompt=AI_PROFILE_SYSTEM_PROMPT,
        )
        # Clean potential markdown fences
        clean_json = re.sub(r"^```(?:json)?\s*", "", raw_output.strip())
        clean_json = re.sub(r"\s*```$", "", clean_json).strip()
        return self.parse_json_profile(clean_json)

    def parse_json_profile(self, raw: str) -> CandidateProfile:
        """Validate and construct CandidateProfile from raw JSON string."""
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
        """Deterministic heuristic regex parser for resume text."""
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


def normalize_text(text: str) -> str:
    """Normalize whitespace and line endings."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Partition text lines into known resume sections."""
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
    """Identify if a line is a section heading."""
    normalized = re.sub(r"[^a-z ]+", "", line.lower()).strip()
    if len(normalized.split()) > 4:
        return None
    for key, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return key
    return None


def parse_personal_info(lines: list[str], full_text: str) -> PersonalInfo:
    """Extract contact and identity info using patterns."""
    email = first_match(EMAIL_RE, full_text)
    phone = first_match(PHONE_RE, full_text)
    urls = URL_RE.findall(full_text)
    linkedin = first_url(urls, "linkedin")
    github = first_url(urls, "github")
    portfolio = next(
        (url for url in urls if "linkedin" not in url.lower() and "github" not in url.lower()),
        "",
    )
    name = ""

    for line in lines[:6]:
        lower = line.lower()
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or "linkedin" in lower or "github" in lower:
            continue
        if 1 <= len(line.split()) <= 5 and not section_key(line):
            name = line
            break

    return PersonalInfo(
        name=name,
        email=email,
        phone=phone,
        linkedin=linkedin,
        github=github,
        portfolio=portfolio,
    )


def parse_skills(lines: list[str], full_text: str) -> dict[str, list[str]]:
    """Extract and categorize skills."""
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
    """Parse work experience entries."""
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
    """Parse education entries."""
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
        education.append(
            Education(
                institution=institution,
                degree=degree,
                year=year,
                details="\n".join(entry[2:]),
            )
        )
    return education


def parse_certifications(lines: list[str]) -> list[Certification]:
    """Parse certifications entries."""
    return [Certification(name=line) for line in parse_bullet_lines(lines)]


def parse_projects(lines: list[str]) -> list[Project]:
    """Parse project entries."""
    projects: list[Project] = []
    for entry in split_entries(lines):
        if not entry:
            continue
        projects.append(Project(name=entry[0], description="\n".join(entry[1:])))
    return projects


def parse_languages(lines: list[str]) -> list[Language]:
    """Parse language proficiencies."""
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
    """Group lines into multi-line entries."""
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
    """Split bullet points and clean formatting."""
    values: list[str] = []
    for line in lines:
        parts = [part.strip(" \t-•*") for part in re.split(r"\s+[•]\s+|\n", line)]
        values.extend(part for part in parts if part)
    return unique_strings(values)


def split_inline_values(text: str) -> list[str]:
    """Split comma or semicolon separated values."""
    parts = re.split(r"[,;|/]| {2,}", text)
    return [part.strip(" \t-•*") for part in parts if part.strip(" \t-•*")]


def unique_strings(values: list[str]) -> list[str]:
    """Deduplicate strings preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def first_match(pattern: re.Pattern[str], text: str) -> str:
    """Extract first regex match string."""
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


def first_url(urls: list[str], needle: str) -> str:
    """Find first URL containing substring."""
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
    """Merge lists of Pydantic models with deduplication by JSON content."""
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
