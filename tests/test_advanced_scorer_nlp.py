"""Unit and property tests for dynamic NLP keyword extraction and ATS scoring engine."""

from backend.models.job import Recommendation
from backend.models.profile import CandidateProfile, Experience, PersonalInfo, Project
from backend.services.job_scorer import (
    JobScorer,
    extract_dynamic_profile_keywords,
    extract_keywords_from_job,
    normalize_term,
)


def test_normalize_term_strips_punctuation_and_standardizes() -> None:
    """Verify normalize_term cleans leading/trailing punctuation and handles edge cases."""
    assert normalize_term("  .js/wagmi/viem/  ") == "js/wagmi/viem"
    assert normalize_term("---Kubernetes---") == "kubernetes"
    assert normalize_term("Smart Contracts") == "smart contract"
    assert normalize_term("CI/CD") == "ci/cd"
    assert normalize_term("C++") == "c++"
    assert normalize_term("Node.js") == "node.js"


def test_stop_words_prevent_generic_english_filler_pollution() -> None:
    """Verify common non-technical English words are never extracted as domain skills."""
    filler_text = (
        "We are looking for someone with ability to work across teams and after hours. "
        "Must have strong understanding, good knowledge, and passion for excellence within fast-paced environment."
    )
    extracted = extract_keywords_from_job(filler_text)

    for filler in [
        "across",
        "after",
        "ability",
        "within",
        "understanding",
        "knowledge",
        "looking",
        "work",
        "team",
        "environment",
        "strong",
        "good",
    ]:
        assert filler not in extracted, f"Filler word '{filler}' was unexpectedly extracted."


def test_compound_and_slashed_tokens_extraction() -> None:
    """Verify technical compound tokens (CI/CD, wagmi/viem, React/Next.js) are extracted both together and split."""
    text = "Experience with CI/CD pipelines, Docker, wagmi/viem, and React/Next.js is required."
    extracted = extract_keywords_from_job(text)

    assert "docker" in extracted
    assert "ci/cd" in extracted or ("ci" in extracted and "cd" in extracted)
    assert "wagmi" in extracted
    assert "viem" in extracted
    assert "react" in extracted
    assert "next.js" in extracted or "next" in extracted


def test_extract_dynamic_profile_keywords_all_sections() -> None:
    """Verify extraction draws from skills, summary, experience bullets, projects, and certifications."""
    profile = CandidateProfile(
        personal_info=PersonalInfo(name="Dev Tester"),
        summary="Principal Distributed Systems Architect specialized in Byzantine Fault Tolerant consensus algorithms, zero-knowledge groth16, and high-throughput Kafka pipelines.",
        skills={
            "languages": ["Rust", "Go", "Solidity"],
            "cloud_infra": ["Terraform", "Kubernetes", "AWS EKS"],
        },
        experience=[
            Experience(
                title="Lead Infrastructure Engineer",
                company="Nexus Systems",
                bullets=[
                    "Engineered multi-region gRPC microservices processing 50k req/sec with Prometheus telemetry."
                ],
            )
        ],
        projects=[
            Project(
                name="zk-Rollup-Verifier",
                tech="Rust, Halo2, Circom",
                description="Zero-knowledge proof verification pipeline on Ethereum optimizing verifier gas consumption by 35%.",
            )
        ],
    )

    keywords, title_kws = extract_dynamic_profile_keywords(profile)

    # Verify skills
    assert "rust" in keywords
    assert "go" in keywords
    assert "solidity" in keywords
    assert "terraform" in keywords
    assert "kubernetes" in keywords

    # Verify summary technical terms
    assert "kafka" in keywords or "byzantine" in keywords

    # Verify experience & project tokens
    assert "grpc" in keywords or "prometheus" in keywords
    assert "halo2" in keywords or "circom" in keywords


def test_job_scorer_edge_cases() -> None:
    """Test score_cv_against_job and score_job_fast on boundary conditions."""
    # 1. Minimal / empty job description
    res_empty = JobScorer.score_cv_against_job("Experienced Python engineer", "")
    assert res_empty.overall_score == 50
    assert len(res_empty.improvement_suggestions) > 0

    # 2. Complete mismatch (0% overlap)
    cv_medical = "# Medical Doctor\nPracticing cardiologist specialized in echocardiography and pediatrics."
    job_tech = "We need a Senior Kubernetes Administrator with Terraform and Golang experience."
    res_zero = JobScorer.score_cv_against_job(cv_medical, job_tech)
    assert res_zero.overall_score == 0
    assert len(res_zero.missing_keywords) > 0

    # 3. High match
    cv_tech = "# Cloud Architect\nKubernetes, Terraform, Golang, Docker, AWS, microservices, Linux."
    res_high = JobScorer.score_cv_against_job(cv_tech, job_tech)
    assert res_high.overall_score >= 60
    assert len(res_high.matched_keywords) >= 3

    # 4. Fast scoring recommendations
    candidate_vocab = {"kubernetes", "terraform", "golang", "docker"}
    fast_match = JobScorer.score_job_fast(
        candidate_keywords=candidate_vocab,
        job_text=job_tech,
        job_title="Senior Kubernetes Administrator",
    )
    assert fast_match.score >= 6.0
    assert fast_match.recommendation in (Recommendation.STRONG_MATCH, Recommendation.GOOD_MATCH)


def test_stop_words_exclude_months_and_dates_and_snippet_verbs() -> None:
    """Verify months, dates, and non-skill verbs are never suggested as missing keywords."""
    snippet = (
        "Aug 3, 2026 · This internship will take place from January 25 - April 16. "
        "Write clean, secure, tested, and documented code. estimated hourly range for this role is $57/hr ..."
    )
    extracted = extract_keywords_from_job(snippet)
    for bad_token in ["aug", "january", "april", "write", "clean", "secure", "tested", "documented", "hourly"]:
        assert bad_token not in extracted, f"Token '{bad_token}' should not be in extracted keywords."


def test_phone_extraction_does_not_extract_dates() -> None:
    """Verify profile extraction never treats date strings as phone numbers."""
    from backend.services.profile_service import extract_personal_info

    resume_text = """
    Alex Mercer
    Email: alex@example.com
    Date: 2026-08-28
    Phone: +1 (555) 019-2834
    Location: San Francisco, CA
    """
    info = extract_personal_info(resume_text, resume_text)
    assert info.phone != "2026-08-28"
    assert "555" in info.phone


def test_clean_candidate_headline_formatting() -> None:
    """Verify messy employer requisition titles are formatted into clean professional headlines."""
    from backend.services.cv_generator import clean_candidate_headline

    h1 = clean_candidate_headline("Software Engineer (Internship, Summer 2027) - US Government Team")
    assert h1 == "Software Engineering Intern"

    h2 = clean_candidate_headline("2026 Early Career Embedded Software Engineer - TP-Link Systems Inc.")
    assert h2 == "Embedded Software Engineer"

    h3 = clean_candidate_headline("Senior React Developer (m/f/d)")
    assert h3 == "Senior React Developer"
