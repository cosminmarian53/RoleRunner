"""Service for deep AI job analysis, strategic framing, and interview process intelligence."""

from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from backend.models.job import JobIntelligenceRequest, JobIntelligenceResponse
from backend.models.profile import CandidateProfile
from backend.services.ai_client import ask

logger = logging.getLogger(__name__)

INTELLIGENCE_SYSTEM_PROMPT = """You are an elite career strategist, executive recruiter, and tech hiring manager.
Analyze the target job opportunity against the candidate's master profile to generate high-leverage application and interview intelligence.

Output strictly formatted JSON matching this schema:
{
  "role_summary": "Concise 2-3 sentence overview of what the team actually needs and the core problems to solve.",
  "framing_strategy": "Strategic positioning plan: how the candidate should frame their background, which 2-3 flagship achievements to emphasize, and how to position any career transitions.",
  "company_insights": "Analysis of the company's business model, engineering culture, likely tech stack priorities, and what they value in high-performing hires.",
  "interview_stages": [
    "1. Recruiter Screen (30m): Alignment on motivations, compensation, and high-level trajectory.",
    "2. Technical Screening / Live Coding (45-60m): Core domain problem solving & architecture.",
    "3. Onsite / System Design Deep-Dive (60-90m): Real-world project deep-dive and scalability tradeoffs.",
    "4. Behavioral & Culture Fit (45m): Team leadership, conflict resolution, and execution velocity.",
    "5. Final Executive / Offer Sync: Alignment on role scope and team roadmap."
  ],
  "talking_points": [
    "High-impact talk track 1 directly addressing a core job requirement",
    "High-impact talk track 2 demonstrating tangible scale or complexity handled",
    "High-impact talk track 3 demonstrating proactive problem-solving or domain leadership"
  ],
  "questions_to_ask": [
    "Strategic question 1 showing deep interest in engineering roadmap and architecture challenges",
    "Strategic question 2 regarding team velocity, metrics for success in first 90 days",
    "Strategic question 3 exploring product vision and developer autonomy"
  ],
  "key_technologies": ["Tech 1", "Tech 2", "Tech 3"],
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
        # 1. Try AI extraction
        try:
            return await self._generate_with_ai(request, profile)
        except Exception as exc:
            logger.info("AI job intelligence fallback to heuristic analysis: %s", exc)
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
        """Deterministic heuristic synthesizer for instant or offline analysis."""
        title = request.job_title.strip()
        company = request.company.strip() or "the organization"
        desc = f"{request.summary} {request.description}".lower()

        # Extract technologies mentioned
        common_tech = [
            "Python",
            "React",
            "TypeScript",
            "JavaScript",
            "FastAPI",
            "Django",
            "Node.js",
            "Next.js",
            "Docker",
            "Kubernetes",
            "AWS",
            "PostgreSQL",
            "Solidity",
            "Rust",
            "Go",
            "GraphQL",
            "Redis",
            "CI/CD",
            "TailwindCSS",
            "Playwright",
        ]
        matched_tech = [t for t in common_tech if t.lower() in desc]
        if not matched_tech:
            matched_tech = ["Core Software Engineering", "System Architecture", "Modern Web Technologies"]

        # Infer role level
        is_intern = "intern" in title.lower() or "internship" in title.lower()
        is_senior = any(w in title.lower() for w in ["senior", "lead", "staff", "principal", "head"])

        if is_intern:
            interview_stages = [
                "1. Recruiter Screen (30 min): Educational background, graduation timeline, and foundational motivation.",
                "2. Technical Assessment / Take-home: Data structures, algorithm basics, or small project implementation.",
                "3. Technical Deep-Dive Interview: Code review of assessment, problem solving, and project walkthrough.",
                "4. Team & Mentor Match Chat: Collaboration style, curiosity, and learning velocity.",
                "5. Offer & Program Alignment: Internship dates, mentorship plan, and formal offer.",
            ]
            framing_strategy = (
                f"Position yourself as a rapid, proactive learner with strong foundations in {', '.join(matched_tech[:3])}. "
                f"Highlight end-to-end shipped projects from your portfolio to prove you can ramp up quickly and contribute immediately."
            )
            culture_notes = (
                "Values high curiosity, eagerness to learn, clean communication, and rapid feedback adoption."
            )
        elif is_senior:
            interview_stages = [
                "1. Recruiter & Hiring Manager Sync (30-45 min): Leadership scope, architectural impact, and compensation.",
                "2. System Design & Distributed Architecture (60 min): Real-world scalability, tradeoffs, and failure modes.",
                "3. Hands-on Technical Deep-Dive (60 min): Live system modeling or code pairing with senior peers.",
                "4. Cross-Functional Collaboration & Product Fit (45 min): Working with product managers and stakeholders.",
                "5. Executive Leadership Final (30 min): Strategic direction, engineering values, and offer negotiation.",
            ]
            framing_strategy = (
                f"Frame your background around ownership, architecture tradeoffs, and business outcomes. "
                f"Anchor discussions on systems you designed with {', '.join(matched_tech[:3])} and how you leveled up team engineering quality."
            )
            culture_notes = "Demands high ownership, technical autonomy, architectural rigor, and velocity."
        else:
            interview_stages = [
                "1. Initial Recruiter Call (30 min): Career story, core skill alignment, and mutual fit.",
                "2. Technical Screen / Coding Session (45-60 min): Practical domain coding and architecture fundamentals.",
                "3. Project Deep-Dive & Peer Pairing (60 min): Walkthrough of past production work and problem solving.",
                "4. Engineering Culture & Behavioral Fit (45 min): Teamwork, debugging mindset, and communication.",
                "5. Offer & Team Welcome: Role expectations and start timeline.",
            ]
            framing_strategy = (
                f"Highlight direct experience shipping production features with {', '.join(matched_tech[:3])}. "
                f"Emphasize reliable full-stack execution, clear communication, and test-driven development."
            )
            culture_notes = "Focuses on delivery velocity, collaborative problem-solving, and clean maintainable code."

        role_summary = (
            f"As a {title} at {company}, you will collaborate on core product development, "
            f"leveraging {', '.join(matched_tech[:4])} to design, implement, and maintain reliable software solutions."
        )

        company_insights = (
            f"{company} is actively scaling their engineering capabilities for this role. "
            f"They seek engineers who combine hands-on technical proficiency in {', '.join(matched_tech[:3])} "
            f"with strong problem-solving independence and high code quality."
        )

        talking_points = [
            f"Proven hands-on experience building and deploying scalable features using {matched_tech[0] if matched_tech else 'modern stacks'}.",
            "Experience navigating ambiguous requirements and taking features from conception to production.",
            "Strong track record of automated testing, maintainable design patterns, and cross-functional collaboration.",
        ]

        questions_to_ask = [
            "What does a successful first 90 days look like for this role, and what are the most critical milestones?",
            "How is the engineering team structured, and what is your deployment velocity and CI/CD workflow?",
            "What is the biggest technical or architectural challenge the team is currently solving?",
            "How does the team balance shipping new features with reducing technical debt?",
        ]

        return JobIntelligenceResponse(
            role_summary=role_summary,
            framing_strategy=framing_strategy,
            company_insights=company_insights,
            interview_stages=interview_stages,
            talking_points=talking_points,
            questions_to_ask=questions_to_ask,
            key_technologies=matched_tech[:6],
            culture_notes=culture_notes,
        )
