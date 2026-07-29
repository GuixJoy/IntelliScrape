"""
IntelliScrape
-------------

Intelligent web scraping library that analyzes sites and auto-selects the best approach.

Features:
- Multi-engine architecture (static, playwright_stealth, nodriver, camoufox)
- TLS fingerprint impersonation (JA3/JA4 bypass)
- Browser fingerprint randomization
- Human-like behavioral simulation
- Intelligent site analysis and auto-configuration
- Residential proxy integration (Bright Data, ScraperAPI, Oxylabs, Smartproxy)
- Smart rate limiting (slower for protected sites)
- CAPTCHA detection and solving
- Smart retry with engine fallback
- Anti-bot vendor detection
- Cookie consent handling
- Structured data extraction
- Authentication and session persistence
- Form submission and search
- Auto-pagination
- Data export (JSON, CSV, Excel, SQLite, Markdown)
- File downloads (images, PDFs, documents)
- Request/response interception

Quick Start:
    >>> from intelliscrape import scrape
    >>> text = scrape("https://example.com")

Intelligent Mode (default):
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape()
    >>> # IntelliScrape auto-detects the best approach
    >>> result = scraper.scrape("https://amazon.com")
    >>> # Automatically uses browser engine, residential proxy, slower rate

With Residential Proxies:
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape(brightdata_key="your_key")
    >>> result = scraper.scrape("https://amazon.com")

Analyze Site:
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape()
    >>> analysis = scraper.analyze("https://amazon.com")
    >>> print(f"Site type: {analysis.site_type.value}")
    >>> print(f"Protection: {analysis.protection_level.value}")
    >>> print(f"Recommended engine: {analysis.recommended_engine}")
"""

from .core import IntelliScrape, scrape
from .crawler import crawl, CrawlResult, ScrapeResult
from .intelligent import SiteAnalyzer, SiteAnalysis, SiteType, ProtectionLevel, SmartRateLimiter
from .proxy import (
    ProxyConfig,
    ProxyManager,
    ProxyType,
    ProxyProviderFactory,
    ProxyProviderConfig,
)
from .proxy.manager import IntelligentProxyManager, ProxyProvider
from .session import SessionManager
from .challenges import CaptchaDetector, CaptchaSolver
from .anti_detection import (
    AntiBotDetector,
    AntiBotInfo,
    AntiBotVendor,
    CookieConsentHandler,
)
from .anti_detection.bypass import (
    AntiBotBypassFactory,
    CloudflareTurnstileBypass,
    DataDomeBypass,
    PerimeterXBypass,
    AkamaiBypass,
)
from .extractor.structured import StructuredExtractor, StructuredData
from .async_scraper import AsyncIntelliScrape, scrape_async, scrape_many_async
from .auth import Authenticator, LoginCredentials, AuthSession
from .forms import FormSubmitter, Form, FormField
from .pagination import Paginator, PageInfo
from .export import DataExporter
from .downloader import Downloader, DownloadResult
from .retry import SmartRetry, RetryConfig, RetryAttempt
from .cookies import CookieManager, CookieData
from .interceptor import RequestInterceptor, ResponseModifier, InterceptedRequest, InterceptedResponse
from .ip_manager import IPManager, NaturalRotator, Proxy, ProxyType, IPInfo

__version__ = "2.5.0"

__all__ = [
    # Main API
    "IntelliScrape",
    "scrape",
    # Async API
    "AsyncIntelliScrape",
    "scrape_async",
    "scrape_many_async",
    # Intelligent mode
    "SiteAnalyzer",
    "SiteAnalysis",
    "SiteType",
    "ProtectionLevel",
    "SmartRateLimiter",
    # Crawler
    "crawl",
    "CrawlResult",
    # Proxy
    "ProxyConfig",
    "ProxyManager",
    "ProxyType",
    "ProxyProviderFactory",
    "ProxyProviderConfig",
    "IntelligentProxyManager",
    "ProxyProvider",
    # Session
    "SessionManager",
    # Challenges
    "CaptchaDetector",
    "CaptchaSolver",
    # Anti-bot
    "AntiBotDetector",
    "AntiBotInfo",
    "AntiBotVendor",
    "CookieConsentHandler",
    # Anti-bot bypass
    "AntiBotBypassFactory",
    "CloudflareTurnstileBypass",
    "DataDomeBypass",
    "PerimeterXBypass",
    "AkamaiBypass",
    # Structured data
    "StructuredExtractor",
    "StructuredData",
    # Authentication
    "Authenticator",
    "LoginCredentials",
    "AuthSession",
    # Forms
    "FormSubmitter",
    "Form",
    "FormField",
    # Pagination
    "Paginator",
    "PageInfo",
    # Export
    "DataExporter",
    # Downloads
    "Downloader",
    "DownloadResult",
    # Retry
    "SmartRetry",
    "RetryConfig",
    "RetryAttempt",
    # Cookies
    "CookieManager",
    "CookieData",
    # Interception
    "RequestInterceptor",
    "ResponseModifier",
    "InterceptedRequest",
    "InterceptedResponse",
    # IP Management
    "IPManager",
    "NaturalRotator",
    "Proxy",
    "ProxyType",
    "IPInfo",
    # Re-exports
    "ScrapeResult",
]
