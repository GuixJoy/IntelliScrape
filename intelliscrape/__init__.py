"""
IntelliScrape
-------------

Smart web scraping library with anti-detection capabilities.
Automatically chooses between static and dynamic scraping,
with TLS impersonation, browser stealth, and CAPTCHA solving.
"""

from .core import IntelliScrape, scrape
from .crawler import crawl, CrawlResult, ScrapeResult
from .proxy import ProxyConfig, ProxyManager
from .session import SessionManager
from .challenges import CaptchaDetector, CaptchaSolver

__version__ = "2.0.0"

__all__ = [
    "IntelliScrape",
    "scrape",
    "crawl",
    "CrawlResult",
    "ScrapeResult",
    "ProxyConfig",
    "ProxyManager",
    "SessionManager",
    "CaptchaDetector",
    "CaptchaSolver",
]
