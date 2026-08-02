"""Static HTML engine using curl_cffi for TLS fingerprint impersonation."""

from __future__ import annotations

from typing import Dict, Optional

from ..anti_detection.headers import HeaderManager
from ..anti_detection.tls import TLSConfig
from ..proxy import ProxyConfig
from .base import BaseEngine, ScrapeResult


class HTTPStatusError(Exception):
    """Raised when server returns a retryable HTTP status code."""

    def __init__(self, status_code: int, url: str):
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} from {url}")


class StaticEngine(BaseEngine):
    """Static HTML downloader with TLS impersonation.

    Uses curl_cffi to impersonate real browser TLS fingerprints,
    bypassing JA3/JA4 fingerprint detection.
    """

    def __init__(
        self,
        *,
        tls_profile: Optional[TLSConfig] = None,
        header_manager: Optional[HeaderManager] = None,
        proxy: Optional[ProxyConfig] = None,
    ):
        self.tls_config = tls_profile or TLSConfig(impersonate="chrome131")
        self.header_manager = header_manager or HeaderManager()
        self.proxy = proxy

    @property
    def name(self) -> str:
        return "curl_cffi"

    def is_available(self) -> bool:
        try:
            import curl_cffi
            return True
        except ImportError:
            return False

    def fetch(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        impersonate: Optional[str] = None,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL with TLS impersonation."""
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            return ScrapeResult(
                url=url,
                html="",
                status_code=0,
                engine=self.name,
                success=False,
                error="curl_cffi not installed. Run: pip install curl_cffi",
            )

        try:
            # Get headers
            request_headers = headers or self.header_manager.get_headers()

            # Get TLS profile
            profile = impersonate or self.tls_config.get_profile()

            # Build proxy dict
            proxy_dict = None
            if self.proxy:
                proxy_dict = self.proxy.dict

            # Make request with TLS impersonation
            response = cffi_requests.get(
                url,
                headers=request_headers,
                cookies=cookies,
                timeout=timeout,
                impersonate=profile,
                proxies=proxy_dict,
                allow_redirects=True,
                verify=False,
            )

            # Raise for retryable status codes so SmartRetry can handle them
            if response.status_code in (429, 500, 502, 503, 504):
                raise HTTPStatusError(response.status_code, url)

            return ScrapeResult(
                url=str(response.url),
                html=response.text,
                status_code=response.status_code,
                headers=dict(response.headers),
                cookies=dict(response.cookies),
                engine=self.name,
                success=True,
                redirect_url=str(response.url) if str(response.url) != url else None,
            )

        except Exception as exc:
            return ScrapeResult(
                url=url,
                html="",
                status_code=0,
                engine=self.name,
                success=False,
                error=str(exc),
            )
