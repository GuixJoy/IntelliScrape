"""
core.py

Main pipeline controller for IntelliScrape v2.
Multi-strategy scraping with anti-detection capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlsplit

from .anti_detection.antibot import AntiBotDetector, AntiBotInfo
from .anti_detection.behavior import HumanBehavior
from .anti_detection.consent import CookieConsentHandler
from .anti_detection.fingerprint import FingerprintGenerator
from .anti_detection.headers import HeaderManager
from .anti_detection.throttle import RateLimitConfig, RetryConfig, SmartThrottle
from .anti_detection.tls import TLSConfig
from .challenges.captcha import CaptchaDetector, CaptchaInfo, CaptchaSolver
from .cleaner import clean_text
from .engines.base import ScrapeResult
from .engines.playwright_stealth import PlaywrightStealthEngine
from .engines.static import StaticEngine
from .engines.stealth import StealthEngine
from .engines.camoufox import CamoufoxEngine
from .exceptions import IntelliScrapeError
from .extractor import extract_text
from .extractor.structured import StructuredExtractor, StructuredData
from .parser import build_dom
from .proxy import ProxyConfig, ProxyManager
from .session import SessionManager
from .utils import force_dynamic, html_needs_browser


logger = logging.getLogger("intelliscrape")


_ALLOWED_SCHEMES = {"http", "https"}


class IntelliScrape:
    """Advanced web scraper with anti-detection capabilities.

    Features:
    - Multi-strategy engine selection (static, playwright_stealth, nodriver)
    - TLS fingerprint impersonation
    - Browser fingerprint randomization
    - Human-like behavioral simulation
    - Proxy rotation support
    - CAPTCHA detection and solving
    - Session persistence
    - Smart retry with exponential backoff
    - Rate limiting
    - Anti-bot vendor detection
    - Cookie consent handling
    - Structured data extraction

    Examples
    --------
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape()
    >>> result = scraper.scrape("https://example.com")
    >>> print(result)

    >>> # With proxy and CAPTCHA solving
    >>> scraper = IntelliScrape(
    ...     proxy="user:pass@proxy:8080",
    ...     api_key="your_api_key",
    ...     captcha_provider="capsolver"
    ... )
    >>> result = scraper.scrape("https://protected-site.com")
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
        max_retries: int = 3,
        min_delay: float = 0.5,
        max_delay: float = 3.0,
        requests_per_minute: Optional[int] = None,
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
        max_retries : int
            Maximum number of retries.
        min_delay : float
            Minimum delay between requests (seconds).
        max_delay : float
            Maximum delay between requests (seconds).
        requests_per_minute : int, optional
            Rate limit (requests per minute).
        log_level : str
            Logging level.
        """
        # Configure logging
        logging.basicConfig(level=getattr(logging, log_level.upper()))
        self.logger = logging.getLogger("intelliscrape")

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

        # Initialize throttle
        self.throttle = SmartThrottle(
            retry_config=RetryConfig(max_retries=max_retries),
            rate_config=RateLimitConfig(
                min_delay=min_delay,
                max_delay=max_delay,
                requests_per_minute=requests_per_minute,
            ),
        )

        # Get proxy for engines
        proxy_config = self.proxy_manager.get_proxy()

        # Initialize engines (in order of preference)
        self.engines = {
            "static": StaticEngine(
                tls_profile=self.tls_config,
                header_manager=self.header_manager,
                proxy=proxy_config,
            ),
            "playwright_stealth": PlaywrightStealthEngine(
                fingerprint_generator=self.fingerprint_gen,
                proxy=proxy_config,
                headless=headless,
                simulate_behavior=simulate_behavior,
            ),
            "nodriver": StealthEngine(
                fingerprint_generator=self.fingerprint_gen,
                proxy=proxy_config,
                headless=headless,
                simulate_behavior=simulate_behavior,
            ),
            "camoufox": CamoufoxEngine(
                fingerprint_generator=self.fingerprint_gen,
                proxy=proxy_config,
                headless=headless,
                simulate_behavior=simulate_behavior,
            ),
        }

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

        self.headless = headless
        self.simulate_behavior = simulate_behavior

    def scrape(
        self,
        url: str,
        *,
        engine: Optional[str] = None,
        extract: bool = True,
        clean: bool = True,
        return_raw: bool = False,
        return_structured: bool = False,
        handle_consent: bool = True,
        force_browser: bool = False,
        **kwargs,
    ) -> Union[str, StructuredData]:
        """Scrape a URL and return text content.

        Parameters
        ----------
        url : str
            Target URL.
        engine : str, optional
            Force a specific engine ("static", "playwright_stealth", "nodriver").
            If None, auto-detect.
        extract : bool
            Extract text content from HTML.
        clean : bool
            Clean extracted text.
        return_raw : bool
            Return raw HTML instead of extracted text.
        return_structured : bool
            Return StructuredData object with all metadata.
        handle_consent : bool
            Attempt to handle cookie consent banners.
        force_browser : bool
            Force using browser engine for JS-heavy sites.

        Returns
        -------
        str or StructuredData
            Extracted content.
        """
        if not url:
            raise IntelliScrapeError("URL is required")

        parsed = urlsplit(url)
        if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
            raise IntelliScrapeError("Only http/https URLs are supported")

        # Force browser engine for known JS-heavy sites
        if force_browser and not engine:
            if force_dynamic(url):
                engine = "playwright_stealth"

        # Get result
        result = self._fetch(url, engine=engine, **kwargs)

        if not result.success:
            raise IntelliScrapeError(f"Scraping failed: {result.error}")

        # Detect anti-bot
        antibot_info = AntiBotDetector.detect(
            html=result.html,
            headers=result.headers,
            cookies=result.cookies,
        )
        if antibot_info:
            self.logger.info(f"Anti-bot detected: {antibot_info.vendor.value} (confidence: {antibot_info.confidence:.2f})")

        # Handle cookie consent
        if handle_consent and result.html:
            consent_info = CookieConsentHandler.detect(result.html)
            if consent_info.has_consent:
                self.logger.info(f"Cookie consent detected: {consent_info.consent_type}")

        if return_structured:
            return StructuredExtractor.extract(result.html, url)

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
        max_concurrent: int = 5,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Scrape multiple URLs with rate limiting.

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

            # Rate limiting
            self.throttle.rate_limiter.wait_if_needed()

        return results

    def get_structured(self, url: str, **kwargs) -> StructuredData:
        """Get structured data from a URL.

        Returns StructuredData with title, description, meta tags, JSON-LD, etc.
        """
        return self.scrape(url, return_structured=True, **kwargs)

    def _fetch(
        self,
        url: str,
        *,
        engine: Optional[str] = None,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL using the appropriate engine with fallback chain."""
        
        # If specific engine requested, use only that
        if engine and engine in self.engines:
            result = self._fetch_with_engine(url, engine, **kwargs)
            if result.success:
                return result
            raise IntelliScrapeError(f"Engine {engine} failed: {result.error}")

        # Auto-detect: try engines in order with fallback
        engine_order = ["static", "playwright_stealth", "camoufox", "nodriver"]
        last_result = None

        for engine_name in engine_order:
            self.logger.info(f"Trying engine: {engine_name}")
            
            result = self._fetch_with_engine(url, engine_name, **kwargs)
            last_result = result
            
            if result.success:
                # Check if we got meaningful content
                if not html_needs_browser(result.html):
                    self.logger.info(f"Success with engine: {engine_name}")
                    return result
                
                # Content needs browser, try next engine
                self.logger.info(f"Engine {engine_name} returned JS-only content, trying next...")
                continue
            
            self.logger.info(f"Engine {engine_name} failed: {result.error}")
            continue

        # All engines failed or returned JS-only content
        if last_result and last_result.success:
            # We got some content, return it
            return last_result
        
        raise IntelliScrapeError(f"All engines failed for {url}")

    def _fetch_with_engine(self, url: str, engine_name: str, **kwargs) -> ScrapeResult:
        """Fetch using a specific engine with retry."""
        engine = self.engines.get(engine_name)
        if not engine:
            return ScrapeResult(
                url=url, html="", status_code=0,
                engine=engine_name, success=False,
                error=f"Engine {engine_name} not available",
            )

        if not engine.is_available():
            return ScrapeResult(
                url=url, html="", status_code=0,
                engine=engine_name, success=False,
                error=f"Engine {engine_name} dependencies not installed",
            )

        def fetch():
            return engine.fetch(url, **kwargs)

        try:
            result = self.throttle.execute(fetch)
            return result
        except Exception as exc:
            self.logger.debug(f"Engine {engine_name} exception: {exc}")
            return ScrapeResult(
                url=url, html="", status_code=0,
                engine=engine_name, success=False,
                error=str(exc),
            )

    def check_captcha(self, url: str) -> Optional[CaptchaInfo]:
        """Check if a URL has a CAPTCHA."""
        result = self._fetch(url)
        if result.success:
            return CaptchaDetector.detect(result.html, url)
        return None

    def check_antibot(self, url: str) -> Optional[AntiBotInfo]:
        """Check anti-bot protection on a URL."""
        result = self._fetch(url)
        if result.success:
            return AntiBotDetector.detect(
                html=result.html,
                headers=result.headers,
                cookies=result.cookies,
            )
        return None


def scrape(url: str, **kwargs) -> str:
    """Quick scrape function.

    This is the simple API for quick scraping.
    For advanced features, use the IntelliScrape class.

    Examples
    --------
    >>> from intelliscrape import scrape
    >>> text = scrape("https://example.com")
    >>> print(text)
    """
    scraper = IntelliScrape()
    return scraper.scrape(url, **kwargs)
