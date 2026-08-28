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

    # Certifications
    certs_list = []
    for cert in profile.certifications:
        date_str = f" ({cert.date})" if cert.date else ""
        certs_list.append(f"{cert.name} – {cert.issuer}{date_str}")
    certs_summary = (
        ", ".join(certs_list)
        if certs_list
        else "Smart Contract Security (Cyfrin, May 2025), Assembly and Formal Verification (Cyfrin, Oct 2025), Introduction to Software Engineering (IBM, Mar 2024), Blockchain Essentials (Cornell University, Oct 2024)"
    )

    return {
        "country": country,
        "city": city,
        "school": school,
        "degree": degree,
        "discipline": discipline,
        "start_year": start_year,
        "end_year": end_year,
        "certs_summary": certs_summary,
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

        # 1. Look for structured form groups (NEVER select bare label tags as blocks!)
        question_blocks = soup.select(
            ".custom-question, .application-question, .form-group, .section-wrapper, "
            "[data-qa='form-field'], .ashby-application-form-field, fieldset, "
            ".field, .form-field, .form-row, .s5-field, #custom_fields .field, "
            "#demographic_questions .field, #eeoc_fields .field, form > div"
        )

        for block in question_blocks:
            # Decompose nested autocomplete dropdown popups and helper search boxes
            for noise_child in block.select(".autocomplete, .dropdown, .helper-text, .search-results, .input-feedback"):
                noise_child.decompose()

            # Find primary label
            label_el = block.find(
                class_=lambda c: c and any(k in c for k in ["application-label", "text", "title", "prompt"])
            )
            if not label_el:
                legend = block.find("legend")
                if legend:
                    label_el = legend
                else:
                    for l_tag in block.find_all("label"):
                        if not l_tag.find(["input"]):
                            label_el = l_tag
                            break
                        if not label_el:
                            label_el = l_tag

            if not label_el:
                continue

            raw_label = label_el.get_text(separator=" ", strip=True)
            # Filter out tiny or noise labels and clean suffixes properly without character-class collisions
            clean_label = re.sub(r"[\s\*✱]+$", "", raw_label).strip()
            clean_label = re.sub(r"\s*\(?(?:Required|Optional|\*|✱)\)?\s*$", "", clean_label, flags=re.I).strip()
            clean_lower = clean_label.lower()

            if len(clean_label) < 2 or clean_lower in seen_labels:
                continue

            # Filter out non-question UI buttons, JD headings, and company FAQ headers
            # Candidate-directed questions should never be filtered as JD headers
            is_candidate_directed = any(
                k in clean_lower
                for k in [
                    "do you",
                    "are you",
                    "would you",
                    "tell us",
                    "your interest",
                    "good fit",
                    "want to work",
                    "why are you",
                ]
            )

            # Filter out non-question UI buttons, JD headings, and company FAQ headers
            if not is_candidate_directed and (
                clean_lower in NOISE_LABELS
                or clean_lower
                in (
                    "select one",
                    "select...",
                    "select",
                    "other",
                    "links",
                    "basic information",
                )
                or bool(
                    re.search(
                        r"^(?:must[\s-]have|nice[\s-]to[\s-]have|good[\s-]to[\s-]have|requirements?|qualifications?|responsibilities|benefits|perks|compensation|overview|about (?:us|the role|the team|the company|the position)|who we are|how we (?:work|hire)|life at .*|culture at .*|equal (?:opportunity|employment).*)$",
                        clean_lower,
                    )
                )
                or bool(
                    re.search(
                        r"^(?:what (?:does\s+.*|is\s+.*|we\s+(?:do|offer|look for|are looking for)|you(?:\'ll|\s+will)\s+(?:do|bring|own|need)|it means to be.*)|why\s+(?:join\s+us|work\s+here|\w+\??$)|who\s+we\s+are)",
                        clean_lower,
                    )
                )
            ):
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
                    "current location",
                    "current company",
                    "linkedin url",
                    "linkedin profile",
                    "other website",
                    "preferred first name",
                    "nick name",
                    "legal first name",
                    "legal last name",
                ]
            ):
                continue

            # Detect field type
            textarea = block.find("textarea")
            select = block.find("select")
            field_type = "textarea" if textarea else ("select" if select else "text")

            # Extract options if radio / checkbox / select
            options = []
            for opt in block.select(".application-list label, select option, .options label, ul li label"):
                opt_text = opt.get_text(strip=True)
                if opt_text and opt_text.lower() not in ["select...", "select one", "select"]:
                    options.append(opt_text)

            seen_labels.add(clean_lower)
            fields.append(
                ApplicationFormField(
                    field_id=f"field_{len(fields) + 1}",
                    label=clean_label,
                    field_type=field_type,
                    required="*" in raw_label or "required" in raw_label.lower() or "✱" in raw_label,
                    options=options[:15],
                )
            )

        if not fields:
            return self._default_standard_questions()

        return fields[:20]

    def _default_standard_questions(self) -> list[ApplicationFormField]:
        """Comprehensive general master form based on the most commonly asked application questions."""
        return [
            # 1. Motivation & Technical Experience
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
            # 2. Portfolio & Work Samples
            ApplicationFormField(
                field_id="portfolio_link",
                label="Portfolio / GitHub / Technical Project Link",
                field_type="text",
                required=False,
            ),
            ApplicationFormField(
                field_id="portfolio_included",
                label="Have you included a portfolio or technical work samples with your application?",
                field_type="select",
                options=["Yes", "No"],
                required=False,
            ),
            # 3. Work Authorization & Immigration
            ApplicationFormField(
                field_id="work_authorization_us",
                label="Are you currently authorized to work in the United States?",
                field_type="select",
                options=["Yes", "No"],
                required=True,
            ),
            ApplicationFormField(
                field_id="visa_sponsorship",
                label="Will you now or in the future require visa sponsorship for employment?",
                field_type="select",
                options=["Yes", "No"],
                required=True,
            ),
            ApplicationFormField(
                field_id="export_control_us_person",
                label="I am one of the following: (a) a citizen of the United States; (b) a lawful permanent resident of the United States; or (c) a person admitted into the United States as an asylee or refugee",
                field_type="select",
                options=["Yes", "No"],
                required=True,
            ),
            ApplicationFormField(
                field_id="restricted_country_check",
                label="If no, is your home country listed on the U.S. EAR restricted country list?",
                field_type="select",
                options=["Yes", "No"],
                required=False,
            ),
            # 4. Timeline & Schedule
            ApplicationFormField(
                field_id="ideal_start_date",
                label="Ideal start date in office / earliest availability",
                field_type="text",
                required=False,
            ),
            ApplicationFormField(
                field_id="ideal_end_date",
                label="Ideal end date / commitment duration",
                field_type="text",
                required=False,
            ),
            ApplicationFormField(
                field_id="full_time_hire_timeline",
                label="When are you available for full-time hire / expected graduation date?",
                field_type="text",
                required=False,
            ),
            ApplicationFormField(
                field_id="schedule_commitment",
                label="Are you able to commit to the required weekly schedule (e.g. 25–40 hrs/week)?",
                field_type="select",
                options=["Yes", "No"],
                required=False,
            ),
            # 5. Education & Background
            ApplicationFormField(
                field_id="education_degree",
                label="What university/college are you currently attending and what degree are you pursuing?",
                field_type="text",
                required=False,
            ),
            ApplicationFormField(
                field_id="certifications_credentials",
                label="Do you have any recognized industry certifications or specialized training?",
                field_type="textarea",
                required=False,
            ),
            ApplicationFormField(
                field_id="prior_internship_experience",
                label="Do you have prior internship or professional engineering experience?",
                field_type="textarea",
                required=False,
            ),
            # 6. Logistics & Referral
            ApplicationFormField(
                field_id="in_person_onboarding_travel",
                label="Would you be able to attend mandatory in-person onboarding or travel as required?",
                field_type="select",
                options=["Yes", "No"],
                required=False,
            ),
            ApplicationFormField(
                field_id="referral_source",
                label="How did you hear about this opportunity?",
                field_type="text",
                required=False,
            ),
        ]

    def parse_text_form(self, text: str) -> list[ApplicationFormField]:
        """Extract structured questions and options from raw pasted job application text."""
        if not text:
            return []

        # 1. If text contains an 'Application' or 'Apply for this role' section header, focus on the form section
        app_split = re.split(
            r"\n\s*(?:application|apply for this (?:job|role|position)|application form)\s*\n",
            text,
            flags=re.IGNORECASE,
        )
        form_text = app_split[-1] if len(app_split) > 1 else text

        lines = [line.strip() for line in form_text.split("\n") if line.strip()]
        fields: list[ApplicationFormField] = []
        seen: set[str] = set()

        noise_prefixes = (
            "autofill from resume",
            "upload your resume",
            "accepted file types",
            "or drag and drop",
            "attach",
            "enter manually",
            "overview",
            "internship benefits",
            "about the role",
            "responsibilities",
            "qualifications",
            "what you will do",
            "compensation",
            "we take on",
            "we build",
            "you will own",
            "this is an in-office",
            "this position involves access",
            "required - please",
            "all interns at",
            "annual range",
            "equal opportunity",
            "privacy policy",
        )
        noise_exact = {
            "name",
            "email",
            "resume",
            "first name",
            "last name",
            "phone",
            "location",
            "select...",
            "select one",
            "select",
            "other",
            "yes",
            "no",
            "intern",
            "application",
            "u.s. export control questions",
            "export control analysis",
            "overview",
        }

        for line in lines:
            clean = re.sub(r"[\s\*✱:]+$", "", line).strip()
            lower = clean.lower()

            if not clean or len(clean) < 3:
                continue
            if lower in noise_exact:
                continue
            if any(lower.startswith(prefix) for prefix in noise_prefixes):
                continue

            # Candidate-directed questions should never be filtered as JD headers
            is_candidate_directed = any(
                k in lower
                for k in [
                    "do you",
                    "are you",
                    "would you",
                    "tell us",
                    "your interest",
                    "good fit",
                    "want to work",
                    "why are you",
                ]
            )

            # Skip job description headings, company marketing questions, and requirement sections
            if not is_candidate_directed and (
                bool(
                    re.search(
                        r"^(?:must[\s-]have|nice[\s-]to[\s-]have|good[\s-]to[\s-]have|requirements?|qualifications?|responsibilities|benefits|perks|compensation|overview|about (?:us|the role|the team|the company|the position)|who we are|how we (?:work|hire)|life at .*|culture at .*|equal (?:opportunity|employment).*)$",
                        lower,
                    )
                )
                or bool(
                    re.search(
                        r"^(?:what (?:does\s+.*|is\s+.*|we\s+(?:do|offer|look for|are looking for)|you(?:\'ll|\s+will)\s+(?:do|bring|own|need)|it means to be.*)|why\s+(?:join\s+us|work\s+here|\w+\??$)|who\s+we\s+are)",
                        lower,
                    )
                )
            ):
                continue

            # Skip multi-sentence descriptive paragraphs unless it is a legal declaration
            if len(re.findall(r"\.\s+[A-Z]", clean)) >= 2 and not (
                "i am one of the following" in lower or "if no" in lower or "if yes" in lower
            ):
                continue

            # Check if line is a legitimate form question
            is_question = (
                line.endswith("?")
                or line.endswith(":")
                or any(
                    lower.startswith(k)
                    for k in [
                        "do you",
                        "are you",
                        "will you",
                        "have you",
                        "would you",
                        "what is",
                        "what are",
                        "when are",
                        "tell us",
                        "why",
                        "how did you",
                        "please list",
                        "please enter",
                        "if yes",
                        "if no",
                        "ideal start",
                        "ideal end",
                        "portfolio",
                        "earliest",
                        "i am one of the following",
                    ]
                )
                or (
                    len(clean.split()) <= 6
                    and any(
                        k in lower
                        for k in [
                            "portfolio",
                            "github",
                            "start date",
                            "end date",
                            "clearance",
                            "certification",
                            "hear about",
                        ]
                    )
                )
            )

            if is_question and lower not in seen:
                seen.add(lower)
                ftype = "textarea" if any(k in lower for k in ["tell us", "why", "describe", "list"]) else "text"
                fields.append(
                    ApplicationFormField(
                        field_id=f"text_field_{len(fields) + 1}",
                        label=clean,
                        field_type=ftype,
                        required=True,
                    )
                )

        return fields

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

        # Fallback to smart text parser if HTML yielded no custom questions but description has form text
        if (not custom_questions or custom_questions == self._default_standard_questions()) and job_description:
            text_questions = self.parse_text_form(job_description)
            if text_questions:
                custom_questions = text_questions

        facts = extract_profile_facts(profile)

        # Standard contact fields prefilled from candidate profile
        p_info = profile.personal_info
        name_parts = (p_info.name or "Candidate").split(" ", 1)
        standard_fields = {
            "Full Name": p_info.name,
            "Legal First Name": name_parts[0],
            "Legal Last Name": name_parts[1] if len(name_parts) > 1 else "",
            "Preferred First Name": name_parts[0].split("-")[0],
            "Email": p_info.email,
            "Phone": p_info.phone,
            "Current Location": p_info.location,
            "Current Company": "Transilvania University of Brasov (Student)",
            "LinkedIn URL": p_info.linkedin,
            "GitHub / Portfolio": p_info.github,
        }

        # Cover note / brief intro
        skills_summary = ", ".join(list(profile.skills.get("Tools & Technologies", []))[:5]) or "full-stack systems"
        cover_note = (
            f"Hi {company} Recruiting Team,\n\n"
            f"I'm excited to apply for the {job_title} position. With hands-on experience building reliable systems, "
            f"automated testing pipelines, and software architectures using {skills_summary}, "
            f"I am eager to contribute directly to your engineering milestones.\n\n"
            f"Best regards,\n{p_info.name}"
        )

        # Smart Answer Generator for each custom question
        for q in custom_questions:
            lbl = q.label.lower().strip()

            # 1. Export Controls / ITAR / 22 C.F.R. § 120.62 / EAR Restricted Countries
            if bool(re.search(r"\b(home country listed below|restricted country)\b", lbl)):
                q.suggested_answer = "No (Home country is Romania, which is not on the restricted list)"
            elif bool(
                re.search(r"\b(citizen of the united states|lawful permanent resident|asylee or refugee)\b", lbl)
            ):
                q.suggested_answer = "No"
            elif bool(re.search(r"\b(export control|u\.?s\.?\s*person|itar|ear|compliance obligation)\b", lbl)):
                q.suggested_answer = "Foreign person. This ITAR/EAR status includes anyone who is not a U.S. person."

            # 2. Portfolio Links & Inclusion
            elif bool(re.search(r"\b(portfolio.*(?:link|website|url)|website link.*portfolio)\b", lbl)):
                q.suggested_answer = (
                    profile.personal_info.portfolio
                    or profile.personal_info.github
                    or "https://github.com/cosminmarian53/security-audit-portofolio"
                )
            elif bool(re.search(r"\b(included a portfolio|include a portfolio)\b", lbl)):
                q.suggested_answer = "Yes (Included link to portfolio and GitHub)"

            # 3. Ideal Start & End Dates
            elif bool(re.search(r"\b(ideal start date|start date in office)\b", lbl)):
                q.suggested_answer = "January 2026 / Winter 2026 (or as aligned with the internship cohort)"
            elif bool(re.search(r"\b(ideal end date|internship end date)\b", lbl)):
                q.suggested_answer = "April 2026 / Spring 2026"

            # 4. Previous Internship Experience
            elif bool(re.search(r"\b(previous internship|prior internship|completed.*internship)\b", lbl)):
                q.suggested_answer = (
                    "Yes. I completed a Cybersecurity Analyst Internship at IBM Summer School (July 2025), where I designed "
                    "and deployed an enterprise 2FA system using TOTP, QR codes, SSO, and RBAC, managed SSL/TLS certificate lifecycles, "
                    "and conducted automated security and reliability assessments."
                )

            # 5. Academic Standing & Junior/Senior Year
            elif bool(re.search(r"\b(junior year|senior year|graduate student|academic level|year of study)\b", lbl)):
                q.suggested_answer = (
                    "Yes (Entering senior year at Transilvania University of Brasov, completing degree in 2026)."
                )

            # 6. Full-time Hire & Graduation Timeline
            elif bool(
                re.search(r"\b(when are you available for full-time|full-time hire|available for full-time)\b", lbl)
            ):
                q.suggested_answer = "Summer 2026 (Upon graduation in 2026)"

            # 7. Schedule & Weekly Hours Commitments
            elif bool(
                re.search(
                    r"\b(25-29|schedule|self-paced|hours|hrs/wk|eastern|monday|friday|training program)\b",
                    lbl,
                )
            ):
                q.suggested_answer = (
                    "Yes, I am fully available to commit to the required 25–29 hrs/week schedule between "
                    "11am–4pm Eastern Monday through Friday for the full duration of the program."
                )

            # 8. Semester Availability
            elif bool(re.search(r"\b(semester|cohort|term)\b", lbl)):
                # Match semester if listed in options or title
                if any("fall 2026" in opt.lower() for opt in q.options):
                    q.suggested_answer = "Fall 2026"
                elif q.options:
                    q.suggested_answer = q.options[0]
                else:
                    q.suggested_answer = "Fall 2026"

            # 9. Referral Source & Employee Affiliation
            elif bool(
                re.search(
                    r"\b(current or former.*employee|employee referral|associated with a customer|vendor partner|connection to them)\b",
                    lbl,
                )
            ):
                q.suggested_answer = "No"
            elif bool(re.search(r"\b(how did you hear|referral|source)\b", lbl)):
                q.suggested_answer = "LinkedIn / Sam's Youtube"

            # 10. Industry Certifications & Training
            elif "cert" in lbl:
                if "list" in lbl or q.field_type in ("textarea", "text"):
                    q.suggested_answer = facts["certs_summary"]
                else:
                    q.suggested_answer = "Yes"
            elif bool(
                re.search(r"\b(formal training|training.*experience within cybersecurity|cybersecurity/it)\b", lbl)
            ):
                q.suggested_answer = "Yes (B.S. in Electrical Engineering & Computer Science, Cybersecurity Analyst Internship at IBM Summer School)"

            # 11. Security Clearance
            elif bool(re.search(r"\b(security clearance|clearance level|active clearance)\b", lbl)):
                q.suggested_answer = "None / Not Applicable"

            # 9. In-Person Onboarding & Travel
            elif bool(
                re.search(r"\b(attend.*onboarding|in-person onboarding|mandatory in-person|willing to travel)\b", lbl)
            ):
                q.suggested_answer = (
                    "Yes, I am fully able to attend mandatory in-person onboarding and travel as required."
                )

            # 10. Physical Location & Address
            elif bool(re.search(r"\b(physically located within the united states|physically located.*us)\b", lbl)):
                q.suggested_answer = (
                    "No (Located in Brasov, Romania; open to travel for onboarding and remote coordination)"
                )
            elif bool(re.search(r"\b(primary location during|where will you primarily be located)\b", lbl)):
                q.suggested_answer = f"{facts['city']}, {facts['country']}"
            elif lbl in (
                "full street address",
                "street address",
                "address",
                "city, state & zip",
                "city, state, zip",
                "postal code",
                "zip code",
            ):
                q.suggested_answer = f"{facts['city']}, {facts['country']}"
            elif lbl in ("country", "country of residence", "current country"):
                q.suggested_answer = facts["country"]
            elif lbl in ("location (city)", "city", "current city", "location") or "what is your location" in lbl:
                q.suggested_answer = (
                    facts["country"]
                    if any(facts["country"].lower() in opt.lower() for opt in q.options)
                    else facts["city"]
                )

            # 11. Signature Name & Date Fields
            elif lbl in ("name", "signature", "full name signature", "applicant signature"):
                q.suggested_answer = profile.personal_info.name or "Cosmin-Marian Lavric"
            elif lbl in ("date", "signature date", "today's date"):
                import datetime

                q.suggested_answer = datetime.date.today().strftime("%m/%d/%Y")

            # 12. Work Authorization & Visa Sponsorship
            elif "require" in lbl and ("visa" in lbl or "sponsorship" in lbl):
                q.suggested_answer = "Yes"
            elif "authorized to work" in lbl or ("legal" in lbl and "work" in lbl):
                if "united states" in lbl or "us" in lbl:
                    q.suggested_answer = "No"
                else:
                    q.suggested_answer = "Yes"

            # 13. Education & University Fields
            elif bool(
                re.search(
                    r"\b(university.*attending|college.*attending|what university|what college|degree.*pursuing|currently attending|education.*background)\b",
                    lbl,
                )
            ):
                q.suggested_answer = f"{facts['degree']} at {facts['school']}"
            elif bool(
                re.search(
                    r"\b(your school|university name|college name|institution name|attended school|school/university)\b|^(?:school|university|college)$",
                    lbl,
                )
            ):
                q.suggested_answer = facts["school"]
            elif bool(
                re.search(
                    r"\b(your degree|degree type|degree level|highest degree|degree earned)\b|^(?:degree|qualification)$",
                    lbl,
                )
            ):
                q.suggested_answer = facts["degree"]
            elif bool(
                re.search(
                    r"\b(academic major|college major|undergraduate major|your major|field of study|area of study|academic discipline|major/field)\b|^(?:major|discipline)$",
                    lbl,
                )
            ):
                q.suggested_answer = facts["discipline"]
            elif bool(re.search(r"\b(start year|start date year)\b", lbl)):
                q.suggested_answer = facts["start_year"]
            elif bool(re.search(r"\b(end date year|graduation year|end year|grad year|year of graduation)\b", lbl)):
                q.suggested_answer = facts["end_year"]

            # 14. Availability & Compensation
            elif bool(re.search(r"\b(start date|earliest start|availability|available)\b", lbl)):
                q.suggested_answer = "Available immediately or as specified in the role timeline."
            elif bool(re.search(r"\b(salary|compensation|hourly rate|expected rate)\b", lbl)):
                q.suggested_answer = "Negotiable / standard range for the role."

            # 15. Voluntary Demographic / EEO Fields
            elif lbl == "gender" or "what gender" in lbl:
                q.suggested_answer = "Male"
            elif bool(re.search(r"\b(are you hispanic|hispanic/latino|hispanic or latino)\b", lbl)):
                q.suggested_answer = "No"
            elif lbl in ("race", "ethnicity") or "ethnicity" in lbl:
                q.suggested_answer = "White (Not Hispanic or Latino)"
            elif "veteran" in lbl:
                q.suggested_answer = "I am not a protected veteran"
            elif "disability" in lbl:
                q.suggested_answer = "No, I do not have a disability"
            elif "age range" in lbl:
                q.suggested_answer = "21-29"

            # 16. Core Motivation & Behavioral Prompts
            elif bool(
                re.search(
                    r"\b(mission|why|interest|interested|about us|excite|tell us a bit about yourself|why you'?d like to join)\b",
                    lbl,
                )
            ):
                q.suggested_answer = (
                    f"I am excited about {company}'s engineering focus and mission. The opportunity to contribute "
                    f"to the {job_title} role aligns directly with my background in software engineering, system architecture, "
                    f"and automated testing pipelines. I thrive in high-ownership environments where robust code directly drives impact."
                )
            elif bool(re.search(r"\b(challenge|project|bug|accomplishment|achievement)\b", lbl)):
                q.suggested_answer = (
                    "In a recent project (X-Scout), I architected an automated threat-intelligence data pipeline processing 500+ daily data points. "
                    "A key challenge was eliminating flaky test executions across concurrent browser workflows. I solved this by implementing "
                    "isolated Playwright browser contexts with exponential retry handling, achieving 100% test scenario reliability."
                )
            else:
                # 13. AI Fallback for unclassified custom employer questions
                if use_ai and self.user_id:
                    try:
                        from backend.services.ai_client import ask

                        prompt = f"""Draft a concise, professional, 1-2 sentence answer for this job application question.
Candidate: {profile.personal_info.name} ({facts['degree']} at {facts['school']}, skilled in Python, Rust, C++, TypeScript, React, SQL, Playwright).
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
                    f"With hands-on experience in software engineering, system architecture, and automated testing, "
                    f"I am well-prepared to execute directly on {company}'s technical requirements."
                )

        return ApplicationPackResponse(
            job_title=job_title,
            company=company,
            apply_url=job_url,
            standard_fields=standard_fields,
            custom_questions=custom_questions,
            cover_note=cover_note,
        )
