"""Unit tests for GitHub intelligence enrichment and profile augmentation."""

from __future__ import annotations

import httpx
import pytest

from backend.models.profile import CandidateProfile, PersonalInfo, Project
from backend.scrapers.http_client import SafeAsyncClient
from backend.services.cv_generator import clean_candidate_headline
from backend.services.profile_enricher import GitHubEnricher, ProfileEnrichmentService


def test_extract_github_username() -> None:
    """Verify robust username extraction from varied GitHub URL formats."""
    enricher = GitHubEnricher()
    assert enricher.extract_username("https://github.com/cosminmarian53") == "cosminmarian53"
    assert enricher.extract_username("https://github.com/cosminmarian53/") == "cosminmarian53"
    assert enricher.extract_username("github.com/cosminmarian53") == "cosminmarian53"
    assert enricher.extract_username("@cosminmarian53") == "cosminmarian53"
    assert enricher.extract_username("cosminmarian53") == "cosminmarian53"
    assert enricher.extract_username("") == ""


@pytest.mark.asyncio
async def test_github_enricher_extracts_projects_and_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GitHub repos and READMEs are parsed into structured Project models with detected tools."""
    mock_repos = [
        {
            "name": "punkz-vault",
            "description": "Rust privacy protocol with concurrency and solvency verification",
            "language": "Rust",
            "fork": False,
            "topics": ["rust", "solana", "tokio", "systems"],
        },
        {
            "name": "x-scout",
            "description": "Automated threat intelligence pipeline in Python",
            "language": "Python",
            "fork": False,
            "topics": ["python", "playwright", "fastapi"],
        },
    ]

    async def fake_get(self, url: str, *args, **kwargs) -> httpx.Response:
        if "api.github.com" in url:
            return httpx.Response(200, json=mock_repos, request=httpx.Request("GET", url))
        if "raw.githubusercontent.com" in url:
            return httpx.Response(
                200,
                text="# Architecture\nBuilt with Tokio async runtime and Serde serialization.",
                request=httpx.Request("GET", url),
            )
        return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    enricher = GitHubEnricher()
    projects, skills = await enricher.extract_github_projects_and_skills("https://github.com/cosminmarian53")

    assert len(projects) == 2
    assert any("Punkz Vault" in p.name for p in projects)
    assert any("X Scout" in p.name for p in projects)
    assert "Rust" in skills
    assert "Tokio" in skills or "Serde" in skills


@pytest.mark.asyncio
async def test_profile_enrichment_service_merges_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ProfileEnrichmentService non-destructively augments master profile."""
    mock_repos = [
        {
            "name": "high-throughput-rust-engine",
            "description": "Custom CAD graphics pipeline using WGPU and Bevy",
            "language": "Rust",
            "fork": False,
            "topics": ["rust", "wgpu", "bevy"],
        }
    ]

    async def fake_get(self, url: str, *args, **kwargs) -> httpx.Response:
        return httpx.Response(200, json=mock_repos, request=httpx.Request("GET", url))

    monkeypatch.setattr(SafeAsyncClient, "get", fake_get)

    profile = CandidateProfile(
        personal_info=PersonalInfo(
            name="Cosmin Lavric",
            github="https://github.com/cosminmarian53",
        ),
        skills={"Tools & Technologies": ["Docker", "Git"]},
        projects=[Project(name="Existing Project", tech="Python", description="Old project")],
    )

    service = ProfileEnrichmentService()
    enriched = await service.enrich_profile(profile)

    assert len(enriched.projects) == 2
    assert any("High Throughput Rust Engine" in p.name for p in enriched.projects)
    assert "Docker" in enriched.skills["Tools & Technologies"]
    assert (
        "Wgpu" in [s.title() for s in enriched.skills["Tools & Technologies"]]
        or "Rust" in enriched.skills["Tools & Technologies"]
    )


def test_clean_candidate_headline_fab2_and_senior() -> None:
    """Verify headline normalizer produces clean industry titles across general market cases."""
    # 1. Company and diversity tags
    h_bosch = clean_candidate_headline("Bosch Group IT Application Support Intern (f/m)", company="Bosch Group")
    assert h_bosch == "Junior IT Application Support Specialist"

    # 2. German/EU tags with location suffix
    h_siemens = clean_candidate_headline(
        "Siemens - Cloud Infrastructure Engineering Trainee (m/w/d) - Munich", company="Siemens"
    )
    assert h_siemens == "Junior Cloud Infrastructure Engineer"

    # 3. Verbal noun development + location
    h_stripe = clean_candidate_headline("Stripe Backend Development Internship - Dublin", company="Stripe")
    assert h_stripe == "Junior Backend Developer"

    # 4. Bracketed team tags + corporate prefix
    h_palantir = clean_candidate_headline(
        "Palantir Technologies [US Government Team] Forward Deployed Software Engineering (Summer 2026)",
        company="Palantir",
    )
    assert h_palantir == "Forward Deployed Software Engineer"

    # 5. Intern with bracketed tools and seasonal suffix
    h1 = clean_candidate_headline("Rust Software Engineering(Chip Design Tools) - Winter Intern")
    assert h1 == "Junior Rust Software Engineer"

    # 6. Senior role with bracketed sub-specialty
    h2 = clean_candidate_headline("Senior Developer (Cloud Platforms) - Winter 2026")
    assert h2 == "Senior Developer"

    # 7. Internship with season and team suffix
    h3 = clean_candidate_headline("Software Engineer (Internship, Summer 2027) - US Government Team")
    assert h3 == "Junior Software Engineer"
