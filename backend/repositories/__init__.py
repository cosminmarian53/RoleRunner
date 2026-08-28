"""Tenant-scoped database repositories guaranteeing user data isolation."""

from backend.repositories.application_repo import ApplicationRepository
from backend.repositories.base import BaseTenantRepository
from backend.repositories.cv_repo import CVRepository
from backend.repositories.job_repo import JobRepository
from backend.repositories.operation_repo import OperationRepository
from backend.repositories.profile_repo import ProfileRepository

__all__ = [
    "ApplicationRepository",
    "BaseTenantRepository",
    "CVRepository",
    "JobRepository",
    "OperationRepository",
    "ProfileRepository",
]
