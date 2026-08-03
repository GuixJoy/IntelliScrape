"""
core.py

Main pipeline controller for IntelliScrape v3.
Intelligent scraping with auto-detection and smart optimization.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from urllib.parse import urlsplit

from .anti_detection.antibot import AntiBotDetector, AntiBotInfo
from .anti_detection.behavior import HumanBehavior
from .anti_detection.consent import CookieConsentHandler
from .anti_detection.fingerprint import FingerprintGenerator
from .anti_detection.headers import HeaderManager
from .anti_detection.throttle import RateLimitConfig, RetryConfig, SmartThrottle
from .anti_detection.tls import TLSConfig
from .challenges.captcha import CaptchaDetector, CaptchaInfo, CaptchaSolver, CaptchaType
from .cleaner import clean_text
from .engines.base import ScrapeResult
from .engines.playwright_stealth import PlaywrightStealthEngine
from .engines.static import StaticEngine
from .engines.stealth import StealthEngine
from .engines.camoufox import CamoufoxEngine
from .engines.drissionpage import DrissionPageEngine
from .exceptions import IntelliScrapeError
from .extractor import extract_text
from .extractor.structured import StructuredExtractor, StructuredData
from .intelligent import SiteAnalyzer, SiteAnalysis, SmartRateLimiter
from .parser import build_dom
from .proxy import ProxyConfig, ProxyManager
from .proxy.manager import IntelligentProxyManager
from .proxy.free_finder import FreeProxyFinder, IntelligentProxyFinder
from .session import SessionManager
from .downloader import TimeoutType
from .link_checker import LinkCheckReport, check_links as _check_links
from .tech.extractor import TechStack, TechStackExtractor
from .api_detector.extractor import ApiReport, ApiDetector
from .utils import force_dynamic, html_needs_browser


logger = logging.getLogger("intelliscrape")


_ALLOWED_SCHEMES = {"http", "https"}

_CLOUDFLARE_STRONG = [
    "checking your browser", "just a moment", "challenge-platform",
    "cf-browser-verification",
]
_CLOUDFLARE_WEAK = [
    "challenges.cloudflare.com", "cf-turnstile", "challenge.js",
    "enable javascript", "verify you are human",
]

_PERIMETERX_STRONG = [
    "press and hold to confirm", "press & hold to confirm",
    "press hold to confirm", "before we continue", "px-captcha",
    "access to this page has been denied",
]
_PERIMETERX_WEAK = [
    "reference id", "_pxhd", "_pxvid", "_px3",
    "perimeterx", "human security",
]

_AKAMAI_STRONG = ["_abck", "ak_bmsc"]
_AKAMAI_WEAK = ["access denied", "request denied", "akamai"]

_DATADOME_STRONG = ["datadome"]
_DATADOME_WEAK = ["blocked by", "access denied by"]


def _is_cloudflare_blocked(html: str) -> bool:
    """Check if HTML is a Cloudflare challenge page.

    Uses a two-tier approach:
    - Strong markers (only on actual challenge pages): 1 match = blocked
    - Weak markers (can appear in docs/blogs): require 3+ AND page <50KB
      (real challenge pages are tiny, content pages are large)
    """
    if not html:
        return False
    lower = html.lower()
    strong = sum(1 for m in _CLOUDFLARE_STRONG if m in lower)
    if strong >= 1:
        return True
    weak = sum(1 for m in _CLOUDFLARE_WEAK if m in lower)
    if weak >= 3 and len(html) < 50000:
        return True
    return False


def _is_perimeterx_blocked(html: str) -> bool:
    """Check if HTML is a PerimeterX / HUMAN Security challenge page."""
    if not html:
        return False
    lower = html.lower()
    strong = sum(1 for m in _PERIMETERX_STRONG if m in lower)
    if strong >= 1:
        return True
    weak = sum(1 for m in _PERIMETERX_WEAK if m in lower)
    if weak >= 3 and len(html) < 50000:
        return True
    return False


def _is_akamai_blocked(html: str) -> bool:
    """Check if HTML is an Akamai Bot Manager challenge page."""
    if not html:
        return False
    lower = html.lower()
    strong = sum(1 for m in _AKAMAI_STRONG if m in lower)
    if strong >= 1:
        return True
    weak = sum(1 for m in _AKAMAI_WEAK if m in lower)
    if weak >= 3 and len(html) < 50000:
        return True
    return False


def _is_datadome_blocked(html: str) -> bool:
    """Check if HTML is a DataDome challenge page."""
    if not html:
        return False
    lower = html.lower()
    strong = sum(1 for m in _DATADOME_STRONG if m in lower)
    if strong >= 1:
        return True
    weak = sum(1 for m in _DATADOME_WEAK if m in lower)
    if weak >= 3 and len(html) < 50000:
        return True
    return False


def _is_any_antibot_blocked(html: str) -> Optional[str]:
    """Check if HTML is blocked by any anti-bot vendor.

    Returns the vendor name if detected, None otherwise.
    """
    if _is_cloudflare_blocked(html):
        return "cloudflare"
    if _is_perimeterx_blocked(html):
        return "perimeterx"
    if _is_akamai_blocked(html):
        return "akamai"
    if _is_datadome_blocked(html):
        return "datadome"
    return None


class IntelliScrape:
    """Intelligent web scraper with auto-detection.

    This is what makes IntelliScrape truly intelligent:
    - Analyzes the URL and auto-selects the best approach
    - Auto-detects site type and protection level
    - Auto-selects residential vs datacenter proxy
    - Auto-configures rate limiting based on site
    - Auto-chooses the best engine
    - Finds free proxies automatically if none provided

    Features:
    - Multi-strategy engine selection (static, playwright_stealth, camoufox)
    - TLS fingerprint impersonation
    - Browser fingerprint randomization
    - Human-like behavioral simulation
    - Intelligent proxy selection (residential for protected sites)
    - Free proxy finder (automatically finds working proxies)
    - Smart rate limiting (slower for protected sites)
    - CAPTCHA detection and solving
    - Session persistence
    - Anti-bot vendor detection
    - Cookie consent handling
    - Structured data extraction

    Examples
    --------
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape()
    >>> result = scraper.scrape("https://example.com")
    >>> print(result)

    >>> # IntelliScrape auto-detects the best approach
    >>> result = scraper.scrape("https://amazon.com")
    >>> # Automatically uses:
    >>> # - Browser engine (e-commerce needs JS)
    >>> # - Free residential proxy (high protection)
    >>> # - Slower rate limiting (avoid blocks)

    >>> # With paid proxy keys (better quality)
    >>> scraper = IntelliScrape(
    ...     brightdata_key="your_key",
    ...     api_key="your_captcha_key",
    ...     captcha_provider="capsolver"
    ... )
    >>> result = scraper.scrape("https://amazon.com")
    """

    def __init__(
        self,
        *,
        proxy: Optional[Union[ProxyConfig, str, List[str]]] = None,
        proxies: Optional[List[str]] = None,
        brightdata_key: Optional[str] = None,
        scraperapi_key: Optional[str] = None,
        oxylabs_key: Optional[str] = None,
        smartproxy_key: Optional[str] = None,
        prefer_residential: bool = True,
        use_free_proxies: bool = True,
        api_key: Optional[str] = None,
        captcha_provider: Optional[str] = None,
        headless: bool = True,
        simulate_behavior: bool = True,
        manual_captcha: bool = False,
        tls_profile: str = "chrome131",
        session_profile: Optional[str] = None,
        max_retries: int = 3,
        min_delay: float = 0.5,
        max_delay: float = 3.0,
        requests_per_minute: Optional[int] = None,
        intelligent: bool = True,
        log_level: str = "WARNING",
    ):
        """Initialize IntelliScrape.

        Parameters
        ----------
        proxy : ProxyConfig, str, or list, optional
            Single proxy or list of proxies.
        proxies : list, optional
            List of proxy strings (host:port or user:pass@host:port).
        brightdata_key : str, optional
            Bright Data API key for residential proxies.
        scraperapi_key : str, optional
            ScraperAPI key.
        oxylabs_key : str, optional
            Oxylabs API key.
        smartproxy_key : str, optional
            Smartproxy API key.
        prefer_residential : bool
            Prefer residential proxies when available.
        use_free_proxies : bool
            Find and use free proxies if no paid proxies available.
        api_key : str, optional
            API key for CAPTCHA solving service.
        captcha_provider : str, optional
            CAPTCHA solving provider ("2captcha" or "capsolver").
        headless : bool
            Run browser in headless mode.
        simulate_behavior : bool
            Enable human-like behavioral simulation.
        manual_captcha : bool
            When a CAPTCHA is detected, open a visible browser window
            and wait for the user to solve it manually, then continue.
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
        intelligent : bool
            Enable intelligent auto-detection (default: True).
        log_level : str
            Logging level.
        """
        # Configure logging
        logging.basicConfig(level=getattr(logging, log_level.upper()))
        self.logger = logging.getLogger("intelliscrape")

        # Initialize intelligent analyzer
        self.intelligent = intelligent
        self.site_analyzer = SiteAnalyzer()
        self._rate_limiters: Dict[str, SmartRateLimiter] = {}

        # Initialize free proxy finder
        self.use_free_proxies = use_free_proxies
        self.free_proxy_finder = FreeProxyFinder()
        self._free_proxies_fetched = False

        # Initialize proxy manager with intelligent selection
        self.proxy_manager = ProxyManager()
        self.intelligent_proxy = IntelligentProxyManager(
            user_proxies=proxies,
            brightdata_key=brightdata_key,
            scraperapi_key=scraperapi_key,
            oxylabs_key=oxylabs_key,
            smartproxy_key=smartproxy_key,
            prefer_residential=prefer_residential,
        )

        # Store provider keys for intelligent proxy finder
        self._brightdata_key = brightdata_key
        self._scraperapi_key = scraperapi_key
        self._oxylabs_key = oxylabs_key
        self._smartproxy_key = smartproxy_key

        # Add user proxies
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
            "drissionpage": DrissionPageEngine(
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
        self.manual_captcha = manual_captcha

    def analyze(self, url: str) -> SiteAnalysis:
        """Analyze a URL and return recommendations.
        
        Parameters
        ----------
        url : str
            URL to analyze.
            
        Returns
        -------
        SiteAnalysis
            Analysis with recommendations.
        """
        return self.site_analyzer.analyze(url)

    def _fetch_free_proxies(self) -> None:
        """Fetch free proxies if needed."""
        if self._free_proxies_fetched:
            return
        
        if self.use_free_proxies:
            print("Finding free proxies (this may take a moment)...")
            self.free_proxy_finder.find_proxies(
                protocol="https",
                test=True,
                max_workers=10,
            )
            self._free_proxies_fetched = True

    def _get_intelligent_proxy(self, url: str) -> Optional[str]:
        """Get proxy for URL using intelligent selection."""
        # Check if we need a proxy for this site
        analysis = self.site_analyzer.analyze(url)
        
        if not analysis.requires_residential_proxy:
            # Site doesn't need proxy, try without
            return None
        
        # Try paid providers first
        paid_proxy = self.intelligent_proxy.get_proxy_for_url(url)
        if paid_proxy:
            return paid_proxy.url
        
        # Fall back to free proxies
        if self.use_free_proxies:
            self._fetch_free_proxies()
            proxy = self.free_proxy_finder.get_best_proxy()
            if proxy:
                return proxy.url
        
        return None

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
        intelligent: Optional[bool] = None,
        on_progress=None,
        **kwargs,
    ) -> Union[str, StructuredData]:
        """Scrape a URL and return text content.

        Parameters
        ----------
        url : str
            Target URL.
        engine : str, optional
            Force a specific engine ("static", "playwright_stealth", "camoufox").
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
        intelligent : bool, optional
            Override intelligent mode for this scrape.

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

        # Analyze site if intelligent mode is enabled
        use_intelligent = intelligent if intelligent is not None else self.intelligent
        if use_intelligent:
            analysis = self.site_analyzer.analyze(url)
            self.logger.info(f"Site analysis: {analysis.site_type.value} | Protection: {analysis.protection_level.value}")
            
            # Intelligent mode: analysis done, but don't force a single engine
            # The fallback chain in _fetch() will try all engines
            pass
            
            # Auto-configure rate limiting
            if url not in self._rate_limiters:
                self._rate_limiters[url] = SmartRateLimiter(analysis)
            
            # Wait if needed (intelligent rate limiting)
            self._rate_limiters[url].wait_if_needed()
            
            # Get intelligent proxy
            proxy_url = self._get_intelligent_proxy(url)
            if proxy_url:
                self.logger.info(f"Using intelligent proxy: {proxy_url}")
                # TODO: Apply proxy to engines
        
        # Force browser engine for known JS-heavy sites
        if force_browser and not engine:
            if force_dynamic(url):
                engine = "playwright_stealth"

        # Inject session cookies if available (from --login)
        session_cookies = self.session_manager.get_cookies()
        if session_cookies and "cookies" not in kwargs:
            kwargs["cookies"] = session_cookies

        # Inject auth token if available (SPA/Firebase auth)
        auth_token = self.session_manager.get_auth_token()
        if auth_token and "headers" not in kwargs:
            kwargs["headers"] = {"Authorization": f"Bearer {auth_token}"}
        elif auth_token and "headers" in kwargs:
            kwargs["headers"]["Authorization"] = f"Bearer {auth_token}"

        # Get result
        result = self._fetch(url, engine=engine, on_progress=on_progress, **kwargs)

        if not result.success:
            if use_intelligent and url in self._rate_limiters:
                self._rate_limiters[url].report_failure()
            raise IntelliScrapeError(f"Scraping failed: {result.error}")
        
        if use_intelligent and url in self._rate_limiters:
            self._rate_limiters[url].report_success()

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
                # Strip consent elements from static HTML results
                if consent_info.accept_button_selector:
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(result.html, "html.parser")
                        # Remove common consent overlay elements
                        for selector in ["[id*='cookie']", "[class*='cookie-consent']",
                                          "[id*='consent']", "[class*='consent-banner']"]:
                            for el in soup.select(selector):
                                el.decompose()
                        result.html = str(soup)
                    except Exception:
                        pass

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
        intelligent: Optional[bool] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently with rate limiting.

        Returns list of dicts with 'url', 'content', 'success', 'error'.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _scrape_one(url):
            try:
                content = self.scrape(url, engine=engine, intelligent=intelligent, **kwargs)
                return {"url": url, "content": content, "success": True, "error": None}
            except Exception as exc:
                return {"url": url, "content": "", "success": False, "error": str(exc)}

        results = []
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_url = {executor.submit(_scrape_one, url): url for url in urls}
            for future in as_completed(future_to_url):
                results.append(future.result())

        # Preserve original URL order
        url_order = {url: i for i, url in enumerate(urls)}
        results.sort(key=lambda r: url_order.get(r["url"], 0))
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
        on_progress=None,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL using the appropriate engine with fallback chain."""
        from .progress import ProgressTracker, ScrapeProgress
        from .challenges.manual import ManualCaptchaSolver

        tracker = ProgressTracker(on_progress=on_progress, url=url)
        total = len(self.engines)
        engine_order = ["static", "playwright_stealth", "camoufox", "nodriver", "drissionpage"]

        # If specific engine requested, use only that
        if engine and engine in self.engines:
            tracker.engine_trying(engine, 1, 1)
            result = self._fetch_with_engine(url, engine, **kwargs)
            if result.success:
                tracker.engine_success(engine, 1, 1)
                return self._handle_manual_captcha(url, result, tracker)
            else:
                tracker.engine_failed(engine, result.error or "unknown", 1, 1)
                raise IntelliScrapeError(f"Engine {engine} failed: {result.error}")

        # Auto-detect: try engines in order with fallback
        last_result = None
        attempt_timeout = 30  # 30s per engine attempt

        for i, engine_name in enumerate(engine_order):
            tracker.engine_trying(engine_name, i + 1, total)

            # Pass proxy to engine if available
            fetch_kwargs = dict(kwargs)
            fetch_kwargs["timeout"] = attempt_timeout
            proxy_cfg = self.proxy_manager.get_proxy()
            if proxy_cfg and "proxy" not in fetch_kwargs:
                fetch_kwargs["proxy"] = proxy_cfg

            result = self._fetch_with_engine(url, engine_name, **fetch_kwargs)
            last_result = result

            if result.success:
                # Check for any anti-bot challenge (Cloudflare, PerimeterX, Akamai, DataDome)
                blocked_vendor = _is_any_antibot_blocked(result.html)
                if blocked_vendor:
                    tracker.engine_blocked(engine_name, blocked_vendor, i + 1, total)
                    # Try manual CAPTCHA solve
                    solver = ManualCaptchaSolver()
                    solved = solver.solve_if_detected(url, result.html, self.session_manager.get_cookies())
                    if solved.solved:
                        tracker.engine_solved(engine_name, f"{blocked_vendor}_challenge")
                        # Re-fetch with solved cookies
                        fetch_kwargs["cookies"] = solved.cookies
                        result = self._fetch_with_engine(url, engine_name, **fetch_kwargs)
                        if result.success and not html_needs_browser(result.html):
                            tracker.engine_success(engine_name, i + 1, total)
                            return result

                # Check for other CAPTCHAs
                captcha_info = CaptchaDetector.detect(result.html, url)
                if captcha_info:
                    tracker.engine_captcha(engine_name, captcha_info.captcha_type.value, i + 1, total)
                    solver = ManualCaptchaSolver()
                    solved = solver.solve(url, captcha_info, self.session_manager.get_cookies())
                    if solved.solved:
                        tracker.engine_solved(engine_name, captcha_info.captcha_type.value)
                        fetch_kwargs["cookies"] = solved.cookies
                        result = self._fetch_with_engine(url, engine_name, **fetch_kwargs)

                # Check if we got meaningful content
                if result.success and not html_needs_browser(result.html):
                    tracker.engine_success(engine_name, i + 1, total)
                    return self._handle_manual_captcha(url, result, tracker)

                # Content needs browser, try next engine
                tracker.engine_js_only(engine_name, i + 1, total)
                continue

            tracker.engine_failed(engine_name, result.error or "unknown", i + 1, total)
            continue

        # All engines failed or returned JS-only content
        if last_result and last_result.success:
            return self._handle_manual_captcha(url, last_result, tracker)

        tracker.all_failed()
        raise IntelliScrapeError(f"All engines failed for {url}")

    def _handle_manual_captcha(self, url: str, result: ScrapeResult, tracker=None) -> ScrapeResult:
        """Check for CAPTCHA and wait for manual solving if enabled."""
        if not self.manual_captcha:
            return result

        captcha_info = CaptchaDetector.detect(result.html, url)

        # Also check for anti-bot challenges (Cloudflare, PerimeterX, etc.)
        if captcha_info is None:
            blocked_vendor = _is_any_antibot_blocked(result.html)
            if blocked_vendor:
                captcha_info = CaptchaInfo(
                    captcha_type=CaptchaType.TURNSTILE,
                    page_url=url,
                )

        if captcha_info is None:
            return result

        if tracker:
            tracker.engine_captcha(result.engine, captcha_info.captcha_type.value,
                                   tracker._last_report.attempt if tracker._last_report else 0,
                                   tracker._last_report.total_attempts if tracker._last_report else 0)

        self.logger.info(f"CAPTCHA detected ({captcha_info.captcha_type.value}), waiting for manual solve")
        return self._wait_for_manual_captcha(url, captcha_info)

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
                engine=engine_name,
                success=False,
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

    def check_links(
        self,
        url: str,
        *,
        timeout: TimeoutType | None = None,
        ignore_external: bool = False,
        max_workers: int = 10,
        allowed_statuses: Sequence[int] | None = None,
        log: Callable[[str], None] | None = None,
    ) -> LinkCheckReport:
        """Check all links on a page and return a full report.

        Parameters
        ----------
        url : str
            The page URL whose links should be verified.
        timeout : int or float, optional
            Per-request timeout in seconds (default 5).
        ignore_external : bool
            When *True* only links on the same host are checked.
        max_workers : int
            Number of concurrent threads used for checking (default 10).
        allowed_statuses : sequence of int, optional
            HTTP status codes considered "OK" (default 200-399).
        log : callable, optional
            Receives progress messages.

        Returns
        -------
        LinkCheckReport
            Report with per-link results and summary statistics.
        """
        return _check_links(
            url,
            timeout=timeout,
            ignore_external=ignore_external,
            max_workers=max_workers,
            allowed_statuses=allowed_statuses,
            log=log,
        )

    def detect_tech(
        self,
        url: str,
        *,
        force_browser: bool = False,
        engine: Optional[str] = None,
    ) -> TechStack:
        """Detect the technology stack of a website.

        Parameters
        ----------
        url : str
            Target URL.
        force_browser : bool
            Force browser engine for JS-heavy sites.
        engine : str, optional
            Force a specific engine.

        Returns
        -------
        TechStack
            Detected frameworks, CSS, analytics, CDN, hosting, CMS,
            payment providers, languages, and more.
        """
        result = self._fetch(url, engine=engine, force_browser=force_browser)
        if not result.success:
            raise IntelliScrapeError(f"Failed to fetch {url}: {result.error}")
        return TechStackExtractor.extract(
            html=result.html,
            headers=result.headers,
            cookies=result.cookies,
            url=url,
        )

    def detect_apis(
        self,
        url: str,
        *,
        force_browser: bool = False,
        engine: Optional[str] = None,
    ) -> ApiReport:
        """Detect API endpoints, third-party services, and key exposures.

        Parameters
        ----------
        url : str
            Target URL.
        force_browser : bool
            Force browser engine for JS-heavy sites.
        engine : str, optional
            Force a specific engine.

        Returns
        -------
        ApiReport
            Detected REST/GraphQL/WebSocket endpoints, API documentation,
            third-party services, and exposed API keys.
        """
        result = self._fetch(url, engine=engine, force_browser=force_browser)
        if not result.success:
            raise IntelliScrapeError(f"Failed to fetch {url}: {result.error}")
        return ApiDetector.extract(
            html=result.html,
            headers=result.headers,
            url=url,
        )

    def _wait_for_manual_captcha(self, url: str, captcha_info: CaptchaInfo) -> ScrapeResult:
        """Open a visible browser and wait for the user to solve a CAPTCHA.

        Parameters
        ----------
        url : str
            The URL that contains the CAPTCHA.
        captcha_info : CaptchaInfo
            Information about the detected CAPTCHA.

        Returns
        -------
        ScrapeResult
            The re-fetched result after the user solves the CAPTCHA.
        """
        from rich.console import Console as RichConsole

        _console = RichConsole()
        _console.print(
            f"\n[yellow]CAPTCHA detected: {captcha_info.captcha_type.value}[/yellow]"
        )
        _console.print(
            "[bold]A browser window will open. Solve the CAPTCHA in the browser, "
            "then press Enter here to continue...[/bold]\n"
        )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            _console.print(
                "[red]Playwright is required for manual CAPTCHA solving. "
                "Run: pip install playwright && playwright install chromium[/red]"
            )
            return ScrapeResult(
                url=url, html="", status_code=0,
                engine="manual_captcha", success=False,
                error="Playwright not installed",
            )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--window-size=1920,1080",
                    ],
                )

                fp = self.fingerprint_gen.generate()
                context = browser.new_context(
                    viewport={"width": fp.viewport_width, "height": fp.viewport_height},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    locale=fp.language,
                    timezone_id=fp.timezone,
                )

                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)

                # Wait for user to solve CAPTCHA
                input("Press Enter after solving the CAPTCHA...")

                html = page.content()
                status_code = 200

                new_cookies = {}
                for cookie in context.cookies():
                    new_cookies[cookie["name"]] = cookie["value"]

                browser.close()

                _console.print("[green]CAPTCHA solved! Continuing...[/green]\n")

                return ScrapeResult(
                    url=url,
                    html=html,
                    status_code=status_code,
                    cookies=new_cookies,
                    engine="manual_captcha",
                    success=True,
                )

        except Exception as exc:
            _console.print(f"[red]Manual CAPTCHA failed: {exc}[/red]")
            return ScrapeResult(
                url=url, html="", status_code=0,
                engine="manual_captcha", success=False,
                error=str(exc),
            )

    def get_proxy_status(self) -> Dict:
        """Get proxy manager status."""
        return self.intelligent_proxy.get_status()

    def find_free_proxies(self, test: bool = True) -> List[Dict]:
        """Find and test free proxies.
        
        Parameters
        ----------
        test : bool
            Test proxies before returning.
            
        Returns
        -------
        List[Dict]
            List of working proxies.
        """
        self._fetch_free_proxies()
        
        return [
            {
                "url": p.url,
                "host": p.host,
                "port": p.port,
                "protocol": p.protocol,
                "speed": p.speed,
                "is_working": p.is_working,
            }
            for p in self.free_proxy_finder._working_proxies
        ]


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
