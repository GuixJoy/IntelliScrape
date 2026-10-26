"""Group representative components from raw observations.

Milestone B records representative rest-state components: buttons, links,
form controls, cards, navigation, badges. It does not yet capture hover/focus
state deltas or generate HTML/CSS recipes — those land in a later milestone.
The :class:`Component` model already has fields for them so the shape is stable.

Grouping uses semantic tags and ARIA roles. Class names are treated as hints,
not identity. Repeated near-identical elements collapse into one representative
with a count, so a page of 40 cards yields one card entry, not 40.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

from .models import BBox, Component, Observation

# Semantic tags/roles we treat as components, keyed by reported kind.
_KIND_TAGS = {
    "button": {"button"},
    "link": {"a"},
    "input": {"input", "select", "textarea"},
    "card": set(),  # inferred from repeated bordered/filled containers
    "nav": {"nav"},
    "badge": set(),
}

_ROLE_KIND = {
    "button": "button",
    "link": "link",
    "navigation": "nav",
    "checkbox": "input",
    "textbox": "input",
    "searchbox": "input",
    "combobox": "input",
}


def _kind_for(obs: Observation) -> str:
    if obs.role and obs.role in _ROLE_KIND:
        return _ROLE_KIND[obs.role]
    if obs.tag in ("button",):
        return "button"
    if obs.tag == "a":
        return "link"
    if obs.tag in ("input", "select", "textarea"):
        # Only treat as a control if it is a visible, non-hidden input.
        return "input"
    if obs.tag == "nav":
        return "nav"
    if obs.tag == "header":
        return "header"
    if obs.tag == "footer":
        return "footer"
    # A repeated styled container reads as a card. We flag a bordered box with
    # a radius and a shadow as a card candidate.
    radius = obs.styles.get("borderTopLeftRadius", "")
    shadow = obs.styles.get("boxShadow", "")
    border = obs.styles.get("borderTopWidth", "")
    if shadow and shadow != "none" and radius and radius != "0px":
        return "card"
    if border and border not in ("0px", "") and radius and radius != "0px" and obs.area > 20000:
        return "card"
    return ""


def _signature(obs: Observation) -> tuple:
    """Style signature used to collapse near-identical repeats."""
    return (
        obs.tag,
        obs.role,
        obs.styles.get("fontSize", ""),
        obs.styles.get("fontWeight", ""),
        obs.styles.get("backgroundColor", ""),
        obs.styles.get("color", ""),
        obs.styles.get("borderTopLeftRadius", ""),
    )


class ComponentAnalyzer:
    """Group observations into representative components."""

    MAX_COMPONENTS = 30

    def analyze(self, observations: List[Observation]) -> List[Component]:
        groups: Dict[tuple, List[Observation]] = {}
        for obs in observations:
            kind = _kind_for(obs)
            if not kind:
                continue
            key = (kind, _signature(obs))
            groups.setdefault(key, []).append(obs)

        components: List[Component] = []
        # Sort by count desc then kind for deterministic output.
        ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0]))
        for idx, ((kind, _sig), members) in enumerate(ordered[: self.MAX_COMPONENTS]):
            rep = members[0]
            components.append(
                Component(
                    id=f"cmp-{idx}-{kind}",
                    kind=kind,
                    label=rep.label,
                    profile=rep.profile,
                    count=len(members),
                    bbox=rep.bbox if isinstance(rep.bbox, BBox) else BBox(),
                    styles={
                        k: rep.styles[k]
                        for k in (
                            "fontSize", "fontWeight", "color", "backgroundColor",
                            "borderTopLeftRadius", "paddingTop", "paddingBottom",
                            "boxShadow", "borderTopWidth", "borderTopColor",
                        )
                        if k in rep.styles
                    },
                )
            )
        return components
