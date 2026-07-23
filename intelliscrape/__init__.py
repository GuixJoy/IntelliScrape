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

Quick Start:
    >>> from intelliscrape import scrape
    >>> text = scrape("https://example.com")

Advanced Usage:
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape(proxy="user:pass@proxy:8080")
    >>> result = scraper.scrape("https://protected-site.com")
    >>> structured = scraper.get_structured("https://example.com")

Async Usage:
    >>> import asyncio
    >>> from intelliscrape import AsyncIntelliScrape
    >>> 
    >>> async def main():
    ...     async with AsyncIntelliScrape() as scraper:
    ...         results = await scraper.scrape_many(urls)
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

__version__ = "2.1.0"

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
    # Re-exports
    "ScrapeResult",
]
