"""
parser.py

HTML parsing engine for IntelliScrape.
Converts raw HTML into structured DOM.
"""

from __future__ import annotations

from typing import Iterable

from bs4 import BeautifulSoup

from .exceptions import IntelliScrapeError

_STRIP_TAGS: Iterable[str] = (
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "img",
)


def parse_html(html: str) -> BeautifulSoup:
    """Parse ``html`` into a ``BeautifulSoup`` object.

    Parameters
    ----------
    html:
        Raw HTML content retrieved from a downloader.

    Returns
    -------
    BeautifulSoup
        Parsed DOM tree.

    Raises
    ------
    IntelliScrapeError
        If the HTML is empty or parsing fails.
    """

    if not html:
        raise IntelliScrapeError("Empty HTML provided")

    try:
        # lxml is faster and more tolerant while still safe when parsing strings
        return BeautifulSoup(html, "lxml")
    except Exception as exc:
        raise IntelliScrapeError(f"HTML parsing failed: {exc}") from exc


def remove_unwanted_tags(soup: BeautifulSoup) -> BeautifulSoup:
    """Strip non-content tags (scripts, style blocks, etc.)."""

    for tag in _STRIP_TAGS:
        for element in soup.find_all(tag):
            element.decompose()
    return soup


def normalize_dom(soup: BeautifulSoup) -> BeautifulSoup:
    """Normalize text nodes by trimming whitespace and removing empties."""

    body = soup.body

    if not body:
        return soup

    for text_node in body.find_all(string=True):
        cleaned = text_node.strip()

        if not cleaned:
            text_node.extract()
        else:
            text_node.replace_with(cleaned)

    return soup


def build_dom(html: str) -> BeautifulSoup:
    """Full parsing pipeline: parse → strip unwanted tags → normalize."""

    soup = parse_html(html)
    soup = remove_unwanted_tags(soup)
    soup = normalize_dom(soup)
    return soup