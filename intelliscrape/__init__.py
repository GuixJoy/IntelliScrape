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
- Link checking (status, categorization, broken link detection)
- Website Intelligence (detect frameworks, CMS, analytics, CDN, hosting, and more)
- SEO auditing (0-100 score, 11 checks, content/link/heading/image/technical/performance analysis)
- Backlink discovery (Google/Bing link: queries, anchor and rel analysis)
- API detection (REST/GraphQL/WebSocket endpoints, exposed keys)
- Markdown corpus for LLM ingestion (llms.txt / llms-full.txt / index.md)
- Website mirroring (HTTrack-style, WARC/ZIP export)

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

Check Links:
    >>> from intelliscrape import check_links
>>> report = check_links("https://example.com")
>>> print(f"Total: {report.summary.total}, Broken: {report.summary.broken}")

Website Intelligence:
    >>> from intelliscrape import IntelliScrape
    >>> scraper = IntelliScrape()
    >>> tech = scraper.detect_tech("https://stripe.com")
    >>> print(tech.summary)
    {'frameworks': ['next.js'], 'cms': [], 'analytics': ['google analytics'], ...}
"""

from .core import IntelliScrape, scrape, analyze_seo, find_backlinks
from .crawler import crawl, CrawlResult, ScrapeResult
from .track import SiteMirror, MirrorConfig, mirror as mirror_site
from .markdown import html_to_markdown, markdown_site, MarkdownConfig, MarkdownResult
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
from .cookies import CookieManager, CookieData
from .interceptor import RequestInterceptor, ResponseModifier, InterceptedRequest, InterceptedResponse
from .ip_manager import IPManager
from .link_checker import (
    check_links,
    collect_links,
    LinkCheckReport,
    LinkCheckSummary,
    SingleLinkResult,
    LinkStatus,
    LinkType,
)
from .web_search import (
    WebSearch,
    WebSearchReport,
    SearchResult,
    web_search,
)
from .tech.extractor import TechStack, TechInfo, TechStackExtractor
from .api_detector.extractor import ApiReport, ApiEndpoint, ApiKeyExposure, ApiDetector
from .seo.analyzer import (
    SEOAnalyzer, SEOReport, SEOCheck, SEOIssue,
    ContentAnalysis, LinkAnalysis, HeadingAnalysis,
    ImageAnalysis, TechnicalAnalysis, PerformanceAnalysis,
)
from .seo.backlinks import BacklinkAnalyzer, BacklinkReport, Backlink

__version__ = "3.1.2"

__all__ = [
    # Main API
    "IntelliScrape",
    "scrape",
    "analyze_seo",
    "find_backlinks",
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
    # Link checking
    "check_links",
    "collect_links",
    "LinkCheckReport",
    "LinkCheckSummary",
    "SingleLinkResult",
    "LinkStatus",
    "LinkType",
    # Web search
    "WebSearch",
    "WebSearchReport",
    "SearchResult",
    "web_search",
    # Website Intelligence
    "TechStack",
    "TechInfo",
    "TechStackExtractor",
    # API Detection
    "ApiReport",
    "ApiEndpoint",
    "ApiKeyExposure",
    "ApiDetector",
    # SEO Analysis
    "SEOAnalyzer",
    "SEOReport",
    "SEOCheck",
    "SEOIssue",
    "ContentAnalysis",
    "LinkAnalysis",
    "HeadingAnalysis",
    "ImageAnalysis",
    "TechnicalAnalysis",
    "PerformanceAnalysis",
    # Backlink Discovery
    "BacklinkAnalyzer",
    "BacklinkReport",
    "Backlink",
    # Re-exports
    "ScrapeResult",
    # HTTrack mirroring
    "SiteMirror",
    "MirrorConfig",
    "mirror_site",
    # Markdown / LLM ingestion
    "html_to_markdown",
    "markdown_site",
    "MarkdownConfig",
    "MarkdownResult",
]
