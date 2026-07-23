"""Camoufox engine - Firefox-based stealth browser.

Camoufox is a custom Firefox build that patches at the C++ source level,
making it virtually undetectable by anti-bot systems.

Unlike Chrome-based tools that patch JavaScript properties, Camoufox
modifies the engine itself, so:
- navigator.webdriver is genuinely absent (not overridden)
- Canvas/WebGL fingerprints are realistic
- No CDP detection possible
- Different fingerprint than Chrome tools (bypasses Chrome-specific detection)
"""

from __future__ import annotations

import asyncio
from typing import Dict, Optional

from ..anti_detection.behavior import HumanBehavior
from ..anti_detection.fingerprint import FingerprintGenerator
from ..proxy import ProxyConfig
from .base import BaseEngine, ScrapeResult


class CamoufoxEngine(BaseEngine):
    """Stealth browser engine using Camoufox (Firefox-based).

    Advantages over Playwright/nodriver:
    - Patches at engine level (not JavaScript)
    - Different fingerprint than Chrome tools
    - Bypasses Chrome-specific detection
    - No navigator.webdriver flag
    - Realistic canvas/WebGL output

    Use when:
    - Target detects Chrome-based automation
    - Need maximum stealth
    - Target uses fingerprint-based detection
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
        return "camoufox"

    def is_available(self) -> bool:
        try:
            from camoufox.sync_api import Camoufox
            return True
        except ImportError:
            return False

    def fetch(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL using Camoufox stealth browser."""
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            return ScrapeResult(
                url=url,
                html="",
                status_code=0,
                engine=self.name,
                success=False,
                error="Camoufox not installed. Run: pip install camoufox",
            )

        browser = None
        try:
            # Build proxy config
            proxy_config = None
            if self.proxy:
                proxy_config = {
                    "server": self.proxy.url,
                }
                if self.proxy.username:
                    proxy_config["username"] = self.proxy.username
                    proxy_config["password"] = self.proxy.password

            # Generate fingerprint
            fp = self.fingerprint_gen.generate()

            # Launch Camoufox
            with Camoufox(
                headless=self.headless,
                proxy=proxy_config,
                humanize=self.simulate_behavior,
            ) as browser:
                page = browser.new_page()

                # Set extra headers if provided
                if headers:
                    page.set_extra_http_headers(headers)

                # Add cookies if provided
                if cookies:
                    page.context.add_cookies([
                        {"name": k, "value": v, "url": url}
                        for k, v in cookies.items()
                    ])

                # Navigate to page
                response = page.goto(url, wait_until="networkidle", timeout=timeout * 1000)

                # Wait for page to stabilize
                page.wait_for_timeout(2000)

                # Get content
                html = page.content()

                # Get cookies
                new_cookies = {}
                for cookie in page.context.cookies():
                    new_cookies[cookie["name"]] = cookie["value"]

                return ScrapeResult(
                    url=url,
                    html=html,
                    status_code=response.status if response else 200,
                    cookies=new_cookies,
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


class CamoufoxAsyncEngine(BaseEngine):
    """Async version of Camoufox engine."""

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
        return "camoufox_async"

    def is_available(self) -> bool:
        try:
            from camoufox.async_api import AsyncCamoufox
            return True
        except ImportError:
            return False

    async def fetch_async(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL asynchronously using Camoufox."""
        try:
            from camoufox.async_api import AsyncCamoufox
        except ImportError:
            return ScrapeResult(
                url=url, html="", status_code=0, engine=self.name,
                success=False, error="Camoufox not installed",
            )

        try:
            proxy_config = None
            if self.proxy:
                proxy_config = {
                    "server": self.proxy.url,
                }
                if self.proxy.username:
                    proxy_config["username"] = self.proxy.username
                    proxy_config["password"] = self.proxy.password

            async with AsyncCamoufox(
                headless=self.headless,
                proxy=proxy_config,
                humanize=self.simulate_behavior,
            ) as browser:
                page = await browser.new_page()

                if headers:
                    await page.set_extra_http_headers(headers)

                if cookies:
                    await page.context.add_cookies([
                        {"name": k, "value": v, "url": url}
                        for k, v in cookies.items()
                    ])

                response = await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                await page.wait_for_timeout(2000)

                html = await page.content()

                new_cookies = {}
                for cookie in await page.context.cookies():
                    new_cookies[cookie["name"]] = cookie["value"]

                return ScrapeResult(
                    url=url, html=html, status_code=200,
                    cookies=new_cookies, engine=self.name, success=True,
                )

        except Exception as exc:
            return ScrapeResult(
                url=url, html="", status_code=0, engine=self.name,
                success=False, error=str(exc),
            )

    def fetch(self, url: str, **kwargs) -> ScrapeResult:
        """Sync wrapper for async fetch."""
        return asyncio.run(self.fetch_async(url, **kwargs))
