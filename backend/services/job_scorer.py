"""Deterministic ATS keyword extraction and job relevance scoring engine."""

from __future__ import annotations

import re
from typing import Set

from backend.models.cv import CVScoreResult

COMMON_TECH_KEYWORDS: set[str] = {
    # Languages
    "python",
    "rust",
    "solidity",
    "typescript",
    "javascript",
    "golang",
    "go",
    "c++",
    "c#",
    "java",
    "sql",
    "bash",
    "vyper",
    "yul",
    "move",
    "ruby",
    "php",
    # Frameworks & Libraries
    "fastapi",
    "django",
    "flask",
    "react",
    "next.js",
    "vue",
    "node.js",
    "express",
    "tailwind",
    "graphql",
    "rest",
    "grpc",
    "redux",
    "web3.js",
    "ethers.js",
    # Databases & Storage
    "postgresql",
    "postgres",
    "mysql",
    "redis",
    "mongodb",
    "sqlite",
    "dynamodb",
    # Cloud & Infra
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "terraform",
    "ci/cd",
    "github actions",
    "linux",
    "nginx",
    # Security & Web3
    "smart contracts",
    "foundry",
    "hardhat",
    "slither",
    "aderyn",
    "echidna",
    "certora",
    "solana",
    "ethereum",
    "evm",
    "defi",
    "amm",
    "penetration testing",
    "threat modeling",
    "cryptography",
    "zero knowledge",
    "zk",
    "audit",
    "formal verification",
    # Methodologies
    "agile",
    "scrum",
    "microservices",
    "unit testing",
    "integration testing",
    "system design",
}

STOP_WORDS: set[str] = {
    "and",
    "the",
    "with",
    "for",
    "our",
    "you",
    "are",
    "will",
    "this",
    "that",
    "from",
    "have",
    "been",
    "team",
    "work",
    "role",
    "years",
    "experience",
    "looking",
    "skills",
    "ability",
    "must",
    "should",
    "plus",
    "required",
}


def extract_keywords_from_text(text: str) -> set[str]:
    """Extract recognized technical keywords and key multi-word phrases from text."""
    text_lower = f" {text.lower()} "
    found: set[str] = set()

    # 1. Check known tech keywords
    for kw in COMMON_TECH_KEYWORDS:
        pattern = rf"\b{re.escape(kw)}\b"
        if re.search(pattern, text_lower):
            found.add(kw)

    # 2. Extract capitalized acronyms / technical identifiers
    raw_tokens = re.findall(r"\b[A-Z][A-Za-z0-9+#.-]{1,15}\b", text)
    for token in raw_tokens:
        tok_lower = token.lower()
        if len(tok_lower) > 1 and tok_lower not in STOP_WORDS and len(tok_lower) < 20:
            found.add(tok_lower)

    return found


class JobScorer:
    """Calculates deterministic ATS keyword match score and actionable recommendations."""

    @staticmethod
    def score_cv_against_job(cv_text: str, job_text: str) -> CVScoreResult:
        """Score CV text against job description keywords."""
        job_keywords: Set[str] = extract_keywords_from_text(job_text)
        cv_keywords: Set[str] = extract_keywords_from_text(cv_text)

        if not job_keywords:
            return CVScoreResult(
                overall_score=80,
                keyword_match_pct=100.0,
                matched_keywords=list(cv_keywords)[:10],
                missing_keywords=[],
                improvement_suggestions=["Job description had minimal detectable keywords."],
            )

        matched = sorted(list(job_keywords.intersection(cv_keywords)))
        missing = sorted(list(job_keywords - cv_keywords))

        match_ratio = len(matched) / len(job_keywords)
        keyword_pct = round(match_ratio * 100, 1)

        # Overall score incorporates keyword match + baseline formatting penalty
        overall = int(round(keyword_pct))
        overall = max(10, min(100, overall))

        suggestions: list[str] = []
        if missing:
            top_missing = missing[:5]
            suggestions.append(f"Consider integrating these target keywords if applicable: {', '.join(top_missing)}.")

        if len(cv_text.split()) < 150:
            suggestions.append("CV appears short; expand on key project metrics and quantifiable achievements.")

        if not re.search(r"\b(achieved|increased|reduced|built|designed|led|discovered)\b", cv_text, re.I):
            suggestions.append(
                "Use strong action verbs (e.g., 'Engineered', 'Optimized', 'Audited') to demonstrate impact."
            )

        return CVScoreResult(
            overall_score=overall,
            keyword_match_pct=keyword_pct,
            matched_keywords=matched,
            missing_keywords=missing,
            improvement_suggestions=suggestions,
        )
