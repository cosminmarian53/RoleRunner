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
    "just",
    "should",
    "now",
    "looking",
    "years",
    "experience",
    "opportunity",
    "team",
    "role",
    "position",
    "join",
    "help",
    "work",
    "working",
    "able",
    "must",
    "plus",
    "required",
    "responsible",
    "responsibilities",
    "qualifications",
    "requirements",
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
    "skills",
    "skill",
    "skilled",
}


def normalize_term(term: str) -> str:
    """Normalize skill or keyword term by stripping punctuation and lowercasing."""
    cleaned = re.sub(r"[^\w\s+#./-]", "", term.strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Singularize common plural endings for single-word skills (e.g. contracts -> contract)
    if cleaned.endswith("contracts"):
        cleaned = cleaned[:-1]
    return cleaned


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
        if cat_norm and cat_norm not in STOP_WORDS and len(cat_norm) > 2:
            profile_keywords.add(cat_norm)

        if isinstance(skill_list, list):
            for skill in skill_list:
                skill_str = str(skill).strip()
                if not skill_str:
                    continue
                # Add full multi-word skill phrase
                norm = normalize_term(skill_str)
                if norm and norm not in STOP_WORDS and len(norm) > 1:
                    profile_keywords.add(norm)
                # If comma/slash separated inside string, add sub-parts
                for sub in re.split(r"[,/|•]+", skill_str):
                    sub_norm = normalize_term(sub)
                    if sub_norm and sub_norm not in STOP_WORDS and len(sub_norm) > 1:
                        profile_keywords.add(sub_norm)

    # 2. Professional Summary & Title / Headline
    if profile.summary:
        # Extract title/headline words from first sentence/line of summary
        first_line = profile.summary.split("\n")[0]
        for token in re.findall(r"\b[A-Za-z0-9+#.-]{3,}\b", first_line):
            t_norm = normalize_term(token)
            if t_norm and t_norm not in STOP_WORDS:
                title_keywords.add(t_norm)
                profile_keywords.add(t_norm)

        # Extract 2-word and 3-word phrases from summary (e.g. "smart contract", "penetration testing")
        words = re.findall(r"\b[A-Za-z0-9+#.-]+\b", profile.summary)
        for i in range(len(words) - 1):
            two_gram = normalize_term(f"{words[i]} {words[i+1]}")
            if two_gram and not any(w.lower() in STOP_WORDS for w in words[i : i + 2]):
                profile_keywords.add(two_gram)

    # 3. Work Experience entries (Titles, Companies, Bullet points)
    for exp in profile.experience:
        if exp.title:
            for token in re.findall(r"\b[A-Za-z0-9+#.-]{3,}\b", exp.title):
                t_norm = normalize_term(token)
                if t_norm and t_norm not in STOP_WORDS:
                    title_keywords.add(t_norm)
                    profile_keywords.add(t_norm)
        if exp.company:
            comp_norm = normalize_term(exp.company)
            if comp_norm and comp_norm not in STOP_WORDS:
                profile_keywords.add(comp_norm)

        for bullet in exp.bullets:
            # Match technical tokens and acronyms
            for token in re.findall(r"\b[A-Z][A-Za-z0-9+#.-]{1,15}\b", bullet):
                tok_norm = normalize_term(token)
                if tok_norm and tok_norm not in STOP_WORDS and len(tok_norm) > 1:
                    profile_keywords.add(tok_norm)

    # 4. Notable Projects (Tech stack, names, descriptions)
    for proj in profile.projects:
        if proj.tech:
            for tech in re.split(r"[,/|•]+", proj.tech):
                t_norm = normalize_term(tech)
                if t_norm and t_norm not in STOP_WORDS and len(t_norm) > 1:
                    profile_keywords.add(t_norm)
        if proj.name:
            p_norm = normalize_term(proj.name)
            if p_norm and p_norm not in STOP_WORDS:
                profile_keywords.add(p_norm)

    # 5. Certifications
    for cert in profile.certifications:
        if cert.name:
            for token in re.findall(r"\b[A-Za-z0-9+#.-]{3,}\b", cert.name):
                t_norm = normalize_term(token)
                if t_norm and t_norm not in STOP_WORDS:
                    profile_keywords.add(t_norm)

    # 6. Notable achievements
    for ach in profile.achievements:
        for token in re.findall(r"\b[A-Z][A-Za-z0-9+#.-]{1,15}\b", ach):
            t_norm = normalize_term(token)
            if tok_norm and tok_norm not in STOP_WORDS and len(tok_norm) > 1:
                profile_keywords.add(tok_norm)

    return profile_keywords, title_keywords


def extract_keywords_from_job(job_text: str, candidate_vocab: set[str] | None = None) -> set[str]:
    """
    Extract dynamic keywords from a job posting. If candidate_vocab is provided,
    prioritizes matching candidate profile phrases and skills.
    """
    if not job_text:
        return set()

    job_text_lower = f" {job_text.lower()} "
    extracted: set[str] = set()

    # 1. Match against candidate dynamic profile vocabulary (multi-word phrases & terms)
    if candidate_vocab:
        for skill in candidate_vocab:
            if len(skill) < 2:
                continue
            pattern = rf"(?:\b|\W){re.escape(skill)}(?:\b|\W)"
            if re.search(pattern, job_text_lower):
                extracted.add(skill)

    # 2. Extract acronyms / compound tokens (e.g. CI/CD, AWS, SEO, PMP)
    raw_tokens = re.findall(r"\b[a-zA-Z0-9+#./-]{2,15}\b", job_text)
    for token in raw_tokens:
        tok_norm = normalize_term(token)
        if "/" in token or token.isupper() or (candidate_vocab and tok_norm in candidate_vocab):
            if tok_norm and tok_norm not in STOP_WORDS and len(tok_norm) > 1:
                extracted.add(tok_norm)

    # 3. Extract word tokens (length >= 3)
    words = re.findall(r"\b[a-zA-Z0-9+#./-]{3,20}\b", job_text)
    for w in words:
        w_norm = normalize_term(w)
        if w_norm and w_norm not in STOP_WORDS and len(w_norm) > 2:
            if candidate_vocab is None or w_norm in candidate_vocab:
                extracted.add(w_norm)

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
        """Score CV text against job description by extracting dynamic keywords from both."""
        job_keywords = extract_keywords_from_job(job_description)
        cv_keywords = extract_keywords_from_job(cv_text)

        if not job_keywords:
            return CVScoreResult(
                overall_score=50,
                keyword_match_pct=0.0,
                matched_keywords=list(cv_keywords),
                missing_keywords=[],
                improvement_suggestions=["Job description had minimal detectable keywords."],
            )

        matched = sorted(list(job_keywords & cv_keywords))
        missing = sorted(list(job_keywords - cv_keywords))

        match_ratio = len(matched) / len(job_keywords)
        keyword_pct = round(match_ratio * 100, 1)

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
