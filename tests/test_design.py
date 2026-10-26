"""Tests for the design-system extractor."""

from intelliscrape.design import (
    DesignExtractor,
    collect_css,
    stylesheet_hrefs,
)

HTML = """
<html>
<head>
  <title>Acme</title>
  <link rel="stylesheet" href="/assets/main.css">
  <link rel="stylesheet" href="https://cdn.acme.com/reset.css">
  <link rel="icon" href="/favicon.ico">
  <style>
    :root {
      --brand: #E8291C;
      --surface: rgb(10, 10, 10);
      --radius: 6px;
    }
    body {
      font-family: "Inter", system-ui, sans-serif;
      font-size: 16px;
      font-weight: 400;
      color: #FAFAFA;
      background: var(--surface);
      margin: 0;
      padding: 24px;
    }
    h1 { font-size: 3rem; font-weight: 700; line-height: 1.05; }
    .btn {
      border-radius: 6px 999px 12px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
      padding: 12px 24px;
      color: #e8291c;
    }
    @media (min-width: 768px) { .grid { gap: 8px; } }
    @media (min-width: 1024px) { .grid { gap: 16px; } }
  </style>
</head>
<body>
  <div style="font-family: 'JetBrains Mono', monospace; color: hsl(2, 80%, 51%)">
    <button style="padding: 8px; border-radius: 4px;">hi</button>
  </div>
</body>
</html>
"""

CSS = """
a { color: #FAFAFA; font-weight: 600; }
.card { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25); }
@media (max-width: 480px) { .card { padding: 4px; } }
"""


def test_stylesheet_hrefs():
    hrefs = stylesheet_hrefs(HTML)
    assert "/assets/main.css" in hrefs
    assert "https://cdn.acme.com/reset.css" in hrefs
    assert all("favicon" not in h for h in hrefs)


def test_extract_counts():
    report = DesignExtractor.extract(html=HTML, css_texts=[CSS], url="https://acme.com")

    # colors: ordered by frequency, case-insensitive
    assert report.colors["#e8291c"] == 2
    assert report.colors["#fafafa"] == 2
    assert report.colors["rgba(0, 0, 0, 0.25)"] == 2

    # fonts: first family of each stack wins
    assert report.font_families["Inter"] == 1
    assert report.font_families["JetBrains Mono"] == 1

    # typography / spacing / radius
    assert "16px" in report.font_sizes
    assert "3rem" in report.font_sizes
    assert "700" in report.font_weights
    assert "24px" in report.spacing
    assert "6px 999px 12px" in report.radii

    # shadows and breakpoints (deduped, ints)
    assert report.shadows["0 4px 12px rgba(0, 0, 0, 0.25)"] == 2
    assert dict(report.breakpoints) == {768: 1, 1024: 1, 480: 1}

    # CSS variables picked up
    assert report.css_variables["brand"] == "#e8291c"
    assert report.css_variables["surface"] == "rgb(10, 10, 10)"


def test_markdown_and_stats(tmp_path):
    report = DesignExtractor.extract(html=HTML, css_texts=[CSS], url="https://acme.com")
    md = report.to_markdown()

    assert md.startswith("# Design spec — acme.com")
    assert "## Color palette" in md
    assert "## Typography" in md
    assert "**Inter**" in md
    assert "## Breakpoints" in md
    assert "768px" in md
    assert "--brand: #e8291c;" in md

    assert report.stats["colors"] >= 3
    assert report.stats["fonts"] == 2
    assert report.stats["breakpoints"] == 3

    path = str(tmp_path / "design.md")
    assert report.save(path) == path
    with open(path, encoding="utf-8") as f:
        assert f.read() == md

    data = report.to_dict()
    assert data["url"] == "https://acme.com"
    assert data["css_variables"]["brand"] == "#e8291c"


def test_empty_css_gives_clean_empty_spec():
    report = DesignExtractor.extract(html="<html><body>hi</body></html>", url="https://x.com")
    md = report.to_markdown()
    assert md.startswith("# Design spec — x.com")
    assert "##" not in md
    assert report.stats == {
        "colors": 0,
        "fonts": 0,
        "font_sizes": 0,
        "spacing": 0,
        "radii": 0,
        "shadows": 0,
        "breakpoints": 0,
        "css_variables": 0,
    }


def test_collect_css_inline_styles():
    css = collect_css(HTML)
    assert "--brand" in css
    assert "font-family" in css and "JetBrains Mono" in css


def test_static_palette_is_canonical_and_named():
    html = """
    <style>
      :root { --ink: #111; --brand: #0058a3; --step: 1.5rem; --font: "Noto IKEA", sans-serif; }
      body { color: #111111; background: var(--ink); font-family: var(--font); font-size: var(--step); }
      a { color: rgb(17, 17, 17); }
      .cta { background: #0058a3; }
      .ghost { color: rgba(0, 0, 0, 0); }
      @media (min-width: 47em) { .cta { padding: 8px 16px; } }
    </style>
    """
    report = DesignExtractor.extract(html=html, url="https://acme.com")

    # #111, #111111 and rgb(17,17,17) are one perceived color.
    assert "#111" not in report.palette
    assert report.palette["#111111"] >= 3
    # Fully transparent is dropped, not listed as a token.
    assert not any(c.endswith("00") for c in report.palette)
    # Saturated brand color gets a named, inferred role.
    assert report.color_roles.get("#0058a3") == "primary"
    token = next(t for t in report.tokens if t["value"] == "#0058a3" and t["category"] == "color")
    assert token["role"] == "primary" and token["role_status"] == "inferred"

    # Relative units resolve to px; calc() never leaks into the scale.
    assert 24.0 in report.sizes_px
    assert "Noto IKEA" in report.families
    assert 752 in report.breakpoints_px
    assert "8px 16px" in report.spacing_px

    # Confidence is evidence-based and exposed for the report.
    assert 0 < report.confidence["overall"] <= 100
    assert report.confidence["sections"]["colors"] == 100
    assert report.confidence["sections"]["components"] == 0

    # The web payload carries a structured model, not just markdown.
    payload = report.to_design_json()
    assert payload["tokens"] and payload["capture"]["title"] == "acme.com"

