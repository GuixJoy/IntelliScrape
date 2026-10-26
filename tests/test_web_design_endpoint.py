"""Checks for the hosted /design payload used by the website.

No network: the live case measures a local fixture, the fallback case stubs the
engine out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import main
from intelliscrape.design import service

FIXTURE = Path(__file__).parent / "fixtures" / "design" / "fixture.html"


def test_live_payload_comes_from_the_engine():
    payload = main.extract_design_payload(FIXTURE.as_uri(), ["desktop"])

    assert payload["engine"] == "playwright-live"
    assert payload["status"] == "succeeded"
    assert set(payload["artifacts"]) == {"DESIGN.md", "design.json", "tokens.css", "preview.html"}
    assert payload["stats"]["colors"] > 0
    assert payload["coverage"]["elements_visible"] > 0


def test_static_fallback_is_explicit(monkeypatch):
    def no_browser(*args, **kwargs):
        raise RuntimeError("chromium missing")

    html = (
        "<html><head><style>"
        ":root{--brand:#0f62fe}"
        "body{font-family:Inter;color:#111;padding:24px}"
        "</style></head><body><h1>Hi</h1></body></html>"
    )
    monkeypatch.setattr(service, "extract_design", no_browser)
    monkeypatch.setattr(main, "fetch_raw", lambda url, render_js=False: (html, {}))

    payload = main.extract_design_payload("https://example.com")

    assert payload["engine"] == "static"
    assert payload["status"] == "partial"
    assert "DESIGN.md" in payload["artifacts"]
    assert any(g["code"] == "static-fallback" for g in payload["gaps"])
    assert payload["stats"]["colors"] >= 1


def test_private_targets_are_rejected():
    with pytest.raises(ValueError):
        main.validate_url("http://127.0.0.1:8000")
