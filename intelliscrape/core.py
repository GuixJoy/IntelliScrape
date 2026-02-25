"""
core.py

Main pipeline controller for IntelliScrape.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .cleaner import clean_text
from .downloader import download_html
from .exceptions import IntelliScrapeError
from .extractor import extract_text
from .parser import build_dom
from .utils import html_needs_browser


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

        # Download HTML
        html = download_html(url)

        # Detect dynamic pages
        needs_browser = html_needs_browser(html)

        if needs_browser:
            raise IntelliScrapeError(
                "Dynamic site detected. Browser engine not implemented yet."
            )

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