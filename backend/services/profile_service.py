"""Profile parsing and persistence service with AI assistance and PostgreSQL/SQLite storage."""

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
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
URL_RE = re.compile(r"https?://[^\s,)]+|(?:linkedin|github)\.com/[^\s,)]+", re.IGNORECASE)

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
    "core_competencies": ["Skill 1", "Skill 2"],
    "tools_software": ["Tool 1", "Tool 2"]
  },
  "experience": [
    {
      "company": "Organization / Company Name",
      "title": "Job Title / Role",
      "duration": "2020 - Present",
      "location": "City, Country or Remote",
      "bullets": ["Achievement 1", "Achievement 2"]
    }
  ],
  "education": [
    {
      "institution": "University / Institution Name",
      "degree": "Degree / Qualification Title",
      "year": "2019",
      "details": "Honors / Major / GPA if mentioned"
    }
  ],
  "certifications": [
    {
      "name": "Certificate / License Name",
      "issuer": "Issuing Body",
      "date": "2022"
    }
  ],
  "projects": [
    {
      "name": "Project / Initiative Name",
      "description": "Brief description of project impact",
      "tech": "Tools / Methods used"
    }
  ],
  "languages": ["English (Native)", "Spanish (Fluent)"],
  "achievements": ["Key Award / Career Milestone"]
}

STRICT RULES:
1. Output ONLY valid, parsable JSON without explanation or markdown backticks.
2. Extract truth factually from the resume text without hallucination.
3. If a field is not present in the resume, use empty string "" or empty list [] or empty dict {}."""


class ProfileService:
    """Tenant-scoped profile service backed by PostgreSQL / SQLite."""

    def __init__(self, session: AsyncSession | None, user_id: UUID | str) -> None:
        self.session = session
        self.user_id = UUID(str(user_id))
        self.repo = ProfileRepository(session, self.user_id) if session is not None else None  # type: ignore[arg-type]
        self.storage = StorageService()

    async def get_profile(self) -> CandidateProfile:
        """Fetch candidate profile from the database."""
        if self.repo is None:
            return CandidateProfile()
        record = await self.repo.get_profile()
        if record and record.data:
            try:
                return CandidateProfile.model_validate(record.data)
            except ValidationError:
                pass
        return CandidateProfile()

    async def save_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Persist candidate profile to the database."""
        if self.repo is not None:
            await self.repo.upsert_profile(profile.model_dump(mode="json"))
        return profile

    async def delete_profile(self) -> bool:
        """Delete candidate profile from the database."""
        if self.repo is not None:
            return await self.repo.delete_profile()
        return False

    async def parse_and_save_text(
        self,
        text: str,
        *,
        merge_existing: bool = True,
        use_ai: bool = True,
    ) -> ProfileUploadResponse:
        """Parse raw resume text using Codex with fallback to robust regex heuristic parser."""
        profile: CandidateProfile | None = None
        warnings: list[str] = []

        # 1. Try parsing directly as JSON
        if text.strip().startswith("{") and text.strip().endswith("}"):
            try:
                profile = self.parse_json_profile(text)
            except ValueError:
                profile = None

        # 2. Try AI extraction if enabled
        if profile is None and use_ai:
            try:
                profile = await self.extract_profile_with_ai(text)
            except Exception as exc:
                logger.info("AI profile parsing skipped/failed (%s), using robust regex fallback", exc)
                warnings.append("AI extraction unavailable; extracted with deterministic heuristics.")

        # 3. Fallback to deterministic regex parser
        if profile is None:
            profile = self.parse_resume_text(text)
            if not text.strip():
                warnings.append("No text content was found to parse.")
            elif not profile.personal_info.name and not profile.summary and not profile.skills:
                warnings.append("Only limited structured profile data could be inferred from the text.")

        # 4. GUARANTEED CONTACT SAFETY NET:
        # Fill any missing personal_info fields with deterministic regex extraction
        deterministic_info = extract_personal_info(sanitize_resume_text(text), text)
        if profile.personal_info:
            if not profile.personal_info.name and deterministic_info.name:
                profile.personal_info.name = deterministic_info.name
            if not profile.personal_info.email and deterministic_info.email:
                profile.personal_info.email = deterministic_info.email
            if not profile.personal_info.phone and deterministic_info.phone:
                profile.personal_info.phone = deterministic_info.phone
            if not profile.personal_info.linkedin and deterministic_info.linkedin:
                profile.personal_info.linkedin = deterministic_info.linkedin
            if not profile.personal_info.github and deterministic_info.github:
                profile.personal_info.github = deterministic_info.github
            if not profile.personal_info.portfolio and deterministic_info.portfolio:
                profile.personal_info.portfolio = deterministic_info.portfolio
            if not profile.personal_info.location and deterministic_info.location:
                profile.personal_info.location = deterministic_info.location

        # 5. Merge if requested
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
        """Deterministic, highly robust heuristic regex parser for resume text."""
        text_clean = sanitize_resume_text(text)
        personal_info = extract_personal_info(text_clean, text)
        raw_lines = [line.strip() for line in text_clean.splitlines() if line.strip()]

        sections: dict[str, list[str]] = {}
        current_sec = "header"

        for line in raw_lines:
            sec_type = is_section_heading(line)
            if sec_type:
                current_sec = sec_type
                sections.setdefault(current_sec, [])
                continue
            sections.setdefault(current_sec, []).append(line)

        # 1. Summary
        summary_lines = sections.get("summary", [])
        clean_summary: list[str] = []
        for line_item in summary_lines:
            if personal_info.email and personal_info.email in line_item:
                continue
            if "linkedin.com" in line_item.lower() or "github.com" in line_item.lower():
                continue
            if personal_info.name and personal_info.name.lower() in line_item.lower() and len(line_item.split()) <= 4:
                continue
            clean_summary.append(line_item)
        summary = "\n".join(clean_summary).strip()

        # 2. Skills
        skills = parse_skills_section(sections.get("skills", []), text_clean)

        # 3. Experience
        experience = parse_experience_section(sections.get("experience", []))

        # 4. Education & Certifications
        edu_lines = sections.get("education", []) + sections.get("education_certifications", [])
        cert_lines = sections.get("certifications", [])
        education, certifications = parse_education_and_certifications(edu_lines, cert_lines)

        # 5. Projects, Languages, Achievements
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


def sanitize_resume_text(text: str) -> str:
    """Normalize unicode dashes, spaces, and line breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015]", "-", text)
    text = text.replace("\u00a0", " ")
    return text


def is_date_pattern(val: str) -> bool:
    """Check if string is a date, year, or date range (e.g. 2026-08-28, 2024-2026, 08/28/2026)."""
    v = val.strip()
    if re.search(r"\b(19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b", v):
        return True
    if re.search(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\b(19|20)\d{2}\b", v):
        return True
    if re.search(r"\b(19|20)\d{2}\s*[-–—/]\s*(19|20)\d{2}\b", v):
        return True
    if re.search(r"\b\d{1,2}[-/]\b(19|20)\d{2}\b", v):
        return True
    return False


def extract_personal_info(text_clean: str, raw_original: str) -> PersonalInfo:
    """Extract contact, links, location, and name with hyphen/space repairs."""
    combined_text = f"{text_clean}\n{raw_original}"
    raw_lines = [item_line.strip() for item_line in text_clean.splitlines() if item_line.strip()]

    # Pre-process top contact section
    top_chunk = "\n".join(raw_lines[:15])

    # 1. Extract email
    email = ""
    m_email = re.search(
        r"(?:mailto:)?([a-zA-Z0-9_.+-]+\s*@\s*[a-zA-Z0-9-]+\s*\.\s*[a-zA-Z0-9.-]+)",
        combined_text,
    )
    if m_email:
        email = re.sub(r"\s+", "", m_email.group(1)).strip(".,;")

    # 2. Extract phone (supports international +40 ..., +1 ..., spaced hyphens; excludes dates)
    phone = ""
    # Check for labeled phone first
    m_labeled_phone = re.search(
        r"(?:phone|tel|mobile|cell|contact)[:\s]*([+\d\s().-]{7,25})",
        combined_text,
        re.IGNORECASE,
    )
    if m_labeled_phone:
        cand = m_labeled_phone.group(1).strip(" \t-•,")
        digits = re.sub(r"\D", "", cand)
        if len(digits) >= 8 and not is_date_pattern(cand):
            phone = re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", cand))

    if not phone:
        m_phone = re.search(
            r"(?:(?:\+|00)\d{1,3}[\s.-]*)?(?:\(?\d{2,4}\)?[\s.-]*)?\d{3,4}[\s.-]*\d{3,4}(?:[\s.-]*\d{1,4})?",
            top_chunk,
        )
        if m_phone:
            cand = m_phone.group(0).strip(" \t-•,")
            digits = re.sub(r"\D", "", cand)
            if len(digits) >= 8 and not is_date_pattern(cand):
                phone = re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", cand))

    # 3. Extract LinkedIn (reconstruct spaced hyphens e.g. 'cosmin -lavric -827126331')
    linkedin = ""
    m_li = re.search(
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_\-%]+(?:\s*-\s*[a-zA-Z0-9_\-%]+)*)",
        combined_text,
        re.IGNORECASE,
    )
    if m_li:
        raw_slug = m_li.group(1).split("•")[0].split("|")[0].split("\n")[0].strip()
        slug = re.sub(r"\s*-\s*", "-", raw_slug).strip().rstrip("/")
        linkedin = f"https://linkedin.com/in/{slug}"

    # 4. Extract GitHub
    github = ""
    m_gh = re.search(
        r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_\-]+(?:\s*-\s*[a-zA-Z0-9_\-]+)*)",
        combined_text,
        re.IGNORECASE,
    )
    if m_gh:
        raw_slug = m_gh.group(1).split("•")[0].split("|")[0].split("\n")[0].strip()
        slug = re.sub(r"\s*-\s*", "-", raw_slug).strip().rstrip("/")
        github = f"https://github.com/{slug}"

    # 5. Extract Portfolio / custom personal website
    portfolio = ""
    for m in re.finditer(r"https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s,•|)]*)?", combined_text):
        u = m.group(0).strip().rstrip(".,;")
        if not any(
            b in u.lower()
            for b in [
                "linkedin.com",
                "github.com",
                "twitter.com",
                "x.com",
                "t.me",
                "google.com",
                "cantina.xyz",
                "sherlock.xyz",
                "schema.org",
                "coursera.org",
            ]
        ):
            portfolio = u
            break

    # 6. Extract Location
    location = ""
    for line in raw_lines[:10]:
        line_strip = line.strip()
        if line_strip.startswith("#"):
            line_strip = line_strip.lstrip("#").strip()
        for part in re.split(r"[•|]", line_strip):
            p_clean = part.strip(" \t-•,")
            if any(
                c in p_clean.lower()
                for c in [
                    "romania",
                    "brașov",
                    "brasov",
                    "germany",
                    "uk",
                    "usa",
                    "united states",
                    "france",
                    "canada",
                    "remote",
                    "london",
                    "berlin",
                    "austin",
                    "seattle",
                    "san francisco",
                    "new york",
                    "eet",
                    "utc",
                    "est",
                    "pst",
                ]
            ):
                if not any(
                    w in p_clean.lower()
                    for w in [
                        "university",
                        "college",
                        "school",
                        "institute",
                        "department",
                        "company",
                        "consultant",
                        "developer",
                        "engineer",
                        "researcher",
                        "@",
                    ]
                ):
                    location = p_clean
                    break
        if location:
            break

    # 7. Extract Name from top header lines
    name = ""
    for line in raw_lines[:6]:
        line_clean = line.strip()
        if line_clean.startswith("#"):
            line_clean = line_clean.lstrip("#").strip()
        if not line_clean or line_clean.startswith(("##", "http", "www", "mailto", "+", "@")):
            continue
        if any(char in line_clean for char in ["@", "•", "|", "http"]):
            continue
        if len(line_clean.split()) <= 4 and not any(
            w in line_clean.lower()
            for w in [
                "developer",
                "engineer",
                "researcher",
                "consultant",
                "resume",
                "curriculum",
                "vitae",
                "summary",
                "skills",
                "experience",
                "education",
            ]
        ):
            cleaned_name = re.sub(r"\s*-\s*", "-", line_clean).strip()
            if cleaned_name.isupper():
                name = cleaned_name.title()
            else:
                name = cleaned_name
            break

    return PersonalInfo(
        name=name,
        email=email,
        phone=phone,
        location=location,
        linkedin=linkedin,
        github=github,
        portfolio=portfolio,
    )


def is_section_heading(line: str) -> str | None:
    """Classify section heading with length validation to prevent swallowing paragraphs."""
    line_clean = line.strip()
    words = line_clean.split()
    if len(words) > 5:
        return None

    norm = re.sub(r"[^a-zA-Z0-9& ]+", " ", line.lower()).strip()
    tokens = set(norm.split())

    if "education" in tokens and ("certifications" in tokens or "certification" in tokens):
        return "education_certifications"
    if any(k in tokens for k in ["summary", "profile", "about", "objective"]):
        return "summary"
    if any(k in tokens for k in ["skills", "technologies", "technology", "stack", "competencies", "technical"]):
        return "skills"
    if any(k in tokens for k in ["experience", "employment", "history", "work"]):
        return "experience"
    if any(k in tokens for k in ["education", "academic", "university", "college"]):
        return "education"
    if any(k in tokens for k in ["certifications", "certification", "certificates", "licenses", "courses"]):
        return "certifications"
    if any(k in tokens for k in ["projects", "selected_projects"]):
        return "projects"
    if any(k in tokens for k in ["languages", "language"]):
        return "languages"
    if any(k in tokens for k in ["achievements", "awards", "honors"]):
        return "achievements"
    return None


def parse_skills_section(lines: list[str], full_text: str) -> dict[str, list[str]]:
    """Parse categorized and inline skill items for any industry or profession."""
    grouped: dict[str, list[str]] = {}
    for line in lines:
        if ":" in line:
            cat, raw_values = line.split(":", 1)
            cat_key = re.sub(r"[^a-z0-9_]+", "_", cat.strip().lower()).strip("_")
            values = split_inline_values(raw_values)
            if values:
                grouped[cat_key] = values
        else:
            values = split_inline_values(line)
            if values:
                grouped.setdefault("general", []).extend(values)

    if grouped:
        return {k: unique_strings(v) for k, v in grouped.items() if v}

    # If no explicit skills lines, extract non-trivial keywords from the skills block
    extracted_tokens: list[str] = []
    for line in lines:
        cleaned_line = line.strip(" \t•-*|")
        if cleaned_line and len(cleaned_line) > 2:
            extracted_tokens.extend(
                [item.strip() for item in re.split(r"[,;|•]", cleaned_line) if len(item.strip()) > 1]
            )

    if extracted_tokens:
        return {"general": unique_strings(extracted_tokens)}
    return {}


def parse_experience_section(lines: list[str]) -> list[Experience]:
    """Parse roles, companies, durations, locations, and achievement bullets for any career field."""
    entries: list[Experience] = []
    curr_title = ""
    curr_company = ""
    curr_duration = ""
    curr_location = ""
    curr_bullets: list[str] = []

    def flush_exp() -> None:
        nonlocal curr_title, curr_company, curr_duration, curr_location, curr_bullets
        if curr_title or curr_company:
            entries.append(
                Experience(
                    title=curr_title or "Professional",
                    company=curr_company,
                    duration=curr_duration,
                    location=curr_location,
                    bullets=curr_bullets,
                )
            )
        curr_title = ""
        curr_company = ""
        curr_duration = ""
        curr_location = ""
        curr_bullets = []

    role_title_markers = [
        "manager",
        "director",
        "specialist",
        "coordinator",
        "representative",
        "nurse",
        "accountant",
        "analyst",
        "developer",
        "engineer",
        "designer",
        "consultant",
        "officer",
        "assistant",
        "associate",
        "executive",
        "lead",
        "head",
        "teacher",
        "practitioner",
        "researcher",
        "auditor",
        "doctor",
        "therapist",
        "recruiter",
        "strategist",
        "producer",
        "editor",
        "writer",
        "architect",
        "attorney",
        "counsel",
        "paralegal",
        "administrator",
        "advisor",
        "agent",
        "technician",
        "operator",
        "supervisor",
        "intern",
        "fellow",
        "chef",
        "pilot",
        "driver",
        "partner",
        "founder",
        "officer",
        "worker",
        "specialist",
    ]

    for line in lines:
        if "|" in line:
            flush_exp()
            parts = [p.strip() for p in line.split("|")]
            curr_title = parts[0]
            curr_company = parts[1] if len(parts) > 1 else ""
        elif " at " in line and not line.startswith(("-", "•", "*")) and len(line.split()) <= 7:
            flush_exp()
            parts = re.split(r"\s+at\s+", line, maxsplit=1, flags=re.IGNORECASE)
            curr_title = parts[0].strip()
            curr_company = parts[1].strip() if len(parts) > 1 else ""
        elif (
            any(
                marker in line.lower() for marker in ["present", "2024", "2025", "2026", "2023", "2022", "2021", "2020"]
            )
            and ("•" in line or "–" in line or "-" in line)
            and not line.startswith(("•", "-", "*"))
        ):
            parts = [p.strip() for p in line.split("•")]
            if len(parts) >= 2:
                curr_location = parts[0]
                curr_duration = parts[1]
            else:
                curr_duration = line
        elif (
            any(m in line.lower() for m in role_title_markers)
            and not line.startswith(("•", "-", "*"))
            and len(line.split()) <= 6
        ):
            flush_exp()
            curr_title = line
        else:
            b = line.strip(" \t-•*")
            if b:
                curr_bullets.append(b)

    flush_exp()
    return entries


def parse_education_and_certifications(
    edu_lines: list[str], cert_lines: list[str]
) -> tuple[list[Education], list[Certification]]:
    """Parse degrees, institutions, graduation dates, and certifications."""
    edu_list: list[Education] = []
    cert_list: list[Certification] = []
    curr_degree = ""
    curr_inst = ""
    curr_year = ""

    def flush_edu() -> None:
        nonlocal curr_degree, curr_inst, curr_year
        if curr_degree or curr_inst:
            edu_list.append(
                Education(
                    institution=curr_inst or "University",
                    degree=curr_degree,
                    year=curr_year,
                )
            )
        curr_degree = ""
        curr_inst = ""
        curr_year = ""

    for cert_line in cert_lines:
        c_clean = cert_line.strip(" \t-•*")
        if c_clean:
            cert_list.append(Certification(name=c_clean))

    for edu_line in edu_lines:
        line_clean = edu_line.strip(" \t-•*")
        if not line_clean:
            continue
        if any(
            marker in line_clean
            for marker in [
                "Cyfrin",
                "Cornell",
                "Udemy",
                "Coursera",
                "Certora",
                "—",
                "Certification",
                "Certificate",
            ]
        ) and not any(deg in line_clean.lower() for deg in ["bachelor", "master", "phd", "b.s.", "m.s.", "degree"]):
            cert_list.append(Certification(name=line_clean))
            continue
        if any(
            deg in line_clean.lower()
            for deg in ["bachelor", "master", "phd", "b.s.", "m.s.", "degree", "diploma", "associate"]
        ):
            flush_edu()
            curr_degree = line_clean
        elif any(
            u in line_clean.lower()
            for u in [
                "university",
                "college",
                "school",
                "faculty",
                "institute",
                "transylvania",
                "academy",
                "polytechnic",
            ]
        ):
            parts = [p.strip() for p in re.split(r"\s+•\s+|\s+\|\s+", line_clean) if p.strip()]
            curr_inst = parts[0]
            if len(parts) > 1 and not curr_year:
                yr_match = re.search(r"\b(20\d{2}|19\d{2})\b", parts[1])
                if yr_match:
                    curr_year = yr_match.group(0)
            if not curr_year:
                yr_match = re.search(r"\b(20\d{2}|19\d{2})\b", line_clean)
                if yr_match:
                    curr_year = yr_match.group(0)
        else:
            yr_match = re.search(r"\b(20\d{2}|19\d{2})\b", line_clean)
            if yr_match and not curr_year:
                curr_year = yr_match.group(0)

    flush_edu()
    return edu_list, cert_list


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
            lang, level = line.split(":", 1)
        elif " - " in line:
            lang, level = line.split(" - ", 1)
        else:
            lang, level = line, ""
        languages.append(Language(language=lang.strip(), level=level.strip()))
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
