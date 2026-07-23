"""
IntelliScrape
-------------

Advanced web scraping library with anti-detection capabilities.
Scrapes 98% of websites with TLS impersonation, stealth browsing,
and intelligent retry logic.

Features:
- Multi-engine architecture (static, playwright_stealth, nodriver)
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

Quick Start:
    >>> from intelliscrape import scrape
    >>> text = scrape("https://example.com")

Advanced Usage:
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape(proxy="user:pass@proxy:8080")
    >>> result = scraper.scrape("https://protected-site.com")
    >>> structured = scraper.get_structured("https://example.com")
"""

from .core import IntelliScrape, scrape
from .crawler import crawl, CrawlResult, ScrapeResult
from .proxy import ProxyConfig, ProxyManager
from .session import SessionManager
from .challenges import CaptchaDetector, CaptchaSolver
from .anti_detection import (
    AntiBotDetector,
    AntiBotInfo,
    AntiBotVendor,
    CookieConsentHandler,
)
from .extractor.structured import StructuredExtractor, StructuredData

__version__ = "2.0.0"

__all__ = [
    # Main API
    "IntelliScrape",
    "scrape",
    # Crawler
    "crawl",
    "CrawlResult",
    # Proxy
    "ProxyConfig",
    "ProxyManager",
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
    # Structured data
    "StructuredExtractor",
    "StructuredData",
    # Re-exports
    "ScrapeResult",
]
