"""SSRF (Server-Side Request Forgery) protection utilities for outbound HTTP requests."""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SSRFProtectionError(Exception):
    """Raised when an outbound URL resolves to a forbidden private or local IP address."""

    def __init__(self, message: str, url: str = "", ip: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.url = url
        self.ip = ip


FORBIDDEN_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "169.254.169.254",  # AWS/GCP/Azure instance metadata
    "metadata.google.internal",
}


def is_ip_private(ip_str: str) -> bool:
    """Check if an IP address string belongs to a private, loopback, link-local, or reserved range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True


def validate_url_safety(url: str) -> str:
    """
    Validate that a URL is safe to fetch via HTTP/HTTPS.

    Resolves domain DNS and checks all resulting IP addresses against private networks.
    Raises SSRFProtectionError if the URL is unsafe.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFProtectionError(
            f"Unsupported scheme '{parsed.scheme}': only http and https are allowed.",
            url=url,
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFProtectionError("Invalid URL: missing hostname.", url=url)

    hostname_lower = hostname.lower()
    if hostname_lower in FORBIDDEN_HOSTS:
        raise SSRFProtectionError(
            f"SSRF blocked: forbidden host '{hostname}'.",
            url=url,
            ip=hostname,
        )

    # Check if host is direct IP literal
    try:
        ip = ipaddress.ip_address(hostname_lower)
        if is_ip_private(str(ip)):
            raise SSRFProtectionError(
                f"SSRF blocked: private IP address '{ip}'.",
                url=url,
                ip=str(ip),
            )
        return url
    except ValueError:
        pass

    # Resolve DNS
    try:
        addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        for entry in addr_info:
            raw_ip = entry[4][0]
            ip_str = str(raw_ip)
            if is_ip_private(ip_str):
                raise SSRFProtectionError(
                    f"SSRF blocked: domain '{hostname}' resolved to private IP '{ip_str}'.",
                    url=url,
                    ip=ip_str,
                )
    except socket.gaierror as exc:
        raise SSRFProtectionError(f"DNS resolution failed for '{hostname}': {exc}", url=url) from exc

    return url
