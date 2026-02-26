"""Playwright-backed dynamic HTML downloader for IntelliScrape."""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from .exceptions import IntelliScrapeError


def download_dynamic_html(url: str, timeout: int = 30000) -> str:
    """Render ``url`` in a headless Chromium browser and return HTML."""

    if not url:
        raise IntelliScrapeError("URL is required for dynamic download")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            try:
                page.goto(url, timeout=timeout, wait_until="networkidle")
                # Initial wait
                page.wait_for_timeout(4000)
                # Multiple scroll passes (important for YouTube)
                for _ in range(5):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1500)
                html = page.content()
                return html
            finally:
                context.close()
                browser.close()

    except Exception as exc:
        raise IntelliScrapeError(
            f"Browser download failed: {exc}"
        ) from exc