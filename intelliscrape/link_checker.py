"""Functional-style link checker for IntelliScrape (pure core, isolated effects)."""

from __future__ import annotations
from typing import Callable, Iterable, List, Sequence, Tuple
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from requests import Response, Session
from requests.exceptions import RequestException
from .downloader import TimeoutType, create_session, download_html

LinkCheckResult = Tuple[str, int]

def _iter_http_links(html: str, base: str) -> Iterable[str]:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        p = urlsplit(href)
        if p.scheme and p.scheme not in {"http", "https"}:
            continue
        yield urljoin(base, href) if not p.scheme else href

def _unique(seq: Iterable[str]) -> List[str]:
    seen = set()
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
    """Impure boundary: downloads then returns unique HTTP(S) links (pure after download)."""
    html = downloader(url, timeout=timeout)
    return _unique(_iter_http_links(html, url))

def check_links(
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
    """Return (all_ok, broken_links). All side effects are via injected session/downloader/log."""
    allowed = tuple(range(200, 400)) if allowed_statuses is None else tuple(allowed_statuses)
    sess = session or create_session_fn()
    try:
        if log:
            log(f"collecting links from {url}")
        links = collect_links(url, timeout=timeout, downloader=downloader)
        if ignore_external:
            base_netloc = urlsplit(url).netloc
            links = [l for l in links if urlsplit(l).netloc == base_netloc]
        if log:
            log(f"checking {len(links)} links")
        def check_one(link: str) -> LinkCheckResult:
            try:
                resp: Response = sess.head(link, allow_redirects=True, timeout=timeout or 5.0)
                return link, resp.status_code
            except RequestException:
                return link, 0
        results = [check_one(l) for l in links]
        if log:
            for i, (l, s) in enumerate(results, 1):
                log(f"checked {i}/{len(results)}: {l} -> {s}")
        broken = [(l, s) for (l, s) in results if s not in allowed]
        return (not broken, broken)
    finally:
        if session is None:
            sess.close()