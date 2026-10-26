"""Design Extract — free, open-source URL-to-DESIGN.md extraction.

Measures a **live rendered page** with Playwright and produces a reusable
design reference: tokens, components, coverage and explicit gaps, exported as
``DESIGN.md``, ``design.json``, ``tokens.css`` and a sanitized ``preview.html``.

No LLM or API key is required. Playwright must be installed and a Chromium
browser present (``pip install playwright && playwright install chromium``).

Pipeline
--------
::

    from intelliscrape import extract_design

    result = extract_design("https://example.com", profiles=["desktop", "mobile"])
    result.save("./example-design")     # writes DESIGN.md, design.json, tokens.css, preview.html
    print(result.design_md)

Async form::

    from intelliscrape import aextract_design
    result = await aextract_design("https://example.com")

Layout
------
- ``models``   versioned result/options/observation/gap types (the contract)
- ``browser``  managed live-page adapter (Playwright)
- ``normalize`` raw observations -> deterministic tokens
- ``components`` representative component grouping
- ``service``  orchestration + public entry points
- ``exporters`` DESIGN.md / JSON / CSS / preview renderers
- ``static``   no-browser CSS-regex fallback (dependency-free)
- ``security`` URL and resource policy

The hosted FastAPI worker should call :func:`extract_design` / the service
layer and read only the serialized model — presentation never re-infers tokens.
"""

from __future__ import annotations

from .models import (
    CaptureProfile,
    Component,
    Coverage,
    DesignExtraction,
    ExtractionOptions,
    Gap,
    Observation,
    Token,
)
from .service import aextract_design, extract_design
from .browser import DesignCaptureError, PlaywrightDesignAdapter
from .normalize import DesignNormalizer

# No-browser fallback (static CSS-regex extractor), kept for lightweight use
# and for the standalone web backend, which vendors it.
from .static import DesignExtractor, DesignReport, collect_css, stylesheet_hrefs

__all__ = [
    # primary entry points
    "extract_design",
    "aextract_design",
    # result model
    "DesignExtraction",
    "ExtractionOptions",
    "CaptureProfile",
    "Observation",
    "Token",
    "Component",
    "Coverage",
    "Gap",
    # engine pieces
    "PlaywrightDesignAdapter",
    "DesignCaptureError",
    "DesignNormalizer",
    # static fallback
    "DesignExtractor",
    "DesignReport",
    "collect_css",
    "stylesheet_hrefs",
]
