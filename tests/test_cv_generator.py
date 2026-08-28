"""Unit tests for CV generation service and deterministic template."""

import pytest

from backend.models.profile import (
    CandidateProfile,
    Certification,
    Education,
    Experience,
    PersonalInfo,
    Project,
)
from backend.services.cv_generator import (
    CVGenerator,
    generate_deterministic_cv_markdown,
)


@pytest.fixture
def sample_profile() -> CandidateProfile:
    return CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin Lavric",
            email="cosmin@test.com",
            github="https://github.com/cosmin",
            location="Brasov, Romania",
        ),
        summary="Specializing in smart contract security, invariant testing, and formal verification.",
        achievements=[
            "Achieved 3rd Place in Kuru Contracts Cantina audit competition.",
            "Ranked Top 7% in Avon Protocol private audit.",
        ],
        skills={
            "Languages": ["Rust", "Solidity", "Python"],
            "Security Tooling": ["Foundry", "Slither", "Certora"],
        },
        experience=[
            Experience(
                title="Independent Security Researcher",
                company="Cantina & CodeHawks",
                duration="Aug 2025 - Present",
                bullets=[
                    "Discovered high-severity logic vulnerability in AMM vault.",
                    "Performed shadow auditing on Aave V4.",
                ],
            )
        ],
        projects=[
            Project(
                name="Smart Contract CTFs",
                tech="Solidity, Foundry",
                description="Completed Damn Vulnerable DeFi and Ethernaut challenges.",
            )
        ],
        certifications=[
            Certification(
                name="Smart Contract Security",
                issuer="Cyfrin",
                date="May 2025",
            )
        ],
        education=[
            Education(
                degree="B.S. in Computer Science",
                institution="Transylvania University",
                year="2026",
            )
        ],
    )


def test_generate_deterministic_cv_markdown_structure(sample_profile: CandidateProfile) -> None:
    md = generate_deterministic_cv_markdown(sample_profile, job_title="Lead Auditor", company="Cyfrin")

    assert "# Cosmin Lavric" in md
    assert "**Lead Auditor**" in md
    assert "cosmin@test.com" in md
    assert "## Key Achievements" in md
    assert "Achieved 3rd Place in Kuru Contracts" in md
    assert "## Core Skills & Competencies" in md
    assert "**Languages:** Rust, Solidity, Python" in md
    assert "## Experience" in md
    assert "Independent Security Researcher | Cantina & CodeHawks" in md
    assert "## Education & Certifications" in md
    assert "Smart Contract Security" in md
    assert "Cyfrin" in md


@pytest.mark.asyncio
async def test_cv_generator_fallback_without_ai(sample_profile: CandidateProfile) -> None:
    generator = CVGenerator()
    md = await generator.generate_markdown(
        sample_profile,
        job_description="Looking for Rust security expert",
        job_title="Security Auditor",
        company="CertiK",
        use_ai=False,
    )

    assert "# Cosmin Lavric" in md
    assert "**Security Auditor**" in md
    assert "Rust" in md
