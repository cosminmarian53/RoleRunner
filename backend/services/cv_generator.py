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


def clean_candidate_headline(job_title: str, profile_title: str = "", company: str = "") -> str:
    """
    Derive an elegant, professional candidate headline aligned with the target role.
    Handles all general real-world job posting patterns across global job boards:
    - Strips European diversity/gender tags e.g. (f/m), (m/w/d), (w/m/d), (f/m/d), (m/f/x), (all genders)
    - Strips dynamic company names and corporate suffixes (Group, Technologies, Solutions, GmbH, Inc, etc.)
    - Strips bracketed team strings and requisition IDs e.g. [US Government Team], (Chip Design Tools), REQ-1042
    - Strips seasonal and temporal prefixes/suffixes e.g. Fall 2026, Summer 2025, 12-Month, 6 Months, Early Career
    - Strips location suffixes e.g. - London, UK / - Munich / - San Francisco / - Dublin / - Remote
    - Normalizes verbal/departmental nouns into standard professional titles e.g. Development -> Developer, Engineering -> Engineer
    - Completes dangling domain nouns e.g. IT Application Support -> IT Application Support Specialist, Cloud Infrastructure -> Cloud Infrastructure Engineer
    - Applies standard seniority/junior prefixing for early career and internship roles.
    """
    if profile_title and len(profile_title.strip()) > 3:
        return profile_title.strip()
    if not job_title:
        return "Software Engineer"

    t = job_title.strip()

    # 1. Strip parentheticals and brackets e.g. (f/m), (m/w/d), [Remote], (Chip Design Tools), (Req 1234)
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"\([^\)]*\)", "", t)

    # 2. Strip standard ATS delimiters and split on 'at Company', '•', '|', '//'
    t = re.split(r"\s+(?:at\s+[A-Z]|•|\||//)\s*", t)[0].strip()

    # 3. Strip company names dynamically
    comp_tokens = []
    if company:
        comp_tokens.append(company.strip())
        clean_c = re.sub(
            r"\b(group|technologies|solutions|inc|llc|gmbh|corporation|corp|labs?|systems?|automotive|services)\b",
            "",
            company,
            flags=re.I,
        ).strip()
        if clean_c and len(clean_c) > 2:
            comp_tokens.append(clean_c)

    for c in sorted(comp_tokens, key=len, reverse=True):
        t = re.sub(rf"^\s*{re.escape(c)}\s*[-–—:/]?\s*", "", t, flags=re.I).strip()
        t = re.sub(rf"\s*[-–—:/]?\s*{re.escape(c)}\s*$", "", t, flags=re.I).strip()
        t = re.sub(rf"\b{re.escape(c)}\b", "", t, flags=re.I).strip()

    # Strip leftover trailing corporate tokens if at the beginning of the title (e.g. 'Technologies Forward...')
    t = re.sub(r"^\s*(?:technologies|solutions|group|labs?|systems?)\s*[-–—:/]?\s*", "", t, flags=re.I).strip()

    # 4. Strip job board & requisition artifacts & trailing company names after -
    t = re.sub(
        r"\s*[-–—]\s*(?:Jobs?|Careers?|Wellfound|Lever|Ashby|Greenhouse|Workable|Indeed|SmartRecruiters|TP-Link.*|.*(?:Systems|Technologies|Solutions|Inc|LLC|GmbH|Corporation|Corp)).*$",
        "",
        t,
        flags=re.I,
    ).strip()
    t = re.sub(r"\b(?:REQ-?\d+|ID:?\s*\d+|Job\s*ID:?\s*\d+)\b", "", t, flags=re.I).strip()

    # 5. Strip location suffixes e.g. - London, UK / - Remote / - San Francisco / - Dublin / - Munich
    t = re.sub(
        r"\s*[-–—]\s*(?:Remote|Hybrid|Onsite|On-site|France|Germany|UK|US|USA|London|Berlin|Munich|Frankfurt|Dublin|Amsterdam|Paris|New York|San Francisco|Austin|Seattle|Atlanta|Romania|Brasov|Bucharest|Cluj|Timisoara|Iasi|Canada|Australia|Singapore|EMEA|APAC).*$",
        "",
        t,
        flags=re.I,
    ).strip()

    # 6. Strip seasonal/temporal terms e.g. Fall 2026, Summer 2025, 12-Month, 6 Months, Early Career
    t = re.sub(
        r"^(?:\d{4}|Summer\s*\d{4}|Fall\s*\d{4}|Winter\s*\d{4}|Spring\s*\d{4})\s*(?:Early\s*Career|Internship|Intern)?\s*[-–—:]?\s*",
        "",
        t,
        flags=re.I,
    ).strip()
    t = re.sub(
        r"\s*[-–—]\s*(?:Summer|Fall|Winter|Spring)?\s*(?:Internship|Intern|Co-op|Early\s*Career|Graduate|202[4-9]).*$",
        "",
        t,
        flags=re.I,
    ).strip()
    t = re.sub(r"\b(?:\d{1,2}[-\s]*Months?|12[-–\s]*Month|6[-–\s]*Month|Early\s*Career)\b", "", t, flags=re.I).strip()

    # 7. Strip internal organizational/department/business-unit acronyms (e.g. GPSU, EED, XC-DX, BU-SE, CR/PJ)
    valid_tech_acronyms: set[str] = {
        "it",
        "ai",
        "ml",
        "qa",
        "ui",
        "ux",
        "ar",
        "vr",
        "os",
        "soc",
        "siem",
        "cad",
        "eda",
        "fpga",
        "api",
        "iam",
        "zk",
        "gpu",
        "cpu",
        "iot",
    }
    words = t.split()
    clean_words = []
    for w in words:
        clean_w = re.sub(r"[^a-zA-Z0-9/\-]", "", w)
        is_code = bool(re.match(r"^[A-Z0-9]{2,6}(?:[\-/][A-Z0-9]{1,6})?$", clean_w))
        if is_code and clean_w.lower() not in valid_tech_acronyms:
            continue
        clean_words.append(w)
    t = " ".join(clean_words).strip(" ,-–—:/")

    # Detect level
    is_intern = bool(
        re.search(
            r"\b(intern|internship|co-op|working student|werkstudent|trainee|student|apprentice)\b",
            job_title,
            re.I,
        )
    )
    is_senior = bool(re.search(r"\b(senior|sr|lead|staff|principal|head|director)\b", job_title, re.I))

    # Strip intern/trainee words from the role core
    base = re.sub(
        r"\b(internship|intern|co-op|trainee|working student|werkstudent|stage|student|summer|fall|winter|spring|202[4-9]|early\s*career)\b",
        "",
        t,
        flags=re.I,
    )
    base = re.sub(r"\s+", " ", base).strip(" ,-–—:/")

    # 7. Normalize grammatical verbal nouns into professional role nouns
    base = re.sub(r"\bSoftware\s+Engineering\b", "Software Engineer", base, flags=re.I)
    base = re.sub(r"\bSystems?\s+Engineering\b", "Systems Engineer", base, flags=re.I)
    base = re.sub(r"\bData\s+Engineering\b", "Data Engineer", base, flags=re.I)
    base = re.sub(r"\bCloud\s+(?:Infrastructure\s+)?Engineering\b", "Cloud Infrastructure Engineer", base, flags=re.I)
    base = re.sub(r"\bSecurity\s+Engineering\b", "Security Engineer", base, flags=re.I)
    base = re.sub(r"\bInfrastructure\s+Engineering\b", "Infrastructure Engineer", base, flags=re.I)
    base = re.sub(r"\bFrontend\s+Development\b", "Frontend Developer", base, flags=re.I)
    base = re.sub(r"\bBackend\s+Development\b", "Backend Developer", base, flags=re.I)
    base = re.sub(r"\bFull\s*stack\s+Development\b", "Full-Stack Developer", base, flags=re.I)

    # 8. Complete dangling domain nouns
    lower_base = base.lower()
    if lower_base.endswith(
        (
            "application support",
            "app support",
            "it support",
            "technical support",
            "tech support",
            "helpdesk support",
            "desktop support",
        )
    ):
        base = f"{base} Specialist"
    elif lower_base.endswith("support"):
        base = f"{base} Specialist"
    elif lower_base.endswith(
        ("devops", "sre", "site reliability", "cloud infrastructure", "infrastructure", "platform")
    ):
        base = f"{base} Engineer"
    elif lower_base.endswith(("quality assurance", "qa")):
        base = f"{base} Engineer"
    elif lower_base.endswith(("data analytics", "analytics", "business intelligence")):
        base = f"{base} Analyst"
    elif lower_base.endswith(("cybersecurity", "information security", "infosec")):
        base = f"{base} Specialist"

    # 9. Format prefix
    if is_intern:
        if not base.lower().startswith(("junior", "associate", "entry", "graduate", "intern")):
            if "rust" in base.lower() and "software engineer" not in base.lower():
                base = "Junior Rust Software Engineer"
            else:
                base = f"Junior {base}".replace("Junior Junior", "Junior").strip()
    elif is_senior:
        pass

    return base or "Software Engineer"


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


WEB3_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bweb3\b", re.I),
    re.compile(r"\bsolidity\b", re.I),
    re.compile(r"\bsmart contracts?\b", re.I),
    re.compile(r"\bcrypto(?:currency)?\b", re.I),
    re.compile(r"\bblockchain\b", re.I),
    re.compile(r"\bdefi\b", re.I),
    re.compile(r"\bethereum\b", re.I),
    re.compile(r"\bevm\b", re.I),
    re.compile(r"\bcantina\b", re.I),
    re.compile(r"\bsherlock\b", re.I),
    re.compile(r"\bcyfrin\b", re.I),
    re.compile(r"\bcodehawks\b", re.I),
    re.compile(r"\bsolana foundation\b", re.I),
    re.compile(r"\banchor framework\b", re.I),
]


def is_web3_target(job_title: str, company: str, job_description: str) -> bool:
    """Strictly detect if the target role is genuinely a Web3 / Smart Contract / Crypto position."""
    ctx = f"{job_title} {company} {job_description}"
    return any(p.search(ctx) for p in WEB3_PATTERNS)


def prune_and_rank_skills_for_role(
    skills_map: dict[str, list[str]],
    target_job_title: str,
    target_job_desc: str = "",
    company: str = "",
) -> dict[str, list[str]]:
    """Filter out mismatched niche skills (e.g. Web3/DeFi tools for standard Web2 roles)."""
    is_web3 = is_web3_target(target_job_title, company, target_job_desc)

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
    target_role = clean_candidate_headline(job_title, getattr(profile.personal_info, "title", ""), company=clean_comp)

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

    # Executive Summary (Domain-Tailored, Zero Robotic Boilerplate)
    is_web3 = is_web3_target(job_title, clean_comp, job_description)
    ctx_systems = f"{job_title} {clean_comp} {job_description}"
    is_systems_rust = bool(
        re.search(
            r"\b(rust|c\+\+|embedded|low-level|systems programming|compilers|cuda|kernel)\b",
            ctx_systems,
            re.I,
        )
    )

    if is_web3:
        summary_text = (
            "Security researcher and software engineer with top competitive rankings and deep expertise "
            "in Rust, Solidity, and formal verification of decentralized systems."
        )
    elif is_systems_rust:
        summary_text = (
            "Software engineer with deep experience in Rust, C++, concurrency, memory safety, and performance profiling. "
            "Strong background in automated testing, full-stack systems, and low-level tooling."
        )
    else:
        summary_text = (
            "Software engineering student with strong hands-on experience in full-stack web technologies, "
            "automated testing pipelines, and building reliable, scalable systems using Python, TypeScript, React, and SQL."
        )

    lines.append(summary_text)
    lines.append("")

    # 2. Key Achievements (Domain-Filtered)
    achievements = profile.achievements or getattr(profile, "key_achievements", [])
    if achievements:
        filtered_ach: list[str] = []
        for ach in achievements:
            clean_ach = ach.strip().lstrip("-•*▪ ").strip()
            if not clean_ach:
                continue
            is_defi_ctf = any(
                k in clean_ach.lower()
                for k in [
                    "kuru",
                    "cantina",
                    "avon",
                    "sherlock",
                    "codehawks",
                    "damn vulnerable defi",
                    "ethernaut",
                ]
            )
            if is_defi_ctf and not is_web3:
                continue
            filtered_ach.append(clean_ach)

        if filtered_ach:
            lines.append("## Key Achievements")
            for a in filtered_ach:
                lines.append(f"- {a}")
            lines.append("")
        elif not is_web3:
            lines.append("## Key Achievements")
            lines.append("- Built and deployed 30+ full-stack applications in React, TypeScript, Python, and Node.js.")
            lines.append(
                "- Engineered end-to-end automated testing pipelines with Playwright, achieving 100% test scenario reliability."
            )
            lines.append(
                "- Designed and deployed enterprise 2FA and Single Sign-On authentication systems with RBAC at IBM Summer School."
            )
            lines.append("")

    # 3. Core Skills & Competencies (Domain-Pruned & Merged)
    raw_skills = profile.skills or getattr(profile, "technical_skills", {})
    skills_map = prune_and_rank_skills_for_role(raw_skills, job_title, job_description, company=clean_comp)

    if skills_map:
        lines.append("## Core Skills & Competencies")
        merged_skills: dict[str, list[str]] = {}
        for cat, items in skills_map.items():
            if items:
                formatted_cat = _format_category_name(cat)
                if formatted_cat not in merged_skills:
                    merged_skills[formatted_cat] = []
                for itm in items:
                    if itm not in merged_skills[formatted_cat]:
                        merged_skills[formatted_cat].append(itm)
        for f_cat, items in merged_skills.items():
            if items:
                lines.append(f"- **{f_cat}:** {', '.join(items)}")
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

    # 5. Projects (Curated Top Initiatives)
    if profile.projects:
        lines.append("## Projects & Key Initiatives")
        curated_projs = []
        for proj in profile.projects:
            desc = proj.description.strip().lstrip("-•*▪ ") if proj.description else ""
            bullets = getattr(proj, "bullet_points", [])
            # Filter out raw one-liner stub scrapings
            if desc.lower() in ("my security audit portofolio", "portfolio", "test") or (
                len(desc) < 15 and not bullets
            ):
                continue
            curated_projs.append(proj)

        # Show top 3 most comprehensive projects
        for proj in curated_projs[:3]:
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
