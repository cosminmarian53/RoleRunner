"""Dynamic candidate profile keyword extraction and ATS relevance scoring engine."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from backend.models.cv import CVScoreResult
from backend.models.job import Recommendation
from backend.models.profile import CandidateProfile

logger = logging.getLogger(__name__)

STOP_WORDS: set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "had",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "that",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
    "you",
    "your",
    "our",
    "we",
    "this",
    "they",
    "them",
    "their",
    "about",
    "into",
    "more",
    "other",
    "some",
    "such",
    "than",
    "then",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "how",
    "what",
    "why",
    "all",
    "any",
    "both",
    "each",
    "few",
    "most",
    "only",
    "own",
    "same",
    "so",
    "too",
    "very",
    "can",
    "could",
    "would",
    "just",
    "should",
    "now",
    "across",
    "after",
    "before",
    "during",
    "while",
    "since",
    "until",
    "upon",
    "within",
    "without",
    "through",
    "throughout",
    "above",
    "below",
    "between",
    "under",
    "over",
    "around",
    "near",
    "against",
    "along",
    "ability",
    "able",
    "looking",
    "years",
    "experience",
    "experienced",
    "opportunity",
    "team",
    "teams",
    "teamers",
    "role",
    "roles",
    "position",
    "positions",
    "join",
    "joining",
    "help",
    "helping",
    "work",
    "working",
    "worked",
    "must",
    "plus",
    "required",
    "requirements",
    "responsible",
    "responsibilities",
    "qualifications",
    "benefits",
    "location",
    "remote",
    "hybrid",
    "onsite",
    "full-time",
    "part-time",
    "contract",
    "internship",
    "candidate",
    "candidates",
    "applicant",
    "applicants",
    "day",
    "days",
    "month",
    "months",
    "year",
    "yr",
    "skills",
    "skill",
    "skilled",
    "strong",
    "good",
    "great",
    "excellent",
    "proven",
    "understanding",
    "knowledge",
    "familiarity",
    "background",
    "passionate",
    "motivated",
    "detail-oriented",
    "self-starter",
    "fast-paced",
    "environment",
    "solutions",
    "collaborate",
    "collaborating",
    "cross-functional",
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "ensure",
    "ensuring",
    "including",
    "include",
    "includes",
    "using",
    "used",
    "use",
    "make",
    "making",
    "take",
    "taking",
    "need",
    "needs",
    "needed",
    "well",
    "also",
    "part",
    "etc",
    "e.g.",
    "eg",
    "i.e.",
    "ie",
    "overview",
    "summary",
    "description",
    "details",
    "level",
    "levels",
    "non",
    "per",
    "via",
    "re",
    "like",
    "new",
    "high",
    "wide",
    "deep",
    "top",
    "best",
    "first",
    "last",
    "agent",
    "agents",
    "guide",
    "builder",
    "application",
    "applications",
    "independent",
    "initiatives",
    "may",
    "out",
    "get",
    "getting",
    "give",
    "giving",
    "find",
    "finding",
    "see",
    "seeing",
    "look",
    "looking",
    "come",
    "go",
    "members",
    "keep",
    "show",
    "say",
    "tell",
    "lets",
    "let",
    "self",
    "rate",
    "rates",
    "pay",
    "salary",
    "compensation",
    "hr",
    "hour",
    "hourly",
    "competitive",
    "visit",
    "apply",
    "applying",
    "assess",
    "assessing",
    "leading",
    "track",
    "record",
    "various",
    "multiple",
    "complex",
    "deliver",
    "delivering",
    "drive",
    "driving",
    "maintain",
    "maintaining",
    "support",
    "supporting",
    "build",
    "building",
    "create",
    "creating",
    "develop",
    "developing",
    "development",
    "management",
    "manage",
    "managing",
    "lead",
    "leading",
    "leader",
    "leadership",
    "strategy",
    "strategic",
    "improve",
    "improving",
    "scale",
    "scaling",
    "learn",
    "learning",
    "culture",
    "values",
}

KNOWN_MULTI_WORD_SKILLS: list[str] = [
    "smart contracts",
    "smart contract",
    "threat modeling",
    "formal verification",
    "differential fuzzing",
    "fuzz testing",
    "vulnerability assessment",
    "security audit",
    "code review",
    "system design",
    "system architecture",
    "cloud architecture",
    "distributed systems",
    "ci/cd",
    "ci cd",
    "machine learning",
    "deep learning",
    "natural language processing",
    "data engineering",
    "data pipeline",
    "rest api",
    "graphql api",
    "front end",
    "frontend",
    "back end",
    "backend",
    "full stack",
    "product management",
    "project management",
    "agile scrum",
    "infrastructure as code",
    "test automation",
    "unit testing",
    "integration testing",
    "web development",
    "mobile development",
    "blockchain development",
    "penetration testing",
]

KNOWN_TECH_TOKENS: set[str] = {
    "solidity",
    "rust",
    "foundry",
    "slither",
    "echidna",
    "hardhat",
    "truffle",
    "python",
    "typescript",
    "javascript",
    "golang",
    "go",
    "java",
    "kotlin",
    "swift",
    "c++",
    "c#",
    ".net",
    "scala",
    "ruby",
    "rails",
    "php",
    "sql",
    "postgresql",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "cassandra",
    "kafka",
    "rabbitmq",
    "docker",
    "kubernetes",
    "k8s",
    "terraform",
    "ansible",
    "aws",
    "gcp",
    "azure",
    "react",
    "next.js",
    "nextjs",
    "vue",
    "angular",
    "node.js",
    "nodejs",
    "express",
    "fastapi",
    "django",
    "flask",
    "pytorch",
    "tensorflow",
    "pandas",
    "numpy",
    "scikit-learn",
    "figma",
    "jira",
    "git",
    "github",
    "gitlab",
    "linux",
    "graphql",
    "rest",
    "grpc",
    "evm",
    "defi",
    "web3",
    "circom",
    "halo2",
    "wagmi",
    "viem",
    "ethers.js",
    "web3.js",
    "tailwind",
    "css",
    "html",
}


def normalize_term(term: str) -> str:
    """Normalize skill or keyword term by stripping punctuation and lowercasing."""
    raw = term.strip().lower().strip("./-_ \t\n")
    cleaned = re.sub(r"[^\w\s+#./-]", "", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned.endswith("contracts"):
        cleaned = cleaned[:-1]
    return cleaned


def is_valid_skill_token(token: str) -> bool:
    """Validate that a token represents a legitimate skill or technical term, not a number, rate, or URL."""
    t = token.strip().lower().strip("./-_ ")
    if not t or len(t) < 2 or len(t) > 35:
        return False
    if t in KNOWN_TECH_TOKENS:
        return True
    if t in STOP_WORDS:
        return False
    # Rejects URL fragments, schemes, domain extensions, email addresses
    if t.startswith(("http", "www", "mailto", "href", "link", "click", "apply", "visit")):
        return False
    if re.search(r"\.(com|io|org|net|co|ai|team|app|dev|sh|so|ly|me)\b", t):
        return False
    # Rejects numbers, rates ($120/hr, 150+, 3-4, 100k, 2026), percentages
    if re.search(r"\d", t):
        return False
    # Rejects pure punctuation or non-alphanumeric noise
    if not re.search(r"[a-zA-Z]", t):
        return False
    return True


def extract_dynamic_profile_keywords(profile: CandidateProfile) -> tuple[set[str], set[str]]:
    """
    Extract dynamic target skills, domain concepts, tools, and title terms directly
    from the user's master candidate profile.

    Returns:
        (profile_keywords, profile_title_keywords)
    """
    profile_keywords: set[str] = set()
    title_keywords: set[str] = set()

    # 1. Explicit Skills from profile.skills dictionary
    for category, skill_list in profile.skills.items():
        cat_norm = normalize_term(category)
        if cat_norm and is_valid_skill_token(cat_norm) and len(cat_norm) > 2:
            profile_keywords.add(cat_norm)

        if isinstance(skill_list, list):
            for skill in skill_list:
                skill_str = str(skill).strip()
                if not skill_str:
                    continue
                # Add full multi-word skill phrase
                norm = normalize_term(skill_str)
                if norm and is_valid_skill_token(norm):
                    profile_keywords.add(norm)
                # If comma/slash separated inside string, add sub-parts
                if "/" in skill_str or "," in skill_str:
                    for sub in re.split(r"[/,]+", skill_str):
                        sub_norm = normalize_term(sub)
                        if sub_norm and is_valid_skill_token(sub_norm):
                            profile_keywords.add(sub_norm)

    # 2. Extract title tokens from personal_info or experience
    for exp in profile.experience:
        if exp.title:
            for token in re.findall(r"\b[A-Za-z0-9+#.-]{2,20}\b", exp.title):
                t_norm = normalize_term(token)
                if t_norm and is_valid_skill_token(t_norm) and len(t_norm) > 2:
                    title_keywords.add(t_norm)
                    profile_keywords.add(t_norm)

        # Experience bullet keywords
        for bullet in exp.bullets:
            for phrase in KNOWN_MULTI_WORD_SKILLS:
                if re.search(rf"(?:\b|\W){re.escape(phrase)}(?:\b|\W)", bullet.lower()):
                    profile_keywords.add(phrase)
            for tok in KNOWN_TECH_TOKENS:
                if re.search(rf"(?:\b|\W){re.escape(tok)}(?:\b|\W)", bullet.lower()):
                    profile_keywords.add(tok)

    # 3. Summary keywords
    if profile.summary:
        for phrase in KNOWN_MULTI_WORD_SKILLS:
            if re.search(rf"(?:\b|\W){re.escape(phrase)}(?:\b|\W)", profile.summary.lower()):
                profile_keywords.add(phrase)
        for tok in KNOWN_TECH_TOKENS:
            if re.search(rf"(?:\b|\W){re.escape(tok)}(?:\b|\W)", profile.summary.lower()):
                profile_keywords.add(tok)

    # 4. Projects tech
    for proj in profile.projects:
        if proj.tech:
            for t in re.split(r"[,/|]+", proj.tech):
                t_norm = normalize_term(t)
                if t_norm and is_valid_skill_token(t_norm):
                    profile_keywords.add(t_norm)

    # 5. Certifications
    for cert in profile.certifications:
        if cert.name:
            for token in re.findall(r"\b[A-Z0-9+#.-]{2,10}\b", cert.name):
                t_norm = normalize_term(token)
                if t_norm and is_valid_skill_token(t_norm):
                    profile_keywords.add(t_norm)

    # 6. Notable achievements
    for ach in profile.achievements:
        for phrase in KNOWN_MULTI_WORD_SKILLS:
            if re.search(rf"(?:\b|\W){re.escape(phrase)}(?:\b|\W)", ach.lower()):
                profile_keywords.add(phrase)
        for tok in KNOWN_TECH_TOKENS:
            if re.search(rf"(?:\b|\W){re.escape(tok)}(?:\b|\W)", ach.lower()):
                profile_keywords.add(tok)

    return profile_keywords, title_keywords


def extract_keywords_from_job(job_text: str, candidate_vocab: set[str] | None = None) -> set[str]:
    """
    Extract legitimate technical skills, domain phrases, tools, and frameworks from text.
    Excludes URLs, rates, numbers, and conversational filler words.
    """
    if not job_text:
        return set()

    job_text_lower = f" {job_text.lower()} "
    extracted: set[str] = set()

    # 1. Multi-word technical and professional skill phrases
    for phrase in KNOWN_MULTI_WORD_SKILLS:
        pattern = rf"(?:\b|\W){re.escape(phrase)}(?:\b|\W)"
        if re.search(pattern, job_text_lower):
            extracted.add(phrase)

    # 2. Known technical tokens & frameworks (e.g. Solidity, Foundry, React, K8s, AWS)
    for tok in KNOWN_TECH_TOKENS:
        pattern = rf"(?:\b|\W){re.escape(tok)}(?:\b|\W)"
        if re.search(pattern, job_text_lower):
            extracted.add(tok)

    # 3. If candidate profile vocabulary is provided, match those terms
    if candidate_vocab:
        for skill in candidate_vocab:
            if len(skill) >= 2 and is_valid_skill_token(skill):
                pattern = rf"(?:\b|\W){re.escape(skill.lower())}(?:\b|\W)"
                if re.search(pattern, job_text_lower):
                    extracted.add(skill.lower())

    # 4. Capitalized technical terms / acronyms (e.g. GraphQL, CI/CD, Slither, Halo2)
    raw_caps = re.findall(r"\b[A-Z][A-Za-z0-9+#.-]{1,20}\b", job_text)
    for cap in raw_caps:
        norm = cap.lower().strip("./-_ ")
        if is_valid_skill_token(norm) and len(norm) > 2:
            extracted.add(norm)

    # 5. Compound slashed technical terms (e.g. CI/CD, wagmi/viem)
    if "/" in job_text:
        for chunk in re.findall(r"[a-zA-Z0-9+#.-]+/[a-zA-Z0-9+#.-]+", job_text):
            norm_chunk = chunk.lower().strip("./-_ ")
            if is_valid_skill_token(norm_chunk):
                extracted.add(norm_chunk)
            for sub in chunk.split("/"):
                sub_norm = sub.lower().strip("./-_ ")
                if is_valid_skill_token(sub_norm):
                    extracted.add(sub_norm)

    return extracted


# For backwards compatibility with CV scoring
extract_keywords_from_text = extract_keywords_from_job


@dataclass
class JobMatchScore:
    """Detailed result of matching a job listing against candidate dynamic profile keywords."""

    score: float  # 0.0 to 10.0 scale
    matched_keywords: list[str]
    missing_keywords: list[str]
    recommendation: Recommendation


class JobScorer:
    """Scores candidate CVs and profile keywords against job listings dynamically."""

    @classmethod
    def score_cv_against_job(cls, cv_text: str, job_description: str) -> CVScoreResult:
        """
        Score CV text against job description by evaluating real domain skills & requirements.
        Produces clean, accurate matched & missing keywords with zero junk.
        """
        job_keywords = extract_keywords_from_job(job_description)
        cv_keywords = extract_keywords_from_job(cv_text)

        if not job_keywords:
            return CVScoreResult(
                overall_score=50,
                keyword_match_pct=0.0,
                matched_keywords=sorted(list(cv_keywords))[:10],
                missing_keywords=[],
                improvement_suggestions=["Target job description had minimal technical requirements."],
            )

        matched = sorted(list(job_keywords & cv_keywords))
        missing = sorted(list(job_keywords - cv_keywords))

        match_ratio = len(matched) / len(job_keywords) if job_keywords else 0.0
        keyword_pct = round(match_ratio * 100.0, 1)

        # Realistic calibrated ATS score (0 to 100)
        if len(matched) >= 6:
            overall = max(80, int(round(keyword_pct)))
        elif len(matched) >= 4:
            overall = max(70, int(round(keyword_pct)))
        elif len(matched) >= 2:
            overall = max(50, int(round(keyword_pct)))
        elif len(matched) == 1:
            overall = max(35, int(round(keyword_pct)))
        else:
            overall = int(round(keyword_pct))

        overall = max(0, min(100, overall))

        suggestions: list[str] = []
        if missing:
            top_missing = missing[:5]
            suggestions.append(f"Consider integrating these target keywords if applicable: {', '.join(top_missing)}.")

        if len(cv_text.split()) < 150:
            suggestions.append("CV appears short; expand on key project metrics and quantifiable achievements.")

        return CVScoreResult(
            overall_score=overall,
            keyword_match_pct=keyword_pct,
            matched_keywords=matched,
            missing_keywords=missing,
            improvement_suggestions=suggestions,
        )

    @classmethod
    def score_job_fast(
        cls,
        candidate_keywords: set[str],
        job_text: str,
        job_title: str = "",
        candidate_title_keywords: set[str] | None = None,
    ) -> JobMatchScore:
        """
        High-performance in-memory scoring on a 0.0 to 10.0 scale, driven dynamically
        by the user's specific candidate profile vocabulary for any profession.

        - If 0 candidate skills match: returns 0.0 (WEAK_MATCH).
        - If skills match: incorporates skill density and title alignment into 0.0 - 10.0 score.
        """
        if not candidate_keywords or not job_text:
            return JobMatchScore(
                score=0.0,
                matched_keywords=[],
                missing_keywords=[],
                recommendation=Recommendation.WEAK_MATCH,
            )

        job_text_lower = f" {job_text.lower()} "

        # 1. Match candidate dynamic skills directly against job text
        matched_skills: list[str] = []
        for skill in candidate_keywords:
            if len(skill) < 2:
                continue
            pattern = rf"(?:\b|\W){re.escape(skill)}(?:\b|\W)"
            if re.search(pattern, job_text_lower):
                matched_skills.append(skill)

        # Sort matched skills by length descending (prioritize multi-word phrases)
        matched_skills = sorted(list(set(matched_skills)), key=lambda s: len(s), reverse=True)

        # If zero candidate skills matched, job relevance is 0.0
        if not matched_skills:
            return JobMatchScore(
                score=0.0,
                matched_keywords=[],
                missing_keywords=[],
                recommendation=Recommendation.WEAK_MATCH,
            )

        # 2. Title Alignment Bonus
        title_bonus = 0.0
        title_lower = f" {job_title.lower()} " if job_title else ""
        if title_lower:
            check_title_vocab = candidate_title_keywords if candidate_title_keywords else candidate_keywords
            matched_title_terms = [
                t
                for t in check_title_vocab
                if len(t) > 2 and re.search(rf"(?:\b|\W){re.escape(t)}(?:\b|\W)", title_lower)
            ]
            if matched_title_terms:
                title_bonus = min(3.0, len(matched_title_terms) * 1.5)

        # 3. Calculate dynamic skill match score
        match_count = len(matched_skills)
        if match_count >= 5:
            base_score = 9.0
        elif match_count == 4:
            base_score = 8.0
        elif match_count == 3:
            base_score = 6.5
        elif match_count == 2:
            base_score = 5.0
        else:
            base_score = 3.5

        raw_score = base_score + title_bonus
        final_score = round(max(0.0, min(10.0, raw_score)), 1)

        if final_score >= 7.5:
            rec = Recommendation.STRONG_MATCH
        elif final_score >= 5.0:
            rec = Recommendation.GOOD_MATCH
        elif final_score >= 2.5:
            rec = Recommendation.PARTIAL_MATCH
        else:
            rec = Recommendation.WEAK_MATCH

        return JobMatchScore(
            score=final_score,
            matched_keywords=matched_skills[:8],
            missing_keywords=[],
            recommendation=rec,
        )
