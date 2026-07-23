"""
core.py

Main pipeline controller for IntelliScrape v2.
Multi-strategy scraping with anti-detection capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlsplit

from .anti_detection.fingerprint import FingerprintGenerator
from .anti_detection.headers import HeaderManager
from .anti_detection.tls import TLSConfig
from .challenges.captcha import CaptchaDetector, CaptchaInfo, CaptchaSolver
from .cleaner import clean_text
from .engines.base import ScrapeResult
from .engines.static import StaticEngine
from .engines.stealth import StealthEngine
from .exceptions import IntelliScrapeError
from .extractor import extract_text
from .parser import build_dom
from .proxy import ProxyConfig, ProxyManager
from .session import SessionManager
from .utils import force_dynamic, html_needs_browser


logger = logging.getLogger("intelliscrape")


_ALLOWED_SCHEMES = {"http", "https"}


class IntelliScrape:
    """Advanced web scraper with anti-detection capabilities.

    Features:
    - Multi-strategy engine selection (static + stealth browser)
    - TLS fingerprint impersonation
    - Browser fingerprint randomization
    - Human-like behavioral simulation
    - Proxy rotation support
    - CAPTCHA detection and solving
    - Session persistence

    Examples
    --------
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape()
    >>> result = scraper.scrape("https://example.com")
    >>> print(result)
    """

    def __init__(
        self,
        *,
        proxy: Optional[Union[ProxyConfig, str, List[str]]] = None,
        proxies: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        captcha_provider: Optional[str] = None,
        headless: bool = True,
        simulate_behavior: bool = True,
        tls_profile: str = "chrome131",
        session_profile: Optional[str] = None,
        log_level: str = "WARNING",
    ):
        """Initialize IntelliScrape.

        Parameters
        ----------
        proxy : ProxyConfig, str, or list, optional
            Single proxy or list of proxies.
        proxies : list, optional
            List of proxy strings (host:port or user:pass@host:port).
        api_key : str, optional
            API key for CAPTCHA solving service.
        captcha_provider : str, optional
            CAPTCHA solving provider ("2captcha" or "capsolver").
        headless : bool
            Run browser in headless mode.
        simulate_behavior : bool
            Enable human-like behavioral simulation.
        tls_profile : str
            TLS fingerprint profile to impersonate.
        session_profile : str, optional
            Persistent session profile name.
        log_level : str
            Logging level.
        """
        # Configure logging
        logging.basicConfig(level=getattr(logging, log_level.upper()))

        # Initialize proxy manager
        self.proxy_manager = ProxyManager()
        if proxy:
            if isinstance(proxy, ProxyConfig):
                self.proxy_manager.add_proxy(proxy)
            elif isinstance(proxy, str):
                self.proxy_manager.add_from_string(proxy)
            elif isinstance(proxy, list):
                self.proxy_manager.add_from_list(proxy)
        if proxies:
            self.proxy_manager.add_from_list(proxies)

        # Initialize anti-detection
        self.header_manager = HeaderManager()
        self.tls_config = TLSConfig(impersonate=tls_profile, randomize=True)
        self.fingerprint_gen = FingerprintGenerator()

        # Initialize engines
        self.static_engine = StaticEngine(
            tls_profile=self.tls_config,
            header_manager=self.header_manager,
        )
        self.stealth_engine = StealthEngine(
            fingerprint_generator=self.fingerprint_gen,
            headless=headless,
            simulate_behavior=simulate_behavior,
        )

        # Initialize CAPTCHA solver
        self.captcha_solver = None
        if api_key and captcha_provider:
            self.captcha_solver = CaptchaSolver(
                provider=captcha_provider,
                api_key=api_key,
            )

        # Initialize session manager
        self.session_manager = SessionManager()
        if session_profile:
            self.session_manager.set_current_profile(session_profile)

    def scrape(
        self,
        url: str,
        *,
        engine: Optional[str] = None,
        extract: bool = True,
        clean: bool = True,
        return_raw: bool = False,
        **kwargs,
    ) -> str:
        """Scrape a URL and return text content.

        Parameters
        ----------
        url : str
            Target URL.
        engine : str, optional
            Force a specific engine ("static" or "stealth").
            If None, auto-detect.
        extract : bool
            Extract text content from HTML.
        clean : bool
            Clean extracted text.
        return_raw : bool
            Return raw HTML instead of extracted text.

        Returns
        -------
        str
            Extracted and cleaned text content.
        """
        if not url:
            raise IntelliScrapeError("URL is required")

        parsed = urlsplit(url)
        if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
            raise IntelliScrapeError("Only http/https URLs are supported")

        # Get result
        result = self._fetch(url, engine=engine, **kwargs)

        if not result.success:
            raise IntelliScrapeError(f"Scraping failed: {result.error}")

        if return_raw:
            return result.html

        if not extract:
            return result.html

        # Parse and extract
        try:
            dom = build_dom(result.html)
            text = extract_text(dom)

            if clean:
                text = clean_text(text)

            return text

        except Exception as exc:
            raise IntelliScrapeError(f"Extraction failed: {exc}") from exc

    def scrape_many(
        self,
        urls: List[str],
        *,
        engine: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Scrape multiple URLs.

        Returns list of dicts with 'url', 'content', 'success', 'error'.
        """
        results = []
        for url in urls:
            try:
                content = self.scrape(url, engine=engine, **kwargs)
                results.append({
                    "url": url,
                    "content": content,
                    "success": True,
                    "error": None,
                })
            except Exception as exc:
                results.append({
                    "url": url,
                    "content": "",
                    "success": False,
                    "error": str(exc),
                })
        return results

    def _fetch(
        self,
        url: str,
        *,
        engine: Optional[str] = None,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL using the appropriate engine."""
        if engine == "static":
            return self.static_engine.fetch(url, **kwargs)
        elif engine == "stealth":
            return self.stealth_engine.fetch(url, **kwargs)

        # Auto-detect: try static first, fallback to stealth
        result = self.static_engine.fetch(url, **kwargs)

        if result.success:
            # Check if we got meaningful content
            if html_needs_browser(result.html):
                logger.info("Static fetch returned JS-heavy content, switching to stealth")
                result = self.stealth_engine.fetch(url, **kwargs)
        else:
            # Static failed, try stealth
            logger.info("Static fetch failed, trying stealth engine")
            result = self.stealth_engine.fetch(url, **kwargs)

        return result

    def check_captcha(self, url: str) -> Optional[CaptchaInfo]:
        """Check if a URL has a CAPTCHA."""
        result = self._fetch(url)
        if result.success:
            return CaptchaDetector.detect(result.html, url)
        return None


def scrape(url: str, **kwargs) -> str:
    """Quick scrape function.

    This is the simple API for quick scraping.
    For advanced features, use the IntelliScrape class.
    """
    scraper = IntelliScrape()
    return scraper.scrape(url, **kwargs)
