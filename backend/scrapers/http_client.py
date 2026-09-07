"""SSRF-protected asynchronous HTTP client for web scrapers and external feeds."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.scrapers.ssrf import validate_url_safety

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


_global_client: SafeAsyncClient | None = None


class SafeAsyncClient:
    """HTTP client that enforces SSRF checks across requests and redirects with persistent connection pooling."""

    def __init__(
        self,
        timeout: float = 10.0,
        max_redirects: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_redirects = max_redirects
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily initialize or return the persistent connection pool."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
                headers=DEFAULT_HEADERS,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=30.0),
            )
            self._owns_client = True
        return self._client

    async def close(self) -> None:
        """Close pooled connections gracefully."""
        if self._owns_client and self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> SafeAsyncClient:
        await self._get_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """
        Execute an SSRF-safe GET request, strictly validating each redirect hop using pooled connections.
        """
        # Validate initial URL
        safe_url = validate_url_safety(url)

        req_headers = {**DEFAULT_HEADERS, **(headers or {})}
        client = await self._get_client()

        current_url = safe_url
        for _ in range(self.max_redirects + 1):
            response = await client.get(current_url, headers=req_headers, params=params)

            if response.is_redirect and "location" in response.headers:
                redirect_target = response.headers["location"]
                # Handle relative redirects
                if not redirect_target.startswith(("http://", "https://")):
                    from urllib.parse import urljoin

                    redirect_target = urljoin(current_url, redirect_target)

                # Validate redirect target for SSRF
                current_url = validate_url_safety(redirect_target)
                params = None  # don't re-apply query params on redirect
                continue

            return response

        raise httpx.TooManyRedirects(f"Exceeded max redirects of {self.max_redirects}")


def get_global_safe_client() -> SafeAsyncClient:
    """Retrieve application-scoped persistent SafeAsyncClient singleton."""
    global _global_client
    if _global_client is None:
        _global_client = SafeAsyncClient()
    return _global_client


async def close_global_safe_client() -> None:
    """Close the application-scoped persistent client pool."""
    global _global_client
    if _global_client is not None:
        await _global_client.close()
        _global_client = None


async def safe_fetch_text(url: str, timeout: float = 10.0) -> str:
    """Convenience helper to fetch response text safely."""
    client = SafeAsyncClient(timeout=timeout)
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return str(resp.text)
    finally:
        await client.close()


async def safe_fetch_json(url: str, timeout: float = 10.0) -> Any:
    """Convenience helper to fetch response JSON safely."""
    client = SafeAsyncClient(timeout=timeout)
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
    finally:
        await client.close()
