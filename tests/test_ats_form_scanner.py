"""Unit tests for ATS form scanner and application pack auto-filler."""

from __future__ import annotations

import httpx
import pytest

from backend.models.profile import CandidateProfile, Certification, Education, Experience, PersonalInfo, Project
from backend.scrapers.http_client import SafeAsyncClient
from backend.services.ats_form_scanner import ATSFormScanner


@pytest.mark.asyncio
async def test_ats_form_scanner_parses_html_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify HTML application forms are parsed into structured questions."""
    sample_html = """
    <html>
      <body>
        <form action="/submit" method="post">
          <div class="application-question">
            <label>Why do you want to work at Vital Lyfe? *</label>
            <textarea name="why_us"></textarea>
          </div>
          <div class="application-question">
            <label>Describe a difficult technical bug you solved. *</label>
            <textarea name="tech_bug"></textarea>
          </div>
          <div class="application-question">
            <label>Are you authorized to work in the United States? (Required)</label>
            <select name="work_auth">
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
        </form>
      </body>
    </html>
    """

    async def fake_get(self, url: str, *args, **kwargs) -> httpx.Response:
        return httpx.Response(200, text=sample_html, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    scanner = ATSFormScanner()
    fields = scanner.parse_form_fields(sample_html, "https://jobs.ashbyhq.com/vital/123")

    assert len(fields) >= 3
    assert any("Why do you want to work at Vital Lyfe" in f.label for f in fields)
    assert any("Describe a difficult technical bug" in f.label for f in fields)
    assert any("authorized to work" in f.label for f in fields)


@pytest.mark.asyncio
async def test_ats_form_scanner_generates_application_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify generate_application_pack produces pre-filled contact fields and tailored answers."""

    async def fake_get(self, url: str, *args, **kwargs) -> httpx.Response:
        return httpx.Response(404, text="", request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    profile = CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin Lavric",
            email="cosmin@test.com",
            phone="+40700000000",
            location="Brasov, Romania",
            github="https://github.com/cosminmarian53",
            linkedin="https://linkedin.com/in/cosmin",
        ),
        skills={"Tools & Technologies": ["Python", "TypeScript", "React", "SQL"]},
    )

    scanner = ATSFormScanner()
    pack = await scanner.generate_application_pack(
        profile=profile,
        job_title="Software Engineering Intern",
        company="Vital Lyfe",
        job_description="Python, TypeScript, React, internal tools, manufacturing data.",
        job_url="https://vital.com/careers/1",
    )

    assert pack.company == "Vital Lyfe"
    assert pack.standard_fields["Full Name"] == "Cosmin Lavric"
    assert pack.standard_fields["Email"] == "cosmin@test.com"
    assert "Vital Lyfe" in pack.cover_note
    assert len(pack.custom_questions) >= 3
    assert any("Vital Lyfe" in q.suggested_answer for q in pack.custom_questions)


@pytest.mark.asyncio
async def test_ats_form_scanner_resolves_education_geo_schedule_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify exact demographic, education, visa, and schedule questions resolve accurately."""
    from backend.models.profile import Education

    sample_html = """
    <div>
      <div class='application-question'><label>Country *</label><input /></div>
      <div class='application-question'><label>Location (City) *</label><input /></div>
      <div class='application-question'><label>Attach</label><button>Attach</button></div>
      <div class='application-question'><label>Enter manually</label><button>Enter</button></div>
      <div class='application-question'><label>School</label><input /></div>
      <div class='application-question'><label>Degree</label><input /></div>
      <div class='application-question'><label>Discipline</label><input /></div>
      <div class='application-question'><label>Start date year</label><input /></div>
      <div class='application-question'><label>End date year</label><input /></div>
      <div class='application-question'><label>Are you legally authorized to work in the United States? *</label><input /></div>
      <div class='application-question'><label>Will you now or in the future require an employment visa to work in the US? *</label><input /></div>
      <div class='application-question'><label>This is not a self-paced training program. Are you able to work 25-29 hrs/wk with a majority of hours being between 11am-4pm eastern Monday - Friday from January 11 - April 2, 2027? *</label><input /></div>
    </div>
    """

    async def fake_get(self, url: str, *args, **kwargs) -> httpx.Response:
        return httpx.Response(200, text=sample_html, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    profile = CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin Lavric",
            location="Brasov, Romania (EET)",
        ),
        education=[
            Education(
                institution="Transilvania University of Brasov",
                degree="Bachelor of Science in Electrical Engineering & Computer Science",
                year="2022 - 2026",
                details="Information Technology / Computer Science",
            )
        ],
    )

    scanner = ATSFormScanner()
    pack = await scanner.generate_application_pack(
        profile=profile,
        job_title="Software Engineering Intern",
        company="Notion",
        job_description="Full-stack intern",
        job_url="https://jobs.ashbyhq.com/notion/1",
    )

    # Verify buttons are filtered out
    labels = [q.label for q in pack.custom_questions]
    assert "Attach" not in labels
    assert "Enter manually" not in labels

    # Map labels to answers
    ans_map = {q.label: q.suggested_answer for q in pack.custom_questions}
    assert ans_map["Country"] == "Romania"
    assert ans_map["Location (City)"] == "Brasov"
    assert ans_map["School"] == "Transilvania University of Brasov"
    assert "Bachelor of Science" in ans_map["Degree"]
    assert "Computer Science" in ans_map["Discipline"]
    assert ans_map["Start date year"] == "2022"
    assert ans_map["End date year"] == "2026"
    assert ans_map["Are you legally authorized to work in the United States?"] == "No"
    assert ans_map["Will you now or in the future require an employment visa to work in the US?"] == "Yes"
    assert (
        "25–29 hrs/week"
        in ans_map[
            "This is not a self-paced training program. Are you able to work 25-29 hrs/wk with a majority of hours being between 11am-4pm eastern Monday - Friday from January 11 - April 2, 2027?"
        ]
    )


@pytest.mark.asyncio
async def test_greenhouse_guidepoint_form_scanning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Greenhouse .field DOM parsing and cybersecurity question answering."""
    greenhouse_html = """
    <form id="application_form">
      <div class="field">
        <label for="first_name">First Name<span class="asterisk">*</span></label>
        <input type="text" name="first_name" id="first_name" />
      </div>
      <div class="field">
        <label for="question_1">Do you have a recognized industry certification?<span class="asterisk">*</span></label>
        <select id="question_1"><option>Select...</option><option>Yes</option><option>No</option></select>
      </div>
      <div class="field">
        <label for="question_2">If yes, please list all recognized industry certifications</label>
        <textarea id="question_2"></textarea>
      </div>
      <div class="field">
        <label for="question_3">What level of security clearance do you have? (please note that this is not required for an internship)<span class="asterisk">*</span></label>
        <select id="question_3"><option>Select...</option><option>None</option></select>
      </div>
      <div class="field">
        <label for="question_4">Would you be able to attend our mandatory in-person onboarding from Jan 11-14 hosted at our Tampa, FL office (all travel/food/lodging costs will be covered)?<span class="asterisk">*</span></label>
        <select id="question_4"><option>Select...</option><option>Yes</option><option>No</option></select>
      </div>
      <div class="field">
        <label for="question_5">When are you available for full-time hire?<span class="asterisk">*</span></label>
        <select id="question_5"><option>Select...</option><option>Summer 2026</option></select>
      </div>
      <div class="field">
        <label for="question_6">Are you Hispanic/Latino?</label>
        <select id="question_6"><option>Select...</option><option>No</option><option>Yes</option></select>
      </div>
    </form>
    """

    async def fake_get(self, url: str, *args, **kwargs) -> httpx.Response:
        return httpx.Response(200, text=greenhouse_html, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    from backend.models.profile import Certification

    profile = CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin Lavric",
            location="Brasov, Romania",
        ),
        certifications=[
            Certification(name="Smart Contract Security", issuer="Cyfrin", date="May 2025"),
            Certification(name="Assembly and Formal Verification", issuer="Cyfrin", date="October 2025"),
        ],
    )

    scanner = ATSFormScanner()
    pack = await scanner.generate_application_pack(
        profile=profile,
        job_title="GPSU Cybersecurity Spring Internship",
        company="GuidePoint Security",
        job_description="Cybersecurity intern",
        job_url="https://boards.greenhouse.io/guidepointsecurity/jobs/123",
    )

    ans = {q.label: q.suggested_answer for q in pack.custom_questions}
    assert ans["Do you have a recognized industry certification?"] == "Yes"
    assert "Smart Contract Security" in ans["If yes, please list all recognized industry certifications"]
    assert (
        ans["What level of security clearance do you have? (please note that this is not required for an internship)"]
        == "None / Not Applicable"
    )
    assert (
        "in-person onboarding"
        in ans[
            "Would you be able to attend our mandatory in-person onboarding from Jan 11-14 hosted at our Tampa, FL office (all travel/food/lodging costs will be covered)?"
        ]
    )
    assert "Summer 2026" in ans["When are you available for full-time hire?"]
    assert ans["Are you Hispanic/Latino?"] == "No"


@pytest.mark.asyncio
async def test_fab2_ashby_text_form_parsing() -> None:
    """Verify smart text parsing and answering for client-rendered Ashby forms."""
    fab2_pasted_text = """
    Portfolio - website link
    Have you included a portfolio with your application?
    Tell us a bit about yourself and why you'd like to join fab2
    Ideal start date in office
    Ideal end date
    Are you currently authorized to work in the United States?
    Will you, at any point, require employer sponsorship to work in the United States?
    How did you hear about us?
    I am one of the following: (a) a citizen of the United States; (b) a lawful permanent resident of the United States; or (c) a person admitted into the United States as an asylee or refugee:
    If no, is your home country listed below? Armenia, Azerbaijan, Belarus, Burma, Cambodia, China, Cuba, Georgia, Iran, Iraq, Kazakhstan, North Korea, Kyrgyzstan, Laos, Libya, Macao, Moldova, Mongolia, Nicaragua, Russia, Syria, Tajikistan, Turkmenistan, Uzbekistan, Venezuela, Vietnam, Yemen
    """

    profile = CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin-Marian Lavric",
            location="Brasov, Romania (EET)",
            portfolio="https://github.com/cosminmarian53/security-audit-portofolio",
            github="https://github.com/cosminmarian53",
        ),
    )

    scanner = ATSFormScanner()
    pack = await scanner.generate_application_pack(
        profile=profile,
        job_title="Rust Software Engineering Intern, Chip Design Tools - Winter",
        company="fab2",
        job_description=fab2_pasted_text,
        job_url="",
    )

    ans = {q.label: q.suggested_answer for q in pack.custom_questions}
    assert ans["Portfolio - website link"] == "https://github.com/cosminmarian53/security-audit-portofolio"
    assert "Included link" in ans["Have you included a portfolio with your application?"]
    assert "January 2026" in ans["Ideal start date in office"]
    assert "April 2026" in ans["Ideal end date"]
    assert ans["Are you currently authorized to work in the United States?"] == "No"
    assert ans["Will you, at any point, require employer sponsorship to work in the United States?"] == "Yes"
    assert "LinkedIn" in ans["How did you hear about us?"]
    assert (
        "Romania"
        in ans[
            "If no, is your home country listed below? Armenia, Azerbaijan, Belarus, Burma, Cambodia, China, Cuba, Georgia, Iran, Iraq, Kazakhstan, North Korea, Kyrgyzstan, Laos, Libya, Macao, Moldova, Mongolia, Nicaragua, Russia, Syria, Tajikistan, Turkmenistan, Uzbekistan, Venezuela, Vietnam, Yemen"
        ]
    )


@pytest.mark.asyncio
async def test_universal_master_form_pack() -> None:
    """Verify comprehensive 17-question universal master form provides complete ready-to-copy content."""
    profile = CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin-Marian Lavric",
            location="Brasov, Romania (EET)",
            portfolio="https://github.com/cosminmarian53/security-audit-portofolio",
            github="https://github.com/cosminmarian53",
            linkedin="https://www.linkedin.com/in/cosmin-lavric-827126331/",
        ),
        education=[
            Education(
                institution="Transilvania University of Brasov",
                degree="Bachelor of Science in Electrical Engineering and Computer Science",
                year="2022 - 2026",
            )
        ],
        certifications=[
            Certification(name="Smart Contract Security", issuer="Cyfrin", date="May 2025"),
        ],
        experience=[
            Experience(
                company="IBM Summer School",
                title="Cybersecurity Analyst Internship",
                duration="July 2025",
                bullets=["Designed and deployed enterprise 2FA system."],
            )
        ],
        projects=[
            Project(
                name="X-Scout",
                tech="Python, Playwright",
                description="Architected automated threat-intelligence data pipeline processing 500+ daily data points.",
            )
        ],
    )

    scanner = ATSFormScanner()
    pack = await scanner.generate_application_pack(
        profile=profile,
        job_title="Software Engineering Intern",
        company="TechCorp",
        job_description="",
        job_url="",
    )

    assert len(pack.custom_questions) >= 15
    ans = {q.label: q.suggested_answer for q in pack.custom_questions}
    assert "TechCorp" in ans["Why are you interested in this role and company?"]
    assert "X-Scout" in ans["Describe a challenging technical project or bug you recently solved."]
    assert (
        ans["Portfolio / GitHub / Technical Project Link"]
        == "https://github.com/cosminmarian53/security-audit-portofolio"
    )
    assert ans["Are you currently authorized to work in the United States?"] == "No"
    assert ans["Will you now or in the future require visa sponsorship for employment?"] == "Yes"
    assert "Romania" in ans["If no, is your home country listed on the U.S. EAR restricted country list?"]
    assert "January 2026" in ans["Ideal start date in office / earliest availability"]
    assert "April 2026" in ans["Ideal end date / commitment duration"]
    assert "Summer 2026" in ans["When are you available for full-time hire / expected graduation date?"]
    assert (
        "Transilvania University of Brasov"
        in ans["What university/college are you currently attending and what degree are you pursuing?"]
    )
    assert (
        "Smart Contract Security" in ans["Do you have any recognized industry certifications or specialized training?"]
    )
    assert "IBM Summer School" in ans["Do you have prior internship or professional engineering experience?"]
    assert (
        "in-person onboarding"
        in ans["Would you be able to attend mandatory in-person onboarding or travel as required?"]
    )


@pytest.mark.asyncio
async def test_jamf_job_description_does_not_extract_jd_headers_as_questions() -> None:
    """Verify marketing headers (Must-have, Nice-to-have, Why Jamf?, What does Jamf do?) are filtered out."""
    jamf_posting_text = """
    Software Engineer II | AI & Agentic Systems
    Remote - US

    What does Jamf do?
    Jamf is the leader in managing and securing Apple at work.

    What it means to be a Jamf?
    At Jamf, we empower people to be their authentic selves.

    Why Jamf?
    We are growing rapidly and investing heavily in AI & Agentic Systems.

    Must-have
    - 2+ years of experience with Python or TypeScript
    - Experience building AI agents, LLM tool-calling, and automated workflows

    Nice-to-have
    - Experience with FastAPI, Docker, vector databases
    - Knowledge of macOS / Apple ecosystems
    """

    profile = CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin-Marian Lavric",
            location="Brasov, Romania (EET)",
            portfolio="https://github.com/cosminmarian53/security-audit-portofolio",
            github="https://github.com/cosminmarian53",
            linkedin="https://www.linkedin.com/in/cosmin-lavric-827126331/",
        ),
    )

    scanner = ATSFormScanner()
    pack = await scanner.generate_application_pack(
        profile=profile,
        job_title="Software Engineer II | AI & Agentic Systems",
        company="Jamf",
        job_description=jamf_posting_text,
        job_url="",
    )

    labels = [q.label for q in pack.custom_questions]
    assert "Must-have" not in labels
    assert "Nice-to-have" not in labels
    assert "What does Jamf do?" not in labels
    assert "What it means to be a Jamf?" not in labels
    assert "Why Jamf?" not in labels

    # Should fall back cleanly to the 17-question universal master form tailored for Jamf
    assert len(pack.custom_questions) >= 15
    ans = {q.label: q.suggested_answer for q in pack.custom_questions}
    assert "Jamf" in ans["Why are you interested in this role and company?"]


@pytest.mark.asyncio
async def test_ats_form_scanner_multi_tenancy_isolation() -> None:
    """Verify ATSFormScanner cleanly derives facts from an arbitrary candidate profile without data leakage."""
    berlin_candidate = CandidateProfile(
        personal_info=PersonalInfo(
            name="Alice Schmidt",
            email="alice@berlin-tech.de",
            location="Berlin, Germany",
            github="https://github.com/alice-schmidt",
        ),
        education=[
            Education(
                institution="Technical University of Berlin",
                degree="M.Sc. Computer Science",
                year="2023 - 2025",
                details="Distributed Systems & Formal Verification",
            )
        ],
        experience=[
            Experience(
                company="Siemens Healthineers",
                title="Systems Engineering Intern",
                duration="Mar 2024 - Sep 2024",
                bullets=["Built high-throughput telemetry pipelines in Go and Rust."],
            )
        ],
        projects=[
            Project(
                name="Rust-Raft",
                tech="Rust, Tokio",
                description="Implemented a consensus engine with deterministic chaos testing.",
            )
        ],
    )

    scanner = ATSFormScanner()
    pack = await scanner.generate_application_pack(
        profile=berlin_candidate,
        job_title="Backend Systems Engineer",
        company="Datadog",
        job_description="Distributed systems, telemetry, high concurrency.",
        job_url="",
    )

    # 1. Verify standard fields
    assert pack.standard_fields["Full Name"] == "Alice Schmidt"
    assert pack.standard_fields["Email"] == "alice@berlin-tech.de"
    assert pack.standard_fields["Current Location"] == "Berlin, Germany"
    assert pack.standard_fields["Current Company"] == "Siemens Healthineers"
    assert pack.standard_fields["GitHub / Portfolio"] == "https://github.com/alice-schmidt"

    # 2. Verify questions are dynamically grounded in Alice's profile
    ans_map = {q.label: q.suggested_answer for q in pack.custom_questions}
    assert (
        "Technical University of Berlin"
        in ans_map["What university/college are you currently attending and what degree are you pursuing?"]
    )
    assert "Siemens Healthineers" in ans_map["Do you have prior internship or professional engineering experience?"]
    assert "Rust-Raft" in ans_map["Describe a challenging technical project or bug you recently solved."]
    assert "Datadog" in ans_map["Why are you interested in this role and company?"]

    # 3. Assert strict multi-tenant isolation: NO hardcoded references to other profiles
    all_answers_text = " ".join(ans_map.values()) + " " + pack.cover_note
    assert "Transilvania" not in all_answers_text
    assert "Brasov" not in all_answers_text
    assert "Romania" not in all_answers_text
    assert "IBM Summer School" not in all_answers_text
    assert "X-Scout" not in all_answers_text
    assert "Cyfrin" not in all_answers_text
