"""Text cleaning utilities for IntelliScrape."""

from __future__ import annotations

from .exceptions import IntelliScrapeError


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace and trim spaces."""

    return " ".join(text.split())


def remove_duplicate_lines(text: str) -> str:
    """Remove duplicate sentences while preserving order."""

    sentences = text.split(". ")

    seen = set()
    unique = []

    for sentence in sentences:

        if sentence not in seen:
            seen.add(sentence)
            unique.append(sentence)

    return ". ".join(unique)


def remove_garbage(text: str) -> str:
    """Remove very short tokens."""

    return " ".join(
        token for token in text.split()
        if len(token) > 1
    )


def clean_text(text: str) -> str:
    """Full cleaning pipeline."""

    if not text:
        raise IntelliScrapeError("Empty text provided")

    text = normalize_whitespace(text)

    text = remove_duplicate_lines(text)

    text = remove_garbage(text)

    if not text:
        raise IntelliScrapeError("Cleaning removed all content")

    return text