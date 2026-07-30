"""Link checker for IntelliScrape.

Provides comprehensive link analysis: collect, categorize, and verify
HTTP status of all links on a page.  Supports concurrent checking for
speed and returns rich result objects with summary statistics.
"""

from __future__ import annotations

import enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from requests import Response, Session
from requests.exceptions import RequestException

from .downloader import TimeoutType, create_session, download_html


# ---------------------------------------------------------------------------
# Backward-compatible alias kept for any external callers.
# ---------------------------------------------------------------------------
LinkCheckResult = Tuple[str, int]


# ---------------------------------------------------------------------------
# Link classification helpers
# ---------------------------------------------------------------------------

class LinkType(str, enum.Enum):
    """Semantic category of a link target."""
    PAGE = "page"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    EMAIL = "email"
    TELEPHONE = "telephone"
    OTHER = "other"


def _classify_link(href: str) -> LinkType:
    """Guess the resource type from the URL extension."""
    path = urlsplit(href).path.lower()
    if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp")):
        return LinkType.IMAGE
    if any(path.endswith(ext) for ext in (".mp4", ".webm", ".avi", ".mov", ".mkv")):
        return LinkType.VIDEO
    if any(path.endswith(ext) for ext in (".mp3", ".wav", ".ogg", ".flac")):
        return LinkType.AUDIO
    if any(path.endswith(ext) for ext in (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv")):
        return LinkType.DOCUMENT
    if any(path.endswith(ext) for ext in (".zip", ".tar", ".gz", ".rar", ".7z")):
        return LinkType.ARCHIVE
    return LinkType.PAGE


# ---------------------------------------------------------------------------
# Link status
# ---------------------------------------------------------------------------

class LinkStatus(str, enum.Enum):
    """Outcome of a single link check."""
    OK = "ok"
    REDIRECT = "redirect"
    BROKEN = "broken"
    TIMEOUT = "timeout"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class SingleLinkResult:
    """Result of checking one link."""
    url: str
    status_code: int
    status: LinkStatus
    link_type: LinkType
    is_external: bool
    redirect_url: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_ok(self) -> bool:
        return self.status in (LinkStatus.OK, LinkStatus.REDIRECT)


@dataclass
class LinkCheckSummary:
    """Aggregated statistics from a link check run."""
    total: int = 0
    ok: int = 0
    broken: int = 0
    redirected: int = 0
    timeout: int = 0
    error: int = 0
    internal: int = 0
    external: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        working = self.ok + self.redirected
        return (working / self.total * 100) if self.total else 0.0

    @property
    def broken_links(self) -> List[Tuple[str, int]]:
        """Return list of (url, status_code) tuples for broken links."""
        return self._broken_list

    # populated externally
    _broken_list: List[Tuple[str, int]] = field(default_factory=list, repr=False)


@dataclass
class LinkCheckReport:
    """Full report returned by :func:`check_links`."""
    url: str
    links: List[SingleLinkResult]
    summary: LinkCheckSummary


# ---------------------------------------------------------------------------
# Link collection (pure helpers)
# ---------------------------------------------------------------------------

def _iter_http_links(html: str, base: str) -> Iterable[str]:
    """Yield all http(s) href targets found in ``html``."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue
        p = urlsplit(href)
        if p.scheme and p.scheme not in {"http", "https"}:
            continue
        yield urljoin(base, href) if not p.scheme else href


def _unique(seq: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for s in seq:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def collect_links(
    url: str,
    *,
    timeout: TimeoutType | None = None,
    downloader: Callable[[str, TimeoutType | None], str] = download_html,
) -> List[str]:
    """Download *url* and return unique HTTP(S) links found on the page."""
    html = downloader(url, timeout=timeout)
    return _unique(_iter_http_links(html, url))


# ---------------------------------------------------------------------------
# Core check function (enhanced)
# ---------------------------------------------------------------------------

def check_links(
    url: str,
    *,
    timeout: TimeoutType | None = None,
    allowed_statuses: Sequence[int] | None = None,
    session: Session | None = None,
    create_session_fn: Callable[[], Session] = create_session,
    downloader: Callable[[str, TimeoutType | None], str] = download_html,
    ignore_external: bool = False,
    max_workers: int = 10,
    log: Callable[[str], None] | None = None,
) -> LinkCheckReport:
    """Check all links on a page and return a full report.

    Parameters
    ----------
    url : str
        Page URL to analyse.
    timeout : int or float, optional
        Per-request timeout in seconds (default 5).
    allowed_statuses : sequence of int, optional
        HTTP codes considered "OK" (default 200-399).
    session : requests.Session, optional
        Re-use an existing session (avoids re-opening connections).
    create_session_fn : callable
        Factory for new sessions.
    downloader : callable
        Function that returns raw HTML for a URL.
    ignore_external : bool
        Skip links that point to a different host.
    max_workers : int
        Number of threads for concurrent link checking (default 10).
    log : callable, optional
        Receives log messages.

    Returns
    -------
    LinkCheckReport
        Full report with per-link results and summary statistics.
    """
    allowed = tuple(range(200, 400)) if allowed_statuses is None else tuple(allowed_statuses)
    sess = session or create_session_fn()
    base_netloc = urlsplit(url).netloc

    try:
        # ---- collect links ----
        if log:
            log(f"Collecting links from {url}")
        all_links = collect_links(url, timeout=timeout, downloader=downloader)

        if ignore_external:
            all_links = [lnk for lnk in all_links if urlsplit(lnk).netloc == base_netloc]

        total = len(all_links)
        if log:
            log(f"Found {total} links to check")

        # ---- classify and filter ----
        link_items: List[Tuple[str, LinkType, bool]] = []
        for lnk in all_links:
            lt = _classify_link(lnk)
            is_ext = urlsplit(lnk).netloc != base_netloc
            link_items.append((lnk, lt, is_ext))

        # ---- check links concurrently ----
        results: List[SingleLinkResult] = [None] * len(link_items)  # type: ignore[list-item]

        def _check_one(idx: int, lnk: str, lt: LinkType, is_ext: bool) -> Tuple[int, SingleLinkResult]:
            try:
                resp: Response = sess.head(lnk, allow_redirects=True, timeout=timeout or 5.0)
                status_code = resp.status_code
                redir = resp.url if resp.url != lnk else None
            except RequestException as exc:
                status_code = 0
                redir = None
                err_msg = str(exc)
                # Distinguish timeout from other errors
                if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                    return (idx, SingleLinkResult(lnk, 0, LinkStatus.TIMEOUT, lt, is_ext, error=err_msg))
                return (idx, SingleLinkResult(lnk, 0, LinkStatus.ERROR, lt, is_ext, error=err_msg))

            if status_code not in allowed:
                # 3xx outside allowed list → broken
                if 300 <= status_code < 400:
                    st = LinkStatus.REDIRECT
                else:
                    st = LinkStatus.BROKEN
            else:
                st = LinkStatus.OK
                if redir:
                    st = LinkStatus.REDIRECT

            return (idx, SingleLinkResult(lnk, status_code, st, lt, is_ext, redirect_url=redir))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_check_one, i, lnk, lt, is_ext): i
                for i, (lnk, lt, is_ext) in enumerate(link_items)
            }
            done_count = 0
            for fut in as_completed(futures):
                idx, res = fut.result()
                results[idx] = res
                done_count += 1
                if log:
                    log(f"Checked {done_count}/{total}: {res.url} -> {res.status_code}")

        # ---- build summary ----
        summary = LinkCheckSummary(total=total)
        broken_list: List[Tuple[str, int]] = []
        for r in results:
            # status counts
            if r.status == LinkStatus.OK:
                summary.ok += 1
            elif r.status == LinkStatus.REDIRECT:
                summary.redirected += 1
            elif r.status == LinkStatus.TIMEOUT:
                summary.timeout += 1
            elif r.status == LinkStatus.ERROR:
                summary.error += 1
            else:
                summary.broken += 1
                broken_list.append((r.url, r.status_code))

            # internal / external
            if r.is_external:
                summary.external += 1
            else:
                summary.internal += 1

            # by type
            key = r.link_type.value
            summary.by_type[key] = summary.by_type.get(key, 0) + 1

        summary._broken_list = broken_list

        return LinkCheckReport(url=url, links=results, summary=summary)

    finally:
        if session is None:
            sess.close()


# ---------------------------------------------------------------------------
# Legacy two-tuple API (kept for backward compatibility)
# ---------------------------------------------------------------------------

def check_links_legacy(
    url: str,
    *,
    timeout: TimeoutType | None = None,
    allowed_statuses: Sequence[int] | None = None,
    session: Session | None = None,
    create_session_fn: Callable[[], Session] = create_session,
    downloader: Callable[[str, TimeoutType | None], str] = download_html,
    ignore_external: bool = False,
    log: Callable[[str], None] | None = None,
) -> Tuple[bool, List[LinkCheckResult]]:
    """Legacy wrapper returning ``(all_ok, broken_links)`` tuple."""
    report = check_links(
        url,
        timeout=timeout,
        allowed_statuses=allowed_statuses,
        session=session,
        create_session_fn=create_session_fn,
        downloader=downloader,
        ignore_external=ignore_external,
        max_workers=1,
        log=log,
    )
    broken = [(r.url, r.status_code) for r in report.links if not r.is_ok]
    return (not broken, broken)
