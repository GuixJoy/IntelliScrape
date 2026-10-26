"""Stealth browser engine using nodriver for anti-detect browsing."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional

from ..anti_detection.behavior import HumanBehavior
from ..anti_detection.fingerprint import FingerprintGenerator
from ..proxy import ProxyConfig
from .base import BaseEngine, ScrapeResult

logger = logging.getLogger("intelliscrape.engines.nodriver")


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

            # Anubis hard-denies headless Chrome, but headed Chrome with
            # stealth patches passes the proof-of-work challenge.  Try
            # headless first, then fall back to headed if blocked.
            attempts = [True, False] if self.headless else [False]

            for attempt, headless in enumerate(attempts):
                # Build browser config
                config = uc.Config()
                config.headless = headless
                config.sandbox = False

                # Add proxy if configured
                if self.proxy:
                    config.add_argument(f"--proxy-server={self.proxy.url}")

                # Stealth arguments: hide automation markers that Anubis and
                # other proof-of-work challenges detect as bots.
                config.add_argument("--disable-blink-features=AutomationControlled")
                config.add_argument("--no-first-run")
                config.add_argument("--no-default-browser-check")

                # Launch browser
                browser = await uc.start(config=config)

                # Navigate to page
                page = await browser.get(url)

                # Apply stealth init script so the navigator.webdriver
                # flag is masked on every page load.  Sent to the tab
                # target (browser.send would raise ProtocolException).
                try:
                    await page.send(uc.cdp.page.add_script_to_evaluate_on_new_document(
                        source="""(() => {
                            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                            Object.defineProperty(navigator, 'plugins', {
                                get: () => [1, 2, 3, 4, 5]
                            });
                            Object.defineProperty(navigator, 'languages', {
                                get: () => ['en-US', 'en']
                            });
                            window.chrome = window.chrome || { runtime: {} };
                        })()
                        """,
                    ))
                except Exception:
                    pass

                # Inject cookies if provided
                if cookies:
                    try:
                        for name, value in cookies.items():
                            await page.send(uc.cdp.network.set_cookie(
                                name=name,
                                value=value,
                                domain=url.split("//")[1].split("/")[0],
                                path="/",
                            ))
                    except Exception:
                        pass

                # Wait for page to load
                await page.sleep(3)

                # Anubis proof-of-work challenge auto-solves in a real browser;
                # wait for it instead of grabbing the challenge page.
                from ..challenges.anubis import is_anubis_challenge

                title = await self._page_title(page)
                if is_anubis_challenge("", title):
                    logger.info(
                        "Anubis challenge detected on %s (headless=%s), waiting for PoW to resolve",
                        url, headless,
                    )
                    deadline = time.monotonic() + min(timeout, 90.0)
                    while time.monotonic() < deadline:
                        title = await self._page_title(page)
                        content = await page.get_content()
                        if not is_anubis_challenge(content, title):
                            logger.info("Anubis challenge resolved: %s", title)
                            break
                        await page.sleep(2)

                # Get page content
                html = await page.get_content()

                # If Anubis still blocks the page (denial page, not the
                # self-solving challenge), retry with headed mode before
                # giving up so the engine chain can escalate.
                title = await self._page_title(page)
                if is_anubis_challenge(html, title):
                    if attempt < len(attempts) - 1:
                        logger.info(
                            "Anubis blocked headless browser on %s, retrying headed", url,
                        )
                        try:
                            browser.stop()
                        except Exception:
                            pass
                        browser = None
                        continue
                    return ScrapeResult(
                        url=url,
                        html=html,
                        status_code=200,
                        cookies={},
                        engine=self.name,
                        success=False,
                        error="Anubis proof-of-work challenge could not be solved",
                    )

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

    async def _page_title(self, page) -> str:
        """Get the page title via JS (nodriver 0.50 has no title() method)."""
        try:
            title = await page.evaluate("document.title")
            return title or ""
        except Exception:
            return ""

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
