"""DESIGN.md exporter.

Renders toward the upstream DESIGN.md spec (alpha): one YAML front-matter
block carrying machine-readable tokens, followed by ordered prose sections
(Overview, Colors, Typography, Layout, Elevation & Depth, Shapes, Components,
Do's and Don'ts). Scope and gaps are added as extra prose sections so missing
categories are explained rather than fabricated.

Values in front matter are quoted, aliases are kept simple, and unsupported
values stay in the richer ``design.json`` rather than being force-converted
into a misleading token.
"""

from __future__ import annotations

from typing import List

from ..models import DESIGNMD_SPEC_VERSION, DesignExtraction, Token


def _yaml_str(value: str) -> str:
    """Quote a scalar for YAML. Doubles inner quotes; always double-quoted."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _token_line(key: str, value: str, indent: int = 4) -> str:
    return " " * indent + f"{key}: {_yaml_str(value)}"


def _front_matter(result: DesignExtraction) -> List[str]:
    lines = ["---", f"version: {DESIGNMD_SPEC_VERSION}"]

    host = result.capture.title or result.capture.final_url or result.capture.requested_url
    lines.append(f"name: {_yaml_str(host)}")
    lines.append(f"source: {_yaml_str(result.capture.requested_url)}")
    lines.append(f"extractor: {_yaml_str('intelliscrape ' + result.extractor_version)}")
    lines.append(f"captured: {_yaml_str(result.capture.captured_at)}")

    def section(category: str, title: str, key_fn) -> None:
        toks = result.tokens_by_category(category)
        if not toks:
            return
        lines.append(f"{title}:")
        for t in toks[:30]:
            lines.append(_token_line(key_fn(t), t.value))

    # Colors: give stable, descriptive names. Prefer an inferred semantic role
    # (primary, ink, surface, ...); numbered neutral/accent fallbacks stay
    # color-<n> so the YAML never claims more than was inferred.
    colors = result.tokens_by_category("color")
    if colors:
        lines.append("colors:")
        used: set = set()
        for i, t in enumerate(colors[:30]):
            base = t.role if t.role and not t.role.startswith(("neutral-", "accent-")) else ""
            if base:
                key = base
                n = 2
                while key in used:
                    key = f"{base}-{n}"
                    n += 1
                used.add(key)
            else:
                key = f"color-{i}"
            lines.append(_token_line(key, t.value))

    # Typography: group font families under one key, then scales as separate
    # named entries only when they cluster to a single obvious value.
    fonts = [t for t in result.tokens_by_category("typography") if t.role == "font-family"]
    sizes = [t for t in result.tokens_by_category("typography") if t.role == "font-size"]
    weights = [t for t in result.tokens_by_category("typography") if t.role == "font-weight"]
    line_heights = [t for t in result.tokens_by_category("typography") if t.role == "line-height"]
    if fonts or sizes:
        lines.append("typography:")
        for t in fonts[:10]:
            lines.append(_token_line(f"font-{_safe_key(t.value)}", t.value))
        for t in sizes[:10]:
            lines.append(_token_line(f"size-{_safe_key(t.value)}", t.value))
        for t in weights[:6]:
            lines.append(_token_line(f"weight-{_safe_key(t.value)}", t.value))
        for t in line_heights[:6]:
            lines.append(_token_line(f"leading-{_safe_key(t.value)}", t.value))

    radii = result.tokens_by_category("radius")
    if radii:
        lines.append("rounded:")
        for t in radii[:10]:
            lines.append(_token_line(f"radius-{_safe_key(t.value)}", t.value))

    spacing = result.tokens_by_category("spacing")
    if spacing:
        lines.append("spacing:")
        for t in spacing[:15]:
            lines.append(_token_line(f"space-{_safe_key(t.value)}", t.value))

    lines.append("---")
    return lines


def _safe_key(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def render_design_md(result: DesignExtraction) -> str:
    """Render the full DESIGN.md document for a result."""
    out: List[str] = _front_matter(result)
    out.append("")

    # ---- Overview ----------------------------------------------------------
    out.append("## Overview")
    out.append("")
    host = result.capture.final_url or result.capture.requested_url
    profiles = ", ".join(p.name for p in result.capture.profiles) or "none"
    out.append(
        f"Observed reference from `{host}` captured at {result.capture.captured_at} "
        f"across the {profiles} profiles. Semantic roles below are inferred from "
        "measured prominence, not read from a brand source."
    )
    out.append("")
    out.append(
        f"Extraction status: **{result.status}**. "
        f"{result.coverage.elements_visible} visible elements measured across "
        f"{result.coverage.pages_completed} page(s); "
        f"{result.coverage.tokens_extracted} tokens extracted."
    )
    out.append("")

    # ---- Confidence --------------------------------------------------------
    confidence = result.confidence or {}
    if confidence.get("overall"):
        sections = confidence.get("sections") or {}
        out.append("## Confidence")
        out.append("")
        out.append(f"Evidence-based score: **{confidence['overall']}%**.")
        measured = " · ".join(f"{k} {v}%" for k, v in sections.items() if v)
        if measured:
            out.append("")
            out.append(measured)
        if confidence.get("basis"):
            out.append("")
            out.append(str(confidence["basis"]))
        out.append("")

    # ---- Colors ------------------------------------------------------------
    colors = result.tokens_by_category("color")
    out.append("## Colors")
    out.append("")
    if colors:
        out.append("| Token | Value | Role | Basis |")
        out.append("| --- | --- | --- | --- |")
        for t in colors[:20]:
            role = t.role or "—"
            basis = "inferred" if t.role_status == "inferred" else "measured"
            out.append(f"| `{_key_for(t)}` | `{t.value}` | {role} | {basis} |")
        out.append("")
        inferred = [t for t in colors if t.role_status == "inferred"]
        if inferred:
            out.append(
                "Roles marked *inferred* are heuristics based on prominence and "
                "saturation. Confirm before treating any value as the brand's "
                "primary color."
            )
            out.append("")
    else:
        out.append("No interface colors were measured in this capture.")
        out.append("")

    # ---- Typography --------------------------------------------------------
    out.append("## Typography")
    out.append("")
    fonts = [t for t in result.tokens_by_category("typography") if t.role == "font-family"]
    sizes = [t for t in result.tokens_by_category("typography") if t.role == "font-size"]
    weights = [t for t in result.tokens_by_category("typography") if t.role == "font-weight"]
    if fonts or sizes:
        if fonts:
            out.append("Font families (first real family in each observed stack):")
            out.append("")
            for t in fonts[:10]:
                out.append(f"- `{t.value}`")
            out.append("")
        if sizes:
            out.append("Observed size scale: " + ", ".join(f"`{t.value}`" for t in sizes[:12]))
            out.append("")
        if weights:
            out.append("Observed weights: " + ", ".join(f"`{t.value}`" for t in weights[:8]))
            out.append("")
        out.append(
            "A declared family is not proof the font was used for every glyph; "
            "loading/fallback evidence is recorded in the JSON model."
        )
        out.append("")
    else:
        out.append("No typography was measured in this capture.")
        out.append("")

    # ---- Layout ------------------------------------------------------------
    spacing = result.tokens_by_category("spacing")
    out.append("## Layout")
    out.append("")
    if spacing:
        out.append("Observed spacing steps (padding/gap, px): " + ", ".join(f"`{t.value}`" for t in spacing[:15]))
        out.append("")
        out.append(
            "These are measured values. A consistent 4px/8px rhythm is a "
            "hypothesis until confirmed; values are not rounded to fit one."
        )
        out.append("")
    else:
        out.append("No spacing scale was established by this capture.")
        out.append("")

    # ---- Elevation & Depth -------------------------------------------------
    shadows = result.tokens_by_category("shadow")
    out.append("## Elevation & Depth")
    out.append("")
    if shadows:
        out.append("Observed box shadows:")
        out.append("")
        for t in shadows[:8]:
            out.append(f"- `{t.value}`")
        out.append("")
    else:
        out.append("No elevation conclusion is supported by this capture.")
        out.append("")

    # ---- Shapes ------------------------------------------------------------
    radii = result.tokens_by_category("radius")
    out.append("## Shapes")
    out.append("")
    if radii:
        out.append("Observed border radii (asymmetric corners preserved):")
        out.append("")
        for t in radii[:10]:
            out.append(f"- `{t.value}`")
        out.append("")
    else:
        out.append("No corner radii were measured in this capture.")
        out.append("")

    # ---- Components --------------------------------------------------------
    out.append("## Components")
    out.append("")
    if result.components:
        out.append("| Kind | Label | Profile | Occurrences |")
        out.append("| --- | --- | --- | --- |")
        for c in result.components[:15]:
            label = (c.label or "—").replace("|", "/")
            out.append(f"| {c.kind} | {label} | {c.profile} | {c.count} |")
        out.append("")
        out.append(
            "Representative rest-state captures only. Hover/focus states and "
            "reconstructed HTML/CSS recipes are not part of this extraction."
        )
        out.append("")
    else:
        out.append("No representative components were grouped in this capture.")
        out.append("")

    # ---- Do's and Don'ts ---------------------------------------------------
    out.append("## Do's and Don'ts")
    out.append("")
    out.append(
        "- Use the measured values above for the elements they were measured "
        "on; do not assume they generalize site-wide without more samples."
    )
    out.append(
        "- Treat inferred color roles as suggestions. Validate a role before "
        "using it as an exact brand token."
    )
    out.append(
        "- Do not assume an unmeasured state (hover, focus, disabled) matches "
        "the rest state shown here."
    )
    out.append("")

    # ---- Scope and gaps ----------------------------------------------------
    out.append("## Scope and Known Gaps")
    out.append("")
    out.append(
        f"Profiles captured: {profiles}. "
        f"Pages: {result.coverage.pages_completed} of "
        f"{result.coverage.pages_attempted} attempted."
    )
    out.append("")
    if result.gaps:
        out.append("Limitations recorded during this run:")
        out.append("")
        for g in result.gaps:
            out.append(f"- `{g.code}`: {g.message}")
        out.append("")
    else:
        out.append("No explicit gaps were recorded, but coverage is still bounded by the capture profiles above.")
        out.append("")

    out.append(
        "_Generated by IntelliScrape Design Extract. This is an observed design "
        "reference, not the site's official brand manual._"
    )
    return "\n".join(out) + "\n"


def _key_for(token: Token) -> str:
    if token.role and not token.role.startswith(("neutral-", "accent-")):
        return token.role
    return token.id.split("|")[0]


def design_md(result: DesignExtraction) -> str:
    """Public alias used by the exporters package."""
    return render_design_md(result)
