"""Real-time progress reporting for IntelliScrape scrape operations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ScrapeProgress:
    """Progress event for a scrape operation."""

    engine: str = ""
    status: str = "idle"
    message: str = ""
    attempt: int = 0
    total_attempts: int = 0
    captcha_type: Optional[str] = None
    anti_bot_vendor: Optional[str] = None
    proxy_used: Optional[str] = None
    elapsed_seconds: float = 0.0
    url: str = ""


class ProgressTracker:
    """Tracks and reports scrape progress via callback."""

    ENGINES = ["static", "playwright_stealth", "camoufox", "nodriver", "drissionpage"]

    def __init__(
        self,
        on_progress: Optional[Callable[[ScrapeProgress], None]] = None,
        url: str = "",
    ):
        self.on_progress = on_progress
        self.url = url
        self.start_time = time.time()
        self._last_report: Optional[ScrapeProgress] = None

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def report(
        self,
        engine: str,
        status: str,
        message: str = "",
        attempt: int = 0,
        total_attempts: int = 0,
        captcha_type: Optional[str] = None,
        anti_bot_vendor: Optional[str] = None,
        proxy_used: Optional[str] = None,
    ) -> ScrapeProgress:
        progress = ScrapeProgress(
            engine=engine,
            status=status,
            message=message,
            attempt=attempt,
            total_attempts=total_attempts,
            captcha_type=captcha_type,
            anti_bot_vendor=anti_bot_vendor,
            proxy_used=proxy_used,
            elapsed_seconds=self.elapsed,
            url=self.url,
        )
        self._last_report = progress
        if self.on_progress:
            try:
                self.on_progress(progress)
            except Exception:
                pass
        return progress

    def engine_trying(self, engine: str, attempt: int, total: int) -> ScrapeProgress:
        return self.report(
            engine=engine,
            status="trying",
            message=f"Trying {engine}...",
            attempt=attempt,
            total_attempts=total,
        )

    def engine_blocked(
        self, engine: str, vendor: str, attempt: int, total: int
    ) -> ScrapeProgress:
        return self.report(
            engine=engine,
            status="blocked",
            message=f"Blocked by {vendor}",
            attempt=attempt,
            total_attempts=total,
            anti_bot_vendor=vendor,
        )

    def engine_captcha(
        self, engine: str, captcha_type: str, attempt: int, total: int
    ) -> ScrapeProgress:
        return self.report(
            engine=engine,
            status="captcha_detected",
            message=f"{captcha_type} detected, opening browser for manual solve...",
            attempt=attempt,
            total_attempts=total,
            captcha_type=captcha_type,
        )

    def engine_solving(self, engine: str, captcha_type: str) -> ScrapeProgress:
        return self.report(
            engine=engine,
            status="solving",
            message=f"Solving {captcha_type}... Please solve in the browser window.",
            captcha_type=captcha_type,
        )

    def engine_solved(self, engine: str, captcha_type: str) -> ScrapeProgress:
        return self.report(
            engine=engine,
            status="solved",
            message=f"{captcha_type} solved successfully",
            captcha_type=captcha_type,
        )

    def engine_js_only(self, engine: str, attempt: int, total: int) -> ScrapeProgress:
        return self.report(
            engine=engine,
            status="js_only",
            message=f"{engine} returned JS-only content, escalating...",
            attempt=attempt,
            total_attempts=total,
        )

    def engine_success(self, engine: str, attempt: int, total: int) -> ScrapeProgress:
        return self.report(
            engine=engine,
            status="success",
            message=f"Success with {engine}",
            attempt=attempt,
            total_attempts=total,
        )

    def engine_failed(
        self, engine: str, error: str, attempt: int, total: int
    ) -> ScrapeProgress:
        return self.report(
            engine=engine,
            status="failed",
            message=f"{engine} failed: {error}",
            attempt=attempt,
            total_attempts=total,
        )

    def all_failed(self) -> ScrapeProgress:
        return self.report(
            engine="",
            status="all_failed",
            message="All engines failed",
        )
