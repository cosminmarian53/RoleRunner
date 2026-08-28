import logging
import re
from uuid import UUID

from backend.models.profile import CandidateProfile

logger = logging.getLogger(__name__)

WEB3_ONLY_SKILLS: set[str] = {
    "foundry",
    "slither",
    "echidna",
    "certora",
    "aderyn",
    "solidity",
    "move",
    "solana",
    "anchor",
    "synpress",
    "groth16",
    "poseidon hashing",
    "zero-knowledge proofs",
    "zk proofs",
    "damn vulnerable defi",
    "ethernaut",
    "smart contract",
    "smart contracts",
    "web3auth",
}


def clean_company_name(company: str) -> str:
    """Strip job-board suffixes, location tags, and legal designations from company names."""
    if not company:
        return ""
    c = company.strip()
    c = re.sub(
        r"\s*(\||-)\s*(Jobs?|Careers?|Wellfound|Lever|Ashby|Greenhouse|Workable|Indeed|SmartRecruiters|Early\s*Career).*$",
        "",
        c,
        flags=re.I,
    ).strip()
    c = re.sub(r"\s*•\s*.*$", "", c).strip()
    return c


def clean_candidate_headline(job_title: str, profile_title: str = "") -> str:
    """
    Derive an elegant, professional candidate headline aligned with the target role.
    Always produces a clean industry job title (e.g. 'Junior Rust Software Engineer' or 'Rust Software Engineer'
    for junior/intern roles, 'Senior Software Engineer' for senior roles).
    Strips raw board suffixes, bracketed team strings, requisition codes, cohorts, and seasonal fluff.
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
        r"\s*[-–—]\s*(?:Jobs?|Careers?|Wellfound|Lever|Ashby|Greenhouse|Workable|Indeed|SmartRecruiters|TP-Link|Palantir|Blink22|Canonical|ScriptChain|Euronet|CertiK|Clickhouse|Fab2).*$",
        "",
        t,
        flags=re.I,
    ).strip()
    # Remove location suffixes
    t = re.sub(
        r"\s*[-–—]\s*(?:France|Germany|UK|US|USA|London|Berlin|New York|San Francisco|Austin|Canada|Australia|Singapore|EMEA|APAC|US\s*Government.*).*$",
        "",
        t,
        flags=re.I,
    ).strip()
    # Remove all parentheticals (e.g. (Chip Design Tools), (m/f/d), (US Government Team))
    t = re.sub(
        r"\s*\([^\)]*\)",
        "",
        t,
        flags=re.I,
    ).strip()
    # Remove seasonal prefixes and suffixes
    t = re.sub(
        r"^(?:\d{4}|Summer\s*\d{4}|Fall\s*\d{4}|Winter\s*\d{4}|Spring\s*\d{4})\s*(?:Early\s*Career|Internship|Intern)?\s*[-–—:]?\s*",
        "",
        t,
        flags=re.I,
    ).strip()
    t = re.sub(
        r"\s*[-–—]\s*(?:Summer|Fall|Winter|Spring)?\s*(?:Internship|Intern|Co-op|202[4-9]).*$",
        "",
        t,
        flags=re.I,
    ).strip()

    # Check seniority and role level
    is_intern = bool(re.search(r"\b(intern|internship|co-op|trainee|student)\b", job_title, re.I))
    is_senior = bool(re.search(r"\b(senior|sr|lead|staff|principal)\b", job_title, re.I))

    # Base title normalization
    base = re.sub(
        r"[\(,]?\s*(?:internship|intern|co-op|trainee|student|summer|fall|winter|spring|202[4-9])\s*[\)]?",
        "",
        t,
        flags=re.I,
    ).strip(" ,-–—")
    base = re.sub(r"Software\s+Engineering\b", "Software Engineer", base, flags=re.I).strip()

    if is_intern:
        if not base.lower().startswith(("junior", "intern")):
            if "rust" in base.lower():
                return "Junior Rust Software Engineer"
            if "software engineer" in base.lower():
                return f"Junior {base}".replace("Junior Junior", "Junior").strip()
            return f"Junior {base}".strip()

    if is_senior:
        return base

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


def prune_and_rank_skills_for_role(
    skills_map: dict[str, list[str]],
    target_job_title: str,
    target_job_desc: str = "",
    company: str = "",
) -> dict[str, list[str]]:
    """Filter out mismatched niche skills (e.g. Web3/DeFi tools for standard Web2 roles)."""
    ctx = f"{target_job_title} {company} {target_job_desc}".lower()
    is_web3 = any(
        w in ctx
        for w in [
            "web3",
            "solidity",
            "smart contract",
            "crypto",
            "blockchain",
            "defi",
            "protocol",
            "ethereum",
            "solana",
            "evm",
            "cantina",
            "sherlock",
            "cyfrin",
            "codehawks",
            "auditor",
            "audit",
        ]
    )

    pruned: dict[str, list[str]] = {}
    for cat, items in skills_map.items():
        filtered_items: list[str] = []
        for item in items:
            item_clean = item.strip()
            item_lower = item_clean.lower()
            # If target role is NOT Web3, omit specialized smart contract tools
            if not is_web3 and item_lower in WEB3_ONLY_SKILLS:
                continue
            filtered_items.append(item_clean)
        if filtered_items:
            pruned[cat] = filtered_items
    return pruned


def generate_deterministic_cv_markdown(
    profile: CandidateProfile,
    job_title: str = "",
    company: str = "",
    job_description: str = "",
) -> str:
    """Deterministic template generator that transforms CandidateProfile into structured ATS Markdown."""
    lines: list[str] = []
    clean_comp = clean_company_name(company)
    target_role = clean_candidate_headline(job_title, getattr(profile.personal_info, "title", ""))

    # 1. Header & Title
    name = profile.personal_info.name or "Candidate"
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

    # Executive Summary (Domain-Tailored)
    ctx = f"{job_title} {company} {job_description}".lower()
    is_web3 = any(
        w in ctx
        for w in [
            "web3",
            "solidity",
            "smart contract",
            "crypto",
            "blockchain",
            "defi",
            "ethereum",
            "solana",
            "cyfrin",
            "codehawks",
            "cantina",
            "auditor",
            "audit",
        ]
    )

    if is_web3:
        summary_text = (
            f"Security researcher and blockchain software engineer with top contest rankings and deep expertise "
            f"in Rust, Solidity, and formal verification. Targeting the {target_role} role at {clean_comp}."
            if clean_comp
            else "Security researcher and blockchain software engineer specializing in smart contracts and distributed protocols."
        )
    else:
        summary_text = (
            f"Software engineering student with strong hands-on experience in full-stack web technologies, "
            f"automated testing pipelines, and building secure, performant software systems using TypeScript, Python, React, and Node.js. "
            f"Targeting the {target_role} role at {clean_comp}."
            if clean_comp
            else "Software engineer with experience in full-stack web technologies, automated testing, and building secure, scalable systems."
        )

    lines.append(summary_text)
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

    # 3. Core Skills & Competencies (Domain-Pruned)
    raw_skills = profile.skills or getattr(profile, "technical_skills", {})
    skills_map = prune_and_rank_skills_for_role(raw_skills, job_title, job_description, company=clean_comp)

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
        clean_comp = clean_company_name(company)

        if not use_ai:
            return generate_deterministic_cv_markdown(profile, job_title, clean_comp, job_description)

        prompt = f"""You are an elite executive career strategist and technical resume writer.
Given the candidate's master profile and the target job description, generate an impeccably tailored, ATS-optimized CV in Markdown.

CRITICAL DOMAIN-AWARE TAILORING RULES:
1. DOMAIN FILTERING & SKILL PRUNING:
   - Carefully inspect the TARGET JOB domain (e.g. General Software Engineering / Web / Full-Stack vs. Web3 / DeFi vs. Cybersecurity).
   - If the target job is a general web or software engineering role (e.g. Notion, Google, Stripe, Palantir), STRICTLY OMIT specialized Web3/DeFi tools (Foundry, Slither, Echidna, Certora, Aderyn, Move, Solidity, Zero-Knowledge Proofs, Groth16, DeFi CTFs) from Core Skills and Executive Summary.
   - Instead, prioritize and feature general software engineering technologies present in the candidate's profile: TypeScript, JavaScript, Python, C++, React, Node.js, PostgreSQL, MongoDB, Docker, Git, CI/CD, Linux, Automated Testing (Playwright), REST APIs, and Software Quality.
2. ADAPTIVE EXECUTIVE SUMMARY:
   - Craft a compelling, customized 2-3 sentence executive summary tailored directly to the target role and company ({clean_comp or 'the company'}).
   - Emphasize relevant engineering strengths (full-stack web development, automated testing, scalable architectures, and clean code) rather than mismatched niche domain keywords.
3. BULLETS & DELIVERABLES:
   - Every single bullet under Experience and Projects MUST start with `- ` and a strong action verb.
   - Reframe project and experience bullets to emphasize core software deliverables, systems architecture, automated testing suites, and performance improvements.
4. HEADLINE & COMPANY:
   - Use candidate headline: `{headline}`.
   - Use clean company name: `{clean_comp}`.

STRICT ATS HIERARCHY:
# [Candidate Name]
**{headline}**
[Email] • [Phone] • [Location] • [GitHub Link] • [LinkedIn Link] • [Portfolio Link]

[Tailored Executive Summary]

## Key Achievements
- [Achievement bullet 1 with measurable impact]
- [Achievement bullet 2 with measurable impact]

## Core Skills & Competencies
- **Tools & Technologies:** [Clean, relevant tools list]
- **Core Competencies:** [Clean, relevant competencies list]
- **Languages & Frameworks:** [TypeScript, Python, JavaScript, C++, Rust, React, Node.js, SQL]

## Experience
### [Job Title] | [Company] | [Dates]
- [Action-driven bullet point]
- [Action-driven bullet point]

## Projects & Key Initiatives
### [Project Name] ([Tech Stack])
- [Architecture, implementation, and impact]

## Education & Certifications
- **[Degree / Certificate]** – [Institution] ([Year])

TARGET JOB DETAILS:
Title: {job_title}
Company: {clean_comp}
Description:
{job_description[:5000]}

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

        return generate_deterministic_cv_markdown(profile, job_title, clean_comp, job_description)
