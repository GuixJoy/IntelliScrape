"""HTML → Markdown conversion and whole-site Markdown corpora for LLM ingestion.

Converts a single page or an entire website into clean, LLM-friendly Markdown:

- YAML frontmatter (title, url, description, date, word count) for RAG chunking
- Site chrome stripped (nav/footer/forms) unless disabled
- Absolute URLs so links stay resolvable outside the corpus
- JSON-LD structured data preserved as a code block
- ``llms.txt`` site map + ``llms-full.txt`` merged corpus (per-page ``.md`` files
  are also written, mirroring the URL tree)

Quick usage::

    from intelliscrape import markdown_site

    result = markdown_site("https://example.com", max_depth=3)

CLI equivalent::

    intelliscrape https://example.com --markdown --md-depth 3
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .track.config import MirrorConfig

try:
    from markdownify import markdownify as _markdownify

    _MARKDOWNIFY_AVAILABLE = True
except ImportError:  # pragma: no cover - only hit on broken installs
    _markdownify = None
    _MARKDOWNIFY_AVAILABLE = False

# Tags that are pure site chrome or non-content and are always stripped.
# ``nav``/``footer``/``aside`` are additionally gated behind ``keep_nav``.
_STRIP_TAGS = frozenset({
    "script", "style", "noscript", "template", "iframe", "svg", "dialog",
    "form", "fieldset", "select", "option", "optgroup", "button", "input",
    "textarea", "label",
})
_NAV_TAGS = frozenset({"nav", "footer", "aside"})

# Tags that must never appear in the output Markdown, passed to markdownify
# as a second line of defence.
_STRIP_PASSTHROUGH = frozenset({
    "script", "style", "noscript", "template", "iframe", "svg", "form",
    "button", "select", "input", "textarea", "dialog", "fieldset", "label",
})

_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_YAML_SPECIAL_RE = re.compile(r'[:#\[\]{},&*!|>\'"%@`]')


def html_to_markdown(
    html: str,
    url: Optional[str] = None,
    *,
    frontmatter: bool = True,
    keep_nav: bool = False,
    include_images: bool = False,
    include_json_ld: bool = True,
) -> str:
    """Convert an HTML document to clean Markdown.

    Parameters
    ----------
    html : str
        Raw HTML to convert. ``None``/empty input yields ``""``.
    url : str, optional
        Source URL. Used to absolutise relative links and for frontmatter.
    frontmatter : bool
        Prepend a YAML block with title/url/description/date/word count.
    keep_nav : bool
        Keep ``nav``/``footer``/``aside`` content (stripped by default —
        they are site chrome, not content).
    include_images : bool
        Keep ``![alt](src)`` image references (dropped by default).
    include_json_ld : bool
        Append JSON-LD structured data as a JSON code block.

    Returns
    -------
    str
        Markdown text (never ``None``). Empty string for empty input.
    """
    if not _MARKDOWNIFY_AVAILABLE:
        raise ImportError(
            "markdownify is required for Markdown output. "
            "Install it with: pip install markdownify"
        )
    if not html or not html.strip():
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # ------------------------------------------------------------------
    # 1. Extract metadata before any stripping
    # ------------------------------------------------------------------
    title = _extract_title(soup)
    description = _extract_meta(soup, "description") or _extract_og(soup, "description")
    canonical = _extract_canonical(soup)
    if canonical and url:
        canonical = urljoin(url, canonical)
    json_ld_blocks = _extract_json_ld(soup) if include_json_ld else []

    # ------------------------------------------------------------------
    # 2. Strip site chrome / non-content
    # ------------------------------------------------------------------
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    if not keep_nav:
        for tag in soup(_NAV_TAGS):
            tag.decompose()
    if not include_images:
        for img in soup.find_all("img"):
            img.decompose()

    # Remove head so stray title/meta text never leaks into the body
    if soup.head:
        soup.head.decompose()

    # ------------------------------------------------------------------
    # 3. Absolutise links (LLMs need resolvable, unambiguous URLs)
    # ------------------------------------------------------------------
    if url:
        for a in soup.find_all("a", href=True):
            a["href"] = urljoin(url, a["href"])
        if include_images:
            for img in soup.find_all("img", src=True):
                img["src"] = urljoin(url, img["src"])

    body = soup.body or soup

    # ------------------------------------------------------------------
    # 4. Convert
    # ------------------------------------------------------------------
    md = _markdownify(
        str(body),
        heading_style="ATX",
        bullets="-",
        strip=list(_STRIP_PASSTHROUGH),
        convert_tables=True,
        default_title=False,
        escape_asterisks=False,
        escape_underscores=False,
    )

    # ------------------------------------------------------------------
    # 5. Clean up whitespace / empty heading residue
    # ------------------------------------------------------------------
    md = _clean_markdown(md)

    if not md.strip():
        return ""

    word_count = len(md.split())

    # ------------------------------------------------------------------
    # 6. Frontmatter
    # ------------------------------------------------------------------
    if frontmatter:
        meta = _build_frontmatter(
            title=title,
            url=url,
            canonical=canonical,
            description=description,
            word_count=word_count,
        )
        if meta:
            md = meta + "\n\n" + md

    # ------------------------------------------------------------------
    # 7. JSON-LD appendix
    # ------------------------------------------------------------------
    for block in json_ld_blocks:
        try:
            parsed = json.loads(block)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pretty = block
        md += "\n\n## Structured Data\n\n```json\n" + pretty + "\n```\n"

    return _clean_markdown(md)


def strip_frontmatter(markdown_text: str) -> str:
    """Remove a leading YAML frontmatter block (``--- ... ---``) if present."""
    if not markdown_text or not markdown_text.startswith("---"):
        return markdown_text
    lines = markdown_text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return markdown_text
    rest = "\n".join(lines[end + 1:])
    return rest.lstrip("\n")


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------


def _extract_title(soup: BeautifulSoup) -> str:
    tag = soup.find("title")
    if tag and tag.string:
        return tag.string.strip()
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(" ", strip=True)
    return ""


def _extract_meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name}) or soup.find(
        "meta", attrs={"property": name}
    )
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def _extract_og(soup: BeautifulSoup, key: str) -> str:
    tag = soup.find("meta", attrs={"property": f"og:{key}"})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def _extract_canonical(soup: BeautifulSoup) -> str:
    tag = soup.find("link", attrs={"rel": "canonical"})
    if tag and tag.get("href"):
        return tag["href"].strip()
    return ""


def _extract_json_ld(soup: BeautifulSoup) -> list[str]:
    blocks = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if tag.string and tag.string.strip():
            blocks.append(tag.string.strip())
    return blocks


def _build_frontmatter(
    title: str,
    url: Optional[str],
    canonical: str,
    description: str,
    word_count: int,
) -> str:
    lines = ["---"]
    if title:
        lines.append(f"title: {_yaml_quote(title)}")
    if url:
        lines.append(f"url: {_yaml_quote(url)}")
    if canonical and canonical != url:
        lines.append(f"canonical: {_yaml_quote(canonical)}")
    if description:
        lines.append(f"description: {_yaml_quote(description)}")
    lines.append(f"date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(f"word_count: {word_count}")
    lines.append("---")
    return "\n".join(lines)


def _yaml_quote(value: str) -> str:
    """Quote a YAML scalar when needed and escape the quotes themselves."""
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    value = value.replace("\n", " ").replace("\r", " ").strip()
    if not value:
        return '""'
    if _YAML_SPECIAL_RE.search(value):
        return f'"{value}"'
    return value


def _clean_markdown(md: str) -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    md = _MULTI_BLANK_RE.sub("\n\n", md)
    md = md.strip()
    return md + "\n" if md else ""


# ---------------------------------------------------------------------------
# Configuration & result
# ---------------------------------------------------------------------------


@dataclass
class MarkdownConfig(MirrorConfig):
    """Configuration for whole-site Markdown conversion.

    Inherits every ``MirrorConfig`` option (depth, robots, filters, engine,
    proxy, delay, ...) and forces ``output_format="markdown"``.
    """

    output_format: str = "markdown"

    def __post_init__(self) -> None:
        super().__post_init__()
        self.output_format = "markdown"


@dataclass
class MarkdownResult:
    """Outcome of a ``markdown_site()`` call."""

    url: str
    output_dir: str
    pages_converted: int = 0
    total_chars: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    llms_file: Optional[str] = None
    llms_full_file: Optional[str] = None
    index_file: Optional[str] = None
    zip_path: Optional[str] = None
    warc_path: Optional[str] = None


def markdown_site(
    url: str,
    *,
    output_dir: str = "./markdown",
    max_depth: int = 5,
    save_zip: Optional[str] = None,
    save_warc: Optional[str] = None,
    progress_callback: Optional[Callable[..., Any]] = None,
    **kwargs: Any,
) -> MarkdownResult:
    """Convert an entire website to a Markdown corpus for LLM ingestion.

    Crawls the site (same engine as ``mirror_site``: robots.txt, sitemap
    discovery, depth limits, filters) and writes:

    - one ``.md`` file per page, mirroring the URL tree
    - ``llms.txt`` — site map with per-page summaries
    - ``llms-full.txt`` — every page merged into a single corpus file
    - ``index.md`` — table of contents linking to local files

    Parameters
    ----------
    url : str
        Starting URL.
    output_dir : str
        Output directory (default: ``./markdown``).
    max_depth : int
        Max link-following depth (default: 5).
    save_zip / save_warc : str, optional
        Also create a ZIP / WARC archive at the given path.
    progress_callback : callable, optional
        Called with progress stats during the crawl.
    **kwargs
        Extra ``MarkdownConfig`` / ``MirrorConfig`` options (delay, engine,
        proxy, exclude_patterns, respect_robots, markdown_merge, ...).

    Returns
    -------
    MarkdownResult
        Stats and output file paths.
    """
    from .track.mirror import SiteMirror  # local import avoids circular deps

    kwargs.pop("output_format", None)  # markdown mode is not negotiable here
    config = MarkdownConfig(
        url=url,
        output_dir=output_dir,
        max_depth=max_depth,
        **kwargs,
    )
    # Seed with a trailing slash so the root page isn't crawled twice
    # (a root page with an empty path is served as "/").
    parsed = urlparse(config.url)
    if not parsed.path and not config.url.endswith("/"):
        config.url = config.url + "/"
    mirror = SiteMirror(config)
    result = mirror.run(
        save_zip=save_zip,
        save_warc=save_warc,
        progress_callback=progress_callback,
    )
    return MarkdownResult(
        url=result.url,
        output_dir=result.output_dir,
        pages_converted=getattr(result, "markdown_pages", result.pages_downloaded),
        total_chars=getattr(result, "markdown_chars", 0),
        errors=result.errors,
        elapsed_seconds=result.elapsed_seconds,
        llms_file=getattr(result, "llms_file", None),
        llms_full_file=getattr(result, "llms_full_file", None),
        index_file=getattr(result, "index_file", None),
        zip_path=result.zip_path,
        warc_path=result.warc_path,
    )