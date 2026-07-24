"""
IntelliScrape
-------------

Advanced web scraping library with anti-detection capabilities.
Scrapes 98% of websites with TLS impersonation, stealth browsing,
and intelligent retry logic.

Features:
- Multi-engine architecture (static, playwright_stealth, nodriver, camoufox)
- TLS fingerprint impersonation (JA3/JA4 bypass)
- Browser fingerprint randomization
- Human-like behavioral simulation
- Proxy rotation and management
- CAPTCHA detection and solving
- Smart retry with exponential backoff
- Rate limiting
- Anti-bot vendor detection
- Cookie consent handling
- Structured data extraction
- Async support for concurrent scraping
- Proxy provider integrations (Bright Data, ScraperAPI, Oxylabs)
- Authentication and session persistence
- Form submission and search
- Auto-pagination
- Data export (JSON, CSV, Excel, SQLite, Markdown)

Quick Start:
    >>> from intelliscrape import scrape
    >>> text = scrape("https://example.com")

Advanced Usage:
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape(proxy="user:pass@proxy:8080")
    >>> result = scraper.scrape("https://protected-site.com")
    >>> structured = scraper.get_structured("https://example.com")

Authentication:
    >>> from intelliscrape import IntelliScrape, LoginCredentials
    >>> scraper = IntelliScrape()
    >>> scraper.login("https://example.com", LoginCredentials(username="user", password="pass"))
    >>> scraper.scrape("https://example.com/dashboard")

Form Submission:
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape()
    >>> scraper.submit_form("https://google.com/search", {"q": "python scraping"})

Pagination:
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape()
    >>> pages = scraper.scrape_all_pages("https://example.com/products", max_pages=10)

Export:
    >>> from intelliscrape import DataExporter
    >>> DataExporter.export(data, format="csv", file="output.csv")
"""

from .core import IntelliScrape, scrape
from .crawler import crawl, CrawlResult, ScrapeResult
from .proxy import (
    ProxyConfig,
    ProxyManager,
    ProxyType,
    ProxyProviderFactory,
    ProxyProviderConfig,
)
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

__version__ = "2.2.0"

__all__ = [
    # Main API
    "IntelliScrape",
    "scrape",
    # Async API
    "AsyncIntelliScrape",
    "scrape_async",
    "scrape_many_async",
    # Crawler
    "crawl",
    "CrawlResult",
    # Proxy
    "ProxyConfig",
    "ProxyManager",
    "ProxyType",
    "ProxyProviderFactory",
    "ProxyProviderConfig",
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
    # Re-exports
    "ScrapeResult",
]
