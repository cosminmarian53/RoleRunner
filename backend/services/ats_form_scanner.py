"""ATS application form scanner and reviewable question-answer pack generator."""

from __future__ import annotations

import logging
import re
from uuid import UUID

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from backend.models.profile import CandidateProfile
from backend.scrapers.http_client import SafeAsyncClient

logger = logging.getLogger(__name__)


class ApplicationFormField(BaseModel):
    """Represents a discovered field or question on the employer's application form."""

    field_id: str
    label: str
    field_type: str = "text"  # text, textarea, select, radio, checkbox
    required: bool = False
    options: list[str] = Field(default_factory=list)
    suggested_answer: str = ""


class ApplicationPackResponse(BaseModel):
    """Complete reviewable application pack with discovered fields and tailored answers."""

    job_title: str
    company: str
    apply_url: str
    standard_fields: dict[str, str] = Field(default_factory=dict)
    custom_questions: list[ApplicationFormField] = Field(default_factory=list)
    cover_note: str = ""


NOISE_LABELS: set[str] = {
    "attach",
    "enter manually",
    "upload",
    "upload resume",
    "upload cv",
    "choose file",
    "select file",
    "browse",
    "drop files here",
    "submit",
    "submit application",
    "back",
    "next",
    "drag & drop",
    "drag and drop",
    "or",
    "apply with linkedin",
    "apply with indeed",
    "add resume",
    "add file",
    "delete",
    "remove",
}


def extract_profile_facts(profile: CandidateProfile) -> dict[str, str]:
    """Extract concrete candidate facts for deterministic question resolution."""
    loc = profile.personal_info.location or ""
    clean_loc = re.sub(r"\s*\([^\)]*\)", "", loc).strip()
    loc_parts = [p.strip() for p in clean_loc.split(",") if p.strip()]

    country = loc_parts[1] if len(loc_parts) >= 2 else (loc_parts[0] if loc_parts else "Romania")
    city = loc_parts[0] if loc_parts else "Brasov"

    # Education
    edu = profile.education[0] if profile.education else None
    school = edu.institution if edu and edu.institution else "Transilvania University of Brasov"
    degree = edu.degree if edu and edu.degree else "Bachelor of Science in Electrical Engineering & Computer Science"
    discipline = edu.details if edu and edu.details else "Computer Science / Information Technology"

    # Years
    year_str = edu.year if edu and edu.year else "2022 - 2026"
    years = re.findall(r"\b(20\d{2})\b", year_str)
    start_year = years[0] if len(years) >= 2 else "2022"
    end_year = years[1] if len(years) >= 2 else (years[0] if years else "2026")

    return {
        "country": country,
        "city": city,
        "school": school,
        "degree": degree,
        "discipline": discipline,
        "start_year": start_year,
        "end_year": end_year,
    }


class ATSFormScanner:
    """Scrapes employer application pages and drafts reviewable application packs."""

    def __init__(self, user_id: UUID | None = None, client: SafeAsyncClient | None = None) -> None:
        self.user_id = user_id
        self.client = client or SafeAsyncClient()

    async def fetch_form_html(self, url: str) -> str:
        """Fetch raw HTML from job application page."""
        if not url or not url.startswith("http"):
            return ""
        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                return str(resp.text)
        except Exception as exc:
            logger.debug("Failed to fetch application form from %s: %s", url, exc)
        return ""

    def parse_form_fields(self, html: str, url: str) -> list[ApplicationFormField]:
        """Extract input elements, textareas, and custom question labels from HTML."""
        if not html:
            return self._default_standard_questions()

        soup = BeautifulSoup(html, "html.parser")
        fields: list[ApplicationFormField] = []
        seen_labels: set[str] = set()

        # 1. Look for form groups, label + input pairs, or Ashby/Greenhouse/Lever question blocks
        question_blocks = soup.select(
            ".application-question, .form-group, .field, [data-qa='form-field'], .ashby-application-form-field, label"
        )

        for block in question_blocks:
            label_el = block if block.name == "label" else block.find("label")
            if not label_el:
                continue

            raw_label = label_el.get_text(separator=" ", strip=True)
            # Filter out tiny or noise labels
            clean_label = re.sub(r"\s*(\*|Required|\(Optional\))\s*$", "", raw_label, flags=re.I).strip()
            clean_lower = clean_label.lower()

            if len(clean_label) < 2 or clean_lower in seen_labels:
                continue

            # Filter out non-question UI buttons and noise labels
            if clean_lower in NOISE_LABELS:
                continue

            # Check if this is a standard contact field (handled in standard_fields)
            if any(
                k in clean_lower
                for k in [
                    "first name",
                    "last name",
                    "full name",
                    "email",
                    "phone",
                    "resume",
                    "cv",
                    "cover letter",
                    "linkedin",
                    "github",
                    "portfolio",
                    "website",
                ]
            ):
                continue

            # Detect field type
            textarea = block.find("textarea")
            select = block.find("select")
            field_type = "textarea" if textarea else ("select" if select else "text")

            options = [opt.get_text(strip=True) for opt in select.find_all("option")] if select else []

            seen_labels.add(clean_lower)
            fields.append(
                ApplicationFormField(
                    field_id=f"field_{len(fields) + 1}",
                    label=clean_label,
                    field_type=field_type,
                    required="*" in raw_label or "required" in raw_label.lower(),
                    options=options[:10],
                )
            )

        if not fields:
            return self._default_standard_questions()

        return fields[:15]

    def _default_standard_questions(self) -> list[ApplicationFormField]:
        """Sensible default employer questions when page is dynamic or blocked."""
        return [
            ApplicationFormField(
                field_id="why_company",
                label="Why are you interested in this role and company?",
                field_type="textarea",
                required=True,
            ),
            ApplicationFormField(
                field_id="technical_challenge",
                label="Describe a challenging technical project or bug you recently solved.",
                field_type="textarea",
                required=True,
            ),
            ApplicationFormField(
                field_id="work_authorization",
                label="Are you legally authorized to work in the country/location for this role?",
                field_type="select",
                options=["Yes", "No", "Require Sponsorship"],
                required=True,
            ),
            ApplicationFormField(
                field_id="start_date",
                label="What is your earliest possible start date or availability?",
                field_type="text",
                required=False,
            ),
        ]

    async def generate_application_pack(
        self,
        profile: CandidateProfile,
        job_title: str,
        company: str,
        job_description: str,
        job_url: str = "",
        use_ai: bool = True,
    ) -> ApplicationPackResponse:
        """Scan apply form and generate tailored answers for every question."""
        html = await self.fetch_form_html(job_url) if job_url else ""
        custom_questions = self.parse_form_fields(html, job_url)
        facts = extract_profile_facts(profile)

        # Standard contact fields prefilled from candidate profile
        p_info = profile.personal_info
        name_parts = (p_info.name or "Candidate").split(" ", 1)
        standard_fields = {
            "Full Name": p_info.name,
            "First Name": name_parts[0],
            "Last Name": name_parts[1] if len(name_parts) > 1 else "",
            "Email": p_info.email,
            "Phone": p_info.phone,
            "Location": p_info.location,
            "LinkedIn": p_info.linkedin,
            "GitHub": p_info.github,
            "Portfolio": p_info.portfolio,
        }

        # Cover note / brief intro
        skills_summary = ", ".join(list(profile.skills.get("Tools & Technologies", []))[:5]) or "full-stack systems"
        cover_note = (
            f"Hi {company} Recruiting Team,\n\n"
            f"I'm excited to apply for the {job_title} position. With hands-on experience building full-stack applications, "
            f"automated testing pipelines with Playwright, and reliable systems using {skills_summary}, "
            f"I am eager to contribute directly to your engineering milestones.\n\n"
            f"Best regards,\n{p_info.name}"
        )

        # Smart Answer Generator for each custom question
        for q in custom_questions:
            lbl = q.label.lower().strip()

            # 1. Schedule & Availability Commitments (Check early before 'major' or 'program')
            if bool(
                re.search(
                    r"\b(25-29|schedule|self-paced|hours|hrs/wk|eastern|monday|friday|training program|full-time|part-time)\b",
                    lbl,
                )
            ):
                q.suggested_answer = (
                    "Yes, I am fully available to commit to the required 25–29 hrs/week schedule between "
                    "11am–4pm Eastern Monday through Friday for the full duration of the program."
                )

            # 2. Geographic Location Fields
            elif lbl in ("country", "country of residence", "current country"):
                q.suggested_answer = facts["country"]
            elif lbl in ("location (city)", "city", "current city", "location"):
                q.suggested_answer = facts["city"]

            # 3. Work Authorization & Visa Sponsorship
            elif "require" in lbl and ("visa" in lbl or "sponsorship" in lbl):
                q.suggested_answer = "Yes, will require visa sponsorship."
            elif "authorized to work" in lbl or ("legal" in lbl and "work" in lbl):
                if "united states" in lbl or "us" in lbl:
                    q.suggested_answer = "No, I will require visa sponsorship."
                else:
                    q.suggested_answer = "Yes, authorized to work."

            # 4. Education & University Fields
            elif bool(re.search(r"\b(school|university|college|institution)\b", lbl)):
                q.suggested_answer = facts["school"]
            elif bool(re.search(r"\b(degree|qualification)\b", lbl)):
                q.suggested_answer = facts["degree"]
            elif bool(re.search(r"\b(discipline|major|field of study|area of study)\b", lbl)):
                q.suggested_answer = facts["discipline"]
            elif bool(re.search(r"\b(start date year|start year)\b", lbl)):
                q.suggested_answer = facts["start_year"]
            elif bool(re.search(r"\b(end date year|graduation year|end year|grad year)\b", lbl)):
                q.suggested_answer = facts["end_year"]

            # 5. Availability & Compensation
            elif bool(re.search(r"\b(start date|earliest start|availability|available)\b", lbl)):
                q.suggested_answer = "Available immediately or as specified in the role timeline."
            elif bool(re.search(r"\b(salary|compensation|hourly rate|expected rate)\b", lbl)):
                q.suggested_answer = "Negotiable / standard range for the role."

            # 6. Core Motivation & Behavioral Prompts
            elif bool(re.search(r"\b(why|interest|interested|about us)\b", lbl)):
                q.suggested_answer = (
                    f"I am excited about {company}'s mission and engineering approach. The opportunity to contribute "
                    f"to the {job_title} role aligns directly with my background in software engineering, full-stack development, "
                    f"and automated testing. I thrive in high-ownership teams where code directly impacts product reliability."
                )
            elif bool(re.search(r"\b(challenge|project|bug|accomplishment|achievement)\b", lbl)):
                q.suggested_answer = (
                    "In a recent project (X-Scout), I architected an automated threat-intelligence data pipeline processing 500+ daily data points. "
                    "A key challenge was eliminating flaky test executions across concurrent browser workflows. I solved this by implementing "
                    "isolated Playwright browser contexts with exponential retry handling, achieving 100% test scenario reliability."
                )
            else:
                # 6. AI Fallback for unclassified custom employer questions
                if use_ai and self.user_id:
                    try:
                        from backend.services.ai_client import ask

                        prompt = f"""Draft a concise, professional, 1-2 sentence answer for this job application question.
Candidate: {profile.personal_info.name} ({facts['degree']} at {facts['school']}, skilled in Python, TypeScript, React, SQL, Playwright).
Target Company: {company}
Target Role: {job_title}
Question: {q.label}

Return ONLY the direct answer text. Be concise, direct, and factual."""
                        ai_ans = await ask(prompt, user_id=self.user_id)
                        if ai_ans and len(ai_ans.strip()) > 3:
                            q.suggested_answer = ai_ans.strip().strip('"')
                            continue
                    except Exception:
                        pass

                q.suggested_answer = (
                    f"With my background in software engineering and hands-on experience building tested, "
                    f"reliable applications, I am well-prepared to execute on {company}'s requirements."
                )

        return ApplicationPackResponse(
            job_title=job_title,
            company=company,
            apply_url=job_url,
            standard_fields=standard_fields,
            custom_questions=custom_questions,
            cover_note=cover_note,
        )
