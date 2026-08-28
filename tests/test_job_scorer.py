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


def test_score_job_fast_differentiates_high_and_zero_match() -> None:
    from backend.models.job import Recommendation

    candidate_keywords = {
        "solidity",
        "smart contracts",
        "rust",
        "audit",
        "ethereum",
        "penetration testing",
        "foundry",
    }

    # 1. Strong matching role
    strong_job = "Smart Contract Security Auditor. Review Solidity smart contracts on Ethereum using Foundry."
    match_high = JobScorer.score_job_fast(candidate_keywords, strong_job, job_title="Smart Contract Security Auditor")
    assert match_high.score >= 8.0
    assert match_high.recommendation == Recommendation.STRONG_MATCH
    assert "solidity" in match_high.matched_keywords
    assert "smart contracts" in match_high.matched_keywords

    # 2. Completely unaligned role (e.g. Medical receptionist / unrelated sales)
    unrelated_job = "Medical Receptionist. Handle front desk check-in, phone appointments, and patient billing."
    match_zero = JobScorer.score_job_fast(candidate_keywords, unrelated_job, job_title="Medical Receptionist")
    assert match_zero.score == 0.0
    assert match_zero.recommendation == Recommendation.WEAK_MATCH
    assert len(match_high.matched_keywords) > 0
    assert len(match_zero.matched_keywords) == 0


def test_extract_dynamic_profile_keywords() -> None:
    from backend.models.profile import CandidateProfile, Experience, PersonalInfo, Project
    from backend.services.job_scorer import extract_dynamic_profile_keywords

    profile = CandidateProfile(
        personal_info=PersonalInfo(name="Cosmin-Marian Lavric"),
        summary="Offensive Security & Blockchain Researcher specializing in source code review and vulnerability assessments.",
        skills={
            "Smart Contracts": ["Solidity", "Foundry", "Slither", "Aderyn", "EVM"],
            "Offensive Security": ["Burp Suite", "Penetration Testing", "Threat Modeling"],
        },
        experience=[
            Experience(
                title="Smart Contract Security Auditor",
                company="Cantina",
                bullets=["Identified critical vulnerabilities in DeFi lending protocols and DEX architectures."],
            )
        ],
        projects=[
            Project(
                name="Jupiter Lend Audit",
                tech="Solidity, Foundry, Slither",
                description="Smart contract security review.",
            )
        ],
    )

    kws, title_kws = extract_dynamic_profile_keywords(profile)

    assert "solidity" in kws
    assert "foundry" in kws
    assert "slither" in kws
    assert "burp suite" in kws
    assert "penetration testing" in kws
    assert "evm" in kws
    assert "security" in title_kws or "auditor" in title_kws or "blockchain" in title_kws
