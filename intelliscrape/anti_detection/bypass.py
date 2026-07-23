"""Advanced anti-bot bypass techniques.

This module provides specialized bypass methods for major anti-bot vendors:
- Cloudflare Turnstile
- DataDome
- PerimeterX (HUMAN Security)
- Akamai
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TurnstileConfig:
    """Cloudflare Turnstile bypass configuration."""
    site_key: Optional[str] = None
    page_url: Optional[str] = None
    action: str = "managed"
    cdata: str = ""


@dataclass
class DataDomeConfig:
    """DataDome bypass configuration."""
    page_url: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None


class CloudflareTurnstileBypass:
    """Bypass Cloudflare Turnstile challenges.

    Turnstile is Cloudflare's CAPTCHA replacement that runs in the background.
    It requires JavaScript execution and browser attestation.

    Bypass strategies:
    1. Use stealth browser (Camoufox/nodriver) - most reliable
    2. Use CAPTCHA solving API (CapSolver/2Captcha)
    3. Use residential proxy + waiting (sometimes auto-resolves)
    """

    @staticmethod
    def detect(html: str) -> bool:
        """Detect Turnstile challenge in HTML."""
        indicators = [
            "challenges.cloudflare.com",
            "cf-turnstile",
            "turnstile",
            "data-sitekey",
        ]
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in indicators)

    @staticmethod
    def extract_site_key(html: str) -> Optional[str]:
        """Extract Turnstile site key from HTML."""
        patterns = [
            r'data-sitekey="([^"]+)"',
            r"sitekey['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"cf-turnstile.*?data-sitekey=\"([^\"]+)\"",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    @staticmethod
    async def solve_with_capsolver(
        page,
        api_key: str,
        site_key: str,
        page_url: str,
    ) -> bool:
        """Solve Turnstile using CapSolver API.

        Parameters
        ----------
        page : playwright.Page
            The page with the Turnstile challenge.
        api_key : str
            CapSolver API key.
        site_key : str
            Turnstile site key.
        page_url : str
            URL of the page.

        Returns
        -------
        bool
            True if solved successfully.
        """
        import requests
        import time

        # Create task
        response = requests.post("https://api.capsolver.com/createTask", json={
            "clientKey": api_key,
            "task": {
                "type": "AntiTurnstileTaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        })

        if response.json().get("errorId") != 0:
            return False

        task_id = response.json()["taskId"]

        # Poll for result
        for _ in range(30):
            time.sleep(2)
            result = requests.post("https://api.capsolver.com/getTaskResult", json={
                "clientKey": api_key,
                "taskId": task_id,
            })

            if result.json().get("status") == "ready":
                token = result.json()["solution"]["token"]
                # Inject token into page
                await page.evaluate(f"""
                    document.querySelector('[name="cf-turnstile-response"]').value = '{token}';
                    document.querySelector('form').submit();
                """)
                return True

        return False


class DataDomeBypass:
    """Bypass DataDome anti-bot protection.

    DataDome uses behavioral analysis and ML scoring.
    Key detection signals:
    - Mouse movement patterns
    - Scroll behavior
    - Request timing
    - Browser fingerprint

    Bypass strategies:
    1. Use Camoufox (Firefox-based, different fingerprint)
    2. Add realistic behavioral simulation
    3. Use residential proxy
    4. Warm up session before hitting protected pages
    """

    @staticmethod
    def detect(html: str, headers: Optional[Dict[str, str]] = None) -> bool:
        """Detect DataDome protection."""
        indicators = [
            "datadome",
            "captcha",
            "access denied",
            "x-datadome",
        ]
        html_lower = html.lower()

        # Check HTML
        if any(indicator in html_lower for indicator in indicators):
            return True

        # Check headers
        if headers:
            for key, value in headers.items():
                if "datadome" in key.lower():
                    return True

        return False

    @staticmethod
    def get_bypass_config() -> Dict:
        """Get recommended bypass configuration for DataDome."""
        return {
            "engine": "camoufox",  # Firefox-based, different fingerprint
            "simulate_behavior": True,  # Human-like mouse/scroll
            "min_delay": 1.0,  # Slower requests
            "max_delay": 4.0,
            "proxy_type": "residential",  # Must use residential IP
        }


class PerimeterXBypass:
    """Bypass PerimeterX (HUMAN Security) protection.

    PerimeterX runs deep fingerprinting via _px scripts.
    Checks: canvas, WebGL, AudioContext, fonts, screen.

    Bypass strategies:
    1. Use Camoufox (engine-level patches)
    2. Randomize fingerprint per session
    3. Use residential proxy
    4. Add session warming
    """

    @staticmethod
    def detect(html: str, cookies: Optional[Dict[str, str]] = None) -> bool:
        """Detect PerimeterX protection."""
        indicators = [
            "_px3",
            "_pxvid",
            "_pxhd",
            "perimeterx",
            "px.js",
            "human security",
        ]
        html_lower = html.lower()

        if any(indicator in html_lower for indicator in indicators):
            return True

        if cookies:
            for cookie_name in cookies:
                if "_px" in cookie_name:
                    return True

        return False

    @staticmethod
    def get_bypass_config() -> Dict:
        """Get recommended bypass configuration for PerimeterX."""
        return {
            "engine": "camoufox",
            "simulate_behavior": True,
            "min_delay": 1.5,
            "max_delay": 5.0,
            "proxy_type": "residential",
            "fingerprint_randomize": True,
        }


class AkamaiBypass:
    """Bypass Akamai Bot Manager.

    Akamai uses behavioral sensor data and session flow analysis.
    The _abck cookie encodes behavior telemetry.

    Bypass strategies:
    1. Use stealth browser with behavioral simulation
    2. Session warming (visit homepage first)
    3. Use residential proxy
    4. Realistic timing patterns
    """

    @staticmethod
    def detect(html: str, headers: Optional[Dict[str, str]] = None, cookies: Optional[Dict[str, str]] = None) -> bool:
        """Detect Akamai protection."""
        indicators = [
            "_abck",
            "akamai",
            "ak_bmsc",
            "akamai-grn",
        ]

        html_lower = html.lower()
        if any(indicator in html_lower for indicator in indicators):
            return True

        if headers:
            for key in headers:
                if "akamai" in key.lower():
                    return True

        if cookies:
            for cookie_name in cookies:
                if "_abck" in cookie_name or "ak_bmsc" in cookie_name:
                    return True

        return False

    @staticmethod
    def get_bypass_config() -> Dict:
        """Get recommended bypass configuration for Akamai."""
        return {
            "engine": "playwright_stealth",
            "simulate_behavior": True,
            "min_delay": 2.0,
            "max_delay": 6.0,
            "proxy_type": "residential",
            "session_warming": True,
        }


class AntiBotBypassFactory:
    """Factory for creating anti-bot bypass handlers."""

    BYPASS_CLASSES = {
        "cloudflare_turnstile": CloudflareTurnstileBypass,
        "datadome": DataDomeBypass,
        "perimeterx": PerimeterXBypass,
        "akamai": AkamaiBypass,
    }

    @classmethod
    def get_bypass(cls, vendor: str):
        """Get bypass handler for a vendor."""
        return cls.BYPASS_CLASSES.get(vendor.lower())

    @classmethod
    def get_config(cls, vendor: str) -> Dict:
        """Get recommended bypass configuration for a vendor."""
        bypass_class = cls.BYPASS_CLASSES.get(vendor.lower())
        if bypass_class and hasattr(bypass_class, "get_bypass_config"):
            return bypass_class.get_bypass_config()
        return {}

    @classmethod
    def list_vendors(cls) -> List[str]:
        """List supported vendors."""
        return list(cls.BYPASS_CLASSES.keys())
