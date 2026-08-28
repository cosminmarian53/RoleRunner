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
