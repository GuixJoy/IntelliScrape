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
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
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
                "challenge-platform",
                "cf-browser-verification",
                "challenges.cloudflare.com",
                "access to this page has been denied",
                "press and hold to confirm",
                "press & hold to confirm",
                "before we continue",
                "perimeterx",
                "human security",
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
                # Confirm challenge page is also gone
                if not current_state["has_challenge_page"]:
                    page.wait_for_timeout(2000)
                    return True

            # Check 2: Challenge page disappeared AND no new challenge markers
            if initial_state["has_challenge_page"] and not current_state["has_challenge_page"]:
                page.wait_for_timeout(2000)
                return True

            # Check 3: New cookies appeared (e.g., cf_clearance, _pxvid)
            new_cookies = set(current_state["cookies"].keys()) - set(initial_state["cookies"].keys())
            security_cookies = {
                "cf_clearance", "__cf_bm", "cf_chl_rc_ni", "captcha_verified",
                "_pxvid", "_px3", "_pxhd",
            }
            if new_cookies & security_cookies:
                # Wait a moment and confirm challenge is gone
                page.wait_for_timeout(3000)
                check = self._capture_state(page, url)
                if not check["has_challenge_page"] and not check["has_captcha_widget"]:
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
            # Check for any anti-bot challenge (Cloudflare, PerimeterX, Akamai, DataDome)
            vendor = self._detect_antibot_vendor(html)
            if vendor:
                captcha_info = CaptchaInfo(
                    captcha_type=CaptchaType.TURNSTILE,
                    page_url=url,
                )
            else:
                return SolvedSession(solved=False)

        return self.solve(url, captcha_info, existing_cookies)

    def _detect_antibot_vendor(self, html: str) -> Optional[str]:
        """Detect which anti-bot vendor is blocking the page.

        Returns the vendor name if detected, None otherwise.
        """
        if not html:
            return None
        lower = html.lower()
        html_len = len(html)

        # Cloudflare — strong markers only appear on actual challenge pages
        cf_strong = ["checking your browser", "just a moment", "challenge-platform", "cf-browser-verification"]
        cf_weak = ["challenges.cloudflare.com", "cf-turnstile", "challenge.js"]
        if sum(1 for m in cf_strong if m in lower) >= 1:
            return "cloudflare"
        if sum(1 for m in cf_weak if m in lower) >= 3 and html_len < 50000:
            return "cloudflare"

        # PerimeterX / HUMAN Security
        px_strong = [
            "press and hold to confirm", "press & hold to confirm",
            "press hold to confirm", "before we continue", "px-captcha",
            "access to this page has been denied",
        ]
        px_weak = ["reference id", "_pxhd", "_pxvid", "_px3", "perimeterx", "human security"]
        if sum(1 for m in px_strong if m in lower) >= 1:
            return "perimeterx"
        if sum(1 for m in px_weak if m in lower) >= 3 and html_len < 50000:
            return "perimeterx"

        # Akamai
        ak_strong = ["_abck", "ak_bmsc"]
        ak_weak = ["access denied", "request denied", "akamai"]
        if sum(1 for m in ak_strong if m in lower) >= 1:
            return "akamai"
        if sum(1 for m in ak_weak if m in lower) >= 3 and html_len < 50000:
            return "akamai"

        # DataDome
        dd_strong = ["datadome-captcha", "dd.datadome.co", "captcha.datadome.net"]
        dd_weak = ["datadome", "blocked by", "access denied by"]
        if sum(1 for m in dd_strong if m in lower) >= 1:
            return "datadome"
        if sum(1 for m in dd_weak if m in lower) >= 3 and html_len < 50000:
            return "datadome"

        return None
