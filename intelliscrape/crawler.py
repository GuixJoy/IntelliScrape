"""Website crawler for IntelliScrape - discovers and scrapes all pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set, TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from .core import IntelliScrape


@dataclass
class ScrapeResult:
    """Result of scraping a single page."""
    url: str
    content: str
    status: str = "success"


@dataclass
class CrawlResult:
    """Result of crawling an entire website."""
    base_url: str
    pages: List[ScrapeResult] = field(default_factory=list)
    failed: List[ScrapeResult] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def total_failed(self) -> int:
        return len(self.failed)

    def to_text(self) -> str:
        """Convert all scraped content to a single text document."""
        parts = []
        for page in self.pages:
            parts.append(f"{'='*80}")
            parts.append(f"URL: {page.url}")
            parts.append(f"{'='*80}")
            parts.append(page.content)
            parts.append("")
        return "\n".join(parts)


def _extract_links(html: str, base_url: str) -> Set[str]:
    """Extract all internal HTTP(S) links from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    base_domain = urlsplit(base_url).netloc

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()

        if not href:
            continue

        # Skip non-HTTP links
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, href)

        # Parse and validate
        parsed = urlsplit(full_url)
        if parsed.scheme not in ("http", "https"):
            continue

        # Only keep internal links (same domain)
        if parsed.netloc == base_domain:
            # Remove fragment
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            links.add(clean_url)

    return links


def crawl(
    url: str,
    *,
    max_pages: int = 50,
    delay: float = 0.5,
    log: Optional[Callable[[str], None]] = None,
    on_page: Optional[Callable[[int, int], None]] = None,
    scraper: Optional["IntelliScrape"] = None,
    on_progress: Optional[Callable] = None,
) -> CrawlResult:
    """Crawl a website starting from the given URL.

    Parameters
    ----------
    url : str
        Starting URL to crawl.
    max_pages : int
        Maximum number of pages to scrape (default: 50).
    delay : float
        Delay between requests in seconds (default: 0.5).
    log : callable, optional
        Logging function for progress updates.
    on_page : callable, optional
        Callback with (pages_done, pages_failed) after each page.
    scraper : IntelliScrape, optional
        Scraper instance with anti-bot detection, manual CAPTCHA, etc.
        If None, a new default scraper is created.
    on_progress : callable, optional
        Progress callback for engine status updates.

    Returns
    -------
    CrawlResult
        Contains all scraped pages and any failures.
    """
    import time

    if not url:
        raise ValueError("URL is required")

    if scraper is None:
        from .core import IntelliScrape
        scraper = IntelliScrape()

    base_domain = urlsplit(url).netloc
    result = CrawlResult(base_url=url)
    visited: Set[str] = set()
    to_visit: Set[str] = {url}

    if log:
        log(f"Starting crawl of {url}")
        log(f"Max pages: {max_pages}")

    try:
        while to_visit and len(result.pages) < max_pages:
            current_url = to_visit.pop()

            if current_url in visited:
                continue

            visited.add(current_url)

            if log:
                log(f"[{len(result.pages)+1}/{max_pages}] Scraping: {current_url}")

            try:
                # Use the scraper's full pipeline (anti-bot, CAPTCHA, fallback chain)
                content = scraper.scrape(current_url, on_progress=on_progress)

                # Extract links from raw HTML for further crawling
                raw_html = scraper.scrape(current_url, return_raw=True, on_progress=on_progress)
                new_links = _extract_links(raw_html, url)
                for link in new_links:
                    if link not in visited:
                        to_visit.add(link)

                result.pages.append(ScrapeResult(url=current_url, content=content))

                if log:
                    log(f"  OK - {len(content)} chars extracted")
                if on_page:
                    on_page(len(result.pages), len(result.failed))

            except Exception as exc:
                result.failed.append(ScrapeResult(
                    url=current_url,
                    content="",
                    status=f"failed: {exc}"
                ))
                if log:
                    log(f"  FAILED - {exc}")
                if on_page:
                    on_page(len(result.pages), len(result.failed))

            # Rate limiting
            if delay > 0:
                time.sleep(delay)

    finally:
        pass

    if log:
        log(f"\nCrawl complete: {result.total_pages} scraped, {result.total_failed} failed")

    return result
