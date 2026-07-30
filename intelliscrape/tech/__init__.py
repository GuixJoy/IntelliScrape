"""Website Intelligence — detect the technology stack of any website.

Usage (library)::

    from intelliscrape.tech import TechStackExtractor

    report = TechStackExtractor.extract(html, headers, cookies, url)
    print(report.summary)

    # Or via IntelliScrape:
    from intelliscrape import IntelliScrape
    scraper = IntelliScrape()
    report = scraper.detect_tech("https://example.com")

Usage (CLI)::

    intelliscrape https://example.com --tech
"""

from .extractor import TechInfo, TechStack, TechStackExtractor

__all__ = [
    "TechInfo",
    "TechStack",
    "TechStackExtractor",
]
