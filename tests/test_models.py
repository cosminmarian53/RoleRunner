"""Validation tests for shared request and persistence models."""

import pytest
from pydantic import ValidationError

from backend.models.application import ApplicationRecord, ApplicationStatus
from backend.models.cv import CVGenerateRequest, ExportFormat, GeneratedCV
from backend.models.job import JobListing, JobSearchRequest, JobSource
from backend.models.operation import Operation
from backend.models.profile import CandidateProfile


def test_candidate_profile_defaults_are_valid_and_isolated() -> None:
    first = CandidateProfile()
    second = CandidateProfile()

    first.skills["Languages"] = ["Python"]
    first.personal_info.extra_links["blog"] = "https://example.com"

    assert first.personal_info.name == ""
    assert second.skills == {}
    assert second.personal_info.extra_links == {}


def test_job_listing_generates_unique_ids_and_serializes_enum() -> None:
    first = JobListing(title="Security Engineer", source=JobSource.COMPANY_CAREER)
    second = JobListing(title="Security Engineer")

    assert first.id
    assert first.id != second.id
    assert first.model_dump(mode="json")["source"] == "company_career"


def test_job_search_request_normalizes_query_and_bounds_limit() -> None:
    request = JobSearchRequest(query="  solidity auditor  ", limit=50)

    assert request.query == "solidity auditor"

    with pytest.raises(ValidationError):
        JobSearchRequest(query="   ")
    with pytest.raises(ValidationError):
        JobSearchRequest(query="security", limit=51)


def test_cv_generation_requires_description_or_url() -> None:
    with pytest.raises(ValidationError):
        CVGenerateRequest()

    request = CVGenerateRequest(job_url="https://example.com/jobs/1", export_format=ExportFormat.DOCX)

    assert request.export_format is ExportFormat.DOCX


def test_generated_cv_and_application_receive_stable_identity() -> None:
    cv = GeneratedCV(company="Example")
    application = ApplicationRecord(title="Engineer", status=ApplicationStatus.APPLIED)

    assert len(cv.id) == 32
    assert len(application.id) == 32
    assert application.model_dump(mode="json")["status"] == "applied"


def test_operation_progress_is_bounded() -> None:
    assert Operation(type="job_search", progress=100).progress == 100

    with pytest.raises(ValidationError):
        Operation(type="job_search", progress=101)
