"""tokens.css exporter.

Deterministically generates CSS custom properties for supported token
categories. Only *observed* values are emitted — inferred roles are never
written as authoritative custom properties. Values are emitted verbatim (no
lossy conversion); unsupported values stay in design.json.
"""

from __future__ import annotations

from typing import List

from ..models import DesignExtraction, Token


def _var_name(category: str, token: Token) -> str:
    """Stable, human-readable custom-property name."""
    base = token.role if token.role and token.role_status == "observed" else token.value
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", str(base).lower()).strip("-")
    return f"--is-{category}-{slug}"


def render_tokens_css(result: DesignExtraction) -> str:
    """Render a :root block of CSS custom properties for the observed tokens."""
    lines: List[str] = [
        "/* IntelliScrape Design Extract — generated tokens */",
        f"/* source: {result.capture.requested_url} */",
        f"/* captured: {result.capture.captured_at} */",
        "/* Values are measured from the live rendered page. */",
        "",
        ":root {",
    ]

    categories = [
        ("color", "Colors"),
        ("typography", "Typography"),
        ("spacing", "Spacing"),
        ("radius", "Radii"),
        ("shadow", "Shadows"),
        ("breakpoint", "Breakpoints"),
        ("custom-property", "Declared custom properties"),
    ]

    seen_names = set()
    for category, title in categories:
        tokens = result.tokens_by_category(category)
        if not tokens:
            continue
        lines.append(f"  /* {title} */")
        for t in tokens:
            name = _var_name(category, t)
            # Deduplicate name collisions deterministically.
            if name in seen_names:
                suffix = 2
                while f"{name}-{suffix}" in seen_names:
                    suffix += 1
                name = f"{name}-{suffix}"
            seen_names.add(name)
            lines.append(f"  {name}: {t.value};")
        lines.append("")

    lines.append("}")
    return "\n".join(lines) + "\n"
