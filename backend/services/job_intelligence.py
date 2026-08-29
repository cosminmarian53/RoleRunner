"""Service for deep AI job analysis, live web scraping, strategic framing, and interview process intelligence."""

from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from bs4 import BeautifulSoup

from backend.models.job import (
    InterviewQuestionGuide,
    JobIntelligenceRequest,
    JobIntelligenceResponse,
    StudyTopic,
)
from backend.models.profile import CandidateProfile
from backend.scrapers.http_client import SafeAsyncClient
from backend.services.ai_client import ask
from backend.services.job_scorer import extract_keywords_from_text

logger = logging.getLogger(__name__)

INTELLIGENCE_SYSTEM_PROMPT = """You are an elite technical career coach, executive recruiter, and hiring manager.
Analyze the target job opportunity (including live scraped details) against the candidate's master profile to generate a comprehensive, high-leverage application & interview preparation guide.

Output strictly formatted JSON matching this schema:
{
  "role_summary": "Concise 2-3 sentence overview of what the team actually needs and the core problems to solve.",
  "framing_strategy": "Strategic positioning plan: how the candidate should frame their background, flagship achievements to emphasize, and how to position their technical narrative.",
  "company_insights": "Analysis of the company's business model, engineering culture, priorities, and what they value in high-performing hires.",
  "interview_stages": [
    "1. Recruiter Screen (30m): Alignment on motivations, core skills, compensation, and trajectory.",
    "2. Technical / Coding Assessment (45-60m): Core domain problem solving and execution competence.",
    "3. Architecture & System Design Deep-Dive (60m): Tradeoffs, failure modes, scalability, and operational rigor.",
    "4. Behavioral & Cross-Team Culture Fit (45m): Teamwork, debugging mindset, communication, and ownership.",
    "5. Hiring Manager / Offer Sync: Team roadmap alignment and final expectations."
  ],
  "study_guide": [
    {
      "topic": "Core Technology / System Design Pattern",
      "key_concepts": "Key theoretical concepts, failure modes, concurrency/scalability patterns to review.",
      "practice_focus": "Specific practice exercise, LeetCode/System design problem type, or hands-on mini-project to build."
    }
  ],
  "improvement_suggestions": [
    "Actionable suggestion 1 to strengthen candidate positioning or bridge missing keywords",
    "Actionable suggestion 2 to showcase tangible proof-of-work (e.g. GitHub repos, benchmarks, metrics)",
    "Actionable suggestion 3 to sharpen domain storytelling during technical deep-dives"
  ],
  "how_to_land_role": [
    "Step 1 - Recruiter Screen: Exact pitch angle to pass initial screening with enthusiasm.",
    "Step 2 - Technical Rounds: How to structure coding & architecture answers using STAR with metrics.",
    "Step 3 - Behavioral Rounds: Key stories demonstrating high ownership, debugging velocity, and empathy.",
    "Step 4 - Reverse Interview: How to ask senior-level questions that position you as a top 1% candidate."
  ],
  "likely_interview_questions": [
    {
      "question": "Likely technical or domain-specific interview question for this role",
      "why_they_ask": "What the interview panel is specifically testing (e.g. concurrency, error handling, system limits).",
      "recommended_angle": "How the candidate should frame their answer using their specific experience and tools."
    }
  ],
  "talking_points": [
    "High-impact talk track 1 directly addressing a core job requirement",
    "High-impact talk track 2 demonstrating tangible scale or complexity handled",
    "High-impact talk track 3 demonstrating proactive problem-solving or domain leadership"
  ],
  "questions_to_ask": [
    "Strategic question 1 showing deep interest in roadmap and core challenges",
    "Strategic question 2 regarding team velocity and metrics for success in first 90 days",
    "Strategic question 3 exploring team vision and architecture autonomy"
  ],
  "key_technologies": ["Core Skill 1", "Core Skill 2", "Core Skill 3"],
  "culture_notes": "Key cultural markers to mirror (e.g. ownership, fast iteration, extreme customer focus, rigor)."
}
Output ONLY raw valid JSON with no markdown formatting or markdown backticks."""


class JobIntelligenceService:
    """Generates role strategic framing, live web-scraped company intelligence, and complete interview prep."""

    def __init__(self, user_id: UUID | str | None = None, client: SafeAsyncClient | None = None) -> None:
        self.user_id = UUID(str(user_id)) if user_id is not None else None
        self.client = client or SafeAsyncClient()

    async def scrape_job_page_content(self, url: str) -> str:
        """Fetch and extract clean readable text from live job posting URL."""
        if not url or not url.startswith("http"):
            return ""
        try:
            resp = await self.client.get(url)
            if resp.status_code == 200 and resp.text:
                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove noise elements
                for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                    tag.decompose()
                text = soup.get_text(separator="\n")
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                clean_text = "\n".join(lines)
                return clean_text[:12000]
        except Exception as exc:
            logger.debug("Failed to scrape live job posting content from %s: %s", url, exc)
        return ""

    async def generate_intelligence(
        self,
        request: JobIntelligenceRequest,
        profile: CandidateProfile,
    ) -> JobIntelligenceResponse:
        """Analyze job posting (with live web scraping) and candidate profile to construct actionable intelligence."""
        # 1. Live web scraping if URL is available and description is minimal
        scraped_text = ""
        if request.link and (not request.description or len(request.description.strip()) < 100):
            scraped_text = await self.scrape_job_page_content(request.link)
            if scraped_text:
                request.description = f"{request.description}\n\n[Live Scraped Web Content]:\n{scraped_text}".strip()

        try:
            res = await self._generate_with_ai(request, profile)
            if scraped_text:
                res.scraped_source = request.link
            return res
        except Exception as exc:
            logger.info("AI job intelligence fallback to dynamic heuristic analysis: %s", exc)
            res = self._generate_heuristic(request, profile)
            if scraped_text:
                res.scraped_source = request.link
            return res

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

        study_guide_raw = data.get("study_guide", [])
        study_guide = [
            StudyTopic(
                topic=item.get("topic", ""),
                key_concepts=item.get("key_concepts", ""),
                practice_focus=item.get("practice_focus", ""),
            )
            for item in study_guide_raw
            if isinstance(item, dict) and item.get("topic")
        ]

        interview_questions_raw = data.get("likely_interview_questions", [])
        likely_questions = [
            InterviewQuestionGuide(
                question=item.get("question", ""),
                why_they_ask=item.get("why_they_ask", ""),
                recommended_angle=item.get("recommended_angle", ""),
            )
            for item in interview_questions_raw
            if isinstance(item, dict) and item.get("question")
        ]

        return JobIntelligenceResponse(
            role_summary=data.get("role_summary", ""),
            framing_strategy=data.get("framing_strategy", ""),
            company_insights=data.get("company_insights", ""),
            interview_stages=data.get("interview_stages", []),
            study_guide=study_guide,
            improvement_suggestions=data.get("improvement_suggestions", []),
            how_to_land_role=data.get("how_to_land_role", []),
            likely_interview_questions=likely_questions,
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
            top_skills = ["Software Architecture", "Automated Testing", "Reliable Systems"]

        is_senior = any(
            w in title.lower() for w in ["senior", "lead", "staff", "principal", "head", "director", "manager"]
        )
        is_junior = any(w in title.lower() for w in ["intern", "junior", "associate", "entry", "graduate"])

        skills_str = ", ".join(top_skills[:3])
        primary_skill = top_skills[0] if top_skills else "Core Domain Architecture"
        secondary_skill = top_skills[1] if len(top_skills) > 1 else "Testing & Automation"

        if is_junior:
            interview_stages = [
                "1. Recruiter Screen (30 min): Foundational background, motivation, and career trajectory.",
                "2. Technical & Coding Assessment (45 min): Live data structures, clean code, and API fundamentals.",
                "3. Practical Project Deep-Dive (45 min): Project walkthrough, testing mindset, and problem solving.",
                "4. Department & Culture Chat (30 min): Growth mindset, collaboration, and feedback reception.",
                "5. Offer Discussion & Roadmap Sync: Team placement and onboarding expectations.",
            ]
            framing_strategy = (
                f"Position yourself as an agile, high-velocity contributor with strong fundamentals in {skills_str}. "
                f"Highlight end-to-end projects and quantifiable results to prove immediate execution readiness."
            )
            culture_notes = "Values high curiosity, fast feedback integration, reliability, and proactive ownership."
            study_guide = [
                StudyTopic(
                    topic=f"{primary_skill.title()} Fundamentals & Problem Solving",
                    key_concepts=f"Core syntax, memory & state management, async patterns, and error handling in {primary_skill}.",
                    practice_focus="Build or review a modular CLI/API service with full automated unit test coverage.",
                ),
                StudyTopic(
                    topic=f"{secondary_skill.title()} & Testing Automation",
                    key_concepts="Integration testing, mock contexts, retry mechanisms, and CI/CD pipelines.",
                    practice_focus="Practice writing deterministic end-to-end test scenarios without flakiness.",
                ),
                StudyTopic(
                    topic="Data Structures & Algorithmic Complexity",
                    key_concepts="Hash maps, trees/graphs, time/space complexity (Big-O), and binary search.",
                    practice_focus="Solve medium difficulty array and string traversal problems cleanly explaining tradeoffs.",
                ),
            ]
            improvement_suggestions = [
                f"Tailor your GitHub pinned repositories to prominently highlight end-to-end applications built with {primary_skill}.",
                "Add clear quantifiable metrics to your resume bullets (e.g. 'reduced flaky runs by 100%', 'processed 500+ daily events').",
                f"Prepare a 2-minute elevator pitch demonstrating your excitement specifically for {company}'s products.",
            ]
            how_to_land_role = [
                f"1. Recruiter Screen: Highlight your enthusiasm for {company} and emphasize your hands-on project velocity.",
                "2. Technical Assessment: Talk out loud before typing, test edge cases proactively, and write clean variable names.",
                "3. Project Deep-Dive: Use the STAR method (Situation, Task, Action, Result) focusing on your specific code contributions.",
                f"4. Closing: Ask thoughtful questions about {company}'s tech stack evolution and first-quarter expectations.",
            ]
            likely_questions = [
                InterviewQuestionGuide(
                    question=f"How do you design and test a reliable service using {primary_skill}?",
                    why_they_ask="Evaluates your understanding of modular code structure, error handling, and testing discipline.",
                    recommended_angle="Describe your project workflow: designing typed interfaces, mocking external APIs, and writing automated test suites.",
                ),
                InterviewQuestionGuide(
                    question="Tell me about a time a test failed in production or CI and how you debugged it.",
                    why_they_ask="Tests your root-cause analysis skills and calmness under technical ambiguity.",
                    recommended_angle="Discuss isolating the environment, replicating locally, adding logging, and introducing regression tests.",
                ),
            ]
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
            study_guide = [
                StudyTopic(
                    topic="Distributed Systems & Scalable Architecture",
                    key_concepts="Event-driven architecture, distributed caching, partition tolerance, and zero-downtime migrations.",
                    practice_focus="Design a high-throughput, fault-tolerant telemetry processing pipeline handling 100k req/sec.",
                ),
                StudyTopic(
                    topic="System Reliability & Failure Mitigation",
                    key_concepts="Circuit breakers, backpressure, rate limiting, distributed tracing, and chaos engineering.",
                    practice_focus="Walk through failure recovery strategies for degraded downstream microservices.",
                ),
            ]
            improvement_suggestions = [
                "Frame your achievements around business impact and architectural scaling rather than individual task execution.",
                f"Prepare concrete examples of technical tradeoffs made when selecting tools like {primary_skill} versus alternatives.",
            ]
            how_to_land_role = [
                f"1. Executive Screen: Speak to business outcomes, team velocity, and alignment with {company}'s strategic goals.",
                "2. System Design: Lead the whiteboard proactively, clarify ambiguities upfront, and quantify resource bottlenecks.",
                "3. Leadership Fit: Emphasize mentoring junior engineers, establishing code quality bars, and cross-team alignment.",
            ]
            likely_questions = [
                InterviewQuestionGuide(
                    question="How would you design a distributed orchestration pipeline to handle sudden traffic spikes?",
                    why_they_ask="Assesses architectural maturity, bottleneck identification, and queue management.",
                    recommended_angle="Propose an event-driven queue with horizontal worker autoscaling, dead-letter queues, and idempotency.",
                )
            ]
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
            study_guide = [
                StudyTopic(
                    topic=f"{primary_skill.title()} Production Patterns",
                    key_concepts="Concurrency, asynchronous I/O, database connection pooling, and resilient API design.",
                    practice_focus=f"Build a clean REST/GraphQL endpoint with rate-limiting, authentication, and structured logging in {primary_skill}.",
                ),
                StudyTopic(
                    topic="Automated Testing & CI/CD Pipelines",
                    key_concepts="Unit vs integration test boundaries, test containerization, and automated regression checks.",
                    practice_focus="Set up a GitHub Actions workflow with linting, security scanning, and automated test execution.",
                ),
            ]
            improvement_suggestions = [
                f"Review {company}'s public technical blog or open-source repositories to speak their architectural dialect.",
                "Highlight end-to-end ownership in your resume and portfolio projects.",
            ]
            how_to_land_role = [
                f"1. Screening: Communicate clearly why {company}'s mission and this specific team excite you.",
                "2. Technical Round: Focus on clean, readable code with explicit error handling rather than clever one-liners.",
                "3. Behavioral Round: Provide concise STAR examples highlighting technical ownership and peer collaboration.",
            ]
            likely_questions = [
                InterviewQuestionGuide(
                    question=f"What are the most common performance bottlenecks you encounter when working with {primary_skill}?",
                    why_they_ask="Validates real production experience beyond superficial syntax knowledge.",
                    recommended_angle="Mention I/O blocking, unindexed database queries, and memory overhead, along with profiling techniques.",
                )
            ]

        role_summary = (
            f"As a {title} at {company}, you will drive key engineering deliverables utilizing {skills_str} "
            f"to solve operational challenges, execute core features, and maintain high system reliability."
        )

        company_insights = (
            f"{company} is seeking an execution-focused {title} who can leverage {skills_str} "
            f"to deliver robust results while maintaining high quality, fast iteration velocity, and team excellence."
        )

        talking_points = [
            f"Hands-on expertise solving domain challenges and building reliable software architectures with {primary_skill}.",
            "Experience managing ambiguous requirements, prioritizing high-impact work, and delivering on tight schedules.",
            "Track record of improving workflows, eliminating test flakiness, and collaborating effectively across teams.",
        ]

        questions_to_ask = [
            "What does a successful first 90 days look like for this role, and what are the most critical milestones?",
            "What is the biggest operational or technical challenge the team is currently working to overcome?",
            "How does the team balance new feature development with technical debt reduction and refactoring?",
            "What does the deployment and continuous integration cadence look like for this team?",
        ]

        return JobIntelligenceResponse(
            role_summary=role_summary,
            framing_strategy=framing_strategy,
            company_insights=company_insights,
            interview_stages=interview_stages,
            study_guide=study_guide,
            improvement_suggestions=improvement_suggestions,
            how_to_land_role=how_to_land_role,
            likely_interview_questions=likely_questions,
            talking_points=talking_points,
            questions_to_ask=questions_to_ask,
            key_technologies=top_skills[:6],
            culture_notes=culture_notes,
        )
