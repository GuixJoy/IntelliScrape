"""DrissionPage-based engine - CDP browser automation with no webdriver detection."""

from __future__ import annotations

import logging
from typing import Dict, Optional

from ..anti_detection.fingerprint import FingerprintGenerator
from ..anti_detection.behavior import HumanBehavior
from ..proxy import ProxyConfig
from .base import BaseEngine, ScrapeResult

logger = logging.getLogger("intelliscrape")


class DrissionPageEngine(BaseEngine):
    """DrissionPage engine for stealth browser automation.

    Uses Chrome DevTools Protocol (CDP) directly without WebDriver,
    making it harder to detect than Playwright/Selenium.

    Advantages over Playwright:
    - No navigator.webdriver flag
    - No ChromeDriver dependency
    - Hybrid HTTP + browser mode
    - Reuses existing Chrome installation
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
        return "drissionpage"

    def is_available(self) -> bool:
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
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
        """Fetch URL using DrissionPage with CDP browser automation."""
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            return ScrapeResult(
                url=url,
                html="",
                status_code=0,
                engine=self.name,
                success=False,
                error="DrissionPage not installed. Run: pip install DrissionPage",
            )

        page = None
        try:
            # Configure browser options
            co = ChromiumOptions()

            if self.headless:
                co.headless()

            # Anti-detection flags
            co.set_argument("--disable-blink-features=AutomationControlled")
            co.set_argument("--no-sandbox")
            co.set_argument("--disable-dev-shm-usage")
            co.set_argument("--window-size=1920,1080")

            # Proxy configuration
            if self.proxy:
                proxy_url = self.proxy.url
                co.set_argument(f"--proxy-server={proxy_url}")

            # Set user agent
            co.set_user_agent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )

            # Launch browser
            page = ChromiumPage(co)

            # Inject cookies if provided
            if cookies:
                for name, value in cookies.items():
                    try:
                        page.set.cookies({
                            "name": name,
                            "value": value,
                            "domain": self._extract_domain(url),
                            "path": "/",
                        })
                    except Exception:
                        pass

            # Set extra headers if provided
            if headers:
                try:
                    page.set.headers(headers)
                except Exception:
                    pass

            # Navigate to page
            page.get(url)

            # Wait for page to load
            page.wait.doc_loaded()

            # Extra wait for JS-heavy pages
            import time
            time.sleep(2)

            # Simulate human behavior
            if self.simulate_behavior:
                try:
                    # Random scroll
                    import random
                    page.scroll.down(random.randint(100, 400))
                    time.sleep(0.5)
                    page.scroll.up(random.randint(50, 200))
                except Exception:
                    pass

            # Get page content
            html = page.html

            # Get cookies
            new_cookies = {}
            try:
                for cookie in page.cookies():
                    if isinstance(cookie, dict):
                        new_cookies[cookie.get("name", "")] = cookie.get("value", "")
            except Exception:
                pass

            return ScrapeResult(
                url=url,
                html=html,
                status_code=200,
                headers=headers or {},
                cookies=new_cookies,
                engine=self.name,
                success=True,
            )

        except Exception as exc:
            logger.debug(f"DrissionPage engine error: {exc}")
            return ScrapeResult(
                url=url,
                html="",
                status_code=0,
                engine=self.name,
                success=False,
                error=str(exc),
            )
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.hostname or ""
        except Exception:
            return ""
