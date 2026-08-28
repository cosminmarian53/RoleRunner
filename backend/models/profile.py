"""Pydantic models for candidate profile — the single master profile."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersonalInfo(BaseModel):
    """Contact and identity information."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    twitter: str = ""
    telegram: str = ""
    location: str = ""
    extra_links: dict[str, str] = Field(default_factory=dict)


class Experience(BaseModel):
    """A single work experience entry."""

    model_config = ConfigDict(extra="ignore")

    company: str = ""
    title: str = ""
    duration: str = ""
    location: str = ""
    bullets: list[str] = Field(default_factory=list)


class Education(BaseModel):
    """Academic education entry."""

    model_config = ConfigDict(extra="ignore")

    institution: str = ""
    degree: str = ""
    year: str = ""
    details: str = ""


class Certification(BaseModel):
    """Professional certification or course."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    issuer: str = ""
    date: str = ""


class Project(BaseModel):
    """Notable project."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    tech: str = ""
    description: str = ""


class Language(BaseModel):
    """Spoken language proficiency."""

    model_config = ConfigDict(extra="ignore")

    language: str = ""
    level: str = ""


class CandidateProfile(BaseModel):
    """
    The single master profile containing ALL candidate data.

    This is exhaustive — every skill, certification, experience entry,
    and project goes here. Nothing is filtered at the profile level.
    The CV generator handles intelligent selection per job.
    """

    model_config = ConfigDict(extra="ignore")

    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: str = ""
    skills: dict[str, list[str]] = Field(default_factory=dict)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class ProfileTextParseRequest(BaseModel):
    """Request to parse pasted resume/profile text into the master profile."""

    model_config = ConfigDict(extra="ignore")

    text: str
    merge_existing: bool = True


class ProfileUploadResponse(BaseModel):
    """Response returned after parsing an uploaded profile document."""

    model_config = ConfigDict(extra="ignore")

    profile: CandidateProfile
    extracted_text: str = ""
    source_filename: str = ""
    warnings: list[str] = Field(default_factory=list)
