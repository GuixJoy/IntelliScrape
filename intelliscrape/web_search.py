"""Web search for IntelliScrape.

Provides Firecrawl-style web search: query DuckDuckGo / Google News / Bing,
parse SERP result cards into a structured list, and optionally scrape
the full content of each result page in one call.

Engine priority:
  1. DuckDuckGo HTML  — static engine, no JS, mixed web + news results
  2. Google News RSS  — static engine, clean XML, 100+ items, authoritative
  3. Bing News RSS    — static engine, clean XML, direct article URLs

All three work with curl_cffi and require no browser.

Quick start
-----------
>>> from intelliscrape import web_search
>>> report = web_search("python web scraping", limit=10)
>>> for r in report.results:
...     print(r.rank, r.title, r.url)

With full page content (Firecrawl-style)
-----------------------------------------
>>> report = web_search("openai", limit=5, fetch_content=True)
>>> print(report.results[0].content[:500])
"""

from __future__ import annotations

import logging
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlsplit

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from .core import IntelliScrape

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WebSearchError(Exception):
    """Base exception for web search errors."""

    pass


class EngineError(WebSearchError):
    """Raised when a search engine fails to respond or returns invalid data."""

    pass


class EngineBlockedError(EngineError):
    """Raised when a search engine returns a block/challenge page."""

    pass


class ParseError(WebSearchError):
    """Raised when search engine results cannot be parsed."""

    pass


class ContentFetchError(WebSearchError):
    """Raised when full content fetching fails for a result URL."""

    pass


class ValidationError(WebSearchError):
    """Raised when input validation fails."""

    pass


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result from a SERP."""

    rank: int
    """1-based position in the results list."""

    title: str
    """Page title as shown in the search engine."""

    url: str
    """Canonical URL of the result page."""

    snippet: str
    """Short description / excerpt shown under the title."""

    content: Optional[str] = None
    """Full scraped text of the result page.

    Populated only when ``fetch_content=True`` is passed to
    :meth:`WebSearch.search` or :func:`web_search`.  ``None`` if not
    requested or if scraping the page failed.
    """

    source: str = ""
    """Search engine that returned this result
    (``duckduckgo``, ``bing_news``, ``google_news``)."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary (JSON-serialisable)."""
        return {
            "rank": self.rank,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "content": self.content,
            "source": self.source,
        }


@dataclass
class WebSearchReport:
    """Aggregated result of a web search operation."""

    query: str
    """The original search query string."""

    engine_used: str
    """Which search engine returned results
    (``duckduckgo`` / ``bing_news`` / ``google_news``)."""

    results: List[SearchResult] = field(default_factory=list)
    """Ordered list of search results (rank 1 = most relevant)."""

    total: int = 0
    """Number of results returned (``len(results)``)."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary (JSON-serialisable)."""
        return {
            "query": self.query,
            "engine_used": self.engine_used,
            "total": self.total,
            "results": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _decode_ddg_url(href: str) -> str:
    """Decode a DuckDuckGo redirect URL into the real target URL.

    Organic results use ``//duckduckgo.com/l/?uddg=<encoded_url>``.
    Ads use ``//duckduckgo.com/y.js?...`` — these are filtered out by
    returning an empty string.
    """
    if not href:
        return ""
    # Normalise protocol-relative
    if href.startswith("//"):
        href = "https:" + href

    parsed = urlsplit(href)

    # Ad links go through y.js — discard them
    if parsed.path.startswith("/y.js"):
        return ""

    qs = parse_qs(parsed.query)
    if "uddg" in qs:
        return unquote(qs["uddg"][0])

    # Direct URL (no redirect wrapper)
    return href if href.startswith("http") else ""


def _decode_bing_news_url(href: str) -> str:
    """Decode a Bing News RSS apiclick redirect into the real article URL.

    Bing wraps links as:
    ``http://www.bing.com/news/apiclick.aspx?...&url=<encoded_url>&...``
    """
    if not href:
        return ""
    parsed = urlsplit(href)
    qs = parse_qs(parsed.query)
    if "url" in qs:
        return unquote(qs["url"][0])
    return href if href.startswith("http") else ""


# ---------------------------------------------------------------------------
# Block detection
# ---------------------------------------------------------------------------

def _is_blocked(html: str) -> bool:
    """Return True if the response looks like a block/challenge page."""
    if not html or len(html) < 500:
        return True
    lower = html.lower()
    signals = [
        "our systems have detected unusual traffic",
        "to continue, please verify",
        "are you a robot",
        "robot or human",
        "verify you are human",
        "checking your browser",
        "403 forbidden",
        "access denied",
        "before we continue",
    ]
    hits = sum(1 for sig in signals if sig in lower)
    if hits >= 1 and len(html) < 5000:
        return True
    if hits >= 2:
        return True
    return False


# ---------------------------------------------------------------------------
# SERP parsers
# ---------------------------------------------------------------------------

def _parse_duckduckgo(html: str, limit: int) -> List[SearchResult]:
    """Parse DuckDuckGo HTML SERP (``html.duckduckgo.com``).

    Organic results live in ``div.result.results_links``.
    Ads use ``//duckduckgo.com/y.js`` links and are filtered out.
    """
    soup = BeautifulSoup(html, "lxml")
    results: List[SearchResult] = []

    containers = soup.select("div.result.results_links")
    if not containers:
        containers = soup.select("div.result")
    containers = [c for c in containers if c.find("h2") or c.find("a", class_="result__a")]

    for container in containers:
        if len(results) >= limit:
            break

        title_tag = (
            container.select_one("h2.result__title a.result__a")
            or container.select_one("a.result__a")
        )
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        if not title:
            continue

        raw_href = title_tag.get("href", "")
        url = _decode_ddg_url(raw_href)

        # Fallback to display URL
        if not url:
            url_tag = container.select_one("a.result__url")
            if url_tag:
                url = _decode_ddg_url(url_tag.get("href", ""))

        # Skip ads and results with no valid URL
        if not url or not url.startswith("http"):
            continue

        # Snippet
        snippet = ""
        snip_tag = container.select_one("a.result__snippet")
        if snip_tag:
            snippet = snip_tag.get_text(" ", strip=True)
        if not snippet:
            for sel in (".result__body", "p"):
                elem = container.select_one(sel)
                if elem:
                    snippet = elem.get_text(" ", strip=True)
                    break

        results.append(SearchResult(
            rank=len(results) + 1,
            title=title,
            url=url,
            snippet=snippet[:500],
            source="duckduckgo",
        ))

    return results


def _parse_bing_news_rss(xml_text: str, limit: int) -> List[SearchResult]:
    """Parse Bing News RSS feed.

    Feed URL: ``https://www.bing.com/news/search?q=...&format=rss&count=N``

    Each ``<item>`` contains:
    - ``<title>`` — article headline
    - ``<link>`` — Bing apiclick redirect wrapping the real URL in ``?url=``
    - ``<description>`` — snippet text (may contain HTML entities)
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    results: List[SearchResult] = []
    for item in channel.findall("item"):
        if len(results) >= limit:
            break

        title = item.findtext("title", "").strip()
        raw_link = item.findtext("link", "").strip()
        raw_desc = item.findtext("description", "").strip()

        url = _decode_bing_news_url(raw_link)
        if not url or not url.startswith("http"):
            continue
        if not title:
            continue

        # Snippet: strip HTML tags from description
        snippet = BeautifulSoup(raw_desc, "lxml").get_text(" ", strip=True)[:500]

        results.append(SearchResult(
            rank=len(results) + 1,
            title=title,
            url=url,
            snippet=snippet,
            source="bing_news",
        ))

    return results


def _parse_google_news_rss(xml_text: str, limit: int) -> List[SearchResult]:
    """Parse Google News RSS feed.

    Feed URL: ``https://news.google.com/rss/search?q=...&hl=en-US&gl=US&ceid=US:en``

    Each ``<item>`` contains:
    - ``<title>`` — headline with appended ``- Source Name``
    - ``<link>`` — Google News redirect (cannot be decoded offline post-2024)
    - ``<source>`` — publisher name
    - ``<pubDate>`` — publication date

    Since Google News article links cannot be decoded offline, we keep the
    Google News redirect URL.  Users who want the real article URL should
    use ``fetch_content=True`` which will follow the redirect.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    results: List[SearchResult] = []
    for item in channel.findall("item"):
        if len(results) >= limit:
            break

        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date = item.findtext("pubDate", "").strip()

        source_tag = item.find("source")
        source_name = source_tag.text.strip() if source_tag is not None and source_tag.text else ""

        if not title or not link:
            continue

        # Strip " - Source Name" suffix from title if present
        clean_title = title
        if source_name and clean_title.endswith(f" - {source_name}"):
            clean_title = clean_title[: -len(f" - {source_name}")].strip()

        snippet = f"{source_name} · {pub_date}" if source_name else pub_date

        results.append(SearchResult(
            rank=len(results) + 1,
            title=clean_title,
            url=link,
            snippet=snippet[:500],
            source="google_news",
        ))

    return results


# ---------------------------------------------------------------------------
# Engine definitions
# ---------------------------------------------------------------------------

_ENGINE_ORDER = ["duckduckgo", "google_news", "bing_news"]

_SEARCH_URLS = {
    "duckduckgo": "https://html.duckduckgo.com/html/?q={query}",
    "bing_news": "https://www.bing.com/news/search?q={query}&format=rss&count={limit}",
    "google_news": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
}

_PARSERS = {
    "duckduckgo": _parse_duckduckgo,
    "bing_news": _parse_bing_news_rss,
    "google_news": _parse_google_news_rss,
}


# ---------------------------------------------------------------------------
# WebSearch class
# ---------------------------------------------------------------------------

class WebSearch:
    """Firecrawl-style web search: query search engines, parse SERPs, and
    optionally scrape the full content of each result page.

    Engine priority: DuckDuckGo → Google News RSS → Bing News RSS.
    All three work with the static (curl_cffi) engine — no browser needed.

    Parameters
    ----------
    scraper : IntelliScrape, optional
        An existing :class:`~intelliscrape.IntelliScrape` instance.  If not
        provided, a new one is created with default settings.
    **scraper_kwargs
        Keyword arguments forwarded to :class:`~intelliscrape.IntelliScrape`
        when ``scraper`` is *not* provided.

    Examples
    --------
    >>> ws = WebSearch()
    >>> report = ws.search("python web scraping", limit=10)
    >>> for r in report.results:
    ...     print(r.rank, r.title)
    """

    def __init__(
        self,
        scraper: Optional["IntelliScrape"] = None,
        **scraper_kwargs: Any,
    ) -> None:
        if scraper is not None:
            self._scraper = scraper
            self._owns_scraper = False
        else:
            from .core import IntelliScrape as _IntelliScrape
            self._scraper = _IntelliScrape(**scraper_kwargs)
            self._owns_scraper = True

    def __enter__(self):
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup resources when exiting context."""
        if self._owns_scraper and hasattr(self._scraper, "close"):
            self._scraper.close()

    def close(self):
        """Explicitly close the scraper if we own it."""
        if self._owns_scraper and hasattr(self._scraper, "close"):
            self._scraper.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        fetch_content: bool = False,
        max_concurrent: int = 3,
    ) -> WebSearchReport:
        """Search the web and return a structured list of results.

        Tries DuckDuckGo first, then Google News RSS, then Bing News RSS.
        Falls back to the next engine on block or 0 results.

        Parameters
        ----------
        query : str
            Search query.
        limit : int
            Maximum number of results to return (default: 10).
        fetch_content : bool
            If ``True``, scrape the full text of each result URL
            concurrently.  Per-URL failures warn and continue.
        max_concurrent : int
            Parallel workers for content fetching (default: 3).

        Returns
        -------
        WebSearchReport
        """
        if not query or not query.strip():
            raise ValidationError("query cannot be empty")
        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError("limit must be a positive integer")
        if not isinstance(max_concurrent, int) or max_concurrent <= 0:
            raise ValidationError("max_concurrent must be a positive integer")

        encoded = quote_plus(query)
        results: List[SearchResult] = []
        engine_used = ""

        def _retry_with_backoff(func, max_retries: int = 2, base_delay: float = 1.0):
            """Retry a function with exponential backoff."""
            for attempt in range(max_retries + 1):
                try:
                    return func()
                except (EngineError, ParseError, ContentFetchError) as e:
                    if attempt == max_retries:
                        raise
                    logger.warning("Attempt %d/%d failed for %s: %s", attempt + 1, max_retries + 1, engine_name, e)
                    time.sleep(base_delay * (2 ** attempt))

        for engine_name in _ENGINE_ORDER:
            def _fetch_and_parse():
                url = _SEARCH_URLS[engine_name].format(query=encoded, limit=limit)
                html = self._scraper.scrape(url, return_raw=True, engine="static")

                if _is_blocked(html):
                    raise EngineBlockedError(f"{engine_name} returned a block page")

                parsed = _PARSERS[engine_name](html, limit)
                if not parsed:
                    raise ParseError(f"{engine_name} returned 0 results")
                return parsed

            try:
                parsed = _retry_with_backoff(_fetch_and_parse, max_retries=2)
                results = parsed
                engine_used = engine_name
                break
            except EngineBlockedError:
                logger.warning("%s returned a block page — trying next engine.", engine_name)
                continue
            except (EngineError, ParseError, ET.ParseError):
                logger.warning("Engine %s failed after retries — trying next engine.", engine_name)
                continue
            except Exception as exc:
                logger.error("Unexpected error with %s: %s", engine_name, exc)
                continue

        if fetch_content and results:
            results = self._fetch_content(results, max_concurrent=max_concurrent)

        return WebSearchReport(
            query=query,
            engine_used=engine_used,
            results=results,
            total=len(results),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_content(
        self,
        results: List[SearchResult],
        max_concurrent: int = 3,
    ) -> List[SearchResult]:
        """Scrape the full text of each result URL concurrently."""

        def _scrape_one(result: SearchResult) -> SearchResult:
            try:
                result.content = self._scraper.scrape(result.url)
            except (TimeoutError, FutureTimeoutError) as exc:
                logger.warning("Timeout fetching content for %s: %s", result.url, exc)
                result.content = None
            except ContentFetchError as exc:
                logger.error("Content fetch error for %s: %s", result.url, exc)
                result.content = None
            except Exception as exc:
                logger.warning("Could not fetch content for %s: %s", result.url, exc)
                result.content = None
            return result

        with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            futures = {pool.submit(_scrape_one, r): r for r in results}
            populated: List[SearchResult] = []
            for future in as_completed(futures):
                try:
                    populated.append(future.result(timeout=30))
                except (TimeoutError, FutureTimeoutError) as exc:
                    original = futures[future]
                    logger.error("Timeout while processing %s: %s", original.url, exc)
                    original.content = None
                    populated.append(original)
                except ContentFetchError as exc:
                    original = futures[future]
                    logger.error("Content fetch error for %s: %s", original.url, exc)
                    original.content = None
                    populated.append(original)
                except Exception as exc:
                    original = futures[future]
                    logger.warning("Unexpected error for %s: %s", original.url, exc)
                    original.content = None
                    populated.append(original)

        populated.sort(key=lambda r: r.rank)
        return populated


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def web_search(
    query: str,
    *,
    limit: int = 10,
    fetch_content: bool = False,
    max_concurrent: int = 3,
    scraper: Optional["IntelliScrape"] = None,
    **scraper_kwargs: Any,
) -> WebSearchReport:
    """Search the web and return a structured list of results.

    Engine priority: DuckDuckGo → Google News RSS → Bing News RSS.

    Parameters
    ----------
    query : str
        Search query string.
    limit : int
        Maximum number of results (default: 10).
    fetch_content : bool
        If ``True``, also scrape the full page text of each result URL.
        Per-URL failures warn and continue.
    max_concurrent : int
        Parallel workers for content fetching (default: 3).
    scraper : IntelliScrape, optional
        Existing scraper instance to reuse.
    **scraper_kwargs
        Forwarded to :class:`~intelliscrape.IntelliScrape` when ``scraper``
        is not provided.

    Returns
    -------
    WebSearchReport

    Examples
    --------
    >>> from intelliscrape import web_search
    >>> report = web_search("python web scraping", limit=5)
    >>> print(report.engine_used, report.total)
    google_news 5
    >>> for r in report.results:
    ...     print(r.rank, r.title, r.url)

    With full page content:

    >>> report = web_search("openai news", fetch_content=True)
    >>> print(report.results[0].content[:300])
    """
    ws = WebSearch(scraper=scraper, **scraper_kwargs)
    return ws.search(
        query,
        limit=limit,
        fetch_content=fetch_content,
        max_concurrent=max_concurrent,
    )
