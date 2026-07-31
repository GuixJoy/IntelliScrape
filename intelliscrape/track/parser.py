"""HTML/CSS/JS asset discovery parser.

Ported from HTTrack's htsparse.c link-extraction logic.
Discovers all linked resources (images, stylesheets, scripts, fonts, etc.)
from HTML, CSS, and JavaScript content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urldefrag

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# HTML attributes that contain URLs  (cf. HTTrack's hts_detect[] in htslib.c)
# ---------------------------------------------------------------------------

HTML_URL_ATTRS: dict[str, list[str]] = {
    "a": ["href"],
    "area": ["href"],
    "audio": ["src"],
    "embed": ["src"],
    "iframe": ["src"],
    "img": ["src", "srcset", "data-src", "data-srcset", "lowsrc", "dynsrc", "poster"],
    "link": ["href"],  # stylesheets, favicons, manifests
    "object": ["data", "codebase"],
    "script": ["src"],
    "source": ["src", "srcset"],
    "track": ["src"],
    "use": ["href", "xlink:href"],
    "video": ["src", "poster"],
}

# Attributes that should never be treated as URL sources
HTML_NON_URL_ATTRS: set[str] = {
    "class", "id", "alt", "title", "style", "name", "type", "rel",
    "content", "charset", "lang", "dir", "tabindex", "accesskey",
}

# ---------------------------------------------------------------------------
# CSS url() / @import patterns
# ---------------------------------------------------------------------------

CSS_URL_RE = re.compile(
    r"""(url\s*\(\s*["']?)([^"')\s]+)(["']?\s*\))""",
    re.IGNORECASE,
)

CSS_IMPORT_RE = re.compile(
    r"""(@import\s+(?:url\s*\(\s*)?["']?)([^"'\s\)]+)(["']?\s*\)?\s*;?)""",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# JavaScript URL patterns
# ---------------------------------------------------------------------------

JS_URL_PATTERNS: list[re.Pattern[str]] = [
    # .src = "url"  /  .href = "url"  /  .action = "url"
    re.compile(r"""\.(?:src|href|url|action)\s*=\s*["']([^"']+)["']"""),
    # window.open("url") / window.location = "url" / window.location.href = "url"
    re.compile(r"""(?:window\.open|window\.location(?:\.href)?)\s*[\(=]\s*["']([^"']+)["']"""),
    # fetch("url") / axios.get("url")
    re.compile(r"""(?:fetch|XMLHttpRequest|axios\.(?:get|post|put|delete))\s*\(\s*["']([^"']+)["']"""),
    # import ... from "url"
    re.compile(r"""import\s+(?:.*?\s+from\s+)?["']([^"']+)["']"""),
    # require("url")
    re.compile(r"""require\s*\(\s*["']([^"']+)["']\s*\)"""),
    # new URL("url", ...)
    re.compile(r"""new\s+URL\s*\(\s*["']([^"']+)["']"""),
    # url("path") inside JS (template literals, strings)
    re.compile(r"""url\s*\(\s*["']([^"')\s]+)["']\s*\)"""),
]

# ---------------------------------------------------------------------------
# File-type classification
# ---------------------------------------------------------------------------

FONT_EXTENSIONS = frozenset({".woff", ".woff2", ".ttf", ".otf", ".eot"})
MEDIA_EXTENSIONS = frozenset({
    ".mp4", ".webm", ".ogg", ".mp3", ".wav", ".flac", ".aac", ".m3u8", ".m4a",
})
IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".avif",
})
CSS_EXTENSIONS = frozenset({".css"})
JS_EXTENSIONS = frozenset({".js", ".mjs", ".jsx", ".ts", ".tsx"})
HTML_EXTENSIONS = frozenset({
    ".html", ".htm", ".xhtml", ".shtml", ".php", ".asp", ".aspx", ".jsp",
})
DATA_EXTENSIONS = frozenset({".json", ".xml", ".rss", ".atom"})

# MIME types → asset class
MIME_TO_TYPE: dict[str, str] = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/css": "css",
    "application/javascript": "js",
    "text/javascript": "js",
    "application/x-javascript": "js",
    "image/jpeg": "image",
    "image/png": "image",
    "image/gif": "image",
    "image/webp": "image",
    "image/svg+xml": "image",
    "image/avif": "image",
    "font/woff": "font",
    "font/woff2": "font",
    "font/ttf": "font",
    "font/otf": "font",
    "video/mp4": "media",
    "video/webm": "media",
    "audio/mpeg": "media",
    "audio/ogg": "media",
    "application/json": "data",
    "application/xml": "data",
    "application/rss+xml": "data",
    "application/atom+xml": "data",
}


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredAsset:
    """A URL discovered inside a hypertext document."""

    url: str
    source_tag: str  # HTML tag name, "css", "js"
    source_attr: str  # attribute name or "url()", "@import", "js"
    asset_type: str  # html | css | js | image | font | media | data | other


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class AssetDiscovery:
    """Discover all linked assets from HTML, CSS, and JavaScript content.

    Inspired by HTTrack's ``htsparse()`` parser (htsparse.c).
    """

    def __init__(self) -> None:
        pass

    # ----- public API -----------------------------------------------------

    def discover_from_html(self, html: str, base_url: str) -> list[DiscoveredAsset]:
        """Extract every linked resource URL from *html*."""
        assets: list[DiscoveredAsset] = []
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(True):
            tag_name = tag.name.lower()
            attrs = HTML_URL_ATTRS.get(tag_name, [])

            for attr in attrs:
                value = tag.get(attr)
                if not value:
                    continue

                if "srcset" in attr:
                    assets.extend(self._parse_srcset(value, tag_name, base_url))
                else:
                    asset = self._resolve_attr(value, tag_name, attr, base_url)
                    if asset is not None:
                        assets.append(asset)

        # <style> blocks
        for style_tag in soup.find_all("style"):
            if style_tag.string:
                assets.extend(self._discover_css(style_tag.string, base_url))

        # inline style="background: url(...)"
        for tag in soup.find_all(style=True):
            assets.extend(self._discover_css(tag["style"], base_url))

        return assets

    def discover_from_css(self, css: str, base_url: str) -> list[DiscoveredAsset]:
        """Extract every linked resource URL from *css*."""
        return self._discover_css(css, base_url)

    def discover_from_js(self, js: str, base_url: str) -> list[DiscoveredAsset]:
        """Extract every linked resource URL from *js*."""
        assets: list[DiscoveredAsset] = []
        for pattern in JS_URL_PATTERNS:
            for match in pattern.finditer(js):
                url = match.group(1)
                resolved = self._resolve(url, base_url)
                if resolved is not None:
                    assets.append(
                        DiscoveredAsset(
                            url=resolved,
                            source_tag="script",
                            source_attr="js",
                            asset_type=classify_url(resolved),
                        )
                    )
        return assets

    # ----- internals ------------------------------------------------------

    def _discover_css(self, css: str, base_url: str) -> list[DiscoveredAsset]:
        assets: list[DiscoveredAsset] = []

        for match in CSS_URL_RE.finditer(css):
            url = match.group(2)
            if url.startswith("data:"):
                continue
            resolved = self._resolve(url, base_url)
            if resolved is not None:
                assets.append(
                    DiscoveredAsset(
                        url=resolved,
                        source_tag="css",
                        source_attr="url()",
                        asset_type=classify_url(resolved),
                    )
                )

        for match in CSS_IMPORT_RE.finditer(css):
            url = match.group(2)
            if url.startswith("data:"):
                continue
            resolved = self._resolve(url, base_url)
            if resolved is not None:
                assets.append(
                    DiscoveredAsset(
                        url=resolved,
                        source_tag="css",
                        source_attr="@import",
                        asset_type=classify_url(resolved),
                    )
                )

        return assets

    def _parse_srcset(
        self, srcset: str, tag: str, base_url: str
    ) -> list[DiscoveredAsset]:
        assets: list[DiscoveredAsset] = []
        for part in srcset.split(","):
            tokens = part.strip().split()
            if tokens:
                resolved = self._resolve(tokens[0], base_url)
                if resolved is not None:
                    assets.append(
                        DiscoveredAsset(
                            url=resolved,
                            source_tag=tag,
                            source_attr="srcset",
                            asset_type=classify_url(resolved),
                        )
                    )
        return assets

    def _resolve_attr(
        self, value: str, tag: str, attr: str, base_url: str
    ) -> DiscoveredAsset | None:
        resolved = self._resolve(value, base_url)
        if resolved is None:
            return None
        return DiscoveredAsset(
            url=resolved,
            source_tag=tag,
            source_attr=attr,
            asset_type=classify_url(resolved),
        )

    @staticmethod
    def _resolve(url: str, base_url: str) -> str | None:
        """Resolve a (possibly relative) URL against *base_url*.

        Returns ``None`` for data: URIs, javascript: URIs, fragments, or
        anything that doesn't resolve to http(s).
        """
        if not url:
            return None
        stripped = url.strip()
        if stripped.startswith(("data:", "javascript:", "mailto:", "tel:")):
            return None
        try:
            resolved = urljoin(base_url, stripped)
            resolved, _ = urldefrag(resolved)  # drop fragment
            parsed = urlparse(resolved)
            if parsed.scheme not in ("http", "https"):
                return None
            return resolved
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify_url(url: str) -> str:
    """Classify a URL by its file extension / MIME hint."""
    path = urlparse(url).path.lower()
    for ext in HTML_EXTENSIONS:
        if path.endswith(ext):
            return "html"
    for ext in CSS_EXTENSIONS:
        if path.endswith(ext):
            return "css"
    for ext in JS_EXTENSIONS:
        if path.endswith(ext):
            return "js"
    for ext in IMAGE_EXTENSIONS:
        if path.endswith(ext):
            return "image"
    for ext in FONT_EXTENSIONS:
        if path.endswith(ext):
            return "font"
    for ext in MEDIA_EXTENSIONS:
        if path.endswith(ext):
            return "media"
    for ext in DATA_EXTENSIONS:
        if path.endswith(ext):
            return "data"
    return "other"


def classify_mime(content_type: str) -> str:
    """Classify a Content-Type header value."""
    mime = content_type.split(";")[0].strip().lower()
    return MIME_TO_TYPE.get(mime, "other")
