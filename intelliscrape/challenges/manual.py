"""Manual CAPTCHA solver - opens visible browser for user to solve."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from .captcha import CaptchaDetector, CaptchaInfo, CaptchaType

logger = logging.getLogger("intelliscrape")


@dataclass
class SolvedSession:
    """Result of a manual CAPTCHA solve."""

    cookies: Dict[str, str] = field(default_factory=dict)
    url: str = ""
    html: str = ""
    solved: bool = False
    solver: str = "manual"


class ManualCaptchaSolver:
    """Opens a visible browser for the user to solve CAPTCHAs manually.

    When a CAPTCHA is detected during scraping, this solver:
    1. Opens a visible Chromium browser window
    2. Navigates to the URL with the CAPTCHA
    3. Waits for the user to solve it
    4. Detects when the CAPTCHA is solved (page changes, cookies appear)
    5. Returns the solved session cookies for continuing the scrape
    """

    def __init__(self, timeout: int = 300, headless: bool = False):
        self.timeout = timeout
        self.headless = headless

    def solve(
        self,
        url: str,
        captcha_info: Optional[CaptchaInfo] = None,
        existing_cookies: Optional[Dict[str, str]] = None,
    ) -> SolvedSession:
        """Open browser for manual CAPTCHA solve.

        Parameters
        ----------
        url : str
            URL with the CAPTCHA.
        captcha_info : CaptchaInfo, optional
            Detected CAPTCHA info. If None, will be auto-detected.
        existing_cookies : dict, optional
            Cookies to inject before showing CAPTCHA.

        Returns
        -------
        SolvedSession
            Solved session with cookies and status.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed - cannot open manual CAPTCHA browser")
            return SolvedSession()

        captcha_name = captcha_info.captcha_type.value if captcha_info else "CAPTCHA"

        print(f"\n[IntelliScrape] {captcha_name} detected on {url}")
        print("[IntelliScrape] Opening browser for manual CAPTCHA solve...")
        print("[IntelliScrape] Please solve the CAPTCHA in the browser window.")
        print("[IntelliScrape] I'll detect when it's solved automatically.\n")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--window-size=1280,720",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            page = context.new_page()

            # Inject existing cookies
            if existing_cookies:
                cookie_list = []
                for name, value in existing_cookies.items():
                    cookie_list.append({
                        "name": name,
                        "value": value,
                        "domain": self._extract_domain(url),
                        "path": "/",
                    })
                if cookie_list:
                    context.add_cookies(cookie_list)

            # Navigate to page
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                logger.warning(f"Navigation timed out, continuing: {e}")

            # Record initial state for change detection
            initial_state = self._capture_state(page, url)

            # Wait for user to solve CAPTCHA
            solved = self._wait_for_solve(page, url, initial_state, captcha_name)

            if solved:
                # Extract cookies after solve
                cookies = {c["name"]: c["value"] for c in context.cookies()}
                html = page.content()
                final_url = page.url

                print(f"[IntelliScrape] {captcha_name} solved! Continuing scrape...")

                browser.close()
                return SolvedSession(
                    cookies=cookies,
                    url=final_url,
                    html=html,
                    solved=True,
                    solver="manual",
                )
            else:
                print(f"[IntelliScrape] {captcha_name} solve timed out after {self.timeout}s")
                browser.close()
                return SolvedSession(solved=False)

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for cookie setting."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.hostname or ""
            # Remove leading dot for cookie domain
            return domain.lstrip(".")
        except Exception:
            return ""

    def _capture_state(self, page, url: str) -> dict:
        """Capture page state for change detection."""
        state = {
            "url": page.url,
            "title": page.title(),
            "cookies": {c["name"]: c["value"] for c in page.context.cookies()},
            "html_length": len(page.content()),
            "has_captcha_widget": False,
            "has_challenge_page": False,
        }

        try:
            html = page.content().lower()
            # Check for CAPTCHA widgets
            captcha_selectors = [
                'iframe[src*="recaptcha"]',
                'iframe[src*="hcaptcha"]',
                'iframe[src*="challenges.cloudflare.com"]',
                '.cf-turnstile',
                '#cf-turnstile-response',
                '.h-captcha',
                '.g-recaptcha',
            ]
            for selector in captcha_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        state["has_captcha_widget"] = True
                        break
                except Exception:
                    continue

            # Check for challenge pages
            challenge_markers = [
                "checking your browser",
                "just a moment",
                "verify you are human",
                "security check",
                "enable javascript",
            ]
            for marker in challenge_markers:
                if marker in html:
                    state["has_challenge_page"] = True
                    break
        except Exception:
            pass

        return state

    def _wait_for_solve(self, page, url: str, initial_state: dict, captcha_name: str) -> bool:
        """Wait for CAPTCHA to be solved by user."""
        check_interval = 3
        elapsed = 0
        max_wait = self.timeout

        while elapsed < max_wait:
            page.wait_for_timeout(check_interval * 1000)
            elapsed += check_interval

            current_state = self._capture_state(page, url)

            # Check 1: CAPTCHA widget disappeared
            if initial_state["has_captcha_widget"] and not current_state["has_captcha_widget"]:
                # Wait a bit more for page to load after solve
                page.wait_for_timeout(2000)
                return True

            # Check 2: Challenge page disappeared
            if initial_state["has_challenge_page"] and not current_state["has_challenge_page"]:
                page.wait_for_timeout(2000)
                return True

            # Check 3: URL changed (redirect after solve)
            if current_state["url"] != initial_state["url"]:
                page.wait_for_timeout(2000)
                return True

            # Check 4: New cookies appeared (e.g., cf_clearance)
            new_cookies = set(current_state["cookies"].keys()) - set(initial_state["cookies"].keys())
            security_cookies = {"cf_clearance", "__cf_bm", "cf_chl_rc_ni", "captcha_verified"}
            if new_cookies & security_cookies:
                page.wait_for_timeout(2000)
                return True

            # Check 5: Page content changed significantly (>50% different)
            if current_state["html_length"] > 0 and initial_state["html_length"] > 0:
                ratio = current_state["html_length"] / initial_state["html_length"]
                if ratio > 1.5 or ratio < 0.5:
                    # Significant content change
                    if not current_state["has_captcha_widget"] and not current_state["has_challenge_page"]:
                        page.wait_for_timeout(2000)
                        return True

            # Progress update every 15 seconds
            if elapsed % 15 == 0:
                remaining = max_wait - elapsed
                print(f"[IntelliScrape] Waiting for {captcha_name} solve... ({remaining}s remaining)")

        return False

    def solve_if_detected(
        self,
        url: str,
        html: str,
        existing_cookies: Optional[Dict[str, str]] = None,
    ) -> SolvedSession:
        """Detect CAPTCHA and solve if found.

        Parameters
        ----------
        url : str
            Page URL.
        html : str
            Page HTML content.
        existing_cookies : dict, optional
            Existing session cookies.

        Returns
        -------
        SolvedSession
            Result of the solve attempt.
        """
        captcha_info = CaptchaDetector.detect(html, url)
        if captcha_info is None:
            # Also check for Cloudflare challenge in HTML
            if self._is_cloudflare_challenge(html):
                captcha_info = CaptchaInfo(
                    captcha_type=CaptchaType.TURNSTILE,
                    page_url=url,
                )
            else:
                return SolvedSession(solved=False)

        return self.solve(url, captcha_info, existing_cookies)

    def _is_cloudflare_challenge(self, html: str) -> bool:
        """Check if HTML is a Cloudflare challenge page."""
        if not html:
            return False
        lower = html.lower()
        markers = [
            "checking your browser",
            "just a moment",
            "enable javascript",
            "verify you are human",
            "challenge-platform",
            "cf-browser-verification",
            "attention required",
            "security check",
        ]
        return any(marker in lower for marker in markers)
