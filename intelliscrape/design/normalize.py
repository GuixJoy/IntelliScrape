"""Normalize raw observations into deterministic design tokens.

Three layers stay strictly separated, per the extraction contract:

1. **Observed** — the raw computed values captured by the collector.
2. **Normalized** — equivalent values deduplicated without changing meaning.
3. **Inferred** — semantic roles and named scales.

Nothing here invents values. A role is only *suggested*, always tagged
``role_status="inferred"`` with a human-readable reason. Colors are ranked by
bounded visual prominence (sqrt of element area) so one full-screen background
cannot dominate the whole palette. Browser/UA default colors and generic font
names are kept out of the "site" palette.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from .models import Observation, Token

# ---------------------------------------------------------------------------
# Value parsing helpers
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_RGB_RE = re.compile(r"rgba?\(\s*([^)]+)\)")
_HSL_RE = re.compile(r"hsla?\(\s*([^)]+)\)")
_PX_RE = re.compile(r"^-?[\d.]+px$")

# Non-colors and fully transparent values. Black and white are NOT here: a
# computed `rgb(0, 0, 0)` is a real design token on most sites (ink/on-dark),
# and dropping it silently removed legitimate palette entries.
_DEFAULT_COLORS = {"transparent", "none", "currentcolor"}
# Generic CSS font keywords that denote a fallback category, not a real typeface.
# A site can legitimately declare Arial/Helvetica/etc., so those are NOT here —
# only the generic keywords the browser resolves to an installed family.
_DEFAULT_FONTS = {
    "sans-serif", "serif", "monospace", "system-ui", "-apple-system",
    "blinkmacsystemfont", "ui-sans-serif", "ui-serif", "ui-monospace",
    "cursive", "fantasy", "ui-rounded", "math", "emoji",
}


def _hex_to_css(hexv: str) -> str:
    h = hexv.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    return "#" + h.lower()


def parse_color(value: str) -> Optional[str]:
    """Return a normalized CSS color string, or None if not a color.

    Alpha and wide-gamut syntax are preserved (never flattened to opaque hex).
    Gradients, var() and url() return None so they are tracked elsewhere.
    """
    if not value:
        return None
    v = value.strip().lower()
    if v in _DEFAULT_COLORS:
        return None
    m = _HEX_RE.search(v)
    if m:
        return _hex_to_css(m.group(0))
    m = _RGB_RE.search(v)
    if m:
        norm = _norm_rgb(m.group(1))
        return None if not norm or _is_transparent(norm) else norm
    m = _HSL_RE.search(v)
    if m:
        norm = _norm_hsl(m.group(1))
        return None if not norm or _is_transparent(norm) else norm
    return None


def _is_transparent(norm: str) -> bool:
    m = _RGB_RE.match(norm)
    if not m:
        return False
    parts = _split_args(m.group(1))
    if len(parts) < 4:
        return False
    try:
        return float(parts[3].rstrip("%")) <= 0.001
    except ValueError:
        return False


def _split_args(inner: str) -> List[str]:
    return [p.strip() for p in re.split(r"[,\s/]+", inner) if p.strip()]


def _norm_rgb(inner: str) -> Optional[str]:
    parts = _split_args(inner)
    if len(parts) < 3:
        return None
    if len(parts) >= 4:
        return f"rgba({', '.join(parts[:3])}, {parts[3]})"
    return f"rgb({', '.join(parts[:3])})"


def _norm_hsl(inner: str) -> Optional[str]:
    parts = _split_args(inner)
    if len(parts) < 3:
        return None
    if len(parts) >= 4:
        return f"hsla({', '.join(parts[:4])})"
    return f"hsl({', '.join(parts[:3])})"


def first_font_family(stack: str) -> Optional[str]:
    """First real family in a font-family stack, dropping generic fallbacks."""
    if not stack:
        return None
    generics = {f.replace(" ", "") for f in _DEFAULT_FONTS}
    for raw in stack.split(","):
        name = raw.strip().strip("'\"").strip()
        if not name:
            continue
        if name.lower().replace(" ", "") in generics:
            continue
        return name
    return None


def px_to_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    v = value.strip()
    if _PX_RE.match(v):
        try:
            return round(float(v[:-2]), 3)
        except ValueError:
            return None
    return None


def _rgb_channels(color: str) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[float]]:
    m = _RGB_RE.match(color)
    if m:
        parts = _split_args(m.group(1))
        try:
            r = int(float(parts[0]))
            g = int(float(parts[1]))
            b = int(float(parts[2]))
            a = None
            if len(parts) >= 4:
                a_s = parts[3]
                a = float(a_s.rstrip("%")) / (100 if a_s.endswith("%") else 1)
            return r, g, b, a
        except (ValueError, IndexError):
            return None, None, None, None
    h = _HEX_RE.match(color)
    if h:
        hv = h.group(1)
        if len(hv) in (3, 4):
            hv = "".join(c * 2 for c in hv)
        try:
            r = int(hv[0:2], 16)
            g = int(hv[2:4], 16)
            b = int(hv[4:6], 16)
            a = int(hv[6:8], 16) / 255 if len(hv) == 8 else None
            return r, g, b, a
        except ValueError:
            return None, None, None, None
    return None, None, None, None


def _hsl_channels(color: str) -> Optional[Tuple[float, float, float, Optional[float]]]:
    """Return (hue 0-360, saturation 0-1, lightness 0-1, alpha).

    Saturation is HSV (chroma / max), not HSL: HSL saturation explodes for
    near-white values (``#fffefb`` reads as fully saturated), which mislabels
    warm off-whites as brand tints.
    """
    r, g, b, a = _rgb_channels(color)
    if r is None:
        return None
    rn, gn, bn = r / 255, g / 255, b / 255
    mx, mn = max(rn, gn, bn), min(rn, gn, bn)
    lightness = (mx + mn) / 2
    delta = mx - mn
    if delta == 0:
        return 0.0, 0.0, lightness, a
    saturation = delta / mx if mx else 0.0
    if mx == rn:
        hue = ((gn - bn) / delta) % 6
    elif mx == gn:
        hue = (bn - rn) / delta + 2
    else:
        hue = (rn - gn) / delta + 4
    return hue * 60, saturation, lightness, a


def _hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
    c = (1 - abs(2 * l - 1)) * s
    hp = (h % 360) / 60
    x = c * (1 - abs(hp % 2 - 1))
    r1, g1, b1 = (
        (c, x, 0) if hp < 1 else
        (x, c, 0) if hp < 2 else
        (0, c, x) if hp < 3 else
        (0, x, c) if hp < 4 else
        (x, 0, c) if hp < 5 else
        (c, 0, x)
    )
    m = l - c / 2
    return round((r1 + m) * 255), round((g1 + m) * 255), round((b1 + m) * 255)


def canonical_color(value: str) -> Optional[str]:
    """Collapse any CSS color to lowercase hex, 8 digits when translucent.

    ``#111``, ``#111111`` and ``rgb(17, 17, 17)`` all become ``#111111`` so a
    palette counts one entry per perceived color. Fully transparent values are
    dropped rather than listed as tokens.
    """
    base = parse_color(value)
    if not base:
        return None
    if base.startswith("hsl"):
        m = _HSL_RE.match(base)
        parts = _split_args(m.group(1)) if m else []
        if len(parts) < 3:
            return None
        try:
            hue = float(parts[0].rstrip("deg"))
            sat = float(parts[1].rstrip("%")) / 100
            light = float(parts[2].rstrip("%")) / 100
            alpha = float(parts[3].rstrip("%")) / (100 if parts[3].endswith("%") else 1) if len(parts) >= 4 else None
        except ValueError:
            return None
        r, g, b = _hsl_to_rgb(hue, sat, light)
        a = alpha
    else:
        r, g, b, a = _rgb_channels(base)
    if r is None:
        return None
    if a is not None and a < 0.05:
        return None
    if a is None or a >= 0.999:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"#{r:02x}{g:02x}{b:02x}{max(0, min(255, round(a * 255))):02x}"


_ROLE_REASONS = {
    "primary": "Most prominent saturated color; likely the brand/action color (inferred from prominence, not verified against components).",
    "primary-tint": "Lighter shade of the primary hue; likely a tint/hover token.",
    "success": "Saturated green; conventional success color.",
    "warning": "Saturated amber; conventional warning color.",
    "danger": "Saturated red; conventional error/danger color.",
    "ink": "Most prominent near-black neutral; likely the primary text color.",
    "ink-black": "Near-black neutral; likely the darkest text, icon or border color.",
    "ink-soft": "Dark neutral; likely secondary text or a dark surface.",
    "muted": "Mid-tone neutral; likely secondary text, icon or border color.",
    "hairline": "Light neutral; likely a hairline border or divider.",
    "surface": "Most prominent near-white neutral; likely the page/card background.",
    "surface-muted": "Light neutral just off the main surface; likely a raised or muted background.",
    "surface-dark": "Dark neutral surface token.",
}


def _hue_close(a: float, b: float, tolerance: float = 14.0) -> bool:
    delta = abs(a - b) % 360
    return min(delta, 360 - delta) <= tolerance


def assign_color_roles(items: List[Tuple[str, float]]) -> Dict[str, Tuple[str, str]]:
    """Name colors by likely role, deterministically.

    ``items`` is ``[(color, prominence_weight), ...]`` ordered by prominence.
    Returns ``{color: (role, reason)}``. Every role is an inference: callers
    must keep ``role_status="inferred"`` and surface the reason.
    """
    stats = {}
    for color, _weight in items:
        hsl = _hsl_channels(color)
        if hsl:
            stats[color] = hsl

    used = set()
    roles: Dict[str, Tuple[str, str]] = {}

    def pick(role: str, predicate) -> Optional[str]:
        for color, _w in items:
            if color in used or color not in stats:
                continue
            h, s, l, a = stats[color]
            if a is not None and a < 0.9:
                continue
            if predicate(h, s, l):
                roles[color] = (role, _ROLE_REASONS[role])
                used.add(color)
                return color
        return None

    # Translucent neutrals are scrims/overlays, not solid palette entries.
    overlay_i = overlay_light_i = 0
    for color, _w in items:
        if color in used or color not in stats:
            continue
        _h, s, l, a = stats[color]
        if a is not None and a < 0.9 and s < 0.2:
            if l < 0.5:
                overlay_i += 1
                role = "overlay" if overlay_i == 1 else f"overlay-{overlay_i}"
            else:
                overlay_light_i += 1
                role = "overlay-light" if overlay_light_i == 1 else f"overlay-light-{overlay_light_i}"
            roles[color] = (
                role,
                "Translucent neutral; likely a scrim, overlay or disabled state.",
            )
            used.add(color)

    primary = pick("primary", lambda h, s, l: s >= 0.3 and 0.2 <= l <= 0.72)
    primary_hue = stats[primary][0] if primary else None

    # Brand tints: lighter, still saturated versions of the primary hue.
    if primary:
        _ph, _ps, pl, _pa = stats[primary]
        tint_i = 0
        for color, _w in items:
            if color in used or color not in stats:
                continue
            h, s, l, a = stats[color]
            if a is not None and a < 0.9:
                continue
            if s >= 0.25 and pl + 0.05 < l <= 0.95 and _hue_close(h, _ph):
                tint_i += 1
                roles[color] = (
                    "primary-tint" if tint_i == 1 else f"primary-tint-{tint_i}",
                    _ROLE_REASONS["primary-tint"],
                )
                used.add(color)

    def away_from_brand(h: float) -> bool:
        return primary_hue is None or not _hue_close(h, primary_hue, 25)

    pick("danger", lambda h, s, l: s >= 0.4 and (h <= 20 or h >= 340) and 0.2 <= l <= 0.65 and away_from_brand(h))
    pick("warning", lambda h, s, l: s >= 0.4 and 30 <= h <= 70 and 0.25 <= l <= 0.7 and away_from_brand(h))
    pick("success", lambda h, s, l: s >= 0.25 and 90 <= h <= 165 and 0.15 <= l <= 0.65 and away_from_brand(h))
    pick("ink", lambda h, s, l: s < 0.15 and l <= 0.15)
    pick("surface", lambda h, s, l: s < 0.15 and l >= 0.97)
    pick("ink-black", lambda h, s, l: s < 0.15 and l <= 0.05)
    pick("ink-soft", lambda h, s, l: s < 0.15 and 0.15 < l <= 0.32)
    pick("surface-muted", lambda h, s, l: s < 0.15 and 0.93 <= l < 1.0)
    pick("hairline", lambda h, s, l: s < 0.15 and 0.74 <= l < 0.93)
    pick("muted", lambda h, s, l: s < 0.15 and 0.4 <= l < 0.74)
    pick("surface-dark", lambda h, s, l: s < 0.2 and 0.08 < l <= 0.2)

    neutral_i = accent_i = 0
    for color, _w in items:
        if color in used or color not in stats:
            continue
        _h, s, _l, _a = stats[color]
        if s < 0.15:
            neutral_i += 1
            roles[color] = (
                f"neutral-{neutral_i}",
                "Neutral color without a stronger inferred role.",
            )
        else:
            accent_i += 1
            roles[color] = (
                f"accent-{accent_i}",
                "Saturated color without a stronger inferred role.",
            )
    return roles





def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:24]


def _dedup(items: Iterable[str]) -> Counter:
    return Counter(i for i in items if i)


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

class DesignNormalizer:
    """Turn Observations into a deterministic, deduped token list.

    Output ordering is stable for a given input, so re-running an identical
    capture yields a meaningful diff.
    """

    MAX_PER_CATEGORY = 40

    def normalize(self, observations: List[Observation]) -> List[Token]:
        return (
            self._collect_colors(observations)
            + self._collect_typography(observations)
            + self._collect_spacing(observations)
            + self._collect_radii(observations)
            + self._collect_shadows(observations)
            + self._collect_breakpoints(observations)
            + self._collect_custom_properties(observations)
        )

    # -- colors --------------------------------------------------------------
    def _collect_colors(self, obs: List[Observation]) -> List[Token]:
        # Prominence = sqrt(area) so one giant background does not dominate.
        weight: Counter = Counter()
        raws: Dict[str, set] = defaultdict(set)
        evidence: Dict[str, List[str]] = defaultdict(list)
        contexts: Dict[str, set] = defaultdict(set)

        for o in obs:
            area_w = (min(o.area, 1_000_000) ** 0.5) if o.area else 1.0
            for prop in ("color", "backgroundColor", "borderTopColor", "fill", "stroke"):
                val = o.styles.get(prop)
                if not val:
                    continue
                norm = parse_color(val)
                if not norm:
                    continue
                weight[norm] += area_w
                raws[norm].add(val.strip())
                if len(evidence[norm]) < 8:
                    evidence[norm].append(o.id)
                contexts[norm].add(f"{o.profile}:rest")

        tokens: List[Token] = []
        ranked = weight.most_common(self.MAX_PER_CATEGORY)
        roles = assign_color_roles([(color, w) for color, w in ranked])
        for idx, (color, _w) in enumerate(ranked):
            role, reason = roles.get(color, ("", ""))
            tokens.append(
                Token(
                    id=f"color-{idx}-{_slug(color)}",
                    category="color",
                    value=color,
                    raw_values=sorted(raws[color]),
                    observed=True,
                    frequency=len(evidence[color]),
                    role=role,
                    role_status="inferred" if role else "observed",
                    role_reason=reason,
                    evidence_ids=evidence[color],
                    contexts=sorted(contexts[color]),
                )
            )
        return tokens


    # -- typography ----------------------------------------------------------
    def _collect_typography(self, obs: List[Observation]) -> List[Token]:
        families: Counter = Counter()
        fam_ev: Dict[str, List[str]] = defaultdict(list)
        sizes: Counter = Counter()
        weights: Counter = Counter()
        line_heights: Counter = Counter()
        tracking: Counter = Counter()

        for o in obs:
            fam = o.styles.get("fontFamily")
            if fam:
                first = first_font_family(fam)
                if first:
                    families[first] += 1
                    if len(fam_ev[first]) < 6:
                        fam_ev[first].append(o.id)
            for store, key in (
                (sizes, "fontSize"),
                (weights, "fontWeight"),
                (line_heights, "lineHeight"),
                (tracking, "letterSpacing"),
            ):
                v = o.styles.get(key)
                if v and v not in ("normal", "0px", "0", "400px"):
                    store[v] += 1

        tokens: List[Token] = []
        for idx, (fam, n) in enumerate(families.most_common(self.MAX_PER_CATEGORY)):
            tokens.append(
                Token(
                    id=f"font-{idx}-{_slug(fam)}",
                    category="typography",
                    value=fam,
                    observed=True,
                    frequency=n,
                    role="font-family",
                    role_status="observed",
                    evidence_ids=fam_ev[fam],
                )
            )
        for idx, (size, n) in enumerate(sizes.most_common(20)):
            tokens.append(Token(id=f"fontsize-{idx}-{_slug(size)}", category="typography", value=size, observed=True, frequency=n, role="font-size", role_status="observed"))
        for idx, (w, n) in enumerate(weights.most_common(12)):
            tokens.append(Token(id=f"fontweight-{idx}-{_slug(w)}", category="typography", value=w, observed=True, frequency=n, role="font-weight", role_status="observed"))
        for idx, (lh, n) in enumerate(line_heights.most_common(12)):
            tokens.append(Token(id=f"lineheight-{idx}-{_slug(lh)}", category="typography", value=lh, observed=True, frequency=n, role="line-height", role_status="observed"))
        for idx, (t, n) in enumerate(tracking.most_common(8)):
            tokens.append(Token(id=f"tracking-{idx}-{_slug(t)}", category="typography", value=t, observed=True, frequency=n, role="letter-spacing", role_status="observed"))
        return tokens

    # -- spacing -------------------------------------------------------------
    def _collect_spacing(self, obs: List[Observation]) -> List[Token]:
        vals: Counter = Counter()
        ev: Dict[str, List[str]] = defaultdict(list)
        for o in obs:
            for prop in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "gap"):
                f = px_to_float(o.styles.get(prop))
                if f is not None and f > 0:
                    key = f"{f:g}px"
                    vals[key] += 1
                    if len(ev[key]) < 5:
                        ev[key].append(o.id)
        return [
            Token(id=f"spacing-{i}-{_slug(v)}", category="spacing", value=v, observed=True, frequency=n, role="spacing-step", role_status="observed", evidence_ids=ev[v])
            for i, (v, n) in enumerate(vals.most_common(self.MAX_PER_CATEGORY))
        ]

    # -- radii ---------------------------------------------------------------
    def _collect_radii(self, obs: List[Observation]) -> List[Token]:
        vals: Counter = Counter()
        ev: Dict[str, List[str]] = defaultdict(list)
        for o in obs:
            corners = [
                o.styles.get("borderTopLeftRadius"),
                o.styles.get("borderTopRightRadius"),
                o.styles.get("borderBottomRightRadius"),
                o.styles.get("borderBottomLeftRadius"),
            ]
            corners = [c for c in corners if c]
            if not corners:
                continue
            uniq = set(corners)
            # Preserve asymmetric corners; collapse only when all match.
            key = corners[0] if len(uniq) == 1 else " ".join(corners)
            vals[key] += 1
            if len(ev[key]) < 5:
                ev[key].append(o.id)
        return [
            Token(id=f"radius-{i}-{_slug(v)}", category="radius", value=v, observed=True, frequency=n, role="radius", role_status="observed", evidence_ids=ev[v])
            for i, (v, n) in enumerate(vals.most_common(self.MAX_PER_CATEGORY))
        ]

    # -- shadows -------------------------------------------------------------
    def _collect_shadows(self, obs: List[Observation]) -> List[Token]:
        vals: Counter = Counter()
        ev: Dict[str, List[str]] = defaultdict(list)
        for o in obs:
            v = o.styles.get("boxShadow")
            if v and v != "none":
                vals[v] += 1
                if len(ev[v]) < 5:
                    ev[v].append(o.id)
        return [
            Token(id=f"shadow-{i}-{_slug(v)}", category="shadow", value=v, observed=True, frequency=n, role="elevation", role_status="observed", evidence_ids=ev[v])
            for i, (v, n) in enumerate(vals.most_common(12))
        ]

    # -- breakpoints ---------------------------------------------------------
    def _collect_breakpoints(self, obs: List[Observation]) -> List[Token]:
        vals: Counter = Counter()
        for o in obs:
            for mw in o.media_widths:
                m = re.search(r"([\d.]+(?:px|rem|em))", mw)
                if m:
                    vals[m.group(1)] += 1
        return [
            Token(
                id=f"breakpoint-{i}-{_slug(v)}",
                category="breakpoint",
                value=v,
                observed=True,
                frequency=n,
                role="breakpoint",
                role_status="observed",
                role_reason="Declared @media width condition (declared evidence, not an observed layout change).",
            )
            for i, (v, n) in enumerate(vals.most_common(20))
        ]

    # -- custom properties ---------------------------------------------------
    def _collect_custom_properties(self, obs: List[Observation]) -> List[Token]:
        seen: Dict[str, str] = {}
        for o in obs:
            for k, v in o.root_vars.items():
                seen.setdefault(k, v)
        return [
            Token(
                id=f"var{i}-{_slug(name)}",
                category="custom-property",
                value=val,
                raw_values=[val],
                observed=True,
                role=name.lstrip("-"),
                role_status="observed",
                role_reason="Declared :root custom property (a token candidate, not proof of visible use).",
            )
            for i, (name, val) in enumerate(sorted(seen.items())[:60])
        ]
