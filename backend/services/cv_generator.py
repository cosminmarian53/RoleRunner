import logging
import re
from uuid import UUID

from backend.models.profile import CandidateProfile

logger = logging.getLogger(__name__)


def clean_candidate_headline(job_title: str, profile_title: str = "") -> str:
    """
    Derive an elegant, professional candidate headline aligned with the target role.
    Strips raw board suffixes, requisition codes, cohorts, location tags, and seasonal fluff.
    """
    if profile_title and len(profile_title.strip()) > 3:
        return profile_title.strip()
    if not job_title:
        return "Software Engineer"

    t = job_title.strip()
    # Remove 'at Company • Location' and everything after 'at ' or '•'
    t = re.split(r"\s+(?:at\s+[A-Z]|•|\|)\s*", t)[0].strip()
    # Remove board suffixes and company suffixes
    t = re.sub(
        r"\s*[-–—]\s*(?:Jobs?|Careers?|Wellfound|Lever|Ashby|Greenhouse|Workable|Indeed|SmartRecruiters|TP-Link|Palantir|Blink22|Canonical|ScriptChain|Euronet|CertiK|Clickhouse).*$",
        "",
        t,
        flags=re.I,
    ).strip()
    # Remove location suffixes
    t = re.sub(
        r"\s*[-–—]\s*(?:France|Germany|UK|US|USA|London|Berlin|New York|San Francisco|Canada|Australia|Singapore|EMEA|APAC|US\s*Government.*).*$",
        "",
        t,
        flags=re.I,
    ).strip()
    # Remove parentheticals
    t = re.sub(
        r"\s*\((?:m/f/d|m/w/d|d/f/m|f/m/d|remote|hybrid|on-site|full-time|part-time|contract|req\s*\d+|us\s*government.*)\)",
        "",
        t,
        flags=re.I,
    ).strip()
    # Remove seasonal prefixes
    t = re.sub(
        r"^(?:\d{4}|Summer\s*\d{4}|Fall\s*\d{4}|Winter\s*\d{4}|Spring\s*\d{4})\s*(?:Early\s*Career|Internship|Intern)?\s*[-–—:]?\s*",
        "",
        t,
        flags=re.I,
    ).strip()

    # Check internship
    is_intern = bool(re.search(r"\b(intern|internship|co-op|trainee|student)\b", job_title, re.I))

    # Clean inner parentheticals like (Internship, Summer 2027)
    base = re.sub(
        r"[\(,]?\s*(?:internship|intern|co-op|trainee|student|summer\s*\d{4}|fall\s*\d{4}|winter\s*\d{4}|spring\s*\d{4}|202[4-9])\s*[\)]?",
        "",
        t,
        flags=re.I,
    ).strip(" ,-–—")
    base = re.sub(r"\s*[-–—]\s*Software\s+Engineering\b", "Software Engineering", base, flags=re.I).strip()

    if is_intern:
        if "intern" not in base.lower():
            if base.lower().endswith("engineer"):
                base = base[:-8] + "Engineering"
            return f"{base.strip()} Intern".strip()

    return base or t


def _format_category_name(raw_category: str) -> str:
    """Transform snake_case or raw category strings into clean CV section labels."""
    cleaned = raw_category.replace("_", " ").strip()
    lower = cleaned.lower()
    if lower in ("tools software", "tools and software", "tools"):
        return "Tools & Technologies"
    if lower in ("core competencies", "competencies", "core skills"):
        return "Core Competencies"
    if lower in ("technical skills", "tech skills"):
        return "Technical Skills"
    if lower in ("languages frameworks", "frameworks"):
        return "Languages & Frameworks"
    return cleaned.title()


def generate_deterministic_cv_markdown(
    profile: CandidateProfile,
    job_title: str = "",
    company: str = "",
) -> str:
    """Deterministic template generator that transforms CandidateProfile into structured ATS Markdown."""
    lines: list[str] = []

    # 1. Header & Title
    name = profile.personal_info.name or "Candidate"
    target_role = clean_candidate_headline(job_title, getattr(profile.personal_info, "title", ""))
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
        gh = profile.personal_info.github
        contact_parts.append(f"[GitHub]({gh if gh.startswith('http') else f'https://{gh}'})")
    if profile.personal_info.linkedin:
        li = profile.personal_info.linkedin
        contact_parts.append(f"[LinkedIn]({li if li.startswith('http') else f'https://{li}'})")
    if profile.personal_info.portfolio:
        pf = profile.personal_info.portfolio
        contact_parts.append(f"[Portfolio]({pf if pf.startswith('http') else f'https://{pf}'})")

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
            clean_ach = ach.strip().lstrip("-•*▪ ").strip()
            if clean_ach:
                lines.append(f"- {clean_ach}")
        lines.append("")

    # 3. Core Skills & Competencies
    skills_map = profile.skills or getattr(profile, "technical_skills", {})
    if skills_map:
        lines.append("## Core Skills & Competencies")
        for cat, items in skills_map.items():
            if items:
                formatted_cat = _format_category_name(cat)
                lines.append(f"- **{formatted_cat}:** {', '.join(items)}")
        lines.append("")

    # 4. Professional Experience
    if profile.experience:
        lines.append("## Experience")
        for exp in profile.experience:
            role_parts = [exp.title.strip(), exp.company.strip()]
            duration = exp.duration.strip() if getattr(exp, "duration", "") else ""
            if not duration:
                start = getattr(exp, "start_date", "").strip()
                end = getattr(exp, "end_date", "").strip()
                if start and end:
                    duration = f"{start} – {end}"
                elif start:
                    duration = f"{start} – Present"
            if duration:
                role_parts.append(duration)

            lines.append(f"### {' | '.join(role_parts)}")

            bullets = exp.bullets or getattr(exp, "bullet_points", [])
            for bullet in bullets:
                # Handle multiline or piped bullets from paste/parsing
                parts = bullet.replace("|", "\n").split("\n") if "|" in bullet else [bullet]
                for p in parts:
                    clean_b = p.strip().lstrip("-•*▪ ").strip()
                    if clean_b:
                        lines.append(f"- {clean_b}")
            lines.append("")

    # 5. Projects
    if profile.projects:
        lines.append("## Projects & Key Initiatives")
        for proj in profile.projects:
            tech = proj.tech or ", ".join(getattr(proj, "technologies", []))
            header = f"### {proj.name}" + (f" ({tech})" if tech else "")
            lines.append(header)
            if proj.description:
                lines.append(f"- {proj.description.strip().lstrip('-•*▪ ')}")
            for b in getattr(proj, "bullet_points", []):
                clean_b = b.strip().lstrip("-•*▪ ").strip()
                if clean_b:
                    lines.append(f"- {clean_b}")
            lines.append("")

    # 6. Education & Certifications
    if profile.education or profile.certifications:
        lines.append("## Education & Certifications")
        for cert in profile.certifications:
            date_str = f" ({cert.date})" if cert.date else ""
            lines.append(f"- **{cert.name}** – {cert.issuer}{date_str}")
        for edu in profile.education:
            degree_str = f"{edu.degree} – {edu.details}" if edu.details else edu.degree
            year_str = f" ({edu.year})" if edu.year else ""
            lines.append(f"- **{degree_str}** – {edu.institution}{year_str}")
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
        headline = clean_candidate_headline(job_title, getattr(profile.personal_info, "title", ""))

        if not use_ai:
            return generate_deterministic_cv_markdown(profile, job_title, company)

        prompt = f"""You are an expert career strategist and professional executive resume writer.
Given the candidate's master profile and the target job description, generate an impeccably formatted, ATS-optimized CV in Markdown.

STRICT FORMATTING & CONTENT RULES:
1. Preserve all factual truth from the master profile; DO NOT fabricate companies, dates, or metrics.
2. Structure all achievements, responsibilities, and project points into distinct markdown bullet points starting with `- `.
3. NEVER output raw unbulleted paragraphs for job experiences or achievements. Every single responsibility must be a bullet point `- `.
4. Convert all skill category names into polished Title Case (e.g. `Tools & Technologies`, `Core Competencies`).
5. Choose a clean, professional candidate headline (recommended: `{headline}`) representing the candidate's qualification level, NEVER verbatim echoing messy employer requisition IDs, locations, or seasonal dates.
6. Adhere strictly to this hierarchy:
   # [Candidate Name]
   **{headline}**
   [Email] • [Phone] • [Location] • [GitHub Link] • [LinkedIn Link]

   [Tailored Executive Summary emphasizing alignment with the role]

   ## Key Achievements
   - [Bulleted achievement 1 with metrics]
   - [Bulleted achievement 2 with metrics]

   ## Core Skills & Competencies
   - **[Category 1]:** [Skill, Skill, Skill]
   - **[Category 2]:** [Skill, Skill, Skill]

   ## Experience
   ### [Job Title] | [Company Name] | [Date Range]
   - [Action-driven bullet point starting with strong verb and measurable impact]
   - [Action-driven bullet point]

   ## Projects & Key Initiatives
   ### [Project Name] ([Tech Stack])
   - [Project impact, architectural decisions, and deliverables]

   ## Education & Certifications
   - **[Degree / Certificate]** – [Institution] ([Year])

TARGET JOB DETAILS:
Title: {job_title}
Company: {company}
Description:
{job_description[:4000]}

CANDIDATE MASTER PROFILE (JSON):
{profile.model_dump_json(indent=2)}

Return ONLY the clean tailored Markdown document without conversational preamble or closing notes."""

        try:
            from backend.services.ai_client import ask

            ai_output = await ask(prompt, user_id=self.user_id)
            cleaned: str = ai_output.strip()
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
