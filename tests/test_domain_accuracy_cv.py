"""Domain accuracy and anti-boilerplate verification tests for CV tailoring engine."""

from __future__ import annotations

from backend.models.profile import CandidateProfile, Experience, PersonalInfo, Project
from backend.services.cv_generator import (
    generate_deterministic_cv_markdown,
    is_web3_target,
)


def get_mock_candidate() -> CandidateProfile:
    return CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin-Marian Lavric",
            email="cosminlavric53@gmail.com",
            location="Brasov, Romania (EET)",
            github="https://github.com/cosminmarian53",
            linkedin="https://www.linkedin.com/in/cosmin-lavric-827126331/",
            portfolio="https://github.com/cosminmarian53/security-audit-portofolio",
        ),
        achievements=[
            "Ranked 3rd out of 723 in Kuru Contracts security assessment.",
            "Ranked 23rd out of 316 in Avon Protocol.",
            "Ranked 29th out of 509 in CurrentFinance on Sherlock.",
            "Top 5 CodeHawks First Flights.",
            "Completed all Damn Vulnerable DeFi challenges.",
            "Completed all Ethernaut CTFs.",
        ],
        skills={
            "Tools & Technologies": [
                "Foundry",
                "Slither",
                "Echidna",
                "Burp Suite",
                "Docker",
                "Git",
                "CI/CD",
                "Linux",
                "Node.js",
                "PostgreSQL",
                "MongoDB",
                "Playwright",
            ],
            "Core Competencies": [
                "Penetration Testing",
                "Threat Modeling",
                "Secure Code Review",
                "OWASP Top 10",
                "Python",
                "Rust",
                "Solidity",
                "JavaScript",
                "TypeScript",
                "C++",
                "SQL",
                "Bash",
            ],
        },
        experience=[
            Experience(
                title="Security-Focused Software Engineer",
                company="Freelance",
                duration="June 2024 - Present",
                bullets=[
                    "Built 30+ full-stack applications in React, Node.js, TypeScript, and Python.",
                    "Implemented automated end-to-end testing with Playwright, achieving 100% test pass rate.",
                ],
            ),
            Experience(
                title="Cybersecurity Analyst Intern",
                company="IBM Summer School",
                duration="July 2025",
                bullets=[
                    "Designed and implemented a 2FA system using TOTP and QR codes with Single Sign-On and RBAC.",
                    "Managed SSL/TLS certificate lifecycle across environments.",
                ],
            ),
        ],
        projects=[
            Project(
                name="X-Scout",
                tech="Python, Playwright, AI",
                description="Automated threat-intelligence pipeline tracking emerging vulnerabilities and processing 500+ data points daily.",
            )
        ],
    )


def test_vital_lyfe_cv_domain_accuracy_and_clean_framing() -> None:
    """Verify Web2 hardware/software job produces 0% Web3 contamination and zero robotic boilerplate."""
    candidate = get_mock_candidate()
    vital_desc = """
    About Vital Lyfe: Tech company redefining water autonomy through innovation.
    The Mission: Software Engineering Intern to help build software behind consumer hardware.
    What You'll Do: Build internal tools for production workflows. Write integrations in Python/TypeScript.
    What We're Looking For: Python, TypeScript, React, SQL, automated testing, APIs.
    """

    # 1. Verify domain detection is NOT Web3 (e.g. 'redefining' must not trigger 'defi')
    assert not is_web3_target("Software Engineering Intern", "Vital Lyfe", vital_desc)

    # 2. Generate CV
    cv_md = generate_deterministic_cv_markdown(
        profile=candidate,
        job_title="Software Engineering Intern",
        company="Vital Lyfe",
        job_description=vital_desc,
    )

    # 3. Assert headline is clean industry title
    assert "**Junior Software Engineer**" in cv_md

    # 4. Assert zero robotic boilerplate
    assert "Targeting the" not in cv_md
    assert "Targeting " not in cv_md

    # 5. Assert zero Web3 CTF contamination
    assert "Ethernaut" not in cv_md
    assert "Damn Vulnerable DeFi" not in cv_md
    assert "Kuru Contracts" not in cv_md
    assert "Foundry" not in cv_md
    assert "Slither" not in cv_md
    assert "Echidna" not in cv_md

    # 6. Assert genuine software engineering accomplishments are highlighted
    assert "30+ full-stack applications" in cv_md
    assert "Playwright" in cv_md
    assert "Python, TypeScript, React, and SQL" in cv_md


def test_fab2_cv_domain_accuracy() -> None:
    """Verify low-level Rust/systems job produces Junior Rust Software Engineer title and systems summary."""
    candidate = get_mock_candidate()
    fab2_desc = """
    About fab2: Fast browser-based multiplayer CAD platform in Rust across the stack, WebAssembly, wgpu.
    Required: Strong Rust or systems C++, memory, concurrency, performance profiling.
    """

    cv_md = generate_deterministic_cv_markdown(
        profile=candidate,
        job_title="Rust Software Engineering(Chip Design Tools) - Winter Intern",
        company="Fab2",
        job_description=fab2_desc,
    )

    assert "**Junior Rust Software Engineer**" in cv_md
    assert "Targeting the" not in cv_md
    assert "Rust, C++, concurrency, memory safety" in cv_md
