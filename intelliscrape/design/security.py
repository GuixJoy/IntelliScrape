"""URL and resource policy for design extraction.

Local-library scope for now: scheme/shape validation only, because a local
user may legitimately target localhost or an intranet host.

The *hosted* service must additionally enforce network-egress SSRF protection
(blocking private, loopback, link-local, metadata and reserved IPv4/IPv6
ranges at connection resolution, validating redirects and subresources). That
is a Milestone C concern and is intentionally not implemented here — the
hosted entry point must reuse this module's policy plus its own egress
boundary, never a flag that disables it.
"""

from __future__ import annotations

from urllib.parse import urlparse

ALLOWED_SCHEMES = ("http", "https")


def validate_target_url(url: str) -> str:
    """Validate a caller-supplied target URL. Returns the URL, raises ValueError.

    Rejects non-http(s) schemes and URLs with embedded credentials.
    """
    if not url or not isinstance(url, str):
        raise ValueError("A URL string is required")
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"Only http/https URLs are supported, got scheme={parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("URL has no hostname")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed")
    return url.strip()


def is_safe_color(value: str) -> bool:
    """Defence-in-depth guard before a value is used in generated preview CSS.

    The normalizer already constrains colors; this re-checks at the render
    boundary so a future regression cannot smuggle arbitrary CSS into the
    preview's inline styles.
    """
    import re

    if not value or len(value) > 120:
        return False
    return bool(
        re.fullmatch(
            r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))",
            value.strip(),
        )
    )
