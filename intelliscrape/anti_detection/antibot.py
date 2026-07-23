"""Complete anti-bot detection and bypass system."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class AntiBotVendor(Enum):
    """Major anti-bot vendors."""
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    PERIMETERX = "perimeterx"
    DATADOME = "datadome"
    KASADA = "kasada"
    INCAPSULA = "incapsula"
    AWS_WAF = "aws_waf"
    F5_SHAPE = "f5_shape"
    UNKNOWN = "unknown"


@dataclass
class AntiBotInfo:
    """Detected anti-bot protection information."""
    vendor: AntiBotVendor
    confidence: float
    indicators: List[str]
    has_challenge: bool = False
    has_captcha: bool = False


class AntiBotDetector:
    """Detects anti-bot protection vendors and challenge types."""

    # Vendor detection signatures
    VENDOR_SIGNATURES: Dict[AntiBotVendor, Dict[str, List[str]]] = {
        AntiBotVendor.CLOUDFLARE: {
            "headers": ["cf-ray", "cf-cache-status", "server: cloudflare"],
            "cookies": ["cf_clearance", "__cf_bm", "__cfduid"],
            "html": ["checking your browser", "cloudflare", "just a moment", "enable javascript"],
            "js": ["challenge.js", "turnstile", "cf-challenge"],
        },
        AntiBotVendor.AKAMAI: {
            "headers": ["akamai-grn", "x-akamai-transformed"],
            "cookies": ["_abck", "ak_bmsc"],
            "html": ["akamai", "access denied"],
            "js": ["akamai-bm-telemetry"],
        },
        AntiBotVendor.PERIMETERX: {
            "headers": ["x-perimeterx-request-id"],
            "cookies": ["_px3", "_pxvid", "_pxhd"],
            "html": ["perimeterx", "human security"],
            "js": ["px.js", "d.js"],
        },
        AntiBotVendor.DATADOME: {
            "headers": ["x-datadome-request-id", "x-datadome"],
            "cookies": ["datadome", "_dd_s"],
            "html": ["datadome", "captcha", "access denied"],
            "js": ["tags.js"],
        },
        AntiBotVendor.KASADA: {
            "headers": [],
            "cookies": ["KP_UIDz"],
            "html": [],
            "js": ["ips.js", "d.js"],
        },
        AntiBotVendor.INCAPSULA: {
            "headers": [],
            "cookies": ["incap_ses_", "visid_incap_", "reese84"],
            "html": ["imperva", "incapsula"],
            "js": [],
        },
        AntiBotVendor.AWS_WAF: {
            "headers": [],
            "cookies": ["aws-waf-token"],
            "html": ["aws waf"],
            "js": ["/challenge.js"],
        },
    }

    @classmethod
    def detect(
        cls,
        html: str = "",
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
    ) -> Optional[AntiBotInfo]:
        """Detect anti-bot protection on a page.

        Parameters
        ----------
        html : str
            Page HTML content.
        headers : dict, optional
            Response headers.
        cookies : dict, optional
            Response cookies.

        Returns
        -------
        AntiBotInfo or None
            Detected anti-bot information.
        """
        headers = headers or {}
        cookies = cookies or {}
        html_lower = html.lower()

        scores: Dict[AntiBotVendor, float] = {}
        indicators: Dict[AntiBotVendor, List[str]] = {}

        for vendor, signatures in cls.VENDOR_SIGNATURES.items():
            score = 0.0
            found = []

            # Check headers
            for sig in signatures.get("headers", []):
                for header_name, header_value in headers.items():
                    if sig.lower() in f"{header_name.lower()}: {header_value.lower()}":
                        score += 0.4
                        found.append(f"header: {header_name}")

            # Check cookies
            for sig in signatures.get("cookies", []):
                for cookie_name in cookies:
                    if sig.lower() in cookie_name.lower():
                        score += 0.3
                        found.append(f"cookie: {cookie_name}")

            # Check HTML
            for sig in signatures.get("html", []):
                if sig.lower() in html_lower:
                    score += 0.2
                    found.append(f"html: {sig}")

            # Check JS
            for sig in signatures.get("js", []):
                if sig.lower() in html_lower:
                    score += 0.1
                    found.append(f"js: {sig}")

            if score > 0:
                scores[vendor] = score
                indicators[vendor] = found

        if not scores:
            return None

        # Get the highest scoring vendor
        best_vendor = max(scores, key=scores.get)
        best_score = scores[best_vendor]

        if best_score < 0.2:
            return None

        # Detect challenge type
        has_challenge = any(
            sig in html_lower
            for sig in ["checking your browser", "just a moment", "challenge", "verify"]
        )
        has_captcha = any(
            sig in html_lower
            for sig in ["captcha", "recaptcha", "hcaptcha", "turnstile"]
        )

        return AntiBotInfo(
            vendor=best_vendor,
            confidence=min(best_score, 1.0),
            indicators=indicators.get(best_vendor, []),
            has_challenge=has_challenge,
            has_captcha=has_captcha,
        )

    @classmethod
    def get_bypass_recommendation(cls, info: AntiBotInfo) -> str:
        """Get bypass recommendation for detected anti-bot."""
        recommendations = {
            AntiBotVendor.CLOUDFLARE: (
                "Use stealth browser (nodriver/Camoufox) with residential proxy. "
                "TLS impersonation alone won't work for JS challenges."
            ),
            AntiBotVendor.AKAMAI: (
                "Use residential proxy with behavioral simulation. "
                "Session warming recommended."
            ),
            AntiBotVendor.PERIMETERX: (
                "Use stealth browser with fingerprint randomization. "
                "Avoid datacenter IPs."
            ),
            AntiBotVendor.DATADOME: (
                "Use stealth browser with mouse movement simulation. "
                "Residential proxy required."
            ),
            AntiBotVendor.KASADA: (
                "Very difficult to bypass. Consider managed service. "
                "DIY requires custom CDP patches."
            ),
            AntiBotVendor.INCAPSULA: (
                "Use session persistence and residential proxy. "
                "Solve reese84 challenge if present."
            ),
            AntiBotVendor.AWS_WAF: (
                "Solve /challenge.js proof-of-work. "
                "Residential proxy recommended."
            ),
            AntiBotVendor.F5_SHAPE: (
                "Use residential proxy with TLS impersonation. "
                "Session persistence required."
            ),
        }
        return recommendations.get(info.vendor, "Try stealth browser with residential proxy.")
