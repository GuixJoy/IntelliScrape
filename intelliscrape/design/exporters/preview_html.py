"""preview.html exporter.

A self-contained, sanitized style guide rendered from the structured model —
not from the site's own markup. It is deliberately inert:

- No ``<script>`` and no event handlers.
- No external network references (fonts, images, stylesheets). Everything is
  inline and local.
- All text is HTML-escaped. Swatches are painted with the measured color
  values, which are already constrained to CSS color syntax by the normalizer.

This is an observed reference view. It does not execute or embed anything from
the target site.
"""

from __future__ import annotations

import html
from typing import List

from ..models import DesignExtraction, Token

# Inline base styles. No network fetches, no imports.
_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 32px; font-family: system-ui, -apple-system, sans-serif;
  background: #ffffff; color: #111111; line-height: 1.5; }
h1 { font-size: 24px; margin: 0 0 4px; }
h2 { font-size: 16px; margin: 40px 0 12px; padding-bottom: 6px;
  border-bottom: 1px solid #e5e5e5; text-transform: uppercase;
  letter-spacing: 0.06em; color: #666; }
.meta { color: #666; font-size: 13px; margin-bottom: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px; }
.card { border: 1px solid #e5e5e5; border-radius: 6px; overflow: hidden; }
.swatch { height: 64px; border-bottom: 1px solid #e5e5e5; }
.card-body { padding: 8px 10px; font-size: 12px; }
.card-body .val { font-family: ui-monospace, monospace; word-break: break-all; }
.card-body .role { color: #888; font-size: 11px; }
.type-row { display: flex; align-items: baseline; gap: 16px; padding: 10px 0;
  border-bottom: 1px solid #f0f0f0; }
.type-spec { flex: 1; }
.type-meta { font-family: ui-monospace, monospace; font-size: 12px; color: #666;
  white-space: nowrap; }
.scale { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; }
.scale-item { text-align: center; }
.scale-bar { background: #e8291c; opacity: 0.85; border-radius: 2px; }
.scale-label { font-family: ui-monospace, monospace; font-size: 11px;
  color: #666; margin-top: 4px; }
.shadow-box { background: #fff; border-radius: 8px; padding: 20px; margin: 8px 0; }
code { font-family: ui-monospace, monospace; background: #f5f5f5; padding: 1px 5px;
  border-radius: 3px; font-size: 12px; }
.gap { border-left: 3px solid #d97706; background: #fffbeb; padding: 8px 12px;
  margin: 6px 0; font-size: 13px; }
.footer { margin-top: 48px; color: #999; font-size: 12px; }
"""


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _is_safe_color(value: str) -> bool:
    """Reject anything that is not a plain CSS color expression.

    The normalizer already constrains these, but this is a defence-in-depth
    guard before the value is interpolated into inline style output.
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


def render_preview_html(result: DesignExtraction) -> str:
    """Render a self-contained, script-free style guide page."""
    host = result.capture.final_url or result.capture.requested_url
    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head><meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append(f"<title>Design reference — {_esc(host)}</title>")
    parts.append(f"<style>{_CSS}</style></head><body>")
    parts.append(f"<h1>{_esc(result.capture.title or host)}</h1>")
    parts.append(
        f'<div class="meta">Observed reference · {_esc(host)} · captured '
        f"{_esc(result.capture.captured_at)} · "
        f"status <strong>{_esc(result.status)}</strong></div>"
    )
    parts.append(
        f'<div class="meta">{result.coverage.elements_visible} visible elements · '
        f"{result.coverage.tokens_extracted} tokens · profiles: "
        f"{_esc(', '.join(p.name for p in result.capture.profiles))}</div>"
    )

    # Colors ---------------------------------------------------------------
    colors = result.tokens_by_category("color")
    parts.append("<h2>Colors</h2>")
    if colors:
        parts.append('<div class="grid">')
        for t in colors[:24]:
            safe = _is_safe_color(t.value)
            style = f"background:{_esc(t.value)};" if safe else "background:#eee;"
            role = _esc(t.role) if t.role else ""
            basis = "inferred" if t.role_status == "inferred" else "measured"
            parts.append('<div class="card">')
            parts.append(f'<div class="swatch" style="{style}"></div>')
            parts.append('<div class="card-body">')
            parts.append(f'<div class="val"><code>{_esc(t.value)}</code></div>')
            if role:
                parts.append(f'<div class="role">{role} ({basis})</div>')
            parts.append("</div></div>")
        parts.append("</div>")
    else:
        parts.append("<p>No interface colors were measured.</p>")

    # Typography -----------------------------------------------------------
    fonts = [t for t in result.tokens_by_category("typography") if t.role == "font-family"]
    sizes = [t for t in result.tokens_by_category("typography") if t.role == "font-size"]
    parts.append("<h2>Typography</h2>")
    if fonts:
        for t in fonts[:8]:
            family = _esc(t.value)
            parts.append('<div class="type-row">')
            parts.append(f'<div class="type-spec" style="font-family:\'{family}\',system-ui,sans-serif;font-size:22px">The quick brown fox</div>')
            parts.append(f'<div class="type-meta">{family}</div>')
            parts.append("</div>")
        if sizes:
            parts.append('<div class="type-row"><div class="type-meta">sizes: ')
            parts.append(_esc(", ".join(t.value for t in sizes[:12])))
            parts.append("</div></div>")
    else:
        parts.append("<p>No typography was measured.</p>")

    # Spacing --------------------------------------------------------------
    spacing = result.tokens_by_category("spacing")
    parts.append("<h2>Spacing</h2>")
    if spacing:
        parts.append('<div class="scale">')
        for t in spacing[:16]:
            try:
                px = float(t.value.replace("px", ""))
            except ValueError:
                continue
            h = max(4, min(px, 64))
            parts.append('<div class="scale-item">')
            parts.append(f'<div class="scale-bar" style="width:24px;height:{int(h)}px"></div>')
            parts.append(f'<div class="scale-label">{_esc(t.value)}</div>')
            parts.append("</div>")
        parts.append("</div>")
    else:
        parts.append("<p>No spacing scale was measured.</p>")

    # Radii ----------------------------------------------------------------
    radii = result.tokens_by_category("radius")
    parts.append("<h2>Shapes</h2>")
    if radii:
        parts.append('<div class="grid">')
        for t in radii[:12]:
            val = t.value if len(t.value) <= 40 else "8px"
            parts.append('<div class="card">')
            parts.append(f'<div style="height:64px;background:#f0f0f0;border:1px solid #ddd;border-radius:{_esc(val)}"></div>')
            parts.append(f'<div class="card-body"><div class="val">{_esc(t.value)}</div></div>')
            parts.append("</div>")
        parts.append("</div>")
    else:
        parts.append("<p>No corner radii were measured.</p>")

    # Shadows --------------------------------------------------------------
    shadows = result.tokens_by_category("shadow")
    parts.append("<h2>Elevation &amp; Depth</h2>")
    if shadows:
        for t in shadows[:6]:
            parts.append(f'<div class="shadow-box" style="box-shadow:{_esc(t.value)}">')
            parts.append(f'<code>{_esc(t.value)}</code></div>')
    else:
        parts.append("<p>No elevation was measured.</p>")

    # Components -----------------------------------------------------------
    parts.append("<h2>Components</h2>")
    if result.components:
        parts.append("<table>")
        parts.append("<tr><th>Kind</th><th>Label</th><th>Profile</th><th>Count</th></tr>")
        for c in result.components[:20]:
            parts.append(
                f"<tr><td>{_esc(c.kind)}</td><td>{_esc(c.label or '—')}</td>"
                f"<td>{_esc(c.profile)}</td><td>{c.count}</td></tr>"
            )
        parts.append("</table>")
    else:
        parts.append("<p>No representative components were grouped.</p>")

    # Gaps -----------------------------------------------------------------
    parts.append("<h2>Known Gaps</h2>")
    if result.gaps:
        for g in result.gaps:
            parts.append(f'<div class="gap"><code>{_esc(g.code)}</code> {_esc(g.message)}</div>')
    else:
        parts.append("<p>No explicit gaps recorded; coverage is still bounded by the capture profiles.</p>")

    parts.append('<div class="footer">Generated by IntelliScrape Design Extract. This is an observed design reference, not the site\'s official brand manual. No scripts or external resources are loaded by this page.</div>')
    parts.append("</body></html>")
    return "\n".join(parts)
