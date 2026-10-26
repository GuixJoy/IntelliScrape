"""Static (no-browser) design extractor — the lightweight fallback.

This is the CSS-regex extractor: it parses ``<style>`` blocks, inline
``style=""`` attributes and caller-supplied stylesheet text out of a raw HTML
string. It is fast and dependency-free, but it cannot measure a live rendered
page — no computed styles, no geometry, no interaction states.

Use it when a browser is unavailable or when you only need a rough palette /
typography read from static markup. For measurement-grade results use the
live engine (:func:`intelliscrape.design.extract_design`), which renders the
page and reads resolved styles.

This module is deliberately dependency-free beyond stdlib + BeautifulSoup so
it can be vendored unchanged by the standalone FastAPI web backend.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .confidence import score as score_confidence
from .normalize import assign_color_roles, canonical_color, first_font_family

# ---------------------------------------------------------------------------
# Extraction regexes (applied to concatenated CSS text)
# ---------------------------------------------------------------------------

_COLOR_RE = re.compile(
    r"#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})\b"
    r"|rgba?\([^)]*\)|hsla?\([^)]*\)",
    re.IGNORECASE,
)
## Value regexes share the same stop set: end of value is ;, {, } or a newline
## (css text from different sources is joined with newlines).
_VAR_RE = re.compile(r"--([\w-]+)\s*:\s*([^\n;{}]+)", re.IGNORECASE)
_FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^\n;{}]+)", re.IGNORECASE)
_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([^\n;{}]+)", re.IGNORECASE)
_FONT_WEIGHT_RE = re.compile(r"font-weight\s*:\s*([\w]+)", re.IGNORECASE)
_LINE_HEIGHT_RE = re.compile(r"line-height\s*:\s*([0-9.]+(?:\s*[a-z%]+)?)", re.IGNORECASE)
_SPACING_RE = re.compile(
    r"(?:margin(?:-(?:top|right|bottom|left))?\s*:"
    r"|padding(?:-(?:top|right|bottom|left))?\s*:"
    r"|gap\s*:)\s*([^\n;{}]+)",
    re.IGNORECASE,
)
_RADIUS_RE = re.compile(r"border-radius(?:-(?:top|bottom)?-?(?:left|right|start|end))?\s*:\s*([^\n;{}]+)", re.IGNORECASE)
_SHADOW_RE = re.compile(r"box-shadow\s*:\s*([^\n;{}]+)", re.IGNORECASE)
_MEDIA_RE = re.compile(
    r"@media[^{]*?\([a-z]*-?width\s*:\s*([\d.]+)\s*(px|rem|em)\)",
    re.IGNORECASE,
)
_VAR_CALL_RE = re.compile(r"var\(\s*--([\w-]+)\s*(?:,\s*([^()]*))?\)")
_TOTAL_VAL_RE = re.compile(r"calc\([^)]*\)")
_LENGTH_RE = re.compile(r"^(-?[\d.]+)(px|rem|em|%)$")

# Caps so a bloated stylesheet can't blow up the report.
_MAX_LISTED = 30
_MAX_VARS = 60

# Values that are not design tokens even though they match a declaration regex.
_NON_VALUES = {"", "0", "0px", "none", "auto", "normal", "inherit", "initial", "unset", "revert"}


def _clean(value: str) -> str:
    """Normalize a CSS value for counting."""
    value = _TOTAL_VAL_RE.sub("calc(...)", value.strip().strip(";"))
    value = re.sub(r"\s+", " ", value)
    return value.strip().lower()


def _strip_important(value: str) -> str:
    return re.sub(r"\s*!important\s*$", "", value.strip(), flags=re.IGNORECASE)


def _length_px(value: str, *, allow_em: bool = False) -> Optional[float]:
    """Convert one CSS length to px. Relative ``em`` is only safe when asked."""
    m = _LENGTH_RE.match(value.strip().lower())
    if not m:
        return None
    number, unit = float(m.group(1)), m.group(2)
    if unit == "px":
        return round(number, 2)
    if unit == "rem" or (unit == "em" and allow_em):
        return round(number * 16, 2)
    return None


def _normalize_lengths(value: str, *, allow_em: bool = False, allow_percent: bool = False) -> Optional[str]:
    """Normalize a 1-4 value box (margin/padding/radius) to px, or None."""
    raw = _strip_important(value)
    if not raw or "calc(" in raw or "var(" in raw:
        return None
    parts: List[str] = []
    for token in raw.split():
        if token in ("0", "0px"):
            parts.append("0")
            continue
        if allow_percent and token.endswith("%"):
            try:
                parts.append(f"{float(token[:-1]):g}%")
                continue
            except ValueError:
                return None
        px = _length_px(token, allow_em=allow_em)
        if px is None:
            return None
        parts.append(f"{px:g}px")
    if not parts or all(p == "0" for p in parts):
        return None
    return " ".join(parts)


def collect_css(html: str) -> str:
    """Concatenate <style> blocks + inline style="" attributes from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    parts: List[str] = []
    for style in soup.find_all("style"):
        if style.string:
            parts.append(style.string)
    for el in soup.select("[style]"):
        parts.append(el.get("style", ""))
    return "\n".join(parts)


def stylesheet_hrefs(html: str) -> List[str]:
    """Return hrefs of external stylesheets declared in *html*."""
    soup = BeautifulSoup(html, "html.parser")
    hrefs: List[str] = []
    for link in soup.find_all("link", href=True):
        rel = link.get("rel") or []
        rel = rel if isinstance(rel, list) else [rel]
        if any(r.lower() in ("stylesheet", "preload") for r in rel) or (link.get("as", "") == "style"):
            hrefs.append(link["href"])
    return hrefs


def _collect_variables(css: str) -> Dict[str, str]:
    """Map ``--name`` to its declared value, first declaration wins."""
    seen: Dict[str, str] = {}
    for name, value in _VAR_RE.findall(css):
        name = re.sub(r"[^\w-]", "", name)  # strip artifacts from jsdom-style css
        raw = _strip_important(value)
        if name and raw and name not in seen:
            seen[name] = raw
    return seen


def resolve_vars(text: str, variables: Dict[str, str], depth: int = 6) -> str:
    """Substitute ``var(--name[, fallback])`` using *variables*.

    Runs repeatedly so nested variables (a token defined in terms of another)
    resolve. Unresolved references fall back to the declared fallback or are
    left in place for the value parsers to reject.
    """

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name in variables:
            return variables[name]
        return match.group(2) or match.group(0)

    for _ in range(depth):
        updated = _VAR_CALL_RE.sub(replace, text)
        if updated == text:
            break
        text = updated
    return text


@dataclass
class DesignReport:
    """Extracted design system for a URL, with Markdown rendering."""

    url: str
    title: str = ""
    # Raw counters — kept for backwards compatibility and rough audits.
    colors: Counter = field(default_factory=Counter)
    font_families: Counter = field(default_factory=Counter)
    font_sizes: Counter = field(default_factory=Counter)
    font_weights: Counter = field(default_factory=Counter)
    line_heights: Counter = field(default_factory=Counter)
    spacing: Counter = field(default_factory=Counter)
    radii: Counter = field(default_factory=Counter)
    shadows: Counter = field(default_factory=Counter)
    breakpoints: Counter = field(default_factory=Counter)
    css_variables: Dict[str, str] = field(default_factory=dict)

    # Normalized layer — this is what the web report and DESIGN.md read.
    palette: Counter = field(default_factory=Counter)
    color_roles: Dict[str, str] = field(default_factory=dict)
    families: Counter = field(default_factory=Counter)
    sizes_px: Counter = field(default_factory=Counter)
    weights: Counter = field(default_factory=Counter)
    leading: Counter = field(default_factory=Counter)
    spacing_px: Counter = field(default_factory=Counter)
    radii_px: Counter = field(default_factory=Counter)
    shadows_norm: Counter = field(default_factory=Counter)
    breakpoints_px: Counter = field(default_factory=Counter)
    tokens: List[dict] = field(default_factory=list)
    sections: Dict[str, int] = field(default_factory=dict)
    confidence: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "colors": self.colors.most_common(_MAX_LISTED),
            "font_families": self.font_families.most_common(_MAX_LISTED),
            "font_sizes": self.font_sizes.most_common(_MAX_LISTED),
            "font_weights": self.font_weights.most_common(_MAX_LISTED),
            "line_heights": self.line_heights.most_common(_MAX_LISTED),
            "spacing": self.spacing.most_common(_MAX_LISTED),
            "radii": self.radii.most_common(_MAX_LISTED),
            "shadows": self.shadows.most_common(_MAX_LISTED),
            "breakpoints": self.breakpoints.most_common(_MAX_LISTED),
            "css_variables": dict(list(self.css_variables.items())[:_MAX_VARS]),
            "palette": self.palette.most_common(_MAX_LISTED),
            "color_roles": self.color_roles,
            "tokens": self.tokens,
            "confidence": self.confidence,
        }

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "colors": len(self.palette),
            "fonts": len(self.families),
            "font_sizes": len(self.sizes_px),
            "spacing": len(self.spacing_px),
            "radii": len(self.radii_px),
            "shadows": len(self.shadows_norm),
            "breakpoints": len(self.breakpoints_px),
            "css_variables": len(self.css_variables),
        }

    def to_design_json(self) -> dict:
        """Structured model consumed by the website report (same shape as live)."""
        host = urlparse(self.url).netloc or self.url
        return {
            "capture": {
                "requested_url": self.url,
                "final_url": self.url,
                "title": self.title or host,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
            "tokens": self.tokens,
            "observations": [],
            "components": [],
            "coverage": {
                "elements_sampled": 0,
                "elements_visible": 0,
                "tokens_extracted": len(self.tokens),
                "components_found": 0,
            },
            "gaps": [],
            "confidence": self.confidence,
        }

    def _palette_rows(self) -> List[Tuple[str, str, int]]:
        return [
            (self.color_roles.get(color, "color"), color, n)
            for color, n in self.palette.most_common(_MAX_LISTED)
        ]

    def to_markdown(self) -> str:
        """Render the report as a Markdown design spec."""
        host = urlparse(self.url).netloc or self.url
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        md: List[str] = [f"# Design spec — {host}", "", f"Extracted {now} from `{self.url}`", ""]
        overall = int(self.confidence.get("overall", 0) or 0)
        if overall:
            md += [
                f"Confidence: **{overall}%** — static HTML/CSS read. "
                "Computed styles, geometry and responsive behavior were not measured.",
                "",
            ]

        # Colors ----------------------------------------------------------------
        rows_data = self._palette_rows()
        if rows_data:
            total = sum(self.palette.values())
            rows = ["| Role | Color | Uses |", "| --- | --- | --- |"]
            for role, color, n in rows_data:
                share = f" ({n * 100 / total:.0f}%)" if total >= 2 else ""
                rows.append(f"| {role} | `{color}` | {n}{share} |")
            md += ["## Color palette", "", *rows, ""]

        # Typography ------------------------------------------------------------
        if self.families:
            block = ["| Family | Uses |", "| --- | --- |"]
            block += [f"| **{f}** | {n} |" for f, n in self.families.most_common(_MAX_LISTED)]
            if self.sizes_px:
                block += ["", "Size scale: " + ", ".join(
                    f"`{v:g}px`" for v, _ in self.sizes_px.most_common(15)
                )]
            if self.weights:
                block += ["", "Weights: " + ", ".join(f"`{v}`" for v, _ in self.weights.most_common(10))]
            if self.leading:
                block += ["", "Line heights: " + ", ".join(f"`{v}`" for v, _ in self.leading.most_common(10))]
            md += ["## Typography", "", *block, ""]

        # Spacing / radius / shadows --------------------------------------------
        if self.spacing_px:
            md += ["## Spacing scale", "", "`" + "` · `".join(
                v for v, _ in self.spacing_px.most_common(_MAX_LISTED)
            ) + "`", ""]
        if self.radii_px:
            md += ["## Border radius", "", "`" + "` · `".join(
                v for v, _ in self.radii_px.most_common(_MAX_LISTED)
            ) + "`", ""]
        if self.shadows_norm:
            md += ["## Shadows", "", *[f"- `{s}`" for s, _ in self.shadows_norm.most_common(10)], ""]

        # Breakpoints -----------------------------------------------------------
        if self.breakpoints_px:
            md += ["## Breakpoints", "", "`" + "` · `".join(
                f"{v}px" for v, _ in self.breakpoints_px.most_common(_MAX_LISTED)
            ) + "`", ""]

        # CSS variables ---------------------------------------------------------
        if self.css_variables:
            md += [
                "## CSS variables",
                "",
                "```css",
                *[f"--{k}: {v};" for k, v in list(self.css_variables.items())[:_MAX_VARS]],
                "```",
                "",
            ]

        return "\n".join(md) + "\n"

    def save(self, path: str) -> str:
        """Write the Markdown spec to *path*; returns the path."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_markdown())
        return path


class DesignExtractor:
    """Extract :class:`DesignReport` from raw HTML + optional stylesheet text."""

    @classmethod
    def extract(
        cls,
        html: str,
        css_texts: Optional[List[str]] = None,
        url: str = "",
    ) -> DesignReport:
        """Analyse *html*, inline styles and each stylesheet string in *css_texts*."""
        raw_css = collect_css(html)
        for text in css_texts or []:
            raw_css += "\n" + (text or "")

        variables = _collect_variables(raw_css)
        css = resolve_vars(raw_css, variables)

        soup = BeautifulSoup(html, "html.parser")
        title = ""
        if soup.title:
            title = re.sub(r"\s+", " ", soup.title.get_text(" ", strip=True))[:120]

        report = DesignReport(
            url=url,
            title=title,
            css_variables={k: _clean(v) for k, v in variables.items()},
        )

        # Raw layer (unchanged behaviour, kept for compatibility).
        for m in _COLOR_RE.findall(raw_css):
            report.colors[m.lower()] += 1
        for raw in _FONT_FAMILY_RE.findall(raw_css):
            family = raw.split(",")[0].strip().strip("'\";")
            if family:
                report.font_families[family] += 1
        for m in _FONT_SIZE_RE.findall(raw_css):
            if (v := _clean(m)):
                report.font_sizes[v] += 1
        for m in _FONT_WEIGHT_RE.findall(raw_css):
            report.font_weights[m.lower()] += 1
        for m in _LINE_HEIGHT_RE.findall(raw_css):
            report.line_heights[m.strip()] += 1
        for m in _SPACING_RE.findall(raw_css):
            if (v := _clean(m)) and v not in _NON_VALUES:
                report.spacing[v] += 1
        for m in _RADIUS_RE.findall(raw_css):
            if (v := _clean(m)) and v not in _NON_VALUES:
                report.radii[v] += 1
        for m in _SHADOW_RE.findall(raw_css):
            if (v := _clean(m)) and v not in _NON_VALUES:
                report.shadows[v] += 1
        for m in _MEDIA_RE.findall(raw_css):
            try:
                report.breakpoints[int(float(m[0]))] += 1
            except ValueError:
                continue

        cls._normalize(report, css)
        return report

    # -- normalized layer ----------------------------------------------------
    @classmethod
    def _normalize(cls, report: DesignReport, css: str) -> None:
        # Colors: canonical hex, duplicates merged, transparent dropped.
        for m in _COLOR_RE.findall(css):
            color = canonical_color(m)
            if color:
                report.palette[color] += 1
        ranked = report.palette.most_common(_MAX_LISTED)
        roles = assign_color_roles([(color, n) for color, n in ranked])
        report.color_roles = {color: role for color, (role, _reason) in roles.items()}

        # Typography: resolved families, px sizes, numeric weights.
        for raw in _FONT_FAMILY_RE.findall(css):
            family = first_font_family(raw)
            if family and "(" not in family and family.lower() not in _NON_VALUES:
                report.families[family] += 1
        size_refs = _FONT_SIZE_RE.findall(css)
        for raw in size_refs:
            px = _length_px(_strip_important(raw))
            if px is not None and px > 0:
                report.sizes_px[px] += 1
        weight_refs = _FONT_WEIGHT_RE.findall(css)
        for raw in weight_refs:
            v = raw.strip().lower()
            if v.isdigit() and 100 <= int(v) <= 900:
                report.weights[str(int(v))] += 1
            elif v == "bold":
                report.weights["700"] += 1
            elif v == "normal":
                report.weights["400"] += 1
        leading_refs = _LINE_HEIGHT_RE.findall(css)
        for raw in leading_refs:
            v = raw.strip().lower()
            if v and v not in _NON_VALUES:
                report.leading[v] += 1

        # Box values: px only; relative em/% values cannot be resolved safely.
        spacing_refs = _SPACING_RE.findall(css)
        for raw in spacing_refs:
            v = _normalize_lengths(raw)
            if v:
                report.spacing_px[v] += 1
        radius_refs = _RADIUS_RE.findall(css)
        for raw in radius_refs:
            v = _normalize_lengths(raw, allow_percent=True)
            if v:
                report.radii_px[v] += 1
        shadow_refs = _SHADOW_RE.findall(css)
        for raw in shadow_refs:
            v = _strip_important(raw)
            if not v or v.lower() in _NON_VALUES or "var(" in v or "calc(" in v:
                continue
            report.shadows_norm[re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", v)).lower()] += 1

        # Breakpoints: em/rem are relative to the 16px root.
        media_refs = _MEDIA_RE.findall(css)
        for number, unit in media_refs:
            try:
                px = float(number) * 16 if unit.lower() in ("em", "rem") else float(number)
            except ValueError:
                continue
            report.breakpoints_px[round(px)] += 1

        report.tokens = cls._tokens(report)
        report.sections = cls._sections(report, css, size_refs, weight_refs, leading_refs,
                                        spacing_refs, radius_refs, shadow_refs, media_refs)
        report.confidence = score_confidence(report.sections, engine="static")

    @staticmethod
    def _tokens(report: DesignReport) -> List[dict]:
        tokens: List[dict] = []

        def add(category: str, value: str, role: str, frequency: int, index: int,
                status: str = "observed", reason: str = "") -> None:
            slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:24]
            tokens.append({
                "id": f"{category}-{index}-{slug}",
                "category": category,
                "value": value,
                "role": role,
                "role_status": status,
                "role_reason": reason,
                "frequency": frequency,
            })

        for i, (color, n) in enumerate(report.palette.most_common(_MAX_LISTED)):
            role = report.color_roles.get(color, "")
            add("color", color, role, n, i, "inferred" if role else "observed",
                "Inferred from prominence and hue; not verified against components." if role else "")
        for i, (family, n) in enumerate(report.families.most_common(_MAX_LISTED)):
            add("typography", family, "font-family", n, i)
        for i, (px, n) in enumerate(report.sizes_px.most_common(20)):
            add("typography", f"{px:g}px", "font-size", n, i)
        for i, (weight, n) in enumerate(report.weights.most_common(12)):
            add("typography", weight, "font-weight", n, i)
        for i, (leading, n) in enumerate(report.leading.most_common(12)):
            add("typography", leading, "line-height", n, i)
        for i, (value, n) in enumerate(report.spacing_px.most_common(_MAX_LISTED)):
            add("spacing", value, "spacing-step", n, i)
        for i, (value, n) in enumerate(report.radii_px.most_common(_MAX_LISTED)):
            add("radius", value, "radius", n, i)
        for i, (value, n) in enumerate(report.shadows_norm.most_common(12)):
            add("shadow", value, "elevation", n, i)
        for i, (px, n) in enumerate(report.breakpoints_px.most_common(20)):
            add("breakpoint", f"{px}px", "breakpoint", n, i, reason=(
                "Declared @media width condition (declared evidence, not an observed layout change)."
            ))
        for i, (name, value) in enumerate(sorted(report.css_variables.items())[:60]):
            add("custom-property", value, name, 1, i, reason=(
                "Declared :root custom property (a token candidate, not proof of visible use)."
            ))
        return tokens

    @staticmethod
    def _sections(
        report: DesignReport,
        css: str,
        size_refs: List[str],
        weight_refs: List[str],
        leading_refs: List[str],
        spacing_refs: List[str],
        radius_refs: List[str],
        shadow_refs: List[str],
        media_refs: List[Tuple[str, str]],
    ) -> Dict[str, int]:
        def pct(ok: int, total: int) -> int:
            return round(100 * ok / total) if total else 0

        color_refs = [m for m in _COLOR_RE.findall(css) if canonical_color(m)]
        family_refs = _FONT_FAMILY_RE.findall(css)
        typography_total = len(size_refs) + len(family_refs)
        typography_ok = sum(report.sizes_px.values()) + sum(report.families.values())
        return {
            "colors": pct(sum(report.palette.values()), len(color_refs)),
            "typography": pct(typography_ok, typography_total),
            "spacing": pct(sum(report.spacing_px.values()), len(spacing_refs)),
            "radii": pct(sum(report.radii_px.values()), len(radius_refs)),
            "shadows": pct(sum(report.shadows_norm.values()), len(shadow_refs)),
            "breakpoints": 100 if media_refs else 0,
            "custom-properties": 100 if report.css_variables else 0,
            "components": 0,
        }
