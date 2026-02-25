"""
exceptions.py

Custom exceptions for IntelliScrape.
"""


class IntelliScrapeError(Exception):
    """Base exception."""
    pass


class DownloadError(IntelliScrapeError):
    """Download failed."""
    pass