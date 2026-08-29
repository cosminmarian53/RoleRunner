"""Integration and heuristic test suite for the 6-stage Strategic Job Intelligence service."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.models.job import JobIntelligenceRequest
from backend.models.profile import CandidateProfile, PersonalInfo
from backend.services.job_intelligence import JobIntelligenceService


@pytest.mark.asyncio
async def test_job_intelligence_heuristic_fallback_multi_domain() -> None:
    """Verify heuristic strategy generation produces complete 6-section breakdowns for diverse domains."""
    user_id = uuid4()
    service = JobIntelligenceService(user_id=user_id)
    profile = CandidateProfile(
        personal_info=PersonalInfo(name="Alex Candidate"),
        summary="Experienced professional",
        skills={"Engineering": ["Python", "Kubernetes", "Telemetry", "SEO"]},
    )

    test_scenarios = [
        {
            "role": "Staff Platform Engineer",
            "company": "Datadog",
            "desc": "Seeking a Staff Engineer to lead our Kubernetes and Golang distributed tracing infrastructure with high reliability.",
            "tech": "Kubernetes",
        },
        {
            "role": "Registered ICU Nurse",
            "company": "St. Jude Hospital",
            "desc": "Critical care nurse needed for intensive care unit. Patient telemetry, IV administration, and rapid response team collaboration.",
            "tech": "Telemetry",
        },
        {
            "role": "Director of Growth Marketing",
            "company": "FintechHub",
            "desc": "Lead performance marketing, paid acquisition, SEO strategy, and conversion rate optimization across multi-channel campaigns.",
            "tech": "SEO",
        },
    ]

    for sc in test_scenarios:
        req = JobIntelligenceRequest(
            job_title=sc["role"],
            company=sc["company"],
            description=sc["desc"],
        )
        res = await service.generate_intelligence(req, profile)

        # 1. Strategic Framing
        assert len(res.framing_strategy) > 15
        assert len(res.company_insights) > 0
        assert sc["company"].lower() in res.company_insights.lower()

        # 2. Culture Signals
        assert len(res.culture_notes) > 0

        # 3. Interview Pipeline
        assert len(res.interview_stages) >= 3

        # 4. Talking Points
        assert len(res.talking_points) >= 2

        # 5. Strategic Questions to Ask
        assert len(res.questions_to_ask) >= 2

        # 6. Core Domain Tech
        assert len(res.key_technologies) >= 1

        # 7. Study Guide & Technical Prep
        assert len(res.study_guide) >= 1
        assert len(res.study_guide[0].topic) > 3

        # 8. Improvement Suggestions & How to Land Role
        assert len(res.improvement_suggestions) >= 1
        assert len(res.how_to_land_role) >= 1
        assert len(res.likely_interview_questions) >= 1


@pytest.mark.asyncio
async def test_job_intelligence_ai_structured_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify AI-assisted structured generation properly cleans markdown and returns complete schema."""
    user_id = uuid4()
    service = JobIntelligenceService(user_id=user_id)
    profile = CandidateProfile(
        personal_info=PersonalInfo(name="Cosmin Lavric"),
        summary="Security researcher",
        skills={"Security": ["Foundry", "Slither", "Solidity", "Rust", "Echidna"]},
    )

    mock_ai_json = """```json
{
  "role_summary": "Lead smart contract security assessments for top DeFi codebases.",
  "framing_strategy": "Position yourself as an offensive security expert with verifiable bug bounty findings.",
  "company_insights": "CertiK emphasizes deep protocol invariants and formal verification.",
  "interview_stages": [
    "Initial Recruiter Screen",
    "Smart Contract Audit Practical",
    "Partner Technical Discussion"
  ],
  "study_guide": [
    {
      "topic": "Solidity Invariant Testing & Formal Verification",
      "key_concepts": "Stateful fuzzing, Certora verification, ERC-4626 inflation vectors.",
      "practice_focus": "Write Echidna stateful invariant tests for a reentrancy-vulnerable vault."
    }
  ],
  "improvement_suggestions": [
    "Highlight your 3rd place finish in the Kuru Contracts audit.",
    "Add link to your public security audit portfolio."
  ],
  "how_to_land_role": [
    "1. Recruiter Screen: Focus on bounty results and proactive invariant modeling.",
    "2. Technical Audit: Walk through root-cause analysis of your recent findings."
  ],
  "likely_interview_questions": [
    {
      "question": "How do you systematically identify precision loss vulnerabilities in DeFi yield vaults?",
      "why_they_ask": "Evaluates numerical analysis and arithmetic truncation understanding.",
      "recommended_angle": "Explain checking rounding directions in division operations before multiplications."
    }
  ],
  "talking_points": [
    "Highlight your 3rd place finish in the Kuru Contracts audit.",
    "Discuss your automated fuzzing framework AegisGuard."
  ],
  "questions_to_ask": [
    "How does the audit team handle multi-auditor consensus on finding severity?",
    "What tooling integrations are prioritized in your internal pipeline?"
  ],
  "key_technologies": [
    "Foundry", "Slither", "Solidity", "Rust", "Echidna"
  ],
  "culture_notes": "Heavy emphasis on peer code review and proof of concepts."
}
```"""

    async def mock_ask(prompt: str, *args, **kwargs) -> str:
        return mock_ai_json

    monkeypatch.setattr("backend.services.job_intelligence.ask", mock_ask)

    req = JobIntelligenceRequest(
        job_title="Lead Smart Contract Auditor",
        company="CertiK",
        description="Seeking a seasoned auditor to lead complex EVM security engagements.",
    )
    res = await service.generate_intelligence(req, profile)

    assert "verifiable bug bounty findings" in res.framing_strategy
    assert len(res.interview_stages) == 3
    assert "Smart Contract Audit Practical" in res.interview_stages[1]
    assert len(res.study_guide) == 1
    assert "Invariant Testing" in res.study_guide[0].topic
    assert len(res.improvement_suggestions) == 2
    assert len(res.how_to_land_role) == 2
    assert len(res.likely_interview_questions) == 1
    assert "precision loss" in res.likely_interview_questions[0].question
    assert len(res.talking_points) == 2
    assert len(res.questions_to_ask) == 2
    assert "Foundry" in res.key_technologies


@pytest.mark.asyncio
async def test_job_intelligence_scrapes_live_job_link(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify live job posting URL is automatically scraped when description is minimal."""
    import httpx

    from backend.scrapers.http_client import SafeAsyncClient

    fake_html = """
    <html>
      <body>
        <main>
          <h1>Software Engineer II - AI Agentic Systems</h1>
          <p>Jamf is hiring a Software Engineer to architect LLM tool-calling agentic pipelines.</p>
        </main>
      </body>
    </html>
    """

    async def fake_get(self, url: str, *args, **kwargs) -> httpx.Response:
        return httpx.Response(200, text=fake_html, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    service = JobIntelligenceService()
    profile = CandidateProfile(
        personal_info=PersonalInfo(name="Cosmin Lavric"),
        skills={"Core": ["Python", "FastAPI", "Docker"]},
    )

    req = JobIntelligenceRequest(
        job_title="Software Engineer II",
        company="Jamf",
        description="",  # Empty description to trigger web scraping
        link="https://jamf.com/careers/ai-eng",
    )

    res = await service.generate_intelligence(req, profile)
    assert res.scraped_source == "https://jamf.com/careers/ai-eng"
    assert len(res.study_guide) >= 1
    assert len(res.how_to_land_role) >= 1
