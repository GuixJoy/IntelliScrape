"""Stealth browser engine using nodriver for anti-detect browsing."""

from __future__ import annotations

import asyncio
from typing import Dict, Optional

from ..anti_detection.behavior import HumanBehavior
from ..anti_detection.fingerprint import FingerprintGenerator
from ..proxy import ProxyConfig
from .base import BaseEngine, ScrapeResult


class StealthEngine(BaseEngine):
    """Stealth browser engine using nodriver.

    nodriver is the successor to undetected-chromedriver.
    It communicates directly with Chrome via CDP (Chrome DevTools Protocol),
    bypassing WebDriver detection.
    """

    def __init__(
        self,
        *,
        fingerprint_generator: Optional[FingerprintGenerator] = None,
        proxy: Optional[ProxyConfig] = None,
        headless: bool = True,
        simulate_behavior: bool = True,
    ):
        self.fingerprint_gen = fingerprint_generator or FingerprintGenerator()
        self.proxy = proxy
        self.headless = headless
        self.simulate_behavior = simulate_behavior

    @property
    def name(self) -> str:
        return "nodriver"

    def is_available(self) -> bool:
        try:
            import nodriver
            return True
        except ImportError:
            return False

    async def _fetch_async(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL using nodriver browser."""
        try:
            import nodriver as uc
        except ImportError:
            return ScrapeResult(
                url=url,
                html="",
                status_code=0,
                engine=self.name,
                success=False,
                error="nodriver not installed. Run: pip install nodriver",
            )

        browser = None
        try:
            # Generate fingerprint
            fp = self.fingerprint_gen.generate()

            # Build browser config
            config = uc.Config()
            config.headless = self.headless
            config.sandbox = False

            # Add proxy if configured
            if self.proxy:
                config.add_argument(f"--proxy-server={self.proxy.url}")

            # Launch browser
            browser = await uc.start(config=config)

            # Navigate to page
            page = await browser.get(url)

            # Wait for page to load
            await page.sleep(3)

            # Simulate human behavior
            if self.simulate_behavior:
                await HumanBehavior.simulate_page_interaction(page, duration=2.0)

            # Get page content
            html = await page.get_content()

            # Get cookies
            cookies_dict = {}
            if hasattr(page, 'target') and hasattr(page.target, 'get_cookies'):
                try:
                    cookies_list = await page.target.get_cookies()
                    for cookie in cookies_list:
                        cookies_dict[cookie['name']] = cookie['value']
                except Exception:
                    pass

            return ScrapeResult(
                url=url,
                html=html,
                status_code=200,
                cookies=cookies_dict,
                engine=self.name,
                success=True,
            )

        except Exception as exc:
            return ScrapeResult(
                url=url,
                html="",
                status_code=0,
                engine=self.name,
                success=False,
                error=str(exc),
            )
        finally:
            if browser:
                try:
                    browser.stop()
                except Exception:
                    pass

    def fetch(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL using nodriver (sync wrapper)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run,
                        self._fetch_async(url, headers=headers, cookies=cookies, timeout=timeout)
                    ).result()
                return result
            else:
                return loop.run_until_complete(
                    self._fetch_async(url, headers=headers, cookies=cookies, timeout=timeout)
                )
        except Exception:
            return asyncio.run(
                self._fetch_async(url, headers=headers, cookies=cookies, timeout=timeout)
            )
