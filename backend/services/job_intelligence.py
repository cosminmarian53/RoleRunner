"""Service for deep AI job analysis, strategic framing, and interview process intelligence."""

from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from backend.models.job import JobIntelligenceRequest, JobIntelligenceResponse
from backend.models.profile import CandidateProfile
from backend.services.ai_client import ask
from backend.services.job_scorer import extract_keywords_from_text

logger = logging.getLogger(__name__)

INTELLIGENCE_SYSTEM_PROMPT = """You are an elite career strategist, executive recruiter, and hiring manager.
Analyze the target job opportunity against the candidate's master profile to generate high-leverage application and interview intelligence.

Output strictly formatted JSON matching this schema:
{
  "role_summary": "Concise 2-3 sentence overview of what the team actually needs and the core problems to solve.",
  "framing_strategy": "Strategic positioning plan: how the candidate should frame their background, which 2-3 flagship achievements to emphasize, and how to position any career transitions.",
  "company_insights": "Analysis of the company's business model, team culture, priorities, and what they value in high-performing hires.",
  "interview_stages": [
    "1. Recruiter Screen (30m): Alignment on motivations, compensation, and high-level trajectory.",
    "2. Technical / Domain Screening (45-60m): Core domain problem solving and execution competence.",
    "3. Onsite / Case Study Deep-Dive (60-90m): Real-world project deep-dive and operational tradeoffs.",
    "4. Behavioral & Culture Fit (45m): Team leadership, conflict resolution, and execution velocity.",
    "5. Final Executive / Offer Sync: Alignment on role scope and team roadmap."
  ],
  "talking_points": [
    "High-impact talk track 1 directly addressing a core job requirement",
    "High-impact talk track 2 demonstrating tangible scale or complexity handled",
    "High-impact talk track 3 demonstrating proactive problem-solving or domain leadership"
  ],
  "questions_to_ask": [
    "Strategic question 1 showing deep interest in roadmap and core challenges",
    "Strategic question 2 regarding team velocity, metrics for success in first 90 days",
    "Strategic question 3 exploring team vision and autonomy"
  ],
  "key_technologies": ["Core Skill 1", "Core Skill 2", "Core Skill 3"],
  "culture_notes": "Key cultural markers to mirror (e.g. ownership, fast iteration, extreme customer focus, rigor)."
}
Output ONLY raw valid JSON with no markdown formatting or markdown backticks."""


class JobIntelligenceService:
    """Generates role strategic framing, company intelligence, and interview prep."""

    def __init__(self, user_id: UUID | str | None = None) -> None:
        self.user_id = UUID(str(user_id)) if user_id is not None else None

    async def generate_intelligence(
        self,
        request: JobIntelligenceRequest,
        profile: CandidateProfile,
    ) -> JobIntelligenceResponse:
        """Analyze job posting and candidate profile to construct actionable intelligence."""
        try:
            return await self._generate_with_ai(request, profile)
        except Exception as exc:
            logger.info("AI job intelligence fallback to dynamic heuristic analysis: %s", exc)
            return self._generate_heuristic(request, profile)

    async def _generate_with_ai(
        self,
        request: JobIntelligenceRequest,
        profile: CandidateProfile,
    ) -> JobIntelligenceResponse:
        """Call AI provider to construct tailored strategic report."""
        skills_summary = ", ".join([f"{k}: {', '.join(v)}" for k, v in profile.skills.items()])
        experience_summary = "\n".join(
            [f"- {exp.title} at {exp.company}: {'; '.join(exp.bullets[:2])}" for exp in profile.experience[:3]]
        )

        candidate_summary = f"""
Candidate Name: {profile.personal_info.name}
Summary: {profile.summary}
Skills: {skills_summary}
Recent Experience:
{experience_summary}
""".strip()

        job_text = f"""
Target Job Title: {request.job_title}
Company: {request.company or "Not specified"}
URL: {request.link}
Job Summary: {request.summary}
Job Description:
{request.description[:8000]}
""".strip()

        prompt = f"Candidate Profile:\n{candidate_summary}\n\nTarget Opportunity:\n{job_text}"

        raw_output = await ask(
            prompt,
            user_id=self.user_id,
            system_prompt=INTELLIGENCE_SYSTEM_PROMPT,
        )

        # Parse JSON output
        clean_json = re.sub(r"^```(?:json)?\s*", "", raw_output.strip())
        clean_json = re.sub(r"\s*```$", "", clean_json).strip()
        data = json.loads(clean_json)

        return JobIntelligenceResponse(
            role_summary=data.get("role_summary", ""),
            framing_strategy=data.get("framing_strategy", ""),
            company_insights=data.get("company_insights", ""),
            interview_stages=data.get("interview_stages", []),
            talking_points=data.get("talking_points", []),
            questions_to_ask=data.get("questions_to_ask", []),
            key_technologies=data.get("key_technologies", []),
            culture_notes=data.get("culture_notes", ""),
        )

    def _generate_heuristic(
        self,
        request: JobIntelligenceRequest,
        profile: CandidateProfile,
    ) -> JobIntelligenceResponse:
        """Deterministic heuristic synthesizer for instant or offline analysis across all career domains."""
        title = request.job_title.strip() or "Target Role"
        company = request.company.strip() or "the organization"
        full_text = f"{title} {request.summary} {request.description}".strip()

        # Extract dynamic keywords from job description
        job_keywords = extract_keywords_from_text(full_text)
        top_skills = list(job_keywords)[:8]
        if not top_skills:
            top_skills = ["Core Domain Expertise", "Cross-functional Execution", "Strategic Problem Solving"]

        is_senior = any(
            w in title.lower() for w in ["senior", "lead", "staff", "principal", "head", "director", "manager"]
        )
        is_junior = any(w in title.lower() for w in ["intern", "junior", "associate", "entry", "graduate"])

        skills_str = ", ".join(top_skills[:3])

        if is_junior:
            interview_stages = [
                "1. Recruiter Screen (30 min): Foundational background, motivation, and career trajectory.",
                "2. Skills & Domain Assessment: Practical domain case study or take-home evaluation.",
                "3. Team Peer Deep-Dive (45 min): Project walkthrough, collaboration style, and problem solving.",
                "4. Department & Culture Chat (30 min): Growth mindset, mentorship fit, and communication.",
                "5. Offer Discussion & Roadmap Sync: Team placement and onboarding expectations.",
            ]
            framing_strategy = (
                f"Position yourself as an agile, high-velocity contributor with strong fundamentals in {skills_str}. "
                f"Highlight end-to-end projects and quantifiable results to prove immediate execution readiness."
            )
            culture_notes = "Values high curiosity, fast feedback integration, reliability, and proactive ownership."
        elif is_senior:
            interview_stages = [
                "1. Recruiter & Hiring Executive Screen (30-45 min): Leadership scope, strategic impact, and compensation.",
                "2. Architecture / Operational Strategy Deep-Dive (60 min): Scalability, risk tradeoffs, and team execution.",
                "3. Domain Deep-Dive & Peer Panel (60 min): Real-world case study solving and past flagship outcomes.",
                "4. Cross-Functional Collaboration & Stakeholder Fit (45 min): Stakeholder management and team enablement.",
                "5. Executive Leadership Final: Long-term organizational vision, team culture, and offer finalization.",
            ]
            framing_strategy = (
                f"Anchor your background around executive ownership, systemic improvements, and business outcomes. "
                f"Emphasize flagship initiatives delivered with {skills_str} and how you level up overall team standards."
            )
            culture_notes = (
                "Demands high autonomy, strategic vision, operational rigor, and cross-functional leadership."
            )
        else:
            interview_stages = [
                "1. Initial Recruiter Sync (30 min): Career narrative, core skill alignment, and mutual fit.",
                "2. Domain / Technical Screen (45-60 min): Hands-on problem solving and domain fundamentals.",
                "3. Practical Project Deep-Dive (60 min): In-depth review of past production deliverables and methodologies.",
                "4. Cross-Team Culture & Behavioral Interview (45 min): Teamwork, debugging mindset, and communication.",
                "5. Offer & Team Welcome: Role expectations and start timeline.",
            ]
            framing_strategy = (
                f"Highlight direct experience delivering measurable outcomes with {skills_str}. "
                f"Emphasize reliable execution, cross-functional clarity, and proactive problem solving."
            )
            culture_notes = "Focuses on delivery velocity, collaborative problem-solving, and continuous improvement."

        role_summary = (
            f"As a {title} at {company}, you will drive key initiatives utilizing {skills_str} "
            f"to solve operational challenges, execute core deliverables, and achieve team milestones."
        )

        company_insights = (
            f"{company} is looking for a high-performing {title} who can immediately leverage {skills_str} "
            f"to deliver robust results while maintaining high quality and operational excellence."
        )

        talking_points = [
            f"Hands-on expertise solving domain challenges and delivering projects using {top_skills[0] if top_skills else 'core industry tools'}.",
            "Experience managing ambiguous requirements, prioritizing high-impact work, and delivering on tight schedules.",
            "Track record of improving workflows, upholding quality standards, and collaborating with cross-functional peers.",
        ]

        questions_to_ask = [
            "What does a successful first 90 days look like for this role, and what are the most critical milestones?",
            "What is the biggest operational or technical challenge the team is currently working to overcome?",
            "How does the team prioritize new initiatives against existing maintenance and optimization?",
            "How is success measured and rewarded within the organization?",
        ]

        return JobIntelligenceResponse(
            role_summary=role_summary,
            framing_strategy=framing_strategy,
            company_insights=company_insights,
            interview_stages=interview_stages,
            talking_points=talking_points,
            questions_to_ask=questions_to_ask,
            key_technologies=top_skills[:6],
            culture_notes=culture_notes,
        )
