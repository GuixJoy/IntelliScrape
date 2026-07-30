"""Core technology stack extractor.

Analyses raw HTML, HTTP headers, cookies and URL to identify technologies
used by a website.  Uses confidence-weighted signature matching (same
pattern as AntiBotDetector).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .signatures import (
    ANALYTICS,
    CDN,
    CMS,
    CSS_FRAMEWORKS,
    EMAIL_MARKETING,
    FRAMEWORKS,
    HOSTING,
    JS_LIBRARIES,
    LANGUAGES,
    OTHER,
    PAYMENT,
)

# Weights for each signal type (must sum to 1.0)
_WEIGHTS = {
    "html": 0.30,
    "headers": 0.30,
    "cookies": 0.20,
    "url": 0.15,
    "js": 0.05,
}

# Minimum confidence to report a detection
_MIN_CONFIDENCE = 0.3


@dataclass
class TechInfo:
    """Single detected technology."""
    name: str
    category: str
    confidence: float
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


@dataclass
class TechStack:
    """Full technology stack report for a URL."""
    url: str
    frameworks: List[TechInfo] = field(default_factory=list)
    css_frameworks: List[TechInfo] = field(default_factory=list)
    js_libraries: List[TechInfo] = field(default_factory=list)
    analytics: List[TechInfo] = field(default_factory=list)
    cdn: List[TechInfo] = field(default_factory=list)
    hosting: List[TechInfo] = field(default_factory=list)
    cms: List[TechInfo] = field(default_factory=list)
    payment: List[TechInfo] = field(default_factory=list)
    languages: List[TechInfo] = field(default_factory=list)
    email_marketing: List[TechInfo] = field(default_factory=list)
    other: List[TechInfo] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)

    @property
    def all_tech(self) -> List[TechInfo]:
        """Return every detected technology as a flat list."""
        out: List[TechInfo] = []
        for attr in (
            "frameworks", "css_frameworks", "js_libraries", "analytics",
            "cdn", "hosting", "cms", "payment", "languages",
            "email_marketing", "other",
        ):
            out.extend(getattr(self, attr))
        return out

    @property
    def summary(self) -> Dict[str, List[str]]:
        """Return category -> list of tech names."""
        return {
            "frameworks": [t.name for t in self.frameworks],
            "css_frameworks": [t.name for t in self.css_frameworks],
            "js_libraries": [t.name for t in self.js_libraries],
            "analytics": [t.name for t in self.analytics],
            "cdn": [t.name for t in self.cdn],
            "hosting": [t.name for t in self.hosting],
            "cms": [t.name for t in self.cms],
            "payment": [t.name for t in self.payment],
            "languages": [t.name for t in self.languages],
            "email_marketing": [t.name for t in self.email_marketing],
            "other": [t.name for t in self.other],
        }

    def to_dict(self) -> dict:
        result: dict = {"url": self.url}
        s = self.summary
        for key, val in s.items():
            if val:
                result[key] = val
        if self.headers:
            result["server_headers"] = {
                k: v for k, v in self.headers.items()
                if k.lower() in (
                    "server", "x-powered-by", "x-generator",
                    "via", "x-amz-cf-pop", "x-vercel",
                    "cf-ray", "x-shopify-stage",
                )
            }
        return result


class TechStackExtractor:
    """Detect the technology stack from raw HTML, headers and cookies."""

    @classmethod
    def extract(
        cls,
        html: str,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        url: str = "",
    ) -> TechStack:
        """Analyse *html* + *headers* + *cookies* and return a TechStack."""
        headers = headers or {}
        cookies = cookies or {}
        html_lower = html.lower()

        # Pre-build helper strings
        header_str = " ".join(
            f"{k.lower()}: {v.lower()}" for k, v in headers.items()
        )
        cookie_names = [c.lower() for c in cookies]
        url_lower = url.lower()

        # Collect all <script src="..."> and <link href="..."> URLs
        asset_urls = " ".join(
            m.lower()
            for m in re.findall(
                r'(?:src|href)=["\']([^"\']+)["\']', html, re.IGNORECASE
            )
        )

        # Extract JS globals from inline scripts
        js_globals = " ".join(
            m
            for m in re.findall(
                r"(?:window\.|globalThis\.)(\w+)", html, re.IGNORECASE
            )
        )

        stack = TechStack(url=url, headers=dict(headers))

        # Run detection for each category
        cat_map = [
            ("frameworks", FRAMEWORKS, "framework"),
            ("css_frameworks", CSS_FRAMEWORKS, "css_framework"),
            ("js_libraries", JS_LIBRARIES, "js_library"),
            ("analytics", ANALYTICS, "analytics"),
            ("cdn", CDN, "cdn"),
            ("hosting", HOSTING, "hosting"),
            ("cms", CMS, "cms"),
            ("payment", PAYMENT, "payment"),
            ("languages", LANGUAGES, "language"),
            ("email_marketing", EMAIL_MARKETING, "email_marketing"),
            ("other", OTHER, "other"),
        ]

        for attr_name, signatures, category in cat_map:
            detected = cls._detect_category(
                signatures, category, html_lower, header_str,
                cookie_names, url_lower, asset_urls, js_globals,
            )
            setattr(stack, attr_name, detected)

        return stack

    @classmethod
    def _detect_category(
        cls,
        signatures: dict[str, dict[str, list[str]]],
        category: str,
        html_lower: str,
        header_str: str,
        cookie_names: list[str],
        url_lower: str,
        asset_urls: str,
        js_globals: str,
    ) -> List[TechInfo]:
        results: List[TechInfo] = []

        for tech_name, sigs in signatures.items():
            evidence: List[str] = []
            total_score = 0.0

            # HTML patterns
            for pat in sigs.get("html", []):
                if pat.lower() in html_lower:
                    total_score += _WEIGHTS["html"]
                    evidence.append(f"html:{pat}")

            # Headers
            for pat in sigs.get("headers", []):
                if pat.lower() in header_str:
                    total_score += _WEIGHTS["headers"]
                    evidence.append(f"header:{pat}")

            # Cookies
            for pat in sigs.get("cookies", []):
                for cn in cookie_names:
                    if pat.lower() in cn:
                        total_score += _WEIGHTS["cookies"]
                        evidence.append(f"cookie:{cn}")
                        break

            # URL patterns (in page URLs and asset URLs)
            for pat in sigs.get("url", []):
                combined = url_lower + " " + asset_urls
                if pat.lower() in combined:
                    total_score += _WEIGHTS["url"]
                    evidence.append(f"url:{pat}")

            # JS globals
            for pat in sigs.get("js", []):
                if pat.lower() in js_globals.lower() or pat.lower() in html_lower:
                    total_score += _WEIGHTS["js"]
                    evidence.append(f"js:{pat}")

            # Clamp to [0, 1]
            confidence = min(total_score, 1.0)

            if confidence >= _MIN_CONFIDENCE and evidence:
                results.append(
                    TechInfo(
                        name=tech_name,
                        category=category,
                        confidence=confidence,
                        evidence=evidence,
                    )
                )

        # Sort by confidence descending
        results.sort(key=lambda t: t.confidence, reverse=True)
        return results
