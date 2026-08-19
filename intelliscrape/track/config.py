"""Configuration data structures for HTTrack-style mirroring."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MirrorConfig:
    """Configuration for website mirroring.

    Inspired by HTTrack's options structure (htsopt.h).
    """

    # --- What to mirror ---
    url: str = ""
    max_depth: int = 5
    max_pages: int = 10000
    max_file_size: int = 50 * 1024 * 1024  # 50 MB per file

    # --- Scope ---
    travel: str = "same_domain"  # same_address | same_domain | same_tld | everywhere
    stay_on_scheme: bool = True

    # --- What to fetch ---
    fetch_html: bool = True
    fetch_css: bool = True
    fetch_js: bool = True
    fetch_images: bool = True
    fetch_fonts: bool = True
    fetch_media: bool = True
    fetch_documents: bool = True
    fetch_other: bool = False

    # --- URL filtering ---
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)

    # --- Output ---
    output_dir: str = "./mirror"
    url_mode: str = "relative"  # relative | absolute | keep_original
    generate_index: bool = True

    # --- Resume / cache ---
    use_cache: bool = True
    update_mode: bool = False

    # --- Politeness ---
    delay: float = 0.5
    max_concurrent: int = 5
    respect_robots: bool = True
    user_agent: str = "IntelliScrape/1.0 (https://github.com/GuixJoy/IntelliScrape)"

    # --- Output formats ---
    save_files: bool = True
    save_zip: bool = False
    save_warc: bool = False

    # --- Markdown corpus mode (output_format="markdown") ---
    # When enabled, HTML pages are converted to Markdown instead of being
    # saved as rewritten HTML. Asset fetching is disabled automatically
    # (only HTML pages are crawled).
    output_format: str = "html"  # "html" | "markdown"
    markdown_merge: bool = True      # write llms.txt + llms-full.txt
    markdown_frontmatter: bool = True  # YAML frontmatter per page
    markdown_keep_nav: bool = False  # keep nav/footer/aside content
    markdown_images: bool = False    # keep image references
    markdown_json_ld: bool = True    # append JSON-LD as code block

    # --- Engine ---
    engine: str = "static"  # static | playwright | camoufox | nodriver | auto

    # --- Proxy & Auth ---
    proxy: str | None = None
    cookies: dict[str, str] | None = None
    headers: dict[str, str] | None = None

    # --- Misc ---
    timeout: int = 30
    retry: int = 3

    def __post_init__(self) -> None:
        if self.url and not self.url.startswith(("http://", "https://")):
            self.url = "https://" + self.url

        # Markdown corpora only need HTML pages — never fetch assets.
        if self.output_format == "markdown":
            self.fetch_css = False
            self.fetch_js = False
            self.fetch_images = False
            self.fetch_fonts = False
            self.fetch_media = False
            self.fetch_documents = False

    # --- Scope helpers ---------------------------------------------------

    def _same_domain(self, base_host: str, target_host: str) -> bool:
        return target_host == base_host or target_host.endswith("." + base_host)

    def _same_tld(self, base_host: str, target_host: str) -> bool:
        base_parts = base_host.rsplit(".", 2)
        target_parts = target_host.rsplit(".", 2)
        return base_parts[-2:] == target_parts[-2:]

    def is_in_scope(self, base_url: str, target_url: str) -> bool:
        """Return True if *target_url* is within the crawl scope of *base_url*."""
        from urllib.parse import urlparse

        base = urlparse(base_url)
        target = urlparse(target_url)

        if self.stay_on_scheme and base.scheme != target.scheme:
            return False

        if self.travel == "everywhere":
            return True
        if self.travel == "same_address":
            return target.netloc == base.netloc
        if self.travel == "same_domain":
            return self._same_domain(base.hostname or "", target.hostname or "")
        if self.travel == "same_tld":
            return self._same_tld(base.hostname or "", target.hostname or "")
        return True

    # --- Fetch-type helpers ----------------------------------------------

    def should_fetch(self, url: str) -> bool:
        """Quick extension-based check for whether a URL is worth fetching."""
        from urllib.parse import urlparse

        path = urlparse(url).path.lower()

        html_ext = (".html", ".htm", ".xhtml", ".php", ".asp", ".aspx", ".jsp", ".shtml")
        css_ext = (".css",)
        js_ext = (".js", ".mjs", ".jsx", ".ts", ".tsx")
        img_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".avif")
        font_ext = (".woff", ".woff2", ".ttf", ".otf", ".eot")
        media_ext = (".mp4", ".webm", ".ogg", ".mp3", ".wav", ".flac", ".aac", ".m3u8")
        doc_ext = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv")

        # No extension or ends with / → treat as HTML page
        if not path or path == "/" or not any(path.endswith(e) for e in
            html_ext + css_ext + js_ext + img_ext + font_ext + media_ext + doc_ext):
            return self.fetch_html

        if any(path.endswith(e) for e in html_ext) and self.fetch_html:
            return True
        if any(path.endswith(e) for e in css_ext) and self.fetch_css:
            return True
        if any(path.endswith(e) for e in js_ext) and self.fetch_js:
            return True
        if any(path.endswith(e) for e in img_ext) and self.fetch_images:
            return True
        if any(path.endswith(e) for e in font_ext) and self.fetch_fonts:
            return True
        if any(path.endswith(e) for e in media_ext) and self.fetch_media:
            return True
        if any(path.endswith(e) for e in doc_ext) and self.fetch_documents:
            return True
        if self.fetch_other:
            return True
        return False
