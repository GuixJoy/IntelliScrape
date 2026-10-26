"""Versioned result, options, observation and gap types for Design Extract.

This module is the internal source of truth for a design extraction. The
serialized JSON (``design.json``) mirrors these models; ``schema_version`` is
IntelliScrape's own result-model version and is tracked separately from the
DESIGN.md specification version rendered by the exporters.

Nothing here talks to a browser or does inference — it is pure data so the
hosted worker, the CLI and the library all share one contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Bump when the serialized shape of these models changes incompatibly.
SCHEMA_VERSION = "1.0"

# The DESIGN.md spec revision we render toward (google-labs-code/design.md alpha).
DESIGNMD_SPEC_VERSION = "alpha"

# Extraction algorithm version, independent of SCHEMA_VERSION.
EXTRACTOR_VERSION = "1.0.0"


class CaptureProfile(BaseModel):
    """A pinned rendering profile so two captures are comparable."""

    name: Literal["desktop", "mobile"] = "desktop"
    width: int = 1440
    height: int = 900
    device_scale_factor: float = 1.0
    color_scheme: Literal["light", "dark"] = "light"
    locale: str = "en-US"

    @classmethod
    def desktop(cls) -> "CaptureProfile":
        return cls(name="desktop", width=1440, height=900)

    @classmethod
    def mobile(cls) -> "CaptureProfile":
        return cls(name="mobile", width=390, height=844, device_scale_factor=1.0)


#: Default profiles used when a caller does not specify any.
DEFAULT_PROFILES: List[str] = ["desktop", "mobile"]


class BBox(BaseModel):
    """Element bounding box in CSS pixels relative to the viewport."""

    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


class Observation(BaseModel):
    """A single measured element. This is the raw-evidence layer.

    ``styles`` holds resolved ``getComputedStyle`` longhand values. Keep this
    faithful: normalization and role inference happen downstream so a bug there
    never corrupts the underlying evidence.
    """

    id: str
    profile: str
    page_url: str
    tag: str
    role: str = ""
    label: str = ""  # sanitized, truncated text or accessible name
    bbox: BBox = Field(default_factory=BBox)
    area: float = 0.0
    visible: bool = True
    styles: Dict[str, str] = Field(default_factory=dict)
    # Declared custom properties on :root for this page (token candidates).
    root_vars: Dict[str, str] = Field(default_factory=dict)
    # Declared @media (min/max-width) conditions seen in accessible stylesheets.
    media_widths: List[str] = Field(default_factory=list)


TokenStatus = Literal["observed", "inferred"]
VerificationStatus = Literal["not_requested", "verified", "mismatch", "unavailable"]


class Token(BaseModel):
    """A normalized design token with a link back to its evidence.

    Three layers stay distinct per the brief: ``value`` is normalized, the
    linked observation ids are observed, and ``role``/``role_reason`` are the
    inferred layer. ``role_status`` is always "inferred" for heuristically
    assigned roles — we never claim a measured role.
    """

    id: str
    category: str  # color | typography | spacing | radius | shadow | breakpoint | custom-property
    value: str
    raw_values: List[str] = Field(default_factory=list)
    observed: bool = True
    frequency: int = 0
    role: str = ""
    role_status: TokenStatus = "observed"
    role_reason: str = ""
    evidence_ids: List[str] = Field(default_factory=list)
    contexts: List[str] = Field(default_factory=list)
    verification_status: VerificationStatus = "not_requested"


class Component(BaseModel):
    """A grouped representative element.

    Milestone B records the representative and its measured rest-state styles.
    Variants, hover/focus state deltas, HTML/CSS recipes and verification land
    in a later milestone; the fields exist now so the model does not change.
    """

    id: str
    kind: str  # button | link | input | card | nav | badge | header | footer
    label: str = ""
    profile: str = ""
    count: int = 1
    bbox: BBox = Field(default_factory=BBox)
    styles: Dict[str, str] = Field(default_factory=dict)
    recipe_html: str = ""  # empty until recipes ship
    verification_status: VerificationStatus = "not_requested"


class Gap(BaseModel):
    """An explicit, machine-coded limitation. Never silently swallow these."""

    code: str
    message: str
    affected_ids: List[str] = Field(default_factory=list)


class Coverage(BaseModel):
    """How much was actually measured — counts, not an invented percentage."""

    pages_attempted: int = 0
    pages_completed: int = 0
    profiles_attempted: List[str] = Field(default_factory=list)
    profiles_completed: List[str] = Field(default_factory=list)
    elements_sampled: int = 0
    elements_visible: int = 0
    tokens_extracted: int = 0
    components_found: int = 0
    states_probed: int = 0  # milestone B: rest only
    screenshots: int = 0


class CaptureContext(BaseModel):
    """Metadata describing how a page was captured."""

    requested_url: str = ""
    final_url: str = ""
    title: str = ""
    captured_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    browser: str = ""
    browser_version: str = ""
    locale: str = "en-US"
    color_scheme: str = "light"
    profiles: List[CaptureProfile] = Field(default_factory=list)


class ExtractionOptions(BaseModel):
    """Effective options actually used for a run (requested options may differ
    when a hosted worker clamps them; both are reported)."""

    scope: Literal["page", "site"] = "page"
    profiles: List[str] = Field(default_factory=lambda: list(DEFAULT_PROFILES))
    max_pages: int = 1
    max_elements: int = 400
    color_schemes: List[str] = Field(default_factory=lambda: ["light"])
    navigation_timeout: float = 30.0
    stabilize_ms: int = 800
    scroll_steps: int = 6
    verify_components: bool = False  # milestone B: schema-ready, not implemented


class DesignExtraction(BaseModel):
    """Top-level result of a design extraction."""

    schema_version: str = SCHEMA_VERSION
    extractor_version: str = EXTRACTOR_VERSION
    designmd_spec_version: str = DESIGNMD_SPEC_VERSION
    status: Literal["succeeded", "partial", "blocked", "failed"] = "succeeded"
    source: Dict[str, Any] = Field(default_factory=dict)
    capture: CaptureContext = Field(default_factory=CaptureContext)
    requested_options: ExtractionOptions = Field(default_factory=ExtractionOptions)
    effective_options: ExtractionOptions = Field(default_factory=ExtractionOptions)
    observations: List[Observation] = Field(default_factory=list)
    tokens: List[Token] = Field(default_factory=list)
    components: List[Component] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)
    # Evidence-based score; see intelliscrape.design.confidence.
    confidence: Dict[str, Any] = Field(default_factory=dict)
    gaps: List[Gap] = Field(default_factory=list)
    # PNG bytes keyed by "profile:color_scheme". Excluded from JSON (not
    # serializable); written to disk by save() and surfaced in the manifest.
    screenshots: Dict[str, bytes] = Field(default_factory=dict)
    # Populated by exporters / save(); maps artifact name -> relative path.
    artifacts: Dict[str, str] = Field(default_factory=dict)

    # -- convenience ---------------------------------------------------------
    def tokens_by_category(self, category: str) -> List[Token]:
        return [t for t in self.tokens if t.category == category]

    @property
    def design_md(self) -> str:
        """The rendered DESIGN.md string (computed on demand)."""
        from .exporters.design_md import render_design_md

        return render_design_md(self)

    @property
    def tokens_css(self) -> str:
        from .exporters.tokens_css import render_tokens_css

        return render_tokens_css(self)

    @property
    def preview_html(self) -> str:
        from .exporters.preview_html import render_preview_html

        return render_preview_html(self)

    def to_json(self, *, indent: int = 2) -> str:
        from .exporters.design_json import render_design_json

        return render_design_json(self, indent=indent)

    def save(self, out_dir: str, *, screenshots: bool = True) -> Dict[str, str]:
        """Write all artifacts to *out_dir*; returns a name→path manifest.

        Writes DESIGN.md, design.json, tokens.css and preview.html, plus any
        capture screenshots. Existing user files are not overwritten silently:
        if the directory already contains a DESIGN.md, this raises unless the
        caller pre-cleans it (the CLI handles the overwrite prompt).
        """
        from pathlib import Path

        directory = Path(out_dir)
        directory.mkdir(parents=True, exist_ok=True)
        manifest: Dict[str, str] = {}

        # Screenshots captured during the run (profile:name -> png bytes).
        if screenshots and self.screenshots:
            shot_dir = directory / "screenshots"
            shot_dir.mkdir(exist_ok=True)
            for name, png in self.screenshots.items():
                safe = "".join(c for c in name if c.isalnum() or c in "-_") or "shot"
                path = shot_dir / f"{safe}.png"
                path.write_bytes(png)
                manifest[f"screenshots/{safe}.png"] = str(path)

        (directory / "DESIGN.md").write_text(self.design_md, encoding="utf-8")
        manifest["DESIGN.md"] = str(directory / "DESIGN.md")

        (directory / "design.json").write_text(self.to_json(), encoding="utf-8")
        manifest["design.json"] = str(directory / "design.json")

        (directory / "tokens.css").write_text(self.tokens_css, encoding="utf-8")
        manifest["tokens.css"] = str(directory / "tokens.css")

        (directory / "preview.html").write_text(self.preview_html, encoding="utf-8")
        manifest["preview.html"] = str(directory / "preview.html")

        self.artifacts = manifest
        return manifest

    @property
    def stats(self) -> Dict[str, int]:
        """Compact counts, mirroring the shape the web UI already consumes."""
        typo = self.tokens_by_category("typography")
        return {
            "colors": len(self.tokens_by_category("color")),
            "fonts": len([t for t in typo if t.role == "font-family"]),
            "font_sizes": len([t for t in typo if t.role == "font-size"]),
            "spacing": len(self.tokens_by_category("spacing")),
            "radii": len(self.tokens_by_category("radius")),
            "shadows": len(self.tokens_by_category("shadow")),
            "breakpoints": len(self.tokens_by_category("breakpoint")),
            "css_variables": len(self.tokens_by_category("custom-property")),
        }
