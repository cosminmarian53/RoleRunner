"""Unit tests for deterministic ATS keyword and job relevance scorer."""

from backend.services.job_scorer import JobScorer, extract_keywords_from_text


def test_extract_keywords_from_text() -> None:
    text = "We require Python, FastAPI, Docker, and PostgreSQL experience with AWS CI/CD pipelines."
    kws = extract_keywords_from_text(text)

    assert "python" in kws
    assert "fastapi" in kws
    assert "docker" in kws
    assert "postgresql" in kws
    assert "aws" in kws
    assert "ci/cd" in kws


def test_job_scorer_high_match() -> None:
    job_desc = "Looking for a Senior Python Engineer with FastAPI, Docker, and PostgreSQL skills."
    cv_text = """
    # Jane Doe
    Senior Python Developer skilled in FastAPI, Docker, PostgreSQL, Redis, and automated testing.
    Achieved 40% latency reduction across microservices architecture.
    """

    res = JobScorer.score_cv_against_job(cv_text, job_desc)

    assert res.overall_score >= 80
    assert "python" in res.matched_keywords
    assert "fastapi" in res.matched_keywords
    assert "docker" in res.matched_keywords
    assert "postgresql" in res.matched_keywords


def test_job_scorer_detects_missing_keywords_and_suggestions() -> None:
    job_desc = "Must have extensive experience with Rust, Solana, Certora formal verification, and Foundry."
    cv_text = "I am a Python developer with Django experience."

    res = JobScorer.score_cv_against_job(cv_text, job_desc)

    assert res.overall_score < 50
    assert "rust" in res.missing_keywords
    assert "solana" in res.missing_keywords
    assert len(res.improvement_suggestions) > 0
