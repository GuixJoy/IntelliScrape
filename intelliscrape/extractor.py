"""DOM text extraction utilities for IntelliScrape."""

from __future__ import annotations

from typing import Iterable

from bs4 import BeautifulSoup

from .exceptions import IntelliScrapeError

_NOISE_TAGS: Iterable[str] = (
    "nav",
    "footer",
    "header",
    "aside",
    "form",
)


def remove_noise(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove structural noise elements (nav, footer, etc.) from ``soup``."""

    if soup is None:
        raise IntelliScrapeError("Invalid DOM provided")

    for tag in _NOISE_TAGS:
        for element in soup.find_all(tag):
            element.decompose()
    return soup


def extract_main_text(soup: BeautifulSoup) -> str:
    """Extract normalized visible text from soup."""

    if soup is None:
        raise IntelliScrapeError("Invalid DOM provided")

    main = soup.find("main")

    if not main:
        main = soup.find("article")

    if not main:
        main = soup.body

    if not main:
        raise IntelliScrapeError("No content container found")

    text = main.get_text(separator=" ", strip=True)

    if not text:
        raise IntelliScrapeError("No text extracted")

    return text


def extract_text(soup: BeautifulSoup) -> str:
    """Full extraction pipeline: remove noise then return cleaned text."""

    cleaned_soup = remove_noise(soup)
    return extract_main_text(cleaned_soup)