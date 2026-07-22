"""
IntelliScrape
-------------

Smart web scraping library that automatically chooses
between static and dynamic scraping.
"""

from .core import scrape
from .crawler import crawl, CrawlResult, ScrapeResult

__all__ = ["scrape", "crawl", "CrawlResult", "ScrapeResult"]