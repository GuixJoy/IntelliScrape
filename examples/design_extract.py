"""Design Extract example — live measurement to a reusable design reference.

Requires Playwright + Chromium (no LLM/API key):
    pip install intelliscrape
    playwright install chromium

Run online against a real site, or offline against the bundled fixture:

    python examples/design_extract.py              # online (example.com)
    python examples/design_extract.py --offline    # local fixture, no network
"""

import pathlib
import sys

from intelliscrape import extract_design


def main() -> None:
    offline = "--offline" in sys.argv
    if offline:
        fixture = pathlib.Path(__file__).parent.parent / "tests" / "fixtures" / "design" / "fixture.html"
        url = fixture.as_uri()
        print(f"Using local fixture: {url}")
    else:
        url = "https://example.com"
        print(f"Measuring {url} ...")

    # Desktop + mobile capture profiles, light scheme.
    result = extract_design(
        url,
        scope="page",
        profiles=["desktop", "mobile"],
        color_schemes=["light"],
    )

    print(f"\nstatus: {result.status}")
    print(f"elements measured: {result.coverage.elements_visible}")
    print(f"tokens extracted:  {result.coverage.tokens_extracted}")
    print(f"components found:  {result.coverage.components_found}")

    print("\ntop colors (value / role / basis):")
    for t in result.tokens_by_category("color")[:8]:
        basis = "inferred" if t.role_status == "inferred" else "measured"
        print(f"  {t.value:24} {t.role or '-':16} {basis}")

    print("\ndeclared custom properties:")
    for t in result.tokens_by_category("custom-property")[:8]:
        print(f"  {t.role}: {t.value}")

    print("\nknown gaps (explicit, not silent):")
    for g in result.gaps:
        print(f"  [{g.code}] {g.message}")

    out_dir = pathlib.Path("design-output")
    manifest = result.save(str(out_dir))
    print("\nwrote artifacts:")
    for name, path in manifest.items():
        print(f"  {name} -> {path}")


if __name__ == "__main__":
    main()
