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
            if len(clean_label) < 3 or clean_label.lower() in seen_labels:
                continue

            # Check if this is a standard contact field (handled separately)
            lower = clean_label.lower()
            if any(k in lower for k in ["first name", "last name", "full name", "email", "phone", "resume", "cv"]):
                continue

            # Detect field type
            textarea = block.find("textarea")
            select = block.find("select")
            field_type = "textarea" if textarea else ("select" if select else "text")

            options = [opt.get_text(strip=True) for opt in select.find_all("option")] if select else []

            seen_labels.add(clean_label.lower())
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

        return fields[:12]

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

        # Auto-draft answers for custom questions
        for q in custom_questions:
            lbl = q.label.lower()
            if "why" in lbl or "interest" in lbl:
                q.suggested_answer = (
                    f"I am excited about {company}'s mission and engineering approach. The opportunity to contribute "
                    f"to the {job_title} role aligns directly with my background in software engineering, API integrations, "
                    f"and automated testing. I thrive in fast-paced environments where software directly impacts real-world operations."
                )
            elif "challenge" in lbl or "project" in lbl or "bug" in lbl:
                q.suggested_answer = (
                    "In a recent project (X-Scout), I architected an automated data pipeline processing 500+ daily data points. "
                    "A key challenge was ensuring zero flaky test failures across concurrent ingestion flows. I solved this by implementing "
                    "isolated Playwright browser contexts and robust exponential backoff handling, achieving a 100% test reliability rate."
                )
            elif "authoriz" in lbl or "sponsorship" in lbl:
                q.suggested_answer = "Yes, authorized to work."
            elif "start" in lbl or "date" in lbl or "availab" in lbl:
                q.suggested_answer = "Available immediately / as specified in the role timeline."
            elif "salary" in lbl or "compensation" in lbl:
                q.suggested_answer = "Negotiable / Standard range for the role."
            else:
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
