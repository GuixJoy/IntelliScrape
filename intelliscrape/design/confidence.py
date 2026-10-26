"""Evidence-based confidence for a design extraction.

The score answers one question: how much of the design system was *measured*
rather than guessed? It is deterministic and derived from the payload, never
from an LLM:

- section quality: share of a category's values that resolved to canonical
  CSS (live capture is 100% by construction, static reads depend on var()
  resolution),
- category coverage: how many of the eight design categories have evidence,
- capture quality: live rendering plus both viewport profiles score higher
  than a static HTML/CSS read.

The formula is exposed with the score so a UI can explain it.
"""

from __future__ import annotations

from typing import Dict, Mapping

SECTIONS = (
    "colors",
    "typography",
    "spacing",
    "radii",
    "shadows",
    "breakpoints",
    "custom-properties",
    "components",
)

SECTION_LABELS = {
    "colors": "colors",
    "typography": "typography",
    "spacing": "spacing",
    "radii": "radii",
    "shadows": "shadows",
    "breakpoints": "breakpoints",
    "custom-properties": "CSS variables",
    "components": "components",
}

BASIS = (
    "Share of the eight design categories with evidence, weighted by how many "
    "values resolved cleanly, and by capture depth (live rendering + profiles). "
    "Not a similarity score against the original page."
)


def score(
    sections: Mapping[str, int],
    *,
    engine: str,
    profiles_completed: int = 0,
) -> Dict[str, object]:
    """Return ``{overall, coverage, sections, basis}`` for the web payload."""
    values = {name: max(0, min(100, int(sections.get(name, 0)))) for name in SECTIONS}
    measured = [v for v in values.values() if v > 0]
    coverage = len(measured) / len(SECTIONS)
    quality = (sum(measured) / len(measured) / 100) if measured else 0.0
    if engine == "live":
        capture = 0.85 + 0.15 * min(max(profiles_completed, 0), 2) / 2
    else:
        capture = 0.80
    return {
        "overall": round(100 * coverage * quality * capture),
        "coverage": round(coverage * 100),
        "sections": values,
        "basis": BASIS,
    }
