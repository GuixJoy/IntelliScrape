"""Tests for the live design-extraction engine (Milestone B).

Runs against a local fixture (file:// URL), so no network and no LLM/API key
are involved. Chromium must be installed (playwright install chromium); if it
is not, the engine-dependent tests skip rather than fail.
"""

import json
import pathlib

import pytest

from intelliscrape.design import extract_design
from intelliscrape.design.models import DesignExtraction
from intelliscrape.design.normalize import DesignNormalizer, parse_color, first_font_family
from intelliscrape.design.components import ComponentAnalyzer
from intelliscrape.design.security import validate_target_url, is_safe_color

FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "design" / "fixture.html").as_uri()


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        return True
    except Exception:
        return False


needs_browser = pytest.mark.skipif(
    not _chromium_available(),
    reason="Chromium not installed (playwright install chromium)",
)


# ---------------------------------------------------------------------------
# Pure-logic tests (no browser)
# ---------------------------------------------------------------------------

def test_parse_color_normalizes_and_rejects():
    assert parse_color("#2864DC") == "#2864dc"
    assert parse_color("RGB(40, 100, 220)") == "rgb(40, 100, 220)"
    assert parse_color("rgba(40,100,220,0.5)") == "rgba(40, 100, 220, 0.5)"
    assert parse_color("hsl(210, 70%, 50%)") == "hsl(210, 70%, 50%)"
    # Black/white are real tokens (ink/on-dark); fully transparent is not.
    assert parse_color("rgb(0, 0, 0)") == "rgb(0, 0, 0)"
    assert parse_color("rgb(255, 255, 255)") == "rgb(255, 255, 255)"
    assert parse_color("rgba(0, 0, 0, 0)") is None
    assert parse_color("transparent") is None
    assert parse_color("var(--brand)") is None
    assert parse_color("linear-gradient(red, blue)") is None
    assert parse_color("") is None


def test_first_font_family_drops_generic_fallbacks():
    assert first_font_family('"Inter", system-ui, sans-serif') == "Inter"
    assert first_font_family("Arial, sans-serif") == "Arial"
    assert first_font_family("system-ui, sans-serif") is None
    assert first_font_family("") is None


def test_security_url_policy():
    assert validate_target_url("https://example.com") == "https://example.com"
    with pytest.raises(ValueError):
        validate_target_url("ftp://example.com")
    with pytest.raises(ValueError):
        validate_target_url("https://user:pass@example.com")
    with pytest.raises(ValueError):
        validate_target_url("")


def test_is_safe_color_guard():
    assert is_safe_color("#2864dc")
    assert is_safe_color("rgb(40, 100, 220)")
    assert not is_safe_color("red; background: url(javascript:alert(1))")
    assert not is_safe_color("expression(alert(1))")
    assert not is_safe_color("")


# ---------------------------------------------------------------------------
# Engine tests (require Chromium)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def result() -> DesignExtraction:
    return extract_design(
        FIXTURE, profiles=["desktop"], max_elements=300, stabilize_ms=200
    )


@needs_browser
def test_extraction_succeeds(result: DesignExtraction):
    assert result.status == "succeeded"
    assert result.coverage.elements_visible > 0
    assert result.coverage.tokens_extracted > 0


@needs_browser
def test_brand_color_measured(result: DesignExtraction):
    # The fixture sets brand #2864DC; the browser reports it as rgb(40,100,220).
    colors = {t.value for t in result.tokens_by_category("color")}
    assert "rgb(40, 100, 220)" in colors
    # The declared custom property is also captured verbatim.
    customs = {t.role: t.value for t in result.tokens_by_category("custom-property")}
    assert customs.get("brand") == "#2864DC"


@needs_browser
def test_typography_measured(result: DesignExtraction):
    fonts = {t.value for t in result.tokens_by_category("typography") if t.role == "font-family"}
    assert "Inter" in fonts
    sizes = {t.value for t in result.tokens_by_category("typography") if t.role == "font-size"}
    assert "32px" in sizes and "16px" in sizes


@needs_browser
def test_radii_and_shadows_measured(result: DesignExtraction):
    radii = {t.value for t in result.tokens_by_category("radius")}
    # 8px control, 12px card, 999px pill badge all present.
    assert {"8px", "12px", "999px"} <= radii
    shadows = result.tokens_by_category("shadow")
    assert len(shadows) >= 1


@needs_browser
def test_breakpoints_declared(result: DesignExtraction):
    bps = {t.value for t in result.tokens_by_category("breakpoint")}
    assert {"768px", "1024px"} <= bps


@needs_browser
def test_components_grouped(result: DesignExtraction):
    kinds = {c.kind for c in result.components}
    assert "button" in kinds
    assert "link" in kinds
    # Repeated nav links collapse to a single representative with a count.
    links = [c for c in result.components if c.kind == "link"]
    assert links and links[0].count >= 2


@needs_browser
def test_design_md_names_roles_and_reports_confidence(result: DesignExtraction):
    md = result.design_md
    assert "## Confidence" in md
    assert "Evidence-based score" in md
    # Inferred roles become stable YAML keys instead of color-<n>.
    assert "primary:" in md
    assert "| `primary` |" in md


@needs_browser
def test_roles_marked_inferred_not_measured(result: DesignExtraction):
    # Every inferred color role must be tagged inferred and carry a reason.
    inferred = [t for t in result.tokens if t.category == "color" and t.role]
    assert inferred, "expected at least one named color role"
    for t in inferred:
        assert t.role_status == "inferred"
        assert t.role_reason


@needs_browser
def test_gaps_are_explicit(result: DesignExtraction):
    codes = {g.code for g in result.gaps}
    # Milestone B honestly reports that states and recipes are not captured.
    assert "states-not-captured" in codes
    assert "recipes-not-generated" in codes


@needs_browser
def test_all_artifacts_written_and_parse(result: DesignExtraction, tmp_path):
    manifest = result.save(str(tmp_path))
    for name in ("DESIGN.md", "design.json", "tokens.css", "preview.html"):
        assert name in manifest
        assert (tmp_path / name).exists()

    # design.json must be valid JSON and carry the version + evidence fields.
    data = json.loads((tmp_path / "design.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == result.schema_version
    assert data["capture"]["requested_url"] == FIXTURE
    assert isinstance(data["observations"], list) and data["observations"]
    # Screenshots are bytes and must be excluded from JSON.
    assert "screenshots" not in data

    # tokens.css must be a :root block with custom properties.
    css = (tmp_path / "tokens.css").read_text(encoding="utf-8")
    assert ":root" in css
    assert "--is-color-" in css

    # preview.html must be inert: no scripts, no external references.
    html = (tmp_path / "preview.html").read_text(encoding="utf-8")
    assert "<script" not in html.lower()
    assert "http://" not in html and "https://" not in html
    assert "rgb(40, 100, 220)" in html

    # DESIGN.md must be valid front matter with no duplicate keys.
    md = (tmp_path / "DESIGN.md").read_text(encoding="utf-8")
    assert md.startswith("---")
    assert "## Colors" in md and "## Typography" in md
    assert "## Scope and Known Gaps" in md


@needs_browser
def test_design_md_no_duplicate_yaml_keys(result: DesignExtraction):
    md = result.design_md
    front = md.split("---")[1]
    keys = [line.split(":")[0].strip() for line in front.splitlines() if ":" in line and line.startswith(("    ", "  "))]
    # Top-level section keys must not repeat.
    top = [l.split(":")[0].strip() for l in front.splitlines() if l and not l.startswith((" ", "\t")) and ":" in l]
    assert len(top) == len(set(top)), f"duplicate top-level YAML keys: {top}"


@needs_browser
def test_deterministic_output(result: DesignExtraction):
    # Re-normalizing the same observations gives the same token ids/values.
    renorm = DesignNormalizer().normalize(result.observations)
    assert [t.id for t in renorm] == [t.id for t in result.tokens]


@needs_browser
def test_two_profiles_capture_independently():
    r = extract_design(FIXTURE, profiles=["desktop", "mobile"], max_elements=300, stabilize_ms=150)
    assert r.status == "succeeded"
    profiles_seen = {o.profile for o in r.observations}
    assert {"desktop", "mobile"} <= profiles_seen


def test_component_analyzer_groups_repeats():
    from intelliscrape.design.models import Observation

    def obs(i, tag, bg="rgb(40, 100, 220)", radius="8px"):
        return Observation(
            id=f"el-{i}", profile="desktop", page_url="x", tag=tag,
            styles={"backgroundColor": bg, "borderTopLeftRadius": radius,
                    "fontSize": "14px", "fontWeight": "600", "color": "rgb(255,255,255)"},
            area=1000,
        )

    obss = [obs(i, "button") for i in range(5)] + [obs(99, "a", bg="rgb(0,0,0)")]
    comps = ComponentAnalyzer().analyze(obss)
    buttons = [c for c in comps if c.kind == "button"]
    assert len(buttons) == 1
    assert buttons[0].count == 5


# ---------------------------------------------------------------------------
# Blocked-detection precision (regression: false positives discarding captures)
# ---------------------------------------------------------------------------

def test_challenge_markers_reject_real_pages():
    """A real page must never match the challenge signatures.

    Regression: the detector previously matched generic words — notably the
    target's own name — so cloudflare.com's homepage (title "Cloudflare: Build
    for the agent era", a successful 200 capture) was reported ``blocked``.
    """
    from intelliscrape.design.browser import _BLOCK_BODY_MARKERS, _BLOCK_TITLE_MARKERS

    real_title = "cloudflare: build for the agent era"
    real_body = (
        "one smart network for workloads + security, close to users, close to "
        "data. powered by cloudflare."
    )
    assert not any(m in real_title for m in _BLOCK_TITLE_MARKERS)
    assert not any(m in real_body for m in _BLOCK_BODY_MARKERS)
    # Generic words that caused false positives must not be list members at all.
    markers = set(_BLOCK_TITLE_MARKERS) | set(_BLOCK_BODY_MARKERS)
    for generic in ("cloudflare", "please wait", "captcha", "security check"):
        assert generic not in markers

    # Genuine interstitials must still match.
    assert any(m in "just a moment..." for m in _BLOCK_TITLE_MARKERS)
    assert any(m in "sorry, you have been blocked" for m in _BLOCK_BODY_MARKERS)
    assert any(m in "checking your browser before accessing" for m in _BLOCK_BODY_MARKERS)


@needs_browser
def test_real_page_naming_the_target_not_reported_blocked():
    """End-to-end regression for the exact false positive we hit on cloudflare.com."""
    url = (pathlib.Path(__file__).parent / "fixtures" / "design" / "brand_named_page.html").as_uri()
    r = extract_design(url, profiles=["desktop"], max_elements=150, stabilize_ms=150)
    assert r.status == "succeeded"
    assert not any(g.code == "blocked-by-challenge" for g in r.gaps)
    assert r.coverage.elements_visible > 0
    assert r.tokens_by_category("color")


@needs_browser
def test_genuine_interstitial_still_detected():
    """Over-correction guard: a real challenge page must still read as blocked."""
    url = (pathlib.Path(__file__).parent / "fixtures" / "design" / "interstitial.html").as_uri()
    r = extract_design(url, profiles=["desktop"], max_elements=50, stabilize_ms=100,
                       challenge_timeout=0)  # local fixture can never auto-solve
    assert r.status == "blocked"
    assert any(g.code == "blocked-by-challenge" for g in r.gaps)
    assert r.coverage.elements_visible == 0


@needs_browser
def test_zero_size_prefix_does_not_consume_element_cap():
    """Regression: invisible scaffolding must not eat the element cap.

    The old collector walked DOM nodes first (capped) and filtered for
    visibility after, so invisible nodes consumed the whole cap. On sentry.io
    an inline icon sprite put hundreds of zero-size <defs>/<symbol>/<path>
    nodes first in document order: a 120-node walk kept 7 of ~2500 visible
    elements. The cap must count measurable elements only.
    """
    url = (pathlib.Path(__file__).parent / "fixtures" / "design" / "zero_size_prefix.html").as_uri()
    # Cap is smaller than the 60-node zero-size prefix: the old walk-then-filter
    # order returned ~0 observations here because all 40 walked nodes were
    # zero-size. The fixed collector skips them and keeps walking.
    r = extract_design(url, profiles=["desktop"], max_elements=40, stabilize_ms=150)
    assert r.status == "succeeded"
    assert r.coverage.elements_visible >= 10
    tags = {o.tag for o in r.observations}
    assert "h1" in tags and "button" in tags
