"""Tailored Markdown CV generation service with AI content curation and deterministic fallback."""

from __future__ import annotations

import logging
from uuid import UUID

from backend.models.profile import CandidateProfile

logger = logging.getLogger(__name__)


def generate_deterministic_cv_markdown(
    profile: CandidateProfile,
    job_title: str = "",
    company: str = "",
) -> str:
    """Deterministic template generator that transforms CandidateProfile into structured ATS Markdown."""
    lines: list[str] = []

    # 1. Header & Title
    name = profile.personal_info.name or "Candidate"
    target_role = job_title or "Software Professional"
    lines.append(f"# {name}")
    lines.append(f"**{target_role}**")
    lines.append("")

    # Contact & Links
    contact_parts: list[str] = []
    if profile.personal_info.email:
        contact_parts.append(profile.personal_info.email)
    if profile.personal_info.phone:
        contact_parts.append(profile.personal_info.phone)
    if profile.personal_info.location:
        contact_parts.append(profile.personal_info.location)
    if profile.personal_info.github:
        contact_parts.append(f"[GitHub]({profile.personal_info.github})")
    if profile.personal_info.linkedin:
        contact_parts.append(f"[LinkedIn]({profile.personal_info.linkedin})")
    if profile.personal_info.portfolio:
        contact_parts.append(f"[Portfolio]({profile.personal_info.portfolio})")

    if contact_parts:
        lines.append(" • ".join(contact_parts))
        lines.append("")

    # Executive Summary
    summary = profile.summary.strip() or getattr(profile.personal_info, "summary", "").strip()
    if summary:
        if company:
            lines.append(f"{summary} Targeting the {target_role} role at {company}.")
        else:
            lines.append(summary)
        lines.append("")

    # 2. Key Achievements (if present)
    achievements = profile.achievements or getattr(profile, "key_achievements", [])
    if achievements:
        lines.append("## Key Achievements")
        for ach in achievements:
            lines.append(f"- {ach.strip()}")
        lines.append("")

    # 3. Technical Skills
    skills_map = profile.skills or getattr(profile, "technical_skills", {})
    if skills_map:
        lines.append("## Technical Skills")
        for cat, items in skills_map.items():
            if items:
                lines.append(f"- **{cat}:** {', '.join(items)}")
        lines.append("")

    # 4. Professional Experience
    if profile.experience:
        lines.append("## Experience")
        for exp in profile.experience:
            role_header = f"### {exp.title} | {exp.company}"
            duration = exp.duration or getattr(exp, "start_date", "")
            if duration:
                role_header += f" | {duration}"
            lines.append(role_header)
            bullets = exp.bullets or getattr(exp, "bullet_points", [])
            for bullet in bullets:
                lines.append(f"- {bullet.strip()}")
            lines.append("")

    # 5. Projects
    if profile.projects:
        lines.append("## Projects")
        for proj in profile.projects:
            proj_header = f"### {proj.name}"
            tech = proj.tech or ", ".join(getattr(proj, "technologies", []))
            if tech:
                proj_header += f" ({tech})"
            lines.append(proj_header)
            if proj.description:
                lines.append(f"- {proj.description.strip()}")
            for b in getattr(proj, "bullet_points", []):
                lines.append(f"- {b.strip()}")
            lines.append("")

    # 6. Education & Certifications
    if profile.education or profile.certifications:
        lines.append("## Education & Certifications")
        for cert in profile.certifications:
            date_str = cert.date
            lines.append(f"- **{cert.name}** - {cert.issuer} ({date_str})")
        for edu in profile.education:
            degree_str = f"{edu.degree} - {edu.details}" if edu.details else edu.degree
            year_str = edu.year
            lines.append(f"- **{degree_str}** - {edu.institution} ({year_str})")
        lines.append("")

    return "\n".join(lines).strip()


class CVGenerator:
    """Generates tailored CVs matching job descriptions."""

    def __init__(self, user_id: UUID | None = None) -> None:
        self.user_id = user_id

    async def generate_markdown(
        self,
        profile: CandidateProfile,
        job_description: str,
        job_title: str = "",
        company: str = "",
        use_ai: bool = False,
    ) -> str:
        """Generate tailored CV Markdown content."""
        if not use_ai:
            return generate_deterministic_cv_markdown(profile, job_title, company)

        prompt = f"""You are an expert technical career strategist and resume writer.
Given the candidate's master profile and the target job description, generate a tailored, professional single-column ATS-friendly CV in Markdown.

STRICT REQUIREMENTS:
1. Preserve all factual truth from the master profile; DO NOT invent metrics, companies, or dates.
2. Select and highlight the skills, achievements, and bullet points most relevant to the target job description.
3. Keep the format concise, clean, and adhering to this structure:
   # [Candidate Name]
   **[Target Role Title]**
   [Email] • [Phone] • [Location] • [Links]

   [Tailored Executive Summary]

   ## Key Achievements
   - [Bulleted achievements with metrics]

   ## Technical Skills
   - **[Category]:** [Comma separated skills]

   ## Experience
   ### [Title] | [Company] | [Date Range]
   - [Relevant action-oriented achievement bullets]

   ## Projects
   ### [Project Name] ([Tech])
   - [Bulleted details]

   ## Education & Certifications
   - [Degree/Certification bullets]

TARGET JOB DETAILS:
Title: {job_title}
Company: {company}
Description:
{job_description[:3000]}

CANDIDATE MASTER PROFILE (JSON):
{profile.model_dump_json(indent=2)}

Return ONLY the final tailored Markdown document without introductory or concluding conversational text.
"""
        try:
            from backend.services.ai_client import ask

            ai_output = await ask(prompt, user_id=self.user_id)
            cleaned: str = str(ai_output).strip()
            # Remove ```markdown blocks if present
            if cleaned.startswith("```markdown"):
                cleaned = cleaned[len("```markdown") :].strip()
            if cleaned.startswith("```"):
                cleaned = cleaned[len("```") :].strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

            if cleaned and cleaned.startswith("#"):
                return cleaned
        except Exception as exc:
            logger.warning("AI CV generation failed, falling back to deterministic template: %s", exc)

        return generate_deterministic_cv_markdown(profile, job_title, company)
