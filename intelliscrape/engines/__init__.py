"""Scraping engines for IntelliScrape."""

from .base import BaseEngine, ScrapeResult
from .static import StaticEngine
from .stealth import StealthEngine
from .playwright_stealth import PlaywrightStealthEngine, PlaywrightAsyncStealthEngine
from .camoufox import CamoufoxEngine, CamoufoxAsyncEngine

__all__ = [
    "BaseEngine",
    "ScrapeResult",
    "StaticEngine",
    "StealthEngine",
    "PlaywrightStealthEngine",
    "PlaywrightAsyncStealthEngine",
    "CamoufoxEngine",
    "CamoufoxAsyncEngine",
]
