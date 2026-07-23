"""Scraping engines for IntelliScrape."""

from .base import BaseEngine, ScrapeResult
from .static import StaticEngine
from .stealth import StealthEngine

__all__ = ["BaseEngine", "ScrapeResult", "StaticEngine", "StealthEngine"]
