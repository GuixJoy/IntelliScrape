"""Main mirror engine — downloads a complete website for offline browsing.

Ported from HTTrack's ``httpmirror()`` (htscore.c).

Orchestrates asset discovery, URL rewriting, caching, robots.txt compliance,
sitemap parsing, WARC export, and ZIP packaging into a single ``mirror()`` call.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
import uuid
import zipfile
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import MirrorConfig
from .parser import AssetDiscovery, classify_url, classify_mime
from .naming import SaveNamer
from .rewriter import URLRewriter
from .cache import MirrorCache
from .robots import RobotsParser
from .filters import URLFilter

from ..markdown import html_to_markdown


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class MirrorResult:
    """Outcome of a ``mirror()`` call."""

    url: str
    output_dir: str
    zip_path: str | None = None
    warc_path: str | None = None
    pages_downloaded: int = 0
    assets_downloaded: int = 0
    total_bytes: int = 0
    elapsed_seconds: float = 0.0
    errors: int = 0
    skipped_robots: int = 0
    skipped_filtered: int = 0
    # --- Markdown corpus mode ---
    markdown_pages: int = 0
    markdown_chars: int = 0
    llms_file: str | None = None
    llms_full_file: str | None = None
    index_file: str | None = None


@dataclass
class _WorkerStats:
    pages: int = 0
    assets: int = 0
    bytes: int = 0
    errors: int = 0
    skipped_robots: int = 0
    skipped_filtered: int = 0


@dataclass
class _DownloadResult:
    """Internal holder for a downloaded response."""

    url: str
    status_code: int
    content_type: str
    content: bytes
    headers: dict[str, str] = field(default_factory=dict)
    redirected_url: str | None = None


def _extract_frontmatter_value(md: str, key: str) -> str:
    """Pull a ``key: value`` line out of a leading YAML frontmatter block."""
    if not md or not md.startswith("---"):
        return ""
    lines = md.split("\n")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith(key + ":"):
            val = line[len(key) + 1:].strip()
            if len(val) >= 2 and val.startswith('"') and val.endswith('"'):
                val = val[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            return val
    return ""


# ---------------------------------------------------------------------------
# Mirror engine
# ---------------------------------------------------------------------------

class SiteMirror:
    """Mirror a complete website for offline browsing.

    Basic usage::

        from intelliscrape.track.mirror import SiteMirror, MirrorConfig

        config = MirrorConfig(url="https://example.com", max_depth=3)
        m = SiteMirror(config)
        result = m.run()

    Or use the convenience function::

        from intelliscrape.track import mirror
        result = mirror("https://example.com", save_zip="site.zip")
    """

    def __init__(self, config: MirrorConfig | None = None) -> None:
        self.config = config or MirrorConfig()
        self._discovery = AssetDiscovery()
        self._namer = SaveNamer(self.config)
        self._rewriter = URLRewriter(self.config)
        self._cache: MirrorCache | None = (
            MirrorCache(self.config.output_dir) if self.config.use_cache else None
        )
        self._robots: RobotsParser | None = (
            RobotsParser() if self.config.respect_robots else None
        )
        self._filter = URLFilter.from_strings(
            self.config.include_patterns + self.config.exclude_patterns
        )
        self._stats = _WorkerStats()
        self._warc_file = None
        self._progress_callback = None
        # Markdown corpus mode state
        self._md_pages: list[dict] = []
        self._md_chars = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, save_zip: str | None = None, save_warc: str | None = None,
            progress_callback=None) -> MirrorResult:
        """Run the mirror synchronously (wraps async engine)."""
        self._progress_callback = progress_callback
        return asyncio.run(self._run_async(save_zip=save_zip, save_warc=save_warc))

    async def _run_async(self, save_zip: str | None = None,
                         save_warc: str | None = None) -> MirrorResult:
        start = time.time()
        url = self.config.url
        if not url:
            raise ValueError("MirrorConfig.url is required")

        output = Path(self.config.output_dir)
        output.mkdir(parents=True, exist_ok=True)

        # Load cache
        if self._cache:
            self._cache.load()

        # Parse sitemap if available
        await self._parse_sitemap(url)

        # Open WARC file if requested
        if save_warc or self.config.save_warc:
            warc_path = save_warc or str(output / "mirror.warc.gz")
            self._open_warc(warc_path)

        # Seed queue: (url, depth, referer)
        queue: asyncio.Queue[tuple[str, int, str | None]] = asyncio.Queue()
        await queue.put((url, 0, None))

        visited: set[str] = set()
        visited.add(url)

        # Launch workers
        workers = [
            asyncio.create_task(self._worker(queue, visited))
            for _ in range(self.config.max_concurrent)
        ]
        await queue.join()
        for w in workers:
            w.cancel()

        # Generate directory indices
        if self.config.generate_index and self.config.output_format != "markdown":
            self._generate_indices(output)

        # Generate Markdown corpus files (llms.txt / llms-full.txt / index.md)
        md_files = self._generate_markdown_outputs(output) if (
            self.config.output_format == "markdown"
        ) else {}

        # Save cache
        if self._cache:
            self._cache.save()

        # Close WARC
        warc_path: str | None = None
        if self._warc_file:
            warc_path = self._close_warc()

        # ZIP output
        zip_path: str | None = None
        if save_zip:
            zip_path = str(self._create_zip(output, save_zip))

        elapsed = time.time() - start
        return MirrorResult(
            url=url,
            output_dir=str(output),
            zip_path=zip_path,
            warc_path=warc_path,
            pages_downloaded=self._stats.pages,
            assets_downloaded=self._stats.assets,
            total_bytes=self._stats.bytes,
            elapsed_seconds=elapsed,
            errors=self._stats.errors,
            skipped_robots=self._stats.skipped_robots,
            skipped_filtered=self._stats.skipped_filtered,
            markdown_pages=len(self._md_pages),
            markdown_chars=self._md_chars,
            llms_file=md_files.get("llms"),
            llms_full_file=md_files.get("llms_full"),
            index_file=md_files.get("index"),
        )

    # ------------------------------------------------------------------
    # Progress reporting
    # ------------------------------------------------------------------

    def _report_progress(self) -> None:
        if self._progress_callback:
            self._progress_callback(
                pages=self._stats.pages,
                assets=self._stats.assets,
                bytes=self._stats.bytes,
                errors=self._stats.errors,
            )

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    async def _worker(
        self,
        queue: asyncio.Queue[tuple[str, int, str | None]],
        visited: set[str],
    ) -> None:
        while True:
            try:
                url, depth, referer = await asyncio.wait_for(queue.get(), timeout=10.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return

            try:
                await self._process(url, depth, referer, queue, visited)
            except Exception as exc:
                self._stats.errors += 1
            finally:
                queue.task_done()
                self._report_progress()

            # Politeness delay
            if self.config.delay > 0:
                await asyncio.sleep(self.config.delay)

    # ------------------------------------------------------------------
    # Core processing per URL
    # ------------------------------------------------------------------

    async def _process(
        self,
        url: str,
        depth: int,
        referer: str | None,
        queue: asyncio.Queue[tuple[str, int, str | None]],
        visited: set[str],
    ) -> None:
        cfg = self.config

        # Depth / quota guards
        if depth > cfg.max_depth:
            return
        if self._stats.pages + self._stats.assets >= cfg.max_pages:
            return

        # robots.txt
        if self._robots:
            host = urlparse(url).hostname or ""
            if self._robots.needs_fetch(host):
                await self._fetch_robots(host)
            if not self._robots.is_allowed(url, cfg.user_agent):
                self._stats.skipped_robots += 1
                return

        # URL filter
        if not self._filter.matches(url):
            self._stats.skipped_filtered += 1
            return

        # Scope check
        if not cfg.is_in_scope(cfg.url, url):
            return

        # Extension-based skip
        if not cfg.should_fetch(url):
            return

        # Cache hit
        if self._cache and self._cache.has(url) and not cfg.update_mode:
            entry = self._cache.get(url)
            if entry and entry.save_path:
                self._rewriter.register(url, entry.save_path)
                if cfg.output_format == "markdown" and (
                    not entry.content_type or entry.content_type.startswith("text/html")
                ):
                    self._restore_from_cache(url, entry)
                return

        # --- Download ---
        result = await self._download(url)
        if result is None or result.status_code >= 400:
            self._stats.errors += 1
            return

        # Handle redirect (skip when only a trailing slash differs)
        if (
            result.redirected_url
            and result.redirected_url != url
            and result.redirected_url.rstrip("/") != url.rstrip("/")
            and result.redirected_url not in visited
        ):
            visited.add(result.redirected_url)
            await queue.put((result.redirected_url, depth, url))

        # Save path
        save_path = self._namer.compute_path(url)
        full_path = Path(cfg.output_dir) / save_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Detect content type
        ctype = result.content_type
        if not ctype:
            ctype = self._guess_ctype(url, result.content)
        asset_class = classify_url(url)
        if asset_class == "other":
            asset_class = classify_mime(ctype)

        # Write file
        if cfg.save_files:
            if asset_class == "html" and cfg.output_format == "markdown":
                # --- Markdown corpus mode: convert page to .md ---
                decoded = result.content.decode("utf-8", errors="replace")
                md_save_path = self._md_save_path(save_path)
                md = html_to_markdown(
                    decoded,
                    url,
                    frontmatter=cfg.markdown_frontmatter,
                    keep_nav=cfg.markdown_keep_nav,
                    include_images=cfg.markdown_images,
                    include_json_ld=cfg.markdown_json_ld,
                )
                if md.strip():
                    md_full = Path(cfg.output_dir) / md_save_path
                    md_full.parent.mkdir(parents=True, exist_ok=True)
                    md_full.write_text(md, encoding="utf-8")
                    self._md_pages.append(self._md_page_meta(url, md, md_save_path))
                    self._md_chars += len(md)
                    save_path = md_save_path
                else:
                    self._stats.errors += 1
                    save_path = ""
            elif asset_class in ("html", "css") and cfg.url_mode != "keep_original":
                decoded = result.content.decode("utf-8", errors="replace")
                if asset_class == "html":
                    decoded = self._rewriter.rewrite_html(decoded, url)
                else:
                    decoded = self._rewriter.rewrite_css(decoded, url)
                full_path.write_text(decoded, encoding="utf-8")
            else:
                full_path.write_bytes(result.content)

        # Register mapping
        if save_path:
            self._rewriter.register(url, save_path)

        # Write WARC record
        if self._warc_file:
            self._write_warc_record(url, result)

        # Cache
        if self._cache and save_path:
            self._cache.set(
                url,
                save_path,
                status_code=result.status_code,
                content_type=ctype,
                content_length=len(result.content),
                body=result.content,
                headers=result.headers,
                depth=depth,
            )

        # Stats
        if asset_class == "html":
            self._stats.pages += 1
        else:
            self._stats.assets += 1
        self._stats.bytes += len(result.content)

        # --- Discover new links ---
        if asset_class == "html":
            html = result.content.decode("utf-8", errors="replace")
            assets = self._discovery.discover_from_html(html, url)
            await self._enqueue_assets(assets, depth, url, queue, visited)

        elif asset_class == "css":
            css = result.content.decode("utf-8", errors="replace")
            assets = self._discovery.discover_from_css(css, url)
            await self._enqueue_assets(assets, depth, url, queue, visited)

        elif asset_class == "js":
            js = result.content.decode("utf-8", errors="replace")
            assets = self._discovery.discover_from_js(js, url)
            await self._enqueue_assets(assets, depth, url, queue, visited)

    # ------------------------------------------------------------------
    # Enqueue discovered assets
    # ------------------------------------------------------------------

    async def _enqueue_assets(
        self,
        assets: list,
        depth: int,
        referer: str,
        queue: asyncio.Queue[tuple[str, int, str | None]],
        visited: set[str],
    ) -> None:
        for asset in assets:
            aurl = asset.url
            if aurl in visited:
                continue
            if any(v.rstrip("/") == aurl.rstrip("/") for v in visited):
                continue
            if not self.config.is_in_scope(self.config.url, aurl):
                continue
            if not self.config.should_fetch(aurl):
                continue
            visited.add(aurl)
            await queue.put((aurl, depth + 1, referer))

    # ------------------------------------------------------------------
    # Markdown corpus mode helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _md_save_path(save_path: str) -> str:
        """Map an HTML save path to its Markdown equivalent (``.md``)."""
        from .naming import _split_ext

        name, _ext = _split_ext(save_path)
        return name + ".md"

    def _md_page_meta(self, url: str, md: str, save_path: str) -> dict:
        """Build metadata for a converted page (used by llms.txt / index)."""
        from ..markdown import strip_frontmatter

        title = _extract_frontmatter_value(md, "title")
        description = _extract_frontmatter_value(md, "description")
        body = strip_frontmatter(md)
        if not title:
            m = re.match(r"^#\s+(.+)$", body, re.MULTILINE)
            title = m.group(1).strip() if m else url
        summary = description
        if not summary:
            for line in body.split("\n"):
                line = line.strip()
                if line and not line.startswith(("#", "-", ">", "|", "```")):
                    summary = line[:160]
                    break
        return {
            "url": url,
            "title": title,
            "summary": summary,
            "save_path": save_path,
            "chars": len(md),
        }

    def _restore_from_cache(self, url: str, entry) -> None:
        """Re-register a cached Markdown page without re-fetching.

        Reads the ``.md`` file written on a previous run so the merged
        corpus outputs stay complete on resume/update runs.
        """
        md_path = Path(self.config.output_dir) / entry.save_path
        try:
            md = md_path.read_text(encoding="utf-8")
        except OSError:
            return
        if not md.strip():
            return
        self._md_pages.append(self._md_page_meta(url, md, entry.save_path))
        self._md_chars += len(md)

    def _generate_markdown_outputs(self, output: Path) -> dict:
        """Write ``llms.txt``, ``llms-full.txt`` and ``index.md``.

        Returns a dict of ``{"llms": path, "llms_full": path, "index": path}``
        for whichever files were written (empty dict when disabled or when no
        pages were converted).
        """
        if not self.config.markdown_merge or not self._md_pages:
            return {}

        from ..markdown import strip_frontmatter

        pages = sorted(self._md_pages, key=lambda p: p["url"])
        site_host = urlparse(self.config.url).hostname or self.config.url
        cfg = self.config
        files: dict[str, str] = {}

        # --- llms.txt: site map with per-page summaries ---
        lines = [
            f"# {site_host}",
            "",
            f"> Markdown corpus of {cfg.url} — generated by IntelliScrape",
            "",
            "# Main",
            "",
        ]
        for p in pages:
            summary = (p.get("summary") or "").strip()
            suffix = f": {summary}" if summary else ""
            lines.append(f"- [{p.get('title') or p['url']}]({p['url']}){suffix}")
        llms = output / "llms.txt"
        llms.write_text("\n".join(lines) + "\n", encoding="utf-8")
        files["llms"] = str(llms)

        # --- llms-full.txt: every page merged into a single corpus ---
        merged: list[str] = []
        for p in pages:
            body = ""
            try:
                body = (output / p["save_path"]).read_text(encoding="utf-8")
            except OSError:
                pass
            body = strip_frontmatter(body).strip()
            header = [f"# {p.get('title') or p['url']}", "", f"> Source: {p['url']}"]
            if p.get("summary"):
                header.append(f"> {p['summary']}")
            merged.append("\n".join(header) + "\n\n" + body)
        llms_full = output / "llms-full.txt"
        llms_full.write_text("\n\n---\n\n".join(merged) + "\n", encoding="utf-8")
        files["llms_full"] = str(llms_full)

        # --- index.md: table of contents with local links ---
        idx = [
            f"# {site_host} — Index",
            "",
            f"> Source: {cfg.url} — generated by IntelliScrape",
            "",
            "## Pages",
            "",
        ]
        for p in pages:
            idx.append(f"- [{p.get('title') or p['url']}]({p['save_path']})")
        index = output / "index.md"
        index.write_text("\n".join(idx) + "\n", encoding="utf-8")
        files["index"] = str(index)

        return files

    # ------------------------------------------------------------------
    # Sitemap parsing
    # ------------------------------------------------------------------

    async def _parse_sitemap(self, base_url: str) -> None:
        """Discover pages from sitemap.xml."""
        parsed = urlparse(base_url)
        sitemap_urls = [
            f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
        ]
        for sitemap_url in sitemap_urls:
            try:
                result = await self._download(sitemap_url)
                if result and result.status_code == 200:
                    body = result.content.decode("utf-8", errors="replace")
                    self._extract_sitemap_urls(body, base_url)
            except Exception:
                pass

    def _extract_sitemap_urls(self, xml_content: str, base_url: str) -> None:
        """Extract URLs from sitemap XML."""
        import re
        # Simple regex extraction for <loc> tags
        loc_pattern = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.IGNORECASE)
        for match in loc_pattern.finditer(xml_content):
            url = match.group(1).strip()
            if url and url.startswith(("http://", "https://")):
                # Store for later queuing (will be processed when queue is seeded)
                if not hasattr(self, "_sitemap_urls"):
                    self._sitemap_urls = []
                self._sitemap_urls.append(url)

    # ------------------------------------------------------------------
    # robots.txt fetcher
    # ------------------------------------------------------------------

    async def _fetch_robots(self, host: str) -> None:
        assert self._robots is not None
        parts = urlparse(self.config.url)
        scheme = parts.scheme or "https"
        robots_url = f"{scheme}://{parts.netloc or host}/robots.txt"
        try:
            result = await self._download(robots_url)
            if result and result.status_code == 200:
                body = result.content.decode("utf-8", errors="replace")
                self._robots.parse(host, body, result.status_code)
            else:
                code = result.status_code if result else None
                self._robots.mark_unfetched(host, code)
        except Exception:
            self._robots.mark_unfetched(host, None)

    # ------------------------------------------------------------------
    # HTTP download (delegates to IntelliScrape engine)
    # ------------------------------------------------------------------

    async def _download(self, url: str) -> _DownloadResult | None:
        """Download *url* using IntelliScrape's engine via thread pool."""
        try:
            from ..core import IntelliScrape

            loop = asyncio.get_running_loop()
            cfg = self.config

            def _do() -> _DownloadResult:
                from urllib.parse import urlparse as _urlparse
                path = _urlparse(url).path.lower()
                is_binary = any(path.endswith(e) for e in
                    (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".avif",
                     ".woff", ".woff2", ".ttf", ".otf", ".eot",
                     ".mp4", ".webm", ".ogg", ".mp3", ".wav",
                     ".pdf", ".zip", ".gz", ".tar", ".warc"))

                if is_binary:
                    # Use curl_cffi directly for binary assets
                    from curl_cffi import requests as cffi_requests
                    kwargs = {"impersonate": "chrome131", "timeout": cfg.timeout}
                    if cfg.proxy:
                        kwargs["proxies"] = {"https": cfg.proxy, "http": cfg.proxy}
                    if cfg.cookies:
                        kwargs["cookies"] = cfg.cookies
                    resp = cffi_requests.get(url, **kwargs)
                    # Handle redirects
                    redirected = None
                    if resp.history:
                        redirected = str(resp.url)
                    return _DownloadResult(
                        url=url,
                        status_code=resp.status_code,
                        content_type=resp.headers.get("content-type", ""),
                        content=resp.content,
                        headers=dict(resp.headers),
                        redirected_url=redirected,
                    )
                else:
                    # Use IntelliScrape for HTML/CSS/JS
                    scraper = IntelliScrape()
                    result = scraper._fetch(url, engine=cfg.engine)
                    content = result.html or ""
                    if isinstance(content, str):
                        content = content.encode("utf-8")
                    headers = result.headers or {}
                    ctype = headers.get("content-type", "text/html")
                    status = result.status_code
                    return _DownloadResult(
                        url=url,
                        status_code=status,
                        content_type=ctype,
                        content=content,
                        headers=headers,
                    )

            return await loop.run_in_executor(None, _do)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Content-type guessing
    # ------------------------------------------------------------------

    @staticmethod
    def _guess_ctype(url: str, content: bytes) -> str:
        """Best-effort content-type guess from URL + magic bytes."""
        path = urlparse(url).path.lower()
        if path.endswith((".html", ".htm", ".xhtml")):
            return "text/html"
        if path.endswith(".css"):
            return "text/css"
        if path.endswith((".js", ".mjs")):
            return "application/javascript"
        if path.endswith(".json"):
            return "application/json"
        if path.endswith(".xml"):
            return "application/xml"
        if path.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if path.endswith(".png"):
            return "image/png"
        if path.endswith(".gif"):
            return "image/gif"
        if path.endswith(".webp"):
            return "image/webp"
        if path.endswith(".svg"):
            return "image/svg+xml"
        if path.endswith(".woff2"):
            return "font/woff2"
        if path.endswith(".woff"):
            return "font/woff"
        if path.endswith(".ttf"):
            return "font/ttf"
        if path.endswith(".otf"):
            return "font/otf"
        if path.endswith(".eot"):
            return "application/vnd.ms-fontobject"
        if path.endswith(".mp4"):
            return "video/mp4"
        if path.endswith(".webm"):
            return "video/webm"
        if path.endswith(".mp3"):
            return "audio/mpeg"
        if path.endswith(".pdf"):
            return "application/pdf"

        # Magic bytes
        if content[:3] == b"\xef\xbb\xbf":
            return "text/html"  # UTF-8 BOM → likely text
        if content[:2] in (b"PK",):
            return "application/zip"
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if content[:3] == b"GIF":
            return "image/gif"
        if content[:2] == b"\xff\xd8":
            return "image/jpeg"

        return "application/octet-stream"

    # ------------------------------------------------------------------
    # Directory index generation
    # ------------------------------------------------------------------

    def _generate_indices(self, output: Path) -> None:
        for dirpath in output.rglob("*"):
            if dirpath.is_dir():
                index = dirpath / "index.html"
                if not index.exists():
                    self._create_dir_index(dirpath)

    def _create_dir_index(self, dirpath: Path) -> None:
        entries = sorted(dirpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        name = dirpath.name or dirpath.parent.name
        rows = '<li><a href="..">..</a></li>\n'
        for entry in entries:
            label = entry.name + ("/" if entry.is_dir() else "")
            rows += f'<li><a href="{entry.name}">{label}</a></li>\n'

        html = (
            "<!DOCTYPE html>\n"
            "<html lang='en'>\n"
            "<head>\n"
            f"<meta charset='utf-8'>\n"
            f"<title>Index of {name}</title>\n"
            "<style>body{font-family:monospace;margin:2em}a{text-decoration:none}a:hover{text-decoration:underline}</style>\n"
            "</head>\n"
            "<body>\n"
            f"<h1>Index of {name}</h1>\n"
            "<ul>\n"
            f"{rows}"
            "</ul>\n"
            "</body>\n"
            "</html>\n"
        )
        (dirpath / "index.html").write_text(html, encoding="utf-8")

    # ------------------------------------------------------------------
    # WARC (Web ARChive) support
    # ------------------------------------------------------------------

    def _open_warc(self, warc_path: str) -> None:
        """Open a WARC file for writing."""
        import gzip
        self._warc_path = warc_path
        self._warc_file = gzip.open(warc_path, "wb")
        # Write WARC version record
        header = (
            f"WARC/1.1\r\n"
            f"WARC-Type: warcinfo\r\n"
            f"WARC-Date: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\r\n"
            f"WARC-Record-ID: <urn:uuid:{uuid.uuid4()}>\r\n"
            f"Content-Type: application/warc-fields\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
            f"\r\n"
        )
        self._warc_file.write(header.encode("utf-8"))

    def _write_warc_record(self, url: str, result: _DownloadResult) -> None:
        """Write a response record to the WARC file."""
        if not self._warc_file:
            return

        # Build WARC headers
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record_id = f"<urn:uuid:{uuid.uuid4()}>"
        content = result.content

        # HTTP response block
        http_block = (
            f"HTTP/1.1 {result.status_code} OK\r\n"
            f"Content-Type: {result.content_type}\r\n"
        )
        for k, v in result.headers.items():
            if k.lower() not in ("transfer-encoding", "content-encoding"):
                http_block += f"{k}: {v}\r\n"
        http_block += f"\r\n"

        # Combine headers + body
        payload = http_block.encode("utf-8") + content
        payload_len = len(payload)

        # WARC record
        record = (
            f"WARC/1.1\r\n"
            f"WARC-Type: response\r\n"
            f"WARC-Target-URI: {url}\r\n"
            f"WARC-Date: {now}\r\n"
            f"WARC-Record-ID: {record_id}\r\n"
            f"Content-Type: application/http;msgtype=response\r\n"
            f"Content-Length: {payload_len}\r\n"
            f"\r\n"
        )
        self._warc_file.write(record.encode("utf-8"))
        self._warc_file.write(payload)
        self._warc_file.write(b"\r\n\r\n")

    def _close_warc(self) -> str:
        """Close the WARC file and return its path."""
        if self._warc_file:
            self._warc_file.close()
            self._warc_file = None
        return getattr(self, "_warc_path", "")

    # ------------------------------------------------------------------
    # ZIP creation
    # ------------------------------------------------------------------

    def _create_zip(self, output: Path, zip_path: str) -> Path:
        zf = Path(zip_path)
        with zipfile.ZipFile(zf, "w", zipfile.ZIP_DEFLATED) as z:
            for file in output.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(output)
                    z.write(file, arcname)
        return zf


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def mirror(
    url: str,
    output_dir: str = "./mirror",
    max_depth: int = 5,
    save_zip: str | None = None,
    save_warc: str | None = None,
    progress_callback=None,
    **kwargs,
) -> MirrorResult:
    """Mirror a website for offline browsing.

    Args:
        url: Starting URL.
        output_dir: Where to save the mirror.
        max_depth: Maximum link-following depth.
        save_zip: If given, also create a ZIP archive at this path.
        save_warc: If given, also create a WARC archive at this path.
        progress_callback: Called with progress stats during download.
        **kwargs: Extra fields forwarded to ``MirrorConfig``.

    Returns:
        ``MirrorResult`` with stats and output paths.
    """
    config = MirrorConfig(url=url, output_dir=output_dir, max_depth=max_depth, **kwargs)
    m = SiteMirror(config)
    return m.run(save_zip=save_zip, save_warc=save_warc, progress_callback=progress_callback)
