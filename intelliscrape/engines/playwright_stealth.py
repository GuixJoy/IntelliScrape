"""Playwright-based stealth engine with anti-detection patches."""

from __future__ import annotations

import asyncio
import random
from typing import Dict, Optional

from ..anti_detection.behavior import HumanBehavior
from ..anti_detection.fingerprint import FingerprintGenerator
from ..proxy import ProxyConfig
from .base import BaseEngine, ScrapeResult


# JavaScript patches for stealth mode
STEALTH_JS = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Override navigator.plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});

// Override navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});

// Override chrome runtime
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// Override permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Override WebGL vendor and renderer
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) {
        return 'Intel Inc.';
    }
    if (parameter === 37446) {
        return 'Intel Iris OpenGL Engine';
    }
    return getParameter.apply(this, arguments);
};

// Override navigator.connection
Object.defineProperty(navigator, 'connection', {
    get: () => ({
        rtt: 50,
        downlink: 10,
        effectiveType: '4g',
        saveData: false
    })
});

// Override navigator.hardwareConcurrency
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});

// Override navigator.deviceMemory
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// Override screen dimensions
Object.defineProperty(screen, 'width', { get: () => 1920 });
Object.defineProperty(screen, 'height', { get: () => 1080 });
Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
Object.defineProperty(screen, 'colorDepth', { get: () => 24 });

// Override Date to prevent timezone fingerprinting
const OriginalDate = Date;
const originalGetMinutes = OriginalDate.prototype.getMinutes;
OriginalDate.prototype.getMinutes = function() {
    const date = new OriginalDate(this);
    return originalGetMinutes.call(date);
};
"""


class PlaywrightStealthEngine(BaseEngine):
    """Stealth browser engine using Playwright with anti-detection patches.

    This engine uses Playwright with JavaScript patches to bypass
    basic bot detection. For advanced detection, use nodriver engine.
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
        return "playwright_stealth"

    def is_available(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            return False

    def fetch(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
        wait_until: str = "domcontentloaded",
        scroll: bool = True,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch URL using Playwright with stealth patches."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ScrapeResult(
                url=url,
                html="",
                status_code=0,
                engine=self.name,
                success=False,
                error="Playwright not installed. Run: pip install playwright && playwright install chromium",
            )

        try:
            with sync_playwright() as p:
                # Launch browser with stealth settings
                browser_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                    "--disable-blink-features=AutomationControlled",
                    "--excludeSwitches=enable-automation",
                    "--use-gl=swiftshader",
                ]

                if self.proxy:
                    browser_args.append(f"--proxy-server={self.proxy.url}")

                browser = p.chromium.launch(
                    headless=self.headless,
                    args=browser_args,
                )

                # Create context with fingerprint
                fp = self.fingerprint_gen.generate()
                context = browser.new_context(
                    viewport={"width": fp.viewport_width, "height": fp.viewport_height},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    locale=fp.language,
                    timezone_id=fp.timezone,
                    device_scale_factor=fp.device_pixel_ratio,
                    has_touch=False,
                    java_script_enabled=True,
                    color_scheme="light",
                )

                # Add cookies if provided
                if cookies:
                    context.add_cookies([
                        {"name": k, "value": v, "url": url}
                        for k, v in cookies.items()
                    ])

                page = context.new_page()

                # Apply stealth patches
                page.add_init_script(STEALTH_JS)

                # Set extra headers if provided
                if headers:
                    page.set_extra_http_headers(headers)

                # Navigate to page
                response = page.goto(url, wait_until=wait_until, timeout=timeout * 1000)

                # Wait for page to stabilize
                page.wait_for_timeout(2000)

                # Simulate human behavior
                if self.simulate_behavior:
                    self._simulate_human(page)

                # Get content
                html = page.content()

                # Get cookies
                new_cookies = {}
                for cookie in context.cookies():
                    new_cookies[cookie["name"]] = cookie["value"]

                browser.close()

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

    def _simulate_human(self, page):
        """Simulate human-like behavior on the page."""
        try:
            # Random mouse movements
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 800)
                y = random.randint(100, 500)
                page.mouse.move(x, y)
                page.wait_for_timeout(random.randint(100, 500))

            # Scroll down
            for _ in range(random.randint(2, 4)):
                page.mouse.wheel(0, random.randint(100, 400))
                page.wait_for_timeout(random.randint(500, 1500))

            # Sometimes scroll back up
            if random.random() < 0.3:
                page.mouse.wheel(0, -random.randint(50, 200))
                page.wait_for_timeout(random.randint(300, 800))

        except Exception:
            pass  # Ignore simulation errors


class PlaywrightAsyncStealthEngine(BaseEngine):
    """Async version of Playwright stealth engine."""

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
        return "playwright_stealth_async"

    def is_available(self) -> bool:
        try:
            from playwright.async_api import async_playwright
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
        """Fetch URL asynchronously."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return ScrapeResult(
                url=url, html="", status_code=0, engine=self.name,
                success=False, error="Playwright not installed",
            )

        try:
            async with async_playwright() as p:
                browser_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ]

                if self.proxy:
                    browser_args.append(f"--proxy-server={self.proxy.url}")

                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=browser_args,
                )

                fp = self.fingerprint_gen.generate()
                context = await browser.new_context(
                    viewport={"width": fp.viewport_width, "height": fp.viewport_height},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    locale=fp.language,
                    timezone_id=fp.timezone,
                )

                if cookies:
                    await context.add_cookies([
                        {"name": k, "value": v, "url": url}
                        for k, v in cookies.items()
                    ])

                page = await context.new_page()
                await page.add_init_script(STEALTH_JS)

                if headers:
                    await page.set_extra_http_headers(headers)

                response = await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                await page.wait_for_timeout(2000)

                html = await page.content()

                new_cookies = {}
                for cookie in await context.cookies():
                    new_cookies[cookie["name"]] = cookie["value"]

                await browser.close()

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
