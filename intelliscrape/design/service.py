"""Orchestration for Design Extract.

One pipeline shared by the library, CLI and (later) the hosted worker:

    plan -> capture live pages -> collect evidence -> normalize tokens
         -> build components -> export artifacts

The public entry points are :func:`extract_design` (sync) and the async form.
The result model is the single source of truth every surface reads from.

No LLM or API key is required. Playwright must be installed and a browser
present; a clear error explains how if not.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Sequence
from urllib.parse import urlparse

from .browser import DesignCaptureError, PlaywrightDesignAdapter
from .components import ComponentAnalyzer
from .confidence import score as score_confidence
from .models import (
    DEFAULT_PROFILES,
    CaptureContext,
    CaptureProfile,
    Coverage,
    DesignExtraction,
    ExtractionOptions,
    Gap,
    Observation,
)
from .normalize import DesignNormalizer

logger = logging.getLogger("intelliscrape.design.service")

_PROFILE_BUILDERS = {
    "desktop": CaptureProfile.desktop,
    "mobile": CaptureProfile.mobile,
}


def _resolve_profiles(names: Sequence[str]) -> List[CaptureProfile]:
    profiles = []
    for n in names:
        builder = _PROFILE_BUILDERS.get(n)
        if builder:
            profiles.append(builder())
    return profiles or [CaptureProfile.desktop()]


def _validate_url(url: str) -> None:
    """Local-library URL check. Allows file:// so fixtures and local HTML work.

    The hosted service must NOT reuse this relaxed rule — it enforces its own
    http/https-only, egress-guarded policy (see ``security.validate_target_url``).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", "file"):
        raise ValueError(f"Only http/https/file URLs are supported for design extraction, got scheme={parsed.scheme!r}")
    if parsed.scheme in ("http", "https") and not parsed.hostname:
        raise ValueError("URL has no hostname")


def _obs_from_raw(raw: dict, profile_name: str, page_url: str) -> Observation:
    """Convert a raw collector dict into a typed Observation."""
    bbox = raw.get("bbox", {}) or {}
    return Observation(
        id=raw.get("id", ""),
        profile=profile_name,
        page_url=page_url,
        tag=raw.get("tag", ""),
        role=raw.get("role", ""),
        label=raw.get("label", ""),
        bbox=bbox,
        area=float(raw.get("area", 0.0) or 0.0),
        visible=True,
        styles=raw.get("styles", {}) or {},
        root_vars=raw.get("root_vars", {}) or {},
        media_widths=raw.get("media_widths", []) or [],
    )


def extract_design(
    url: str,
    *,
    scope: str = "page",
    profiles: Optional[Sequence[str]] = None,
    max_pages: int = 1,
    color_schemes: Optional[Sequence[str]] = None,
    max_elements: int = 400,
    navigation_timeout: float = 30.0,
    stabilize_ms: int = 800,
    scroll_steps: int = 6,
    challenge_timeout: float = 20.0,
    headless: bool = True,
    include_screenshots: bool = False,
) -> DesignExtraction:
    """Extract a design reference from a live-rendered page.

    Parameters mirror :class:`ExtractionOptions`; see that model for defaults.
    Returns a :class:`DesignExtraction` — inspect ``.status``, ``.tokens``,
    ``.gaps`` and ``.coverage``. Use ``.save(dir)`` to write all artifacts.

    ``challenge_timeout`` bounds how long a served JS challenge may try to
    auto-solve before the capture is reported ``blocked`` (0 = report
    immediately). The browser itself is stealthed the same way the scraping
    engine is; no API key or paid service is involved.
    """
    profiles = list(profiles) if profiles else list(DEFAULT_PROFILES)
    color_schemes = list(color_schemes) if color_schemes else ["light"]

    requested = ExtractionOptions(
        scope=scope,  # type: ignore[arg-type]
        profiles=profiles,
        max_pages=max_pages,
        max_elements=max_elements,
        color_schemes=color_schemes,
        navigation_timeout=navigation_timeout,
        stabilize_ms=stabilize_ms,
        scroll_steps=scroll_steps,
    )

    _validate_url(url)
    capture_profiles = _resolve_profiles(profiles)

    result = DesignExtraction(
        requested_options=requested,
        effective_options=requested.model_copy(),
    )
    result.source = {"requested_url": url}

    gaps: List[Gap] = []
    observations: List[Observation] = []
    raw_captures: List[dict] = []

    try:
        with PlaywrightDesignAdapter(
            headless=headless,
            navigation_timeout=navigation_timeout,
            stabilize_ms=stabilize_ms,
            challenge_timeout=challenge_timeout,
        ) as adapter:
            browser_version = adapter.browser_version()
            # Milestone B: single-page capture. Site scope is a later milestone;
            # honour max_pages by only capturing the submitted page for now.
            if scope == "site" and max_pages > 1:
                gaps.append(
                    Gap(
                        code="site-scope-not-implemented",
                        message=f"Site scope requested (max_pages={max_pages}) but only single-page capture is available in this version. The submitted page was captured.",
                    )
                )

            for scheme in color_schemes:
                for profile in capture_profiles:
                    prof = profile.model_copy(update={"color_scheme": scheme})
                    try:
                        cap = adapter.capture(
                            url, prof,
                            max_elements=max_elements,
                            scroll_steps=scroll_steps,
                            take_screenshot=include_screenshots,
                        )
                    except DesignCaptureError as exc:
                        gaps.append(
                            Gap(
                                code="capture-failed",
                                message=f"{prof.name}/{scheme}: {exc}",
                            )
                        )
                        continue

                    if cap.blocked:
                        result.status = "blocked"
                        gaps.append(
                            Gap(
                                code="blocked-by-challenge",
                                message=f"{prof.name}/{scheme}: an anti-bot or login interstitial was detected at {cap.final_url or url}. The design was not accepted as the target's.",
                            )
                        )
                        continue

                    result.coverage.screenshots += 1 if cap.screenshot_png else 0
                    if not result.capture.title:
                        result.capture.title = cap.title
                        result.capture.final_url = cap.final_url
                        result.capture.browser_version = cap.browser_version

                    for raw in cap.observations:
                        obs = _obs_from_raw(raw, prof.name, cap.final_url or url)
                        # Attach root vars / media widths (page-level) onto each
                        # observation so the normalizer can read them uniformly.
                        obs.root_vars = cap.root_vars
                        obs.media_widths = cap.media_widths
                        observations.append(obs)

                    raw_captures.append(
                        {
                            "profile": prof.name,
                            "scheme": scheme,
                            "title": cap.title,
                            "final_url": cap.final_url,
                            "count": len(cap.observations),
                            "screenshot": cap.screenshot_png,
                        }
                    )
                    result.coverage.profiles_attempted.append(prof.name)
                    result.coverage.pages_completed = max(result.coverage.pages_completed, 1)
    except DesignCaptureError as exc:
        result.status = "failed"
        result.gaps = gaps + [Gap(code="browser-unavailable", message=str(exc))]
        return result
    except ValueError as exc:
        result.status = "failed"
        result.gaps = gaps + [Gap(code="invalid-url", message=str(exc))]
        return result

    # Coverage + gaps.
    result.coverage.pages_attempted = 1
    result.coverage.profiles_attempted = sorted(set(result.coverage.profiles_attempted))
    result.coverage.profiles_completed = list(result.coverage.profiles_attempted)
    result.coverage.elements_sampled = len(observations)
    result.coverage.elements_visible = len(observations)

    if not observations:
        if result.status != "blocked":
            result.status = "failed"
            gaps.append(Gap(code="no-observations", message="No visible elements could be measured."))
        result.gaps = gaps
        return result

    if result.status != "blocked":
        result.status = "succeeded"

    # Normalize + components.
    normalizer = DesignNormalizer()
    tokens = normalizer.normalize(observations)
    result.observations = observations
    result.tokens = tokens
    result.coverage.tokens_extracted = len(tokens)

    analyzer = ComponentAnalyzer()
    components = analyzer.analyze(observations)
    result.components = components
    result.coverage.components_found = len(components)

    result.confidence = score_confidence(
        {
            "colors": 100 if result.tokens_by_category("color") else 0,
            "typography": 100 if result.tokens_by_category("typography") else 0,
            "spacing": 100 if result.tokens_by_category("spacing") else 0,
            "radii": 100 if result.tokens_by_category("radius") else 0,
            "shadows": 100 if result.tokens_by_category("shadow") else 0,
            "breakpoints": 100 if result.tokens_by_category("breakpoint") else 0,
            "custom-properties": 100 if result.tokens_by_category("custom-property") else 0,
            "components": 100 if components else 0,
        },
        engine="live",
        profiles_completed=len(result.coverage.profiles_completed),
    )

    # Capture context.
    result.capture.requested_url = url
    result.capture.profiles = capture_profiles
    result.capture.locale = capture_profiles[0].locale if capture_profiles else "en-US"
    result.capture.color_scheme = color_schemes[0] if color_schemes else "light"

    # Known, honest gaps for this milestone.
    gaps.append(
        Gap(
            code="states-not-captured",
            message="Only rest state was measured. Hover, focus, active and disabled states are not captured in this version.",
        )
    )
    gaps.append(
        Gap(
            code="recipes-not-generated",
            message="HTML/CSS component recipes and independent verification are not generated in this version.",
        )
    )
    result.gaps = gaps
    return result


async def aextract_design(url: str, **kwargs) -> DesignExtraction:
    """Async wrapper around the sync pipeline.

    The sync Playwright adapter is run in a worker thread so the event loop is
    never blocked. A later milestone moves the pipeline fully async.
    """
    return await asyncio.to_thread(extract_design, url, **kwargs)
