"""CAPTCHA detection and solving integration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class CaptchaType(Enum):
    """Types of CAPTCHAs."""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    TURNSTILE = "turnstile"
    FUNCAPTCHA = "funcaptcha"
    IMAGE_CAPTCHA = "image_captcha"
    TEXT_CAPTCHA = "text_captcha"
    UNKNOWN = "unknown"


@dataclass
class CaptchaInfo:
    """Information about a detected CAPTCHA."""
    captcha_type: CaptchaType
    site_key: Optional[str] = None
    page_url: Optional[str] = None
    widget_id: Optional[str] = None


class CaptchaDetector:
    """Detects CAPTCHA types on a page."""

    # CAPTCHA signatures in HTML
    SIGNATURES = {
        CaptchaType.RECAPTCHA_V2: [
            r'google\.com/recaptcha',
            r'g-recaptcha',
            r'data-sitekey',
        ],
        CaptchaType.RECAPTCHA_V3: [
            r'google\.com/recaptcha/api\.js\?.*render=',
            r'grecaptcha\.execute',
        ],
        CaptchaType.HCAPTCHA: [
            r'hcaptcha\.com',
            r'h-captcha',
            r'data-hcaptcha-widget-id',
        ],
        CaptchaType.TURNSTILE: [
            r'challenges\.cloudflare\.com',
            r'cf-turnstile',
            r'turnstile',
        ],
        CaptchaType.FUNCAPTCHA: [
            r'funcaptcha',
            r'arkoselabs\.com',
            r'fc Challenge',
        ],
    }

    @classmethod
    def detect(cls, html: str, url: Optional[str] = None) -> Optional[CaptchaInfo]:
        """Detect CAPTCHA type in HTML content.

        Parameters
        ----------
        html : str
            Page HTML content.
        url : str, optional
            Page URL for context.

        Returns
        -------
        CaptchaInfo or None
            Detected CAPTCHA information.
        """
        if not html:
            return None

        html_lower = html.lower()

        for captcha_type, patterns in cls.SIGNATURES.items():
            for pattern in patterns:
                if re.search(pattern, html_lower):
                    # Try to extract site key
                    site_key = cls._extract_site_key(html, captcha_type)
                    return CaptchaInfo(
                        captcha_type=captcha_type,
                        site_key=site_key,
                        page_url=url,
                    )

        return None

    @classmethod
    def _extract_site_key(cls, html: str, captcha_type: CaptchaType) -> Optional[str]:
        """Extract site key from HTML."""
        if captcha_type == CaptchaType.RECAPTCHA_V2:
            match = re.search(r'data-sitekey="([^"]+)"', html)
            if match:
                return match.group(1)

        elif captcha_type == CaptchaType.HCAPTCHA:
            match = re.search(r'data-sitekey="([^"]+)"', html)
            if match:
                return match.group(1)

        elif captcha_type == CaptchaType.TURNSTILE:
            match = re.search(r'data-sitekey="([^"]+)"', html)
            if match:
                return match.group(1)
            # Also check for sitekey in script
            match = re.search(r"sitekey['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]", html)
            if match:
                return match.group(1)

        return None


class CaptchaSolver:
    """Solves CAPTCHAs using external services.

    Supports:
    - 2Captcha (2captcha.com)
    - CapSolver (capsolver.com)
    """

    def __init__(
        self,
        provider: str = "2captcha",
        api_key: Optional[str] = None,
    ):
        self.provider = provider.lower()
        self.api_key = api_key

    def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        *,
        invisible: bool = False,
    ) -> Optional[str]:
        """Solve reCAPTCHA v2.

        Returns the response token.
        """
        if not self.api_key:
            raise ValueError(f"{self.provider} API key required")

        if self.provider == "2captcha":
            return self._solve_2captcha_recaptcha_v2(site_key, page_url, invisible=invisible)
        elif self.provider == "capsolver":
            return self._solve_capsolver_recaptcha_v2(site_key, page_url)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def solve_hcaptcha(self, site_key: str, page_url: str) -> Optional[str]:
        """Solve hCaptcha."""
        if not self.api_key:
            raise ValueError(f"{self.provider} API key required")

        if self.provider == "2captcha":
            return self._solve_2captcha_hcaptcha(site_key, page_url)
        elif self.provider == "capsolver":
            return self._solve_capsolver_hcaptcha(site_key, page_url)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def solve_turnstile(self, site_key: str, page_url: str) -> Optional[str]:
        """Solve Cloudflare Turnstile."""
        if not self.api_key:
            raise ValueError(f"{self.provider} API key required")

        if self.provider == "capsolver":
            return self._solve_capsolver_turnstile(site_key, page_url)
        else:
            raise ValueError(f"Turnstile solving requires capsolver provider")

    def _solve_2captcha_recaptcha_v2(
        self, site_key: str, page_url: str, *, invisible: bool = False
    ) -> Optional[str]:
        """Solve reCAPTCHA v2 via 2Captcha."""
        import requests
        import time

        # Submit task
        response = requests.post("http://2captcha.com/in.php", data={
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "invisible": 1 if invisible else 0,
            "json": 1,
        })

        if response.json().get("status") != 1:
            return None

        task_id = response.json()["request"]

        # Poll for result
        for _ in range(60):
            time.sleep(3)
            result = requests.get(
                f"http://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1"
            )
            if result.json().get("status") == 1:
                return result.json()["request"]

        return None

    def _solve_2captcha_hcaptcha(self, site_key: str, page_url: str) -> Optional[str]:
        """Solve hCaptcha via 2Captcha."""
        import requests
        import time

        response = requests.post("http://2captcha.com/in.php", data={
            "key": self.api_key,
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1,
        })

        if response.json().get("status") != 1:
            return None

        task_id = response.json()["request"]

        for _ in range(60):
            time.sleep(3)
            result = requests.get(
                f"http://2captcha.com/res.php?key={self.api_key}&action=get&id={task_id}&json=1"
            )
            if result.json().get("status") == 1:
                return result.json()["request"]

        return None

    def _solve_capsolver_recaptcha_v2(self, site_key: str, page_url: str) -> Optional[str]:
        """Solve reCAPTCHA v2 via CapSolver."""
        import requests
        import time

        response = requests.post("https://api.capsolver.com/createTask", json={
            "clientKey": self.api_key,
            "task": {
                "type": "ReCaptchaV2TaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        })

        if response.json().get("errorId") != 0:
            return None

        task_id = response.json()["taskId"]

        for _ in range(60):
            time.sleep(3)
            result = requests.post("https://api.capsolver.com/getTaskResult", json={
                "clientKey": self.api_key,
                "taskId": task_id,
            })
            if result.json().get("status") == "ready":
                return result.json()["solution"]["gRecaptchaResponse"]

        return None

    def _solve_capsolver_hcaptcha(self, site_key: str, page_url: str) -> Optional[str]:
        """Solve hCaptcha via CapSolver."""
        import requests
        import time

        response = requests.post("https://api.capsolver.com/createTask", json={
            "clientKey": self.api_key,
            "task": {
                "type": "HCaptchaTaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        })

        if response.json().get("errorId") != 0:
            return None

        task_id = response.json()["taskId"]

        for _ in range(60):
            time.sleep(3)
            result = requests.post("https://api.capsolver.com/getTaskResult", json={
                "clientKey": self.api_key,
                "taskId": task_id,
            })
            if result.json().get("status") == "ready":
                return result.json()["solution"]["gRecaptchaResponse"]

        return None

    def _solve_capsolver_turnstile(self, site_key: str, page_url: str) -> Optional[str]:
        """Solve Cloudflare Turnstile via CapSolver."""
        import requests
        import time

        response = requests.post("https://api.capsolver.com/createTask", json={
            "clientKey": self.api_key,
            "task": {
                "type": "AntiTurnstileTaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        })

        if response.json().get("errorId") != 0:
            return None

        task_id = response.json()["taskId"]

        for _ in range(60):
            time.sleep(3)
            result = requests.post("https://api.capsolver.com/getTaskResult", json={
                "clientKey": self.api_key,
                "taskId": task_id,
            })
            if result.json().get("status") == "ready":
                return result.json()["solution"]["token"]

        return None
