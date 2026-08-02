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
import ctypes
import os
from typing import Dict, Optional

from ..anti_detection.behavior import HumanBehavior
from ..anti_detection.fingerprint import FingerprintGenerator
from ..proxy import ProxyConfig
from .base import BaseEngine, ScrapeResult


def _get_camoufox_executable() -> Optional[str]:
    """Get the camoufox executable path, handling spaces in Windows usernames.

    Playwright's Node.js driver can't handle spaces in paths on Windows,
    so we copy the browser to a space-free path if needed.
    """
    try:
        from camoufox.utils import get_path
        path = get_path("camoufox") + ".exe"
        if os.path.exists(path):
            # If no spaces, use directly
            if " " not in path:
                return path

            # Space in path — copy to a short location
            import shutil
            safe_dir = r"C:\camoufox_browser"
            safe_exe = os.path.join(safe_dir, "camoufox.exe")
            if os.path.exists(safe_exe):
                return safe_exe

            # Copy the entire browser directory
            src_dir = os.path.dirname(path)
            shutil.copytree(src_dir, safe_dir)
            if os.path.exists(safe_exe):
                return safe_exe
    except Exception:
        pass
    return None


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

            # Resolve executable path (handles spaces in Windows usernames)
            exe_path = _get_camoufox_executable()

            # Launch Camoufox with anti-detection settings
            # Let Camoufox handle its own fingerprinting (it has its own database)
            launch_kwargs = {
                "headless": self.headless,
                "proxy": proxy_config,
                "humanize": self.simulate_behavior,
                "block_webrtc": True,
            }
            if exe_path:
                launch_kwargs["executable_path"] = exe_path

            with Camoufox(**launch_kwargs) as browser:
                page = browser.new_page()

                # Set extra headers if provided
                if headers:
                    page.set_extra_http_headers(headers)
                else:
                    # Set realistic default headers
                    page.set_extra_http_headers({
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "DNT": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1",
                    })

                # Add cookies if provided
                if cookies:
                    page.context.add_cookies([
                        {"name": k, "value": v, "url": url}
                        for k, v in cookies.items()
                    ])

                # Navigate to page
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)

                # Human-like delay after page load
                page.wait_for_timeout(2000)

                # Random scroll to simulate human behavior
                page.evaluate("window.scrollBy(0, Math.random() * 500)")
                page.wait_for_timeout(500)
                page.evaluate("window.scrollBy(0, -Math.random() * 200)")
                page.wait_for_timeout(1000)

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
                executable_path=_get_camoufox_executable(),
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
