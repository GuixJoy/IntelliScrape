"""Anubis proof-of-work challenge handling.

Anubis (https://within.website/x/cmd/anubis) protects sites like
lore.kernel.org with a JavaScript proof-of-work challenge.  Real browsers
auto-solve it: the challenge page computes a PoW and then redirects to the
real content.  These helpers let the browser engines wait for the challenge
to resolve instead of grabbing the challenge page as if it were content.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger("intelliscrape.challenges")

# Markers present on the Anubis challenge interstitial page.
ANUBIS_TITLE_MARKERS = (
    "making sure you're not a bot",
    "making sure you are not a bot",
    "oh noes",
)
ANUBIS_BODY_MARKERS = (
    "this website is running anubis",
    "anubis is compromise",
    "anubis uses proof-of-work",
    "anubis could not load its javascript",
    ".within.website/x/cmd/anubis",
    "proof-of-work",
)


def is_anubis_challenge(html: str = "", title: str = "") -> bool:
    """Return True if the page looks like an Anubis challenge."""
    lower_title = (title or "").lower()
    for m in ANUBIS_TITLE_MARKERS:
        if m in lower_title:
            return True

    lower_html = (html or "").lower()
    strong = sum(1 for m in ANUBIS_BODY_MARKERS if m in lower_html)
    if strong >= 1:
        return True
    return False


def wait_for_anubis_resolution(
    page: Any,
    *,
    timeout: float = 90.0,
    poll_interval: float = 2.0,
    max_wait: float = 90.0,
) -> Optional[str]:
    """Wait until the Anubis PoW challenge has resolved.

    The challenge page auto-redirects to the real content once the proof
    of work completes.  This polls the page title/URL until the challenge
    markers are gone.

    Parameters
    ----------
    page : object
        A browser page object exposing ``title()`` and ``url``
        (Playwright/Stealth page, Camoufox page, nodriver page).
    timeout : float
        Total seconds to wait before giving up.
    poll_interval : float
        Seconds between checks.
    max_wait : float
        Alias kept for compatibility.

    Returns
    -------
    str or None
        The resolved page title once the challenge cleared, or None if the
        challenge was not resolved in time.
    """
    deadline = time.monotonic() + timeout
    last_title = ""

    while time.monotonic() < deadline:
        try:
            title = page.title() if hasattr(page, "title") else ""
            cur_url = getattr(page, "url", "") or ""
        except Exception:
            title, cur_url = "", ""

        last_title = title
        # Challenge resolved when neither title nor URL shows the challenge.
        if not is_anubis_challenge("", title) and not is_anubis_challenge(cur_url, ""):
            # Double-check the body too, in case the title is generic.
            try:
                content = page.content()
                if not is_anubis_challenge(content, title):
                    return title
            except Exception:
                return title

        # Let the page finish the PoW; a short sleep is important — the
        # worker runs on the page's main thread.
        try:
            page.wait_for_timeout(poll_interval * 1000)
        except Exception:
            time.sleep(poll_interval)

    logger.debug("Anubis challenge not resolved within %ss", timeout)
    return None


def pass_anubis(html: str, title: str = "") -> bool:
    """Return True if the returned page is real content, not a challenge."""
    return not is_anubis_challenge(html, title)