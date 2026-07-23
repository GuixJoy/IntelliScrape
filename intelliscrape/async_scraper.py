"""Async scraping support for concurrent requests.

This module provides async versions of the main scraping functions,
allowing you to scrape multiple pages concurrently for better performance.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional, Union

from .anti_detection.throttle import RateLimitConfig, SmartThrottle
from .core import IntelliScrape
from .engines.base import ScrapeResult
from .proxy import ProxyConfig


class AsyncIntelliScrape:
    """Async version of IntelliScrape for concurrent scraping.

    Examples
    --------
    >>> import asyncio
    >>> from intelliscrape import AsyncIntelliScrape
    >>> 
    >>> async def main():
    ...     async with AsyncIntelliScrape() as scraper:
    ...         urls = [
    ...             "https://example.com",
    ...             "https://python.org",
    ...             "https://github.com",
    ...         ]
    ...         results = await scraper.scrape_many(urls, max_concurrent=5)
    ...         for result in results:
    ...             print(f"{result['url']}: {len(result['content'])} chars")
    >>> 
    >>> asyncio.run(main())
    """

    def __init__(
        self,
        *,
        proxy: Optional[Union[ProxyConfig, str]] = None,
        api_key: Optional[str] = None,
        captcha_provider: Optional[str] = None,
        headless: bool = True,
        simulate_behavior: bool = True,
        min_delay: float = 0.5,
        max_delay: float = 3.0,
        max_concurrent: int = 10,
    ):
        """Initialize async scraper.

        Parameters
        ----------
        proxy : ProxyConfig or str, optional
            Proxy configuration.
        api_key : str, optional
            CAPTCHA solving API key.
        captcha_provider : str, optional
            CAPTCHA solving provider.
        headless : bool
            Run browser in headless mode.
        simulate_behavior : bool
            Enable behavioral simulation.
        min_delay : float
            Minimum delay between requests.
        max_delay : float
            Maximum delay between requests.
        max_concurrent : int
            Maximum concurrent requests.
        """
        self.scraper = IntelliScrape(
            proxy=proxy,
            api_key=api_key,
            captcha_provider=captcha_provider,
            headless=headless,
            simulate_behavior=simulate_behavior,
            min_delay=min_delay,
            max_delay=max_delay,
        )
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def scrape(
        self,
        url: str,
        *,
        engine: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Scrape a single URL asynchronously.

        Parameters
        ----------
        url : str
            Target URL.
        engine : str, optional
            Force a specific engine.

        Returns
        -------
        str
            Scraped text content.
        """
        async with self._semaphore:
            # Run sync scrape in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.scraper.scrape(url, engine=engine, **kwargs),
            )

    async def scrape_many(
        self,
        urls: List[str],
        *,
        engine: Optional[str] = None,
        max_concurrent: Optional[int] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently.

        Parameters
        ----------
        urls : list of str
            URLs to scrape.
        engine : str, optional
            Force a specific engine.
        max_concurrent : int, optional
            Override max concurrent requests.

        Returns
        -------
        list of dict
            Results with 'url', 'content', 'success', 'error'.
        """
        if max_concurrent:
            self._semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_one(url: str) -> Dict[str, Any]:
            try:
                content = await self.scrape(url, engine=engine, **kwargs)
                return {
                    "url": url,
                    "content": content,
                    "success": True,
                    "error": None,
                }
            except Exception as exc:
                return {
                    "url": url,
                    "content": "",
                    "success": False,
                    "error": str(exc),
                }

        tasks = [scrape_one(url) for url in urls]
        return await asyncio.gather(*tasks)

    async def scrape_structured(
        self,
        urls: List[str],
        *,
        max_concurrent: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get structured data from multiple URLs concurrently.

        Returns list of dicts with full metadata.
        """
        if max_concurrent:
            self._semaphore = asyncio.Semaphore(max_concurrent)

        async def get_one(url: str) -> Dict[str, Any]:
            try:
                data = self.scraper.get_structured(url)
                return {
                    "url": url,
                    "data": data.to_dict(),
                    "success": True,
                    "error": None,
                }
            except Exception as exc:
                return {
                    "url": url,
                    "data": None,
                    "success": False,
                    "error": str(exc),
                }

        tasks = [get_one(url) for url in urls]
        return await asyncio.gather(*tasks)


async def scrape_async(
    url: str,
    *,
    proxy: Optional[str] = None,
    engine: Optional[str] = None,
    **kwargs,
) -> str:
    """Async convenience function for scraping a single URL.

    Examples
    --------
    >>> import asyncio
    >>> from intelliscrape import scrape_async
    >>> 
    >>> text = asyncio.run(scrape_async("https://example.com"))
    """
    async with AsyncIntelliScrape(proxy=proxy) as scraper:
        return await scraper.scrape(url, engine=engine, **kwargs)


async def scrape_many_async(
    urls: List[str],
    *,
    proxy: Optional[str] = None,
    engine: Optional[str] = None,
    max_concurrent: int = 10,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Async convenience function for scraping multiple URLs.

    Examples
    --------
    >>> import asyncio
    >>> from intelliscrape import scrape_many_async
    >>> 
    >>> urls = ["https://example.com", "https://python.org"]
    >>> results = asyncio.run(scrape_many_async(urls, max_concurrent=5))
    """
    async with AsyncIntelliScrape(proxy=proxy, max_concurrent=max_concurrent) as scraper:
        return await scraper.scrape_many(urls, engine=engine, **kwargs)
