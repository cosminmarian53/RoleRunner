"""Unit tests for ATS form scanner and application pack auto-filler."""

from __future__ import annotations

import httpx
import pytest

from backend.models.profile import CandidateProfile, PersonalInfo
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
    assert "visa sponsorship" in ans_map["Are you legally authorized to work in the United States?"].lower()
    assert (
        "visa sponsorship"
        in ans_map["Will you now or in the future require an employment visa to work in the US?"].lower()
    )
    assert (
        "25–29 hrs/week"
        in ans_map[
            "This is not a self-paced training program. Are you able to work 25-29 hrs/wk with a majority of hours being between 11am-4pm eastern Monday - Friday from January 11 - April 2, 2027?"
        ]
    )
