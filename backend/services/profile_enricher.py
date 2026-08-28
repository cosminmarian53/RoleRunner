"""Background intelligence service to automatically enrich candidate profiles from GitHub and public profiles."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

from backend.models.profile import CandidateProfile, Project
from backend.scrapers.http_client import SafeAsyncClient

logger = logging.getLogger(__name__)

# Known technical frameworks and libraries to automatically detect from repo topics/descriptions/readmes
TECH_DETECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "Tokio": re.compile(r"\btokio\b", re.IGNORECASE),
    "Axum": re.compile(r"\baxum\b", re.IGNORECASE),
    "Actix": re.compile(r"\bactix\b", re.IGNORECASE),
    "WGPU": re.compile(r"\bwgpu\b", re.IGNORECASE),
    "WebGPU": re.compile(r"\bwebgpu\b", re.IGNORECASE),
    "Bevy": re.compile(r"\bbevy\b", re.IGNORECASE),
    "WebAssembly": re.compile(r"\b(wasm|webassembly)\b", re.IGNORECASE),
    "Serde": re.compile(r"\bserde\b", re.IGNORECASE),
    "Rayon": re.compile(r"\brayon\b", re.IGNORECASE),
    "Playwright": re.compile(r"\bplaywright\b", re.IGNORECASE),
    "FastAPI": re.compile(r"\bfastapi\b", re.IGNORECASE),
    "Pytest": re.compile(r"\bpytest\b", re.IGNORECASE),
    "Docker": re.compile(r"\bdocker\b", re.IGNORECASE),
    "PostgreSQL": re.compile(r"\b(postgres|postgresql)\b", re.IGNORECASE),
    "MongoDB": re.compile(r"\bmongodb\b", re.IGNORECASE),
    "Redis": re.compile(r"\bredis\b", re.IGNORECASE),
    "React": re.compile(r"\breact(\.js)?\b", re.IGNORECASE),
    "Next.js": re.compile(r"\bnext(\.js)?\b", re.IGNORECASE),
    "TypeScript": re.compile(r"\btypescript\b", re.IGNORECASE),
    "Anchor": re.compile(r"\banchor\b", re.IGNORECASE),
    "Solana": re.compile(r"\bsolana\b", re.IGNORECASE),
    "Foundry": re.compile(r"\bfoundry\b", re.IGNORECASE),
}


class GitHubEnricher:
    """Fast, unauthenticated public GitHub intelligence extractor."""

    def __init__(self, client: SafeAsyncClient | None = None) -> None:
        self.client = client or SafeAsyncClient()

    @staticmethod
    def extract_username(github_url: str) -> str:
        """Extract GitHub username from various URL or handle formats."""
        if not github_url:
            return ""
        clean = github_url.strip().rstrip("/")
        if clean.startswith("@"):
            return clean[1:]
        if not clean.startswith(("http://", "https://")):
            clean = f"https://{clean}"
        if "github.com" in clean:
            path = urlparse(clean).path.strip("/")
            parts = path.split("/")
            if parts and parts[0]:
                return parts[0]
        return clean.split("/")[-1]

    async def fetch_user_repositories(self, username: str, limit: int = 15) -> list[dict[str, Any]]:
        """Fetch public repositories metadata from GitHub REST API."""
        if not username:
            return []
        url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page={limit}"
        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
            logger.debug("GitHub API returned status %d for user %s", resp.status_code, username)
        except Exception as exc:
            logger.debug("Failed to fetch GitHub repos for user %s: %s", username, exc)
        return []

    async def fetch_repo_readme(self, username: str, repo_name: str) -> str:
        """Fetch raw README content for a repository."""
        for branch in ["main", "master"]:
            url = f"https://raw.githubusercontent.com/{username}/{repo_name}/{branch}/README.md"
            try:
                resp = await self.client.get(url)
                if resp.status_code == 200 and resp.text:
                    return str(resp.text)
            except Exception:
                continue
        return ""

    async def extract_github_projects_and_skills(
        self,
        github_url: str,
    ) -> tuple[list[Project], set[str]]:
        """Extract structured projects and discovered technologies from candidate's GitHub."""
        username = self.extract_username(github_url)
        if not username:
            return [], set()

        repos = await self.fetch_user_repositories(username, limit=12)
        if not repos:
            return [], set()

        projects: list[Project] = []
        discovered_skills: set[str] = set()

        # Concurrently fetch readmes for top 5 non-forked repos
        valid_repos = [r for r in repos if not r.get("fork", False)][:6]
        if not valid_repos:
            valid_repos = repos[:4]

        readme_tasks = [self.fetch_repo_readme(username, r.get("name", "")) for r in valid_repos]
        readmes = await asyncio.gather(*readme_tasks, return_exceptions=True)

        for i, repo in enumerate(valid_repos):
            repo_name = repo.get("name", "").strip()
            if not repo_name:
                continue

            desc = (repo.get("description") or "").strip()
            lang = (repo.get("language") or "").strip()
            topics = repo.get("topics") or []

            raw_rm = readmes[i] if i < len(readmes) and isinstance(readmes[i], str) else ""
            readme_text = raw_rm[:2000] if isinstance(raw_rm, str) else ""
            combined_context = f"{repo_name} {desc} {' '.join(topics)} {readme_text}"

            repo_techs: list[str] = []
            if lang:
                repo_techs.append(lang)
                discovered_skills.add(lang)

            for topic in topics:
                t_clean = topic.replace("-", " ").title()
                if len(t_clean) >= 2:
                    repo_techs.append(t_clean)
                    discovered_skills.add(t_clean)

            # Detect specific frameworks/libraries
            for tech_name, pattern in TECH_DETECTION_PATTERNS.items():
                if pattern.search(combined_context) and tech_name not in repo_techs:
                    repo_techs.append(tech_name)
                    discovered_skills.add(tech_name)

            # Format project entry
            formatted_name = repo_name.replace("-", " ").replace("_", " ").title()
            tech_str = ", ".join(repo_techs[:5]) if repo_techs else (lang or "Software")
            summary_desc = desc or f"Open-source software project built in {lang or 'modern technologies'}."

            projects.append(
                Project(
                    name=formatted_name,
                    tech=tech_str,
                    description=summary_desc,
                )
            )

        return projects, discovered_skills


class ProfileEnrichmentService:
    """Coordinates seamless, non-blocking background enrichment of candidate profiles."""

    def __init__(self, client: SafeAsyncClient | None = None) -> None:
        self.github_enricher = GitHubEnricher(client)

    async def enrich_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """
        Enrich candidate profile with verified GitHub projects and technologies.
        Preserves existing user data while appending newly discovered technical artifacts.
        """
        github_url = profile.personal_info.github or ""
        if not github_url:
            return profile

        try:
            gh_projects, gh_skills = await self.github_enricher.extract_github_projects_and_skills(github_url)

            # Merge discovered projects
            existing_project_names = {p.name.lower().replace(" ", "") for p in profile.projects}
            for p in gh_projects:
                norm = p.name.lower().replace(" ", "")
                if norm not in existing_project_names:
                    profile.projects.append(p)
                    existing_project_names.add(norm)

            # Merge discovered skills into profile.skills map
            if gh_skills:
                skills_map = dict(profile.skills or {})
                tools_list = list(skills_map.get("Tools & Technologies", []))
                existing_tools_lower = {t.lower() for t in tools_list}

                for sk in gh_skills:
                    if sk.lower() not in existing_tools_lower:
                        tools_list.append(sk)
                        existing_tools_lower.add(sk.lower())

                skills_map["Tools & Technologies"] = tools_list
                profile.skills = skills_map

            logger.info("Enriched profile with %d GitHub projects and %d skills", len(gh_projects), len(gh_skills))
        except Exception as exc:
            logger.debug("Background profile enrichment completed with notice: %s", exc)

        return profile
