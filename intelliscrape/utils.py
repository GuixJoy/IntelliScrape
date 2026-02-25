"""HTML intelligence utilities used by the IntelliScrape pipeline."""

from __future__ import annotations

from typing import Iterable, Optional, Union

from bs4 import BeautifulSoup, SoupStrainer

HtmlInput = Optional[Union[str, bytes]]

_MIN_HTML_CHARS = 480
_MIN_TEXT_CHARS = 220
_MIN_WORD_COUNT = 35
_MAX_SCRIPT_DIV_RATIO = 0.8

_PLACEHOLDER_TOKENS = {
    "loading",
    "please wait",
    "checking your browser",
    "enable javascript",
    "just a moment",
    "stand by",
}

_FRAMEWORK_MARKERS = {
    'id="app"',
    'id="root"',
    'id="__next"',
    "data-server-rendered",
    "data-reactroot",
    "ng-version",
    "sapper-app",
    "vite-legacy-polyfill",
    "window.__NUXT__",
    "window.__NEXT_DATA__",
}

_JS_LIB_MARKERS = {
    "react",
    "next.js",
    "nextjs",
    "vue",
    "nuxt",
    "svelte",
    "angular",
    "astro",
    "remix",
}

_SECURITY_INTERSTITIAL_MARKERS = {
    "cf-browser-verification",
    "cloudflare",
    "captcha",
    "hcaptcha",
    "__cf_chl_captcha_tk__",
    "access denied",
}

_LOGIN_MARKERS = {
    'type="password"',
    'name="password"',
    "forgot password",
    "sign in",
    "log in",
    "account-required",
    "two-factor",
}


def _normalize_html(html: HtmlInput) -> str:
    """Return a stripped string representation."""

    if html is None:
        return ""

    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="ignore")

    elif not isinstance(html, str):
        html = str(html)

    return html.strip()


def _contains_any(haystack: str, needles: Iterable[str]) -> bool:
    """Case-insensitive membership helper."""

    lowered = haystack.lower()
    return any(n.lower() in lowered for n in needles)


def is_html_empty(html: HtmlInput) -> bool:
    """Return True if HTML looks empty."""

    normalized = _normalize_html(html)

    if not normalized:
        return True

    if len(normalized) < _MIN_HTML_CHARS:
        return True

    html_lower = normalized.lower()

    if "<html" not in html_lower and "<body" not in html_lower:
        return True

    return False


def has_meaningful_text(html: HtmlInput) -> bool:
    """Return True if HTML contains readable text."""

    normalized = _normalize_html(html)

    # Large HTML almost always has meaningful content
    if len(normalized) > 20000:
        return True

    if len(normalized) < 200:
        return False

    try:
        soup = BeautifulSoup(normalized, "html.parser")
    except Exception:
        return False

    text = soup.get_text(" ", strip=True)

    if not text:
        return False

    if _contains_any(text, _PLACEHOLDER_TOKENS):
        return False

    return len(text) > 80

    # Allow small but valid static pages (example.com fix)
    if len(text) >= 80:
        return True

    # Normal pages
    return len(text) >= _MIN_TEXT_CHARS and len(words) >= _MIN_WORD_COUNT



def looks_like_js_page(html: HtmlInput) -> bool:
    """Detect JS-heavy pages."""

    normalized = _normalize_html(html)

    if not normalized:
        return True

    # Large pages are almost always static
    if len(normalized) > 50000:
        return False

    # Login markers only matter on small pages
    if len(normalized) < 3000 and _contains_any(html_lower, _LOGIN_MARKERS):
        return True

    # Only trigger JS detection if HTML is small
    if len(normalized) < 5000 and _contains_any(html_lower, _JS_LIB_MARKERS):
        return True

    if _contains_any(html_lower, _SECURITY_INTERSTITIAL_MARKERS):
        return True

    if _contains_any(html_lower, _LOGIN_MARKERS):
        return True

    script_count = html_lower.count("<script")
    div_count = html_lower.count("<div") or 1

    if div_count > 10:
        return (script_count / div_count) > _MAX_SCRIPT_DIV_RATIO

    return False


def html_needs_browser(html: HtmlInput) -> bool:
    """Decide if browser rendering is required."""

    normalized = _normalize_html(html)

    if not normalized:
        return True

    if is_html_empty(normalized):
        return True

    if looks_like_js_page(normalized):
        return True

    if not has_meaningful_text(normalized):
        return True

    return False