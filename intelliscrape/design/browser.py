"""Managed live-page adapter for design measurement.

The scraper engines return an HTML string; that is not enough for design work
because layout, resolved styles and interaction states only exist while a page
is rendered and alive. This adapter owns a Playwright browser/context/page for
the duration of a capture and exposes the two operations design extraction
needs: run a collector script in the live page, and take a screenshot.

The first implementation is Playwright (the only browser engine the library
already depends on for rendering). Capabilities are reported explicitly, so an
engine that cannot do something yields a recorded gap rather than a silent
drop in coverage.
"""

from __future__ import annotations

import importlib.resources
import logging
import platform as _platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import CaptureProfile

logger = logging.getLogger("intelliscrape.design.browser")


class DesignCaptureError(RuntimeError):
    """Raised when a page cannot be captured (navigation failure, timeout)."""

    def __init__(self, message: str, *, blocked: bool = False):
        super().__init__(message)
        # Distinguish an anti-bot/challenge wall from an ordinary network error
        # so the caller can report a "blocked" outcome instead of treating a
        # Cloudflare interstitial as the target's design.
        self.blocked = blocked


# Precise challenge signatures. Deliberately narrow — these must never match a
# real page. An earlier version matched generic words (notably "cloudflare"),
# which reported cloudflare.com's own homepage as blocked even though the
# capture had succeeded. A false positive discards a good measurement, which is
# worse than a missed challenge.
#
# Title markers: interstitials replace the document title outright.
_BLOCK_TITLE_MARKERS = (
    "just a moment",         # Cloudflare JS managed challenge
    "attention required",    # Cloudflare 403 block page title
    "access denied",
    "checking your browser",
)
# Body markers: phrases a legitimate content page does not use verbatim.
_BLOCK_BODY_MARKERS = (
    "checking your browser",
    "verify you are human",
    "please turn javascript on",
    "enable javascript and cookies to continue",
    "complete the following security check",
    "performing security verification",
    "checking if the site connection is secure",
    "sorry, you have been blocked",      # Cloudflare 403 block page
)
# HTTP statuses that mean the page itself was refused (nothing to measure).
_HARD_STATUSES = (401, 403, 429, 503)

# Mirrors PlaywrightStealthEngine's launch flags. A naked Chromium advertises
# `navigator.webdriver`, a `HeadlessChrome` UA and the AutomationControlled
# blink feature — enough to trigger a challenge before measurement starts.
STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--excludeSwitches=enable-automation",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-accelerated-2d-canvas",
    "--disable-gpu",
    "--use-gl=swiftshader",
]

# Real (non-Headless) Chrome user agents, keyed by fingerprint platform so the
# UA and the spoofed GPU/platform fingerprint stay coherent. {v} is filled with
# the RUNNING browser's version.
_DESKTOP_UAS = {
    "win": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v} Safari/537.36",
    "mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v} Safari/537.36",
    "linux": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v} Safari/537.36",
}
_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7 Pro) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{v} Mobile Safari/537.36"
)
_FALLBACK_CHROME = "131.0.0.0"

# Pinned rather than fingerprint-randomized: a timezone that changes per run
# would change rendered timestamps and break run-to-run diffing, which design
# extraction depends on.
_TIMEZONE = "America/New_York"


def _user_agent_for(profile: CaptureProfile, fp, browser_version: str = "") -> str:
    """A real UA coherent with the profile, fingerprint and actual browser.

    The version comes from the running browser, not a hardcoded value: the UA
    must agree with ``navigator.userAgentData`` (UA-CH), which exposes the true
    Chromium version to any script that asks.
    """
    if profile.name == "mobile":
        return _MOBILE_UA.format(v=browser_version or _FALLBACK_CHROME)
    platform = (getattr(fp, "platform", "Win32") or "Win32").lower()
    if platform.startswith("mac"):
        template = _DESKTOP_UAS["mac"]
    elif platform.startswith("linux"):
        template = _DESKTOP_UAS["linux"]
    else:
        template = _DESKTOP_UAS["win"]
    return template.format(v=browser_version or _FALLBACK_CHROME)


#: Host OS -> FingerprintGenerator platform key. The fingerprint must match the
#: real ``navigator.platform`` (which we do not patch), or the UA and platform
#: fields contradict each other — a free bot signal.
_HOST_PLATFORM_KEY = {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}


def _load_collector_js(max_elements: int) -> str:
    """Load the packaged collector script and stamp in the element cap."""
    try:
        # __package__ keeps this working when the engine is vendored under a
        # different package name (e.g. the standalone web backend).
        ref = importlib.resources.files(__package__).joinpath("collect.js")
        src = ref.read_text(encoding="utf-8")
    except Exception:  # pragma: no cover - source-tree fallback
        from pathlib import Path

        src = (Path(__file__).parent / "collect.js").read_text(encoding="utf-8")
    return src.replace("__MAX_ELEMENTS__", str(int(max_elements)))


@dataclass
class PageCapture:
    """Raw result of a single live-page capture."""

    profile: CaptureProfile
    title: str = ""
    final_url: str = ""
    observations: List[dict] = field(default_factory=list)
    root_vars: Dict[str, str] = field(default_factory=dict)
    media_widths: List[str] = field(default_factory=list)
    screenshot_png: Optional[bytes] = None
    browser_version: str = ""
    blocked: bool = False


class PlaywrightDesignAdapter:
    """Owns one Playwright browser and captures pages under pinned profiles."""

    #: Capabilities this adapter actually provides. A later adapter that lacks
    #: one of these should report the gap rather than claim parity.
    capabilities = {
        "evaluate": True,
        "screenshot": True,
        "keyboard_focus": False,  # state probes arrive in a later milestone
        "css_inspection": True,
        "stealth": True,               # fingerprint + UA + webdriver patches
        "challenge_auto_solve": True,  # bounded wait for JS challenges
    }

    def __init__(
        self,
        *,
        headless: bool = True,
        navigation_timeout: float = 30.0,
        stabilize_ms: int = 800,
        block_resources: bool = False,
        challenge_timeout: float = 20.0,
        fingerprint_generator=None,
    ):
        self.headless = headless
        self.navigation_timeout = navigation_timeout
        self.stabilize_ms = stabilize_ms
        self.block_resources = block_resources
        # Bounded window for a served JS challenge to solve itself in-page.
        self.challenge_timeout = challenge_timeout
        if fingerprint_generator is None:
            from ..anti_detection.fingerprint import FingerprintGenerator

            fingerprint_generator = FingerprintGenerator()
        self.fingerprint_gen = fingerprint_generator
        self._pw = None
        self._browser = None

    def __enter__(self) -> "PlaywrightDesignAdapter":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - env without playwright
            raise DesignCaptureError(
                "Playwright is required for design extraction. "
                "Install with: pip install playwright && playwright install chromium"
            ) from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=list(STEALTH_LAUNCH_ARGS),
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        # Always release the browser/process, including on exceptions.
        try:
            if self._browser:
                self._browser.close()
        finally:
            self._browser = None
            if self._pw:
                try:
                    self._pw.stop()
                finally:
                    self._pw = None

    def browser_version(self) -> str:
        try:
            return self._browser.version if self._browser else ""
        except Exception:
            return ""

    def capture(
        self,
        url: str,
        profile: CaptureProfile,
        *,
        max_elements: int = 400,
        scroll_steps: int = 6,
        take_screenshot: bool = True,
    ) -> PageCapture:
        """Navigate to *url* under *profile* and collect design evidence."""
        if not self._browser:
            raise DesignCaptureError("Adapter not opened; use as a context manager.")

        from playwright.sync_api import Error as PWError

        # Fingerprint kept coherent on three axes: with the pinned viewport (a
        # screen smaller than the viewport is itself a bot tell), with the real
        # navigator.platform (which we deliberately do not patch), and with the
        # running browser's version (UA-CH exposes it to any script that asks).
        fp = self.fingerprint_gen.generate(
            platform=_HOST_PLATFORM_KEY.get(_platform.system())
        )
        if profile.name == "mobile":
            fp.screen_width, fp.screen_height = profile.width, profile.height
        else:
            fp.screen_width = max(fp.screen_width, profile.width)
            fp.screen_height = max(fp.screen_height, profile.height)

        context_kwargs: dict = dict(
            viewport={"width": profile.width, "height": profile.height},
            device_scale_factor=profile.device_scale_factor,
            color_scheme=profile.color_scheme,
            locale=profile.locale,
            timezone_id=_TIMEZONE,
            user_agent=_user_agent_for(profile, fp, self.browser_version()),
            java_script_enabled=True,
        )
        if profile.name == "mobile":
            # Real phones report touch + a coarse pointer, and sites gate
            # mobile-only UI on it — mobile design capture should emulate it.
            context_kwargs.update(is_mobile=True, has_touch=True)

        context = self._browser.new_context(**context_kwargs)
        page = context.new_page()

        # Patch navigator.webdriver/plugins/chrome/WebGL before any page script
        # runs — the same patches the scraping engine applies. Best-effort: a
        # patching failure degrades stealth, it does not fail the capture.
        try:
            from ..anti_detection.stealth_js import build_stealth_js

            page.add_init_script(build_stealth_js(fp))
            if profile.name == "mobile":
                # The Android UA above would otherwise be contradicted by the
                # host machine's desktop navigator.platform.
                page.add_init_script(
                    "Object.defineProperty(navigator, 'platform', {get: () => 'Linux armv81'});"
                )
        except Exception:
            logger.debug("stealth init script not applied", exc_info=True)

        try:
            if self.block_resources:
                self._block_heavy_resources(page)

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.navigation_timeout * 1000,
            )

            # Detect an anti-bot interstitial before accepting the design.
            if self._is_challenge(page):
                # A stealthed browser can solve a served JS challenge in-page
                # and reload (same idea as the engine's Anubis PoW wait). Give
                # it a bounded window, then re-check: never measure an
                # interstitial and pass it off as the target's design.
                resolved = (
                    self._await_challenge_resolution(page)
                    and not self._is_challenge(page)
                )
                if not resolved:
                    return PageCapture(
                        profile=profile,
                        title=page.title(),
                        final_url=page.url,
                        blocked=True,
                        browser_version=self.browser_version(),
                    )
            elif self._looks_blocked(page, response):
                return PageCapture(
                    profile=profile,
                    title=page.title(),
                    final_url=page.url,
                    blocked=True,
                    browser_version=self.browser_version(),
                )

            self._stabilize(page, scroll_steps)

            collector = _load_collector_js(max_elements)
            raw = page.evaluate(collector)
            import json

            data = json.loads(raw) if isinstance(raw, str) else (raw or {})

            shot = None
            if take_screenshot:
                try:
                    shot = page.screenshot(full_page=False)
                except PWError:
                    shot = None

            return PageCapture(
                profile=profile,
                title=data.get("title", "") or page.title(),
                final_url=data.get("finalUrl", "") or page.url,
                observations=data.get("observations", []),
                root_vars=data.get("rootVars", {}),
                media_widths=data.get("mediaWidths", []),
                screenshot_png=shot,
                browser_version=self.browser_version(),
                blocked=False,
            )
        except PWError as exc:
            raise DesignCaptureError(f"Capture failed for {url}: {exc}") from exc
        finally:
            context.close()

    # -- internals -----------------------------------------------------------
    def _block_heavy_resources(self, page) -> None:
        """Optionally drop expensive media. Off by default: aggressive blocking
        makes pages fast but makes design measurements wrong."""

        def route(route_obj):
            req = route_obj.request
            if req.resource_type in ("media", "websocket", "eventsource"):
                route_obj.abort()
            else:
                route_obj.continue_()

        page.route("**/*", route)

    def _is_challenge(self, page) -> bool:
        """True when the page is an interstitial rather than the target's design.

        Only precise challenge signatures count (see ``_BLOCK_*_MARKERS``) —
        generic words are never matched, so a page that merely mentions the
        target's name cannot be misreported as blocked.
        """
        try:
            title = (page.title() or "").lower()
            if any(m in title for m in _BLOCK_TITLE_MARKERS):
                return True
            body = page.evaluate(
                "() => (document.body && document.body.innerText || '').slice(0, 2000).toLowerCase()"
            )
            return any(m in body for m in _BLOCK_BODY_MARKERS)
        except Exception:
            # A mid-challenge navigation destroys the execution context; treat
            # as "still unclear" so the caller re-checks rather than trusting
            # an exception as a resolution signal.
            return True

    def _looks_blocked(self, page, response) -> bool:
        """Blocked when an interstitial shows, or the page itself was refused."""
        if self._is_challenge(page):
            return True
        return response is not None and response.status in _HARD_STATUSES

    def _await_challenge_resolution(self, page) -> bool:
        """Wait a bounded window for a served JS challenge to solve itself.

        Managed challenges compute a clearance cookie in-page and reload; a
        stealthed browser passes on its own (cf. the engine's Anubis PoW wait).
        Returns True once the page is settled and no longer an interstitial —
        an in-flight navigation destroys the execution context, so that is
        treated as "not yet", never as a resolution signal.
        """
        import time

        deadline = time.monotonic() + self.challenge_timeout
        while time.monotonic() < deadline:
            page.wait_for_timeout(500)
            try:
                state = page.evaluate("() => document.readyState")
            except Exception:
                continue  # navigation in flight
            if state in ("interactive", "complete") and not self._is_challenge(page):
                return True
        return False

    def _stabilize(self, page, scroll_steps: int) -> None:
        """Bounded readiness: fonts, lazy content via scrolling, settle time.

        We deliberately avoid networkidle — live sites keep connections open.
        Coverage gaps from the scroll cap are the caller's responsibility to
        report.
        """
        # Bounded font readiness.
        try:
            page.wait_for_function(
                "() => document.fonts ? document.fonts.status === 'loaded' : true",
                timeout=4000,
            )
        except Exception:
            pass  # record a font-availability gap upstream if needed

        # Activate lazy content by scrolling in bounded steps, then return.
        try:
            page.evaluate(
                """async (steps) => {
                    const height = () => document.body.scrollHeight;
                    const step = Math.max(400, Math.floor(window.innerHeight * 0.8));
                    for (let i = 0; i < steps; i++) {
                        window.scrollBy(0, step);
                        await new Promise(r => setTimeout(r, 120));
                    }
                    window.scrollTo(0, 0);
                }""",
                scroll_steps,
            )
        except Exception:
            pass

        # Settle so transitions/animations are measured at rest.
        if self.stabilize_ms > 0:
            try:
                page.wait_for_timeout(self.stabilize_ms)
            except Exception:
                pass
