"""URL rewriting for offline-browsable mirrors.

Ported from HTTrack's ``lienrelatif()`` (htstools.c) and the rewriting
logic in ``htsparse.c``.

Rewrites internal URLs in HTML, CSS, and JS to point at the local copies
so the mirrored site can be browsed offline.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse, urldefrag

from bs4 import BeautifulSoup

from .parser import HTML_URL_ATTRS, CSS_URL_RE, CSS_IMPORT_RE
from .config import MirrorConfig


class URLRewriter:
    """Rewrite URLs in HTML/CSS/JS for offline browsing.

    Supports three modes (matching HTTrack's ``hts_urlmode``):

    * **relative** (default) – ``../dir/file.html`` – best for local browsing.
    * **absolute** – ``http://host/dir/file.html`` – useful for preview servers.
    * **keep_original** – leave URLs untouched.
    """

    def __init__(self, config: MirrorConfig) -> None:
        self.config = config
        # Remote URL → local save path
        self._url_map: dict[str, str] = {}
        # Remote URL → base href if present
        self._base_hrefs: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, remote_url: str, save_path: str) -> None:
        """Register a known remote URL → local path mapping."""
        self._url_map[remote_url] = save_path

    def set_base_href(self, page_url: str, base_href: str) -> None:
        """Record a ``<base href>`` for *page_url*."""
        self._base_hrefs[page_url] = base_href

    # ------------------------------------------------------------------
    # Public rewrite API
    # ------------------------------------------------------------------

    def rewrite_html(self, html: str, current_url: str) -> str:
        """Rewrite all internal URLs in *html* for offline browsing."""
        if self.config.url_mode == "keep_original":
            return html

        soup = BeautifulSoup(html, "html.parser")

        # Detect <base href>
        base_tag = soup.find("base")
        if base_tag and base_tag.get("href"):
            try:
                base_resolved = urljoin(current_url, base_tag["href"])
                self._base_hrefs[current_url] = base_resolved
            except Exception:
                pass

        # Rewrite all URL-containing attributes
        for tag in soup.find_all(True):
            tag_name = tag.name.lower()
            attrs = HTML_URL_ATTRS.get(tag_name, [])

            for attr in attrs:
                value = tag.get(attr)
                if not value:
                    continue

                if "srcset" in attr:
                    tag[attr] = self._rewrite_srcset(value, current_url)
                else:
                    tag[attr] = self._rewrite_single(value, current_url)

        # Rewrite inline styles
        for tag in soup.find_all(style=True):
            tag["style"] = self._rewrite_css_text(tag["style"], current_url)

        # Rewrite <style> blocks
        for style_tag in soup.find_all("style"):
            if style_tag.string:
                style_tag.string = self._rewrite_css_text(
                    style_tag.string, current_url
                )

        return str(soup)

    def rewrite_css(self, css: str, current_url: str) -> str:
        """Rewrite all URLs in CSS text."""
        if self.config.url_mode == "keep_original":
            return css
        return self._rewrite_css_text(css, current_url)

    def rewrite_js(self, js: str, current_url: str) -> str:
        """Best-effort URL rewrite in JavaScript (string literals only)."""
        if self.config.url_mode == "keep_original":
            return js
        # JS rewriting is fragile; only do the obvious quoted URL patterns.
        for pattern in (
            r"""(?:src|href|url|action)\s*=\s*["']([^"']+)["']""",
            r"""(?:window\.open|window\.location(?:\.href)?)\s*[\(=]\s*["']([^"']+)["']""",
        ):
            js = re.sub(
                pattern,
                lambda m: m.group(0).replace(
                    m.group(1), self._rewrite_single(m.group(1), current_url)
                ),
                js,
            )
        return js

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rewrite_css_text(self, css: str, current_url: str) -> str:
        def _replace_url(m: re.Match) -> str:
            prefix, url, suffix = m.group(1), m.group(2), m.group(3)
            if url.startswith("data:"):
                return m.group(0)
            return f"{prefix}{self._rewrite_single(url, current_url)}{suffix}"

        css = CSS_URL_RE.sub(_replace_url, css)
        css = CSS_IMPORT_RE.sub(_replace_url, css)
        return css

    def _rewrite_srcset(self, srcset: str, current_url: str) -> str:
        parts = []
        for part in srcset.split(","):
            tokens = part.strip().split()
            if tokens:
                tokens[0] = self._rewrite_single(tokens[0], current_url)
            parts.append(" ".join(tokens))
        return ", ".join(parts)

    def _rewrite_single(self, url: str, current_url: str) -> str:
        """Rewrite one URL value."""
        if not url or url.startswith(("data:", "javascript:", "mailto:", "tel:")):
            return url

        # Resolve against <base href> if present
        base = self._base_hrefs.get(current_url, current_url)

        try:
            absolute = urldefrag(urljoin(base, url))[0]
        except Exception:
            return url

        # Look up local save path
        save_path = self._url_map.get(absolute)
        if save_path is None:
            # Not an internal URL – keep original
            return url

        if self.config.url_mode == "absolute":
            return absolute

        # Relative mode (default)
        current_save = self._url_map.get(current_url)
        if current_save is None:
            return save_path
        return _relative_path(current_save, save_path)

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------

    def rewrite_all(
        self,
        content: str,
        current_url: str,
        content_type: str,
    ) -> str:
        """Dispatch to the correct rewriter based on content type."""
        if "html" in content_type:
            return self.rewrite_html(content, current_url)
        if "css" in content_type:
            return self.rewrite_css(content, current_url)
        if "javascript" in content_type or current_url.endswith((".js", ".mjs")):
            return self.rewrite_js(content, current_url)
        return content


# ---------------------------------------------------------------------------
# Pure path helper (cf. HTTrack's lienrelatif())
# ---------------------------------------------------------------------------

def _relative_path(from_path: str, to_path: str) -> str:
    """Compute a relative path from *from_path* to *to_path*.

    Both paths are mirror-relative (e.g. ``example.com/dir/page.html``).
    """
    from_parts = PurePosixPath(from_path).parent.parts
    to_parts = PurePosixPath(to_path).parts

    # Find common prefix
    common = 0
    for i in range(min(len(from_parts), len(to_parts))):
        if from_parts[i] == to_parts[i]:
            common += 1
        else:
            break

    # Go up from 'from' to common ancestor
    ups = len(from_parts) - common
    prefix = "../" * ups if ups else ""

    # Go down from common ancestor to 'to'
    remainder = "/".join(to_parts[common:])
    result = prefix + remainder

    return result or "."
