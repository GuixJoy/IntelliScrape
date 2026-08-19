"""Tests for Markdown / LLM-ingestion features (converter, markdown_site, CLI)."""

from __future__ import annotations

import http.server
import subprocess
import sys
import threading
from pathlib import Path
from typing import ClassVar

import pytest

from intelliscrape import html_to_markdown, markdown_site
from intelliscrape.markdown import MarkdownConfig, strip_frontmatter

# ---------------------------------------------------------------------------
# Fixtures: tiny multi-page site served over local HTTP
# ---------------------------------------------------------------------------

INDEX_HTML = """<!DOCTYPE html>
<html><head><title>Fixture Home</title>
<meta name="description" content="Home of the fixture site.">
<link rel="canonical" href="/">
<script type="application/ld+json">{"@context": "https://schema.org",
  "@type": "WebSite", "name": "Fixture"}</script>
</head><body>
<nav><a href="/docs/guide">Guide</a></nav>
<h1>Fixture Home</h1>
<p>Welcome to the fixture <a href="/docs/guide">guide</a>.</p>
<p>Also see the <a href="/about">about page</a>.</p>
<footer>Fixture footer</footer>
</body></html>"""

GUIDE_HTML = """<!DOCTYPE html>
<html><head><title>Guide</title>
<meta name="description" content="A guide page with a table.">
</head><body>
<nav><a href="/">Home</a></nav>
<h1>Guide</h1>
<p>This is the <strong>guide</strong> page.</p>
<table><tr><th>Key</th><th>Value</th></tr><tr><td>alpha</td><td>1</td></tr></table>
<pre><code>def hello(): return "world"</code></pre>
<a href="/about">About</a>
<footer>Fixture footer</footer>
</body></html>"""

ABOUT_HTML = """<!DOCTYPE html>
<html><head><title>About Us</title></head><body>
<h1>About Us</h1>
<p>We are a fixture.</p>
<a href="/private">Private area</a>
</body></html>"""

PRIVATE_HTML = """<!DOCTYPE html>
<html><head><title>Private</title></head><body>
<h1>Private</h1>
<p>Secret content that robots.txt disallows.</p>
</body></html>"""

ROBOTS_TXT = "User-agent: *\nDisallow: /private\n"


class _Handler(http.server.BaseHTTPRequestHandler):
    routes: ClassVar[dict[str, tuple[object, str]]] = {
        "/": (INDEX_HTML, "text/html"),
        "/index.html": (INDEX_HTML, "text/html"),
        "/docs/guide": (GUIDE_HTML, "text/html"),
        "/about": (ABOUT_HTML, "text/html"),
        "/private": (PRIVATE_HTML, "text/html"),
        "/assets/style.css": ("body { color: red; }", "text/css"),
        "/assets/logo.png": (b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png"),
        "/robots.txt": (ROBOTS_TXT, "text/plain"),
    }

    def do_GET(self):
        entry = self.routes.get(self.path)
        if entry is None:
            self.send_response(404)
            self.end_headers()
            return
        body, ctype = entry
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _md_args(site_server, tmp_path, **overrides):
    args = {
        "url": site_server,
        "output_dir": str(tmp_path / "corpus"),
        "max_depth": 3,
        "delay": 0,
        "use_cache": True,
    }
    args.update(overrides)
    return args


# ---------------------------------------------------------------------------
# Converter unit tests
# ---------------------------------------------------------------------------


class TestHtmlToMarkdown:
    def test_empty_input(self):
        assert html_to_markdown("") == ""
        assert html_to_markdown(None) == ""  # type: ignore[arg-type]
        assert html_to_markdown("   \n  ") == ""

    def test_basic_structure(self):
        md = html_to_markdown(
            "<h1>Head</h1><p>Para with <strong>bold</strong> and <em>em</em>.</p>"
            "<ul><li>A</li><li>B</li></ul>"
        )
        assert md.startswith("---")
        assert "# Head" in md
        assert "**bold**" in md and "*em*" in md
        assert "- A\n- B" in md

    def test_table_and_code(self):
        md = html_to_markdown(
            "<table><tr><th>K</th></tr><tr><td>V</td></tr></table>"
            "<pre><code>x = 1</code></pre>"
        )
        assert "| K |" in md and "| --- |" in md and "| V |" in md
        assert "```\nx = 1\n```" in md

    def test_relative_links_absolutized(self):
        md = html_to_markdown(
            '<a href="/docs/guide">Guide</a>', url="https://example.com/start"
        )
        assert "[Guide](https://example.com/docs/guide)" in md

    def test_absolute_links_untouched(self):
        md = html_to_markdown(
            '<a href="https://other.dev/x">X</a>', url="https://example.com/"
        )
        assert "[X](https://other.dev/x)" in md

    def test_nav_footer_stripped_by_default(self):
        md = html_to_markdown(
            "<nav>NavLinks</nav><h1>T</h1><p>Body text.</p><footer>Copyright</footer>"
        )
        assert "NavLinks" not in md
        assert "Copyright" not in md
        assert "Body text." in md

    def test_keep_nav(self):
        md = html_to_markdown(
            "<nav>NavLinks</nav><h1>T</h1><p>Body.</p>", keep_nav=True
        )
        assert "NavLinks" in md

    def test_images_dropped_by_default(self):
        md = html_to_markdown('<img src="/logo.png" alt="Logo"><p>Body.</p>')
        assert "logo.png" not in md

    def test_images_kept_when_requested(self):
        md = html_to_markdown(
            '<img src="/logo.png" alt="Logo"><p>Body.</p>',
            url="https://example.com/",
            include_images=True,
        )
        assert "![Logo](https://example.com/logo.png)" in md

    def test_script_style_never_leaks(self):
        md = html_to_markdown(
            "<h1>T</h1><script>var x = 1;</script>"
            "<style>body{color:red}</style><p>Text</p>"
        )
        assert "var x" not in md
        assert "color:red" not in md

    def test_head_never_leaks(self):
        md = html_to_markdown(
            "<html><head><title>Leak</title></head><body><h1>Real</h1></body></html>"
        )
        assert "# Real" in md
        assert "Leak" not in strip_frontmatter(md)

    def test_frontmatter_fields(self):
        md = html_to_markdown(
            '<html><head><title>My Page</title>'
            '<meta name="description" content="A nice description.">'
            '<link rel="canonical" href="https://example.com/canonical-page">'
            '</head>'
            "<body><h1>My Page</h1><p>Some content words here.</p></body></html>",
            url="https://example.com/page",
        )
        assert md.startswith("---")
        assert "title: My Page" in md
        assert 'url: "https://example.com/page"' in md
        assert 'canonical: "https://example.com/canonical-page"' in md
        assert "description: A nice description." in md
        assert "date:" in md
        assert "word_count:" in md
        assert "Some content words here." in md

    def test_canonical_omitted_when_same_as_url(self):
        md = html_to_markdown(
            '<html><head><title>T</title>'
            '<link rel="canonical" href="/page"></head>'
            "<body><h1>T</h1><p>Body.</p></body></html>",
            url="https://example.com/page",
        )
        assert "canonical:" not in md

    def test_frontmatter_disabled(self):
        md = html_to_markdown("<h1>T</h1><p>Body.</p>", frontmatter=False)
        assert not md.startswith("---")

    def test_json_ld_appended(self):
        md = html_to_markdown(
            '<script type="application/ld+json">{"@type": "Article"}</script>'
            "<h1>T</h1><p>Body.</p>"
        )
        assert "## Structured Data" in md
        assert '"@type": "Article"' in md

    def test_json_ld_disabled(self):
        md = html_to_markdown(
            '<script type="application/ld+json">{"@type": "Article"}</script>'
            "<h1>T</h1><p>Body.</p>",
            include_json_ld=False,
        )
        assert "Structured Data" not in md

    def test_title_fallbacks(self):
        og = html_to_markdown(
            '<meta property="og:title" content="OG Title"><h1>T</h1><p>B.</p>'
        )
        assert "title: OG Title" in og
        h1 = html_to_markdown("<h1>From H1</h1><p>B.</p>")
        assert "title: From H1" in h1

    def test_yaml_quotes_special_chars(self):
        md = html_to_markdown(
            '<meta name="description" content=\'Colon: and "quotes" here\'>'
            "<h1>T</h1><p>B.</p>"
        )
        assert 'description: "Colon: and \\"quotes\\" here"' in md

    def test_whitespace_collapsed(self):
        md = html_to_markdown("<h1>T</h1>\n\n\n\n\n<p>P1</p>\n\n\n\n<p>P2</p>")
        assert "\n\n\n" not in md

    def test_strip_frontmatter(self):
        md = "---\ntitle: X\n---\n\n# Body"
        assert strip_frontmatter(md) == "# Body"
        assert strip_frontmatter("# No frontmatter") == "# No frontmatter"
        assert strip_frontmatter("") == ""

    def test_missing_dependency_raises_clear_error(self, monkeypatch):
        import intelliscrape.markdown as md_mod

        monkeypatch.setattr(md_mod, "_markdownify", None)
        monkeypatch.setattr(md_mod, "_MARKDOWNIFY_AVAILABLE", False)
        with pytest.raises(ImportError, match="markdownify"):
            html_to_markdown("<h1>T</h1>")


# ---------------------------------------------------------------------------
# markdown_site() integration tests
# ---------------------------------------------------------------------------


class TestMarkdownSite:
    def test_full_site_conversion(self, site_server, tmp_path):
        result = markdown_site(**_md_args(site_server, tmp_path))

        assert result.errors == 0
        assert result.pages_converted == 3
        assert result.llms_file and result.llms_full_file and result.index_file

        corpus = Path(tmp_path) / "corpus"
        host_dir = corpus / "127.0.0.1"
        assert (host_dir / "index.md").exists()
        assert (host_dir / "docs" / "guide" / "index.md").exists()
        assert (host_dir / "about" / "index.md").exists()

        # No assets fetched in markdown mode
        assert not list(corpus.rglob("*.css"))
        assert not list(corpus.rglob("*.png"))

        # Frontmatter + absolutized links
        guide = (host_dir / "docs" / "guide" / "index.md").read_text(encoding="utf-8")
        assert guide.startswith("---")
        assert "title: Guide" in guide
        assert f"]({site_server}/about)" in guide
        assert "Fixture footer" not in guide

        # llms-full.txt merges every page with source headers
        merged = (corpus / "llms-full.txt").read_text(encoding="utf-8")
        assert f"> Source: {site_server}/docs/guide" in merged
        assert f"> Source: {site_server}/about" in merged
        assert "def hello" in merged

        # llms.txt site map
        sitemap = (corpus / "llms.txt").read_text(encoding="utf-8")
        assert "Fixture Home" in sitemap
        assert f"({site_server}/docs/guide)" in sitemap

        # index.md links to local files
        index = (corpus / "index.md").read_text(encoding="utf-8")
        assert "(127.0.0.1/index.md)" in index
        assert "(127.0.0.1/docs/guide/index.md)" in index

    def test_robots_respected(self, site_server, tmp_path):
        result = markdown_site(**_md_args(site_server, tmp_path))
        assert result.pages_converted == 3
        assert not (
            Path(tmp_path) / "corpus" / "127.0.0.1" / "private" / "index.md"
        ).exists()

    def test_no_robots_ignores_disallow(self, site_server, tmp_path):
        result = markdown_site(
            **_md_args(site_server, tmp_path, respect_robots=False)
        )
        assert result.pages_converted == 4
        assert (
            Path(tmp_path) / "corpus" / "127.0.0.1" / "private" / "index.md"
        ).exists()

    def test_merge_disabled(self, site_server, tmp_path):
        result = markdown_site(
            **_md_args(site_server, tmp_path, markdown_merge=False)
        )
        assert result.llms_file is None
        assert result.llms_full_file is None
        assert result.index_file is None
        corpus = Path(tmp_path) / "corpus"
        assert not (corpus / "llms.txt").exists()
        assert not (corpus / "llms-full.txt").exists()
        assert (corpus / "127.0.0.1" / "index.md").exists()

    def test_frontmatter_disabled(self, site_server, tmp_path):
        markdown_site(
            **_md_args(site_server, tmp_path, markdown_frontmatter=False)
        )
        guide = (
            Path(tmp_path) / "corpus" / "127.0.0.1" / "docs" / "guide" / "index.md"
        ).read_text(encoding="utf-8")
        assert not guide.startswith("---")

    def test_keep_nav(self, site_server, tmp_path):
        markdown_site(**_md_args(site_server, tmp_path, markdown_keep_nav=True))
        guide = (
            Path(tmp_path) / "corpus" / "127.0.0.1" / "docs" / "guide" / "index.md"
        ).read_text(encoding="utf-8")
        assert "Home" in guide  # nav link kept

    def test_resume_restores_from_cache(self, site_server, tmp_path):
        args = _md_args(site_server, tmp_path)
        first = markdown_site(**args)
        assert first.pages_converted == 3

        second = markdown_site(**args)
        assert second.pages_converted == 3
        merged = (
            Path(tmp_path) / "corpus" / "llms-full.txt"
        ).read_text(encoding="utf-8")
        assert f"> Source: {site_server}/docs/guide" in merged
        assert f"> Source: {site_server}/about" in merged
        assert (Path(tmp_path) / "corpus" / "127.0.0.1" / "about" / "index.md").exists()

    def test_save_zip(self, site_server, tmp_path):
        result = markdown_site(
            **_md_args(site_server, tmp_path, save_zip=str(tmp_path / "corpus.zip"))
        )
        assert result.zip_path and Path(result.zip_path).exists()

    def test_exclude_patterns(self, site_server, tmp_path):
        markdown_site(
            **_md_args(site_server, tmp_path, exclude_patterns=["/about*"])
        )
        corpus = Path(tmp_path) / "corpus"
        assert not (corpus / "127.0.0.1" / "about" / "index.md").exists()
        assert (corpus / "127.0.0.1" / "docs" / "guide" / "index.md").exists()

    def test_markdown_config_forces_format(self, site_server, tmp_path):
        cfg = MarkdownConfig(url=site_server, output_dir=str(tmp_path / "c2"))
        assert cfg.output_format == "markdown"
        assert not cfg.fetch_css and not cfg.fetch_js and not cfg.fetch_images


# ---------------------------------------------------------------------------
# CLI tests (subprocess = the exact user-facing surface)
# ---------------------------------------------------------------------------

CLI_CWD = str(Path(__file__).resolve().parent.parent)


class TestMarkdownCli:
    def test_cli_markdown_command(self, site_server, tmp_path):
        out = tmp_path / "cli_corpus"
        proc = subprocess.run(
            [
                sys.executable, "-m", "intelliscrape",
                "--markdown", site_server,
                "--md-output", str(out),
                "--md-depth", "2",
                "--no-md-merge",
                "--mirror-delay", "0",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            cwd=CLI_CWD,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert (out / "127.0.0.1" / "docs" / "guide" / "index.md").exists()
        assert (out / "127.0.0.1" / "about" / "index.md").exists()
        assert not (out / "llms-full.txt").exists()

    def test_cli_markdown_help_flags_parse(self):
        proc = subprocess.run(
            [sys.executable, "-m", "intelliscrape", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cwd=CLI_CWD,
            check=False,
        )
        assert proc.returncode == 0
        assert "--markdown" in proc.stdout
        assert "--md-output" in proc.stdout
        assert "--no-md-merge" in proc.stdout