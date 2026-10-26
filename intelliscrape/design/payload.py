"""Web payload shape for hosted design extraction.

The website frontend reads exactly this dict. The deployed API and the
standalone web backend both build their responses through these helpers, so the
contract cannot drift between the two deployments.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

#: Hosted capture policy. A request is served within these bounds; the effective
#: values are reported in the response so callers know what was measured.
HOSTED_OPTIONS = {
    "max_elements": 400,
    "navigation_timeout": 25.0,
    "stabilize_ms": 600,
    "challenge_timeout": 8.0,
}

SUPPORTED_PROFILES = ("desktop", "mobile")
DEFAULT_PROFILES = ("desktop",)

STATIC_FALLBACK_GAP = {
    "code": "static-fallback",
    "message": (
        "Live rendering was unavailable on the server, so this spec was extracted "
        "from static HTML/CSS. Computed styles, geometry and responsive behavior "
        "were not measured."
    ),
}


def clean_profiles(requested: Optional[Sequence[str]]) -> List[str]:
    """Clamp requested profiles to the supported, hosted set."""
    wanted = [p for p in (requested or DEFAULT_PROFILES) if p in SUPPORTED_PROFILES]
    return wanted[: len(SUPPORTED_PROFILES)] or list(DEFAULT_PROFILES)


def live_payload(result) -> Dict[str, object]:
    """Serialize a live :class:`DesignExtraction` into the web response shape."""
    has_tokens = result.status in ("succeeded", "partial")
    return {
        "url": result.capture.requested_url or result.source.get("requested_url", ""),
        "engine": "playwright-live",
        "status": result.status,
        "markdown": result.design_md,
        "artifacts": (
            {
                "DESIGN.md": result.design_md,
                "design.json": result.to_json(),
                "tokens.css": result.tokens_css,
                "preview.html": result.preview_html,
            }
            if has_tokens
            else {}
        ),
        "stats": result.stats,
        "coverage": result.coverage.model_dump(),
        "confidence": result.confidence,
        "gaps": [g.model_dump() for g in result.gaps],
        "profiles": list(result.effective_options.profiles),
        "schema_version": result.schema_version,
        "extractor_version": result.extractor_version,
    }


def static_payload(
    url: str,
    report,
    live_gaps: Optional[List[dict]] = None,
) -> Dict[str, object]:
    """Serialize a static :class:`DesignReport` when no browser was available."""
    import json

    markdown = report.to_markdown()
    design_json = json.dumps(report.to_design_json(), ensure_ascii=False)
    gaps = list(live_gaps or [])
    gaps.append(dict(STATIC_FALLBACK_GAP))
    return {
        "url": url,
        "engine": "static",
        "status": "partial",
        "markdown": markdown,
        "artifacts": {"DESIGN.md": markdown, "design.json": design_json},
        "stats": report.stats,
        "coverage": report.to_design_json()["coverage"],
        "confidence": report.confidence,
        "gaps": gaps,
        "profiles": [],
        "schema_version": None,
        "extractor_version": None,
    }
