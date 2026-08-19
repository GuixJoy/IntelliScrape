"""Backlink Analyzer — discover backlinks via search engine queries.

Uses Google/Bing search operators to find pages linking to a target domain,
then scrapes each referring page to extract the exact link, anchor text,
and follow/nofollow status.
"""

from __future__ import annotations

import base64
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger("intelliscrape.seo")


@dataclass
class Backlink:
    """A single discovered backlink."""

    source_url: str  # The page that links to the target
    target_url: str  # The URL being linked to
    anchor_text: str  # Link text
    is_nofollow: bool  # True if rel="nofollow"
    is_sponsored: bool  # True if rel="sponsored"
    is_ugc: bool  # True if rel="ugc"
    context: str = ""  # Text snippet around the link
    search_engine: str = ""  # Which search engine found it
    verified: bool = True  # True if the link was confirmed on the source page

    @property
    def rel_type(self) -> str:
        types = []
        if self.is_nofollow:
            types.append("nofollow")
        if self.is_sponsored:
            types.append("sponsored")
        if self.is_ugc:
            types.append("ugc")
        return ",".join(types) if types else "follow"

    def to_dict(self) -> dict:
        return {
            "source_url": self.source_url,
            "target_url": self.target_url,
            "anchor_text": self.anchor_text,
            "rel": self.rel_type,
            "is_nofollow": self.is_nofollow,
            "context": self.context,
            "search_engine": self.search_engine,
            "verified": self.verified,
        }


@dataclass
class BacklinkReport:
    """Backlink analysis report for a target URL/domain."""

    target: str
    backlinks: List[Backlink] = field(default_factory=list)
    total_found: int = 0
    search_engines_used: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def unique_domains(self) -> int:
        domains = set()
        for bl in self.backlinks:
            if not bl.verified:
                continue
            parsed = urlparse(bl.source_url)
            if parsed.netloc:
                domains.add(parsed.netloc)
        return len(domains)

    @property
    def dofollow_count(self) -> int:
        return sum(1 for bl in self.backlinks if bl.verified and not bl.is_nofollow)

    @property
    def nofollow_count(self) -> int:
        return sum(1 for bl in self.backlinks if bl.verified and bl.is_nofollow)

    @property
    def verified_count(self) -> int:
        return sum(1 for bl in self.backlinks if bl.verified)

    @property
    def unverified_count(self) -> int:
        return sum(1 for bl in self.backlinks if not bl.verified)

    @property
    def anchor_text_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        for bl in self.backlinks:
            anchor = bl.anchor_text.strip()
            if anchor:
                dist[anchor] = dist.get(anchor, 0) + 1
        return dict(sorted(dist.items(), key=lambda x: -x[1]))

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "total_found": self.total_found,
            "verified": self.verified_count,
            "unverified": self.unverified_count,
            "unique_domains": self.unique_domains,
            "dofollow": self.dofollow_count,
            "nofollow": self.nofollow_count,
            "backlinks": [bl.to_dict() for bl in self.backlinks],
            "anchor_text_distribution": self.anchor_text_distribution,
            "errors": self.errors,
        }


class BacklinkAnalyzer:
    """Discover backlinks using search engine queries.

    Usage
    -----
    >>> from intelliscrape.seo import BacklinkAnalyzer
    >>> report = BacklinkAnalyzer.find("https://example.com", limit=50)
    >>> print(report.total_found)
    42
    """

    # Search engine result page patterns
    _GOOGLE_RESULT_PATTERN = re.compile(
        r'<a[^>]+href="(/url\?q=([^&"]+)[^"]*|([^"]*example[^"]*))"',
        re.IGNORECASE,
    )

    # Bing appends redirect/footer noise to almost every result page. These
    # are redirect/link-shortener services that never contain real content
    # linking to a target, so they are dropped before verification.
    _BING_JUNK_DOMAINS = {
        "go.microsoft.com",
        "link.com",
        "app.link.com",
        "phonelink.microsoft.com",
        "tinyurl.com",
        "bit.ly",
        "t.co",
        "ow.ly",
        "goo.gl",
    }

    @staticmethod
    def find(
        target: str,
        *,
        limit: int = 50,
        sources: Optional[List[str]] = None,
        scrape_backlinks: bool = True,
        max_workers: int = 5,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> BacklinkReport:
        """Find backlinks to a target URL/domain.

        Parameters
        ----------
        target : str
            Target URL or domain to find backlinks for.
        limit : int
            Maximum number of backlinks to find.
        sources : list, optional
            Search engines to use. Default: ["google", "bing"].
        scrape_backlinks : bool
            If True, visit each referring page to extract exact link details.
            If False, just return the search result URLs.
        max_workers : int
            Number of concurrent threads for scraping referring pages.
        on_progress : callable, optional
            Called with status messages during the search.

        Returns
        -------
        BacklinkReport
            Report with discovered backlinks.
        """
        if sources is None:
            sources = ["google", "bing"]

        report = BacklinkReport(target=target)
        report.search_engines_used = sources

        # Normalize target to domain for search
        parsed = urlparse(target)
        domain = parsed.netloc or parsed.path
        domain = domain.replace("www.", "")

        all_result_urls: List[tuple[str, str]] = []  # (url, search_engine)

        for source in sources:
            if on_progress:
                on_progress(f"Searching {source} for backlinks to {domain}...")

            try:
                urls = BacklinkAnalyzer._search_engine_query(source, domain, limit)
                for url in urls:
                    all_result_urls.append((url, source))
            except Exception as e:
                error_msg = f"{source} search failed: {e}"
                report.errors.append(error_msg)
                logger.warning(error_msg)

        if not all_result_urls:
            if on_progress:
                on_progress("No backlink results found.")
            return report

        # Deduplicate
        seen = set()
        unique_results = []
        for url, se in all_result_urls:
            if url not in seen:
                seen.add(url)
                unique_results.append((url, se))

        # Limit
        unique_results = unique_results[:limit]
        report.total_found = len(unique_results)

        if not scrape_backlinks:
            # Return search result URLs as-is (unverified)
            for url, se in unique_results:
                report.backlinks.append(Backlink(
                    source_url=url,
                    target_url=target,
                    anchor_text="",
                    is_nofollow=False,
                    is_sponsored=False,
                    is_ugc=False,
                    search_engine=se,
                    verified=False,
                ))
            return report

        # Visit each referring page to extract link details
        if on_progress:
            on_progress(f"Scraping {len(unique_results)} referring pages...")

        def _scrape_referrer(item: tuple[str, str]) -> List[Backlink]:
            url, se = item
            try:
                found = BacklinkAnalyzer._extract_backlinks_from_page(url, target, domain, se)
            except Exception as e:
                logger.debug(f"Failed to scrape {url}: {e}")
                found = []
            if not found:
                # Search engines (esp. Bing's link:) can return pages that
                # don't actually link to the target. Keep the result as an
                # unverified candidate so it's visible in the report.
                found = [Backlink(
                    source_url=url,
                    target_url=target,
                    anchor_text="",
                    is_nofollow=False,
                    is_sponsored=False,
                    is_ugc=False,
                    search_engine=se,
                    verified=False,
                )]
            return found

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_scrape_referrer, item): item for item in unique_results}
            for future in as_completed(futures):
                try:
                    backlinks = future.result()
                    report.backlinks.extend(backlinks)
                except Exception:
                    pass

        if on_progress:
            on_progress(f"Found {len(report.backlinks)} backlinks from {report.unique_domains} domains.")

        return report

    @staticmethod
    def _search_engine_query(engine: str, domain: str, limit: int) -> List[str]:
        """Query a search engine for pages linking to the domain.

        Note: Google's ``link:`` operator returns an ``enablejs`` page to plain
        HTTP clients (0 results), and Bing's ``link:`` operator is treated as a
        keyword match for the word "link" (returns link.com, tinyurl, fwlink,
        etc. — not real backlinks). Both engines respond to the mention query
        ``"domain" -site:domain``, which surfaces pages that reference the
        target and are then verified by scraping.

        Returns a list of result URLs.
        """
        from curl_cffi import requests as curl_requests

        # Mention query works on both engines; for Bing it is the only
        # reliable way to surface actual referring pages.
        query = f'"{domain}" -site:{domain}'
        encoded = quote_plus(query)

        if engine == "google":
            url = f"https://www.google.com/search?q={encoded}&num={min(limit, 100)}"
        elif engine == "bing":
            url = f"https://www.bing.com/search?q={encoded}&count={min(limit, 50)}"
        else:
            raise ValueError(f"Unsupported search engine: {engine}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        resp = curl_requests.get(url, headers=headers, impersonate="chrome131", timeout=30)
        resp.raise_for_status()

        return BacklinkAnalyzer._parse_search_results(resp.text, engine, domain)

    @staticmethod
    def _is_junk_url(parsed) -> bool:
        """Return True for redirect services and search-engine widget noise."""
        if parsed.netloc in BacklinkAnalyzer._BING_JUNK_DOMAINS:
            return True
        # Bing's "related searches" widget leaks Google property pages
        if parsed.netloc == "google.com" or parsed.netloc.endswith(".google.com"):
            return True
        return False

    @staticmethod
    def _parse_search_results(html: str, engine: str, target_domain: str) -> List[str]:
        """Extract result URLs from search engine HTML."""
        soup = BeautifulSoup(html, "html.parser")
        urls = []

        if engine == "google":
            # Google wraps results in <a> tags with /url?q= or direct hrefs
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/url?q=" in href:
                    # Extract actual URL from /url?q=...&...
                    match = re.search(r"/url\?q=([^&]+)", href)
                    if match:
                        url = match.group(1)
                        parsed = urlparse(url)
                        if (
                            parsed.netloc
                            and parsed.netloc != target_domain
                            and not BacklinkAnalyzer._is_junk_url(parsed)
                        ):
                            urls.append(url)
                elif href.startswith("http"):
                    parsed = urlparse(href)
                    if (
                        parsed.netloc
                        and target_domain not in parsed.netloc
                        and not BacklinkAnalyzer._is_junk_url(parsed)
                    ):
                        # Only include if it looks like a search result
                        parent = a.find_parent(["div", "li"])
                        if parent and ("data-sokoban" in str(parent) or "g" in parent.get("class", [])):
                            urls.append(href)

        elif engine == "bing":
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Bing wraps result links in /ck/a redirects; decode the real
                # destination from the base64url "u" parameter
                decoded = BacklinkAnalyzer._decode_bing_redirect(href)
                if decoded:
                    parsed = urlparse(decoded)
                    if (
                        parsed.netloc
                        and target_domain not in parsed.netloc
                        and "bing.com" not in parsed.netloc
                        and not BacklinkAnalyzer._is_junk_url(parsed)
                    ):
                        urls.append(decoded)
                    continue
                if href.startswith("http"):
                    parsed = urlparse(href)
                    if (
                        parsed.netloc
                        and target_domain not in parsed.netloc
                        and "bing.com" not in parsed.netloc
                        and not BacklinkAnalyzer._is_junk_url(parsed)
                    ):
                        urls.append(href)

        return urls

    @staticmethod
    def _decode_bing_redirect(href: str) -> Optional[str]:
        """Extract the destination URL from a Bing ``/ck/a`` redirect link.

        Bing wraps every result link in ``https://www.bing.com/ck/a?...&u=a1a...``
        where the ``u`` parameter is a base64url-encoded destination URL.
        Returns ``None`` for non-redirect links.
        """
        if "/ck/a" not in href and "/ck/" not in href:
            return None
        params = parse_qs(unquote(href))
        for key in ("u", "r"):
            if key in params:
                raw = params[key][0]
                try:
                    # Bing prefixes some payloads with an "a1" marker; strip
                    # any leading non-base64 characters before decoding
                    cleaned = re.sub(r"^[^a-zA-Z0-9_-]+", "", raw)
                    if cleaned.startswith("a1") and len(cleaned) % 4 != 0:
                        cleaned = cleaned[2:]
                    cleaned = cleaned + "=" * (-len(cleaned) % 4)
                    decoded = base64.urlsafe_b64decode(cleaned).decode("utf-8", "ignore")
                    if decoded.startswith("http"):
                        return decoded
                except Exception:
                    continue
        return None

    @staticmethod
    def _extract_backlinks_from_page(
        page_url: str,
        target_url: str,
        target_domain: str,
        search_engine: str,
    ) -> List[Backlink]:
        """Visit a page and extract all links pointing to the target."""
        from curl_cffi import requests as curl_requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }

        try:
            resp = curl_requests.get(page_url, headers=headers, impersonate="chrome131", timeout=15)
            resp.raise_for_status()
        except Exception:
            return []

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        backlinks = []

        target_parsed = urlparse(target_url)
        target_path = target_parsed.path.rstrip("/")

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            # Resolve relative URLs
            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)

            # Check if this link points to the target domain
            link_domain = parsed.netloc.replace("www.", "")
            link_path = parsed.path.rstrip("/")

            if link_domain != target_domain.replace("www.", ""):
                continue

            # Optional: check if the path matches too (for more precise matching)
            # For domain-level matching, just the domain is enough

            anchor_text = a.get_text(strip=True)

            # Get context (parent paragraph or surrounding text)
            context = ""
            parent = a.find_parent(["p", "div", "li", "td", "span", "article", "section"])
            if parent:
                context = parent.get_text(separator=" ", strip=True)[:200]

            # Check rel attributes
            rel = a.get("rel", [])
            is_nofollow = "nofollow" in rel
            is_sponsored = "sponsored" in rel
            is_ugc = "ugc" in rel

            backlinks.append(Backlink(
                source_url=page_url,
                target_url=full_url,
                anchor_text=anchor_text,
                is_nofollow=is_nofollow,
                is_sponsored=is_sponsored,
                is_ugc=is_ugc,
                context=context,
                search_engine=search_engine,
            ))

        return backlinks

    @staticmethod
    def audit(
        target: str,
        referrer_urls: List[str],
        *,
        max_workers: int = 5,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> BacklinkReport:
        """Audit a list of known backlink URLs.

        Parameters
        ----------
        target : str
            Target URL/domain being linked to.
        referrer_urls : list
            List of URLs that supposedly link to the target.
        max_workers : int
            Concurrent threads for checking.
        on_progress : callable, optional
            Progress callback.

        Returns
        -------
        BacklinkReport
            Audit report showing which links still exist, anchor text, etc.
        """
        parsed = urlparse(target)
        domain = parsed.netloc or parsed.path
        domain = domain.replace("www.", "")

        report = BacklinkReport(target=target)
        report.total_found = len(referrer_urls)

        if on_progress:
            on_progress(f"Auditing {len(referrer_urls)} backlinks...")

        def _audit_one(url: str) -> List[Backlink]:
            return BacklinkAnalyzer._extract_backlinks_from_page(url, target, domain, "manual")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_audit_one, url): url for url in referrer_urls}
            for future in as_completed(futures):
                try:
                    backlinks = future.result()
                    report.backlinks.extend(backlinks)
                except Exception:
                    pass

        if on_progress:
            on_progress(f"Audit complete: {len(report.backlinks)} active backlinks found.")

        return report
