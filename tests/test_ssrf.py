"""Unit tests for SSRF protection and URL validation."""

import pytest

from backend.scrapers.ssrf import (
    SSRFProtectionError,
    is_ip_private,
    validate_url_safety,
)


def test_is_ip_private() -> None:
    assert is_ip_private("127.0.0.1") is True
    assert is_ip_private("10.0.0.5") is True
    assert is_ip_private("192.168.1.1") is True
    assert is_ip_private("172.16.0.1") is True
    assert is_ip_private("169.254.169.254") is True
    assert is_ip_private("::1") is True
    assert is_ip_private("8.8.8.8") is False
    assert is_ip_private("1.1.1.1") is False


def test_validate_url_safety_blocks_private_ips_and_forbidden_hosts() -> None:
    with pytest.raises(SSRFProtectionError, match="SSRF blocked"):
        validate_url_safety("http://127.0.0.1:8000/internal")

    with pytest.raises(SSRFProtectionError, match="SSRF blocked"):
        validate_url_safety("http://localhost:3000")

    with pytest.raises(SSRFProtectionError, match="SSRF blocked"):
        validate_url_safety("http://169.254.169.254/latest/meta-data")

    with pytest.raises(SSRFProtectionError, match="SSRF blocked"):
        validate_url_safety("http://10.200.0.1/admin")


def test_validate_url_safety_rejects_non_http_schemes() -> None:
    with pytest.raises(SSRFProtectionError, match="Unsupported scheme"):
        validate_url_safety("file:///etc/passwd")

    with pytest.raises(SSRFProtectionError, match="Unsupported scheme"):
        validate_url_safety("ftp://internal.server/data")


def test_validate_url_safety_accepts_valid_public_domain() -> None:
    url = "https://example.com/careers"
    assert validate_url_safety(url) == url
