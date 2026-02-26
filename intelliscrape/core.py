"""
core.py

Main pipeline controller for IntelliScrape.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .browser import download_dynamic_html
from .cleaner import clean_text
from .downloader import download_html
from .exceptions import IntelliScrapeError
from .extractor import extract_text
from .parser import build_dom
from .utils import force_dynamic, html_needs_browser


_ALLOWED_SCHEMES = {"http", "https"}


def scrape(url: str) -> str:
    """
    Run the full IntelliScrape pipeline for a URL.
    """

    if not url:
        raise IntelliScrapeError("URL is required")

    parsed = urlsplit(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise IntelliScrapeError(
            "Only http/https URLs are supported"
        )

    try:

        try:
            html = download_html(url)

            needs_browser = html_needs_browser(html)

            if force_dynamic(url) or needs_browser:
                html = download_dynamic_html(url)

        except IntelliScrapeError:
            # Fallback to browser if static download fails
            html = download_dynamic_html(url)

        # Parse DOM
        dom = build_dom(html)

        # Extract text
        text = extract_text(dom)

        # Clean text
        cleaned = clean_text(text)

        return cleaned

    except IntelliScrapeError:
        raise

    except Exception as exc:
        raise IntelliScrapeError(
            f"Scraping failed: {exc}"
        ) from exc