"""design.json exporter.

Serializes the full versioned result model. This carries everything the
concise DESIGN.md omits: raw observations, evidence links, coverage, gaps and
artifact manifests. Ordering is deterministic so identical captures diff well.
"""

from __future__ import annotations

import json

from ..models import DesignExtraction


def render_design_json(result: DesignExtraction, *, indent: int = 2) -> str:
    """Render the result as a stable, pretty-printed JSON string."""
    # model_dump gives us the full versioned shape; observations are kept but
    # can be large, so they are included verbatim for full evidence fidelity.
    data = result.model_dump(mode="json", exclude={"screenshots"})
    return json.dumps(data, indent=indent, sort_keys=False, ensure_ascii=False)
