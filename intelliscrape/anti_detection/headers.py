"""Smart header rotation and management."""

from __future__ import annotations

import random
from typing import Dict, List, Optional


# Real Chrome header profiles (2024-2026)
_CHROME_PROFILES: List[Dict[str, str]] = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Linux"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Google Chrome";v="129", "Chromium";v="129", "Not_A Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
]

_FIREFOX_PROFILES: List[Dict[str, str]] = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    },
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en-US;q=0.9,en;q=0.8",
    "en-US,en;q=0.9,es;q=0.8",
    "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
]


class HeaderManager:
    """Manages realistic browser headers with rotation."""

    def __init__(
        self,
        *,
        browser: str = "chrome",
        language: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ):
        self.browser = browser.lower()
        self.language = language
        self.custom_headers = custom_headers or {}

    def get_headers(self) -> Dict[str, str]:
        """Get a random realistic header set."""
        if self.browser == "firefox":
            profile = random.choice(_FIREFOX_PROFILES).copy()
        else:
            profile = random.choice(_CHROME_PROFILES).copy()

        # Base headers that all browsers send
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": self.language or random.choice(_ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        # Add browser-specific headers
        headers.update(profile)

        # Add custom headers (override defaults)
        headers.update(self.custom_headers)

        return headers
