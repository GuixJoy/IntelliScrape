"""Camoufox browser installation and management.

The official ``camoufox fetch`` downloads a ~470 MB zip that expands to
~930 MB -- 65% of which is bundled system fonts (mostly macOS/Linux).
Those files exist so pages *render* with the fonts of a spoofed OS.
When you spoof your own OS (the common case), your system already has
those fonts, so they are dead weight.

This module installs trimmed profiles:

- ``mini`` : no bundled fonts (~330 MB installed).  The JS-level font
  list spoofing still works exactly the same; glyph rendering falls back
  to system fonts.  Recommended when spoofing your own OS.
- ``full`` : identical to ``camoufox fetch`` (~930 MB).  Needed when you
  spoof a different OS than the host (e.g. spoofing macOS from Linux)
  AND the target measures canvas text rendering.

Implementation note: we always delegate the download/extraction to the
official ``camoufox`` package machinery (its on-disk layout changed
between versions), then remove the bundled font files afterwards.
This keeps the install registered correctly in camoufox's config no
matter which camoufox version is installed.

The browser itself is Mozilla Firefox (MPL-2.0) as patched by Camoufox;
trimming and redistribution are permitted under that license.

To cut download bandwidth too, build a trimmed zip with
``scripts/repack_camoufox.py`` and host it on the IntelliScrape GitHub
Releases, then point ``INTELLISCRAPE_BROWSER_URL`` at it.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("intelliscrape.browser_setup")

PROFILES = ("mini", "full")

# Approximate installed sizes shown to the user before download.
PROFILE_SIZES_MB = {"mini": 330, "full": 930}

# Font file kept even in mini profile (Firefox emoji fallback).
_KEEP_FONTS = {"twemojimozilla.ttf"}

# Environment variable pointing at a pre-trimmed browser zip hosted
# elsewhere (e.g. an IntelliScrape GitHub Release asset).
BROWSER_URL_ENV = "INTELLISCRAPE_BROWSER_URL"

INSTALL_COMMAND = "intelliscrape --install-browser [mini|full]"


def get_install_dir() -> Optional[str]:
    """Return the camoufox browser directory (None if unavailable)."""
    try:
        try:
            from camoufox.multiversion import get_active_path

            active = get_active_path()
            if active:
                return str(active)
        except Exception:
            pass
        from camoufox.pkgman import INSTALL_DIR

        return str(INSTALL_DIR)
    except Exception:
        return None


def camoufox_browser_installed() -> bool:
    """Check whether the camoufox *browser* (not just the pip package) exists."""
    try:
        from camoufox.pkgman import launch_path

        launch_path()
        return True
    except Exception:
        return False


def _trim_fonts(profile: str, quiet: bool = False) -> int:
    """Remove bundled font files from the active camoufox install.

    Returns the number of files removed.
    """
    install_dir = get_install_dir()
    if not install_dir or not os.path.isdir(install_dir):
        return 0

    removed = 0
    for dirpath, dirnames, filenames in os.walk(install_dir):
        if os.path.basename(dirpath).lower() != "fonts":
            continue
        for name in filenames:
            if name.lower() in _KEEP_FONTS:
                continue
            try:
                os.remove(os.path.join(dirpath, name))
                removed += 1
            except OSError as exc:
                logger.warning("Could not remove %s: %s", name, exc)
    if removed and not quiet:
        print(f"Trimmed profile '{profile}': removed {removed} bundled font files.")
    return removed


def install_camoufox(profile: str = "mini", force: bool = False, quiet: bool = False) -> bool:
    """Download and install the Camoufox browser with a trimmed profile.

    Parameters
    ----------
    profile : str
        ``mini`` (no bundled fonts) or ``full`` (everything, like
        ``camoufox fetch``).
    force : bool
        Re-download even if a browser already exists.
    quiet : bool
        Suppress interactive output.

    Returns True when a usable browser is installed afterwards.
    """
    profile = (profile or "mini").lower()
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile '{profile}'. Choose from: {', '.join(PROFILES)}")

    try:
        from camoufox.pkgman import CamoufoxFetcher
    except ImportError:
        print("The 'camoufox' pip package is required but not installed.")
        print("Install it with:  pip install camoufox")
        return False

    def say(msg: str) -> None:
        if not quiet:
            print(msg)

    if not force and camoufox_browser_installed():
        say("Camoufox browser is already installed.")
        if profile == "mini":
            say("Trimming bundled fonts from the existing install...")
            _trim_fonts(profile, quiet=quiet)
        return True

    custom_url = os.environ.get(BROWSER_URL_ENV) or ""
    approx = PROFILE_SIZES_MB[profile]
    if custom_url:
        say(f"Using browser package from {BROWSER_URL_ENV}.")
    else:
        say(f"Fetching latest Camoufox release info (profile: {profile})...")
        say(f"  Download: ~470 MB | Install size after extraction: ~{approx} MB")

    # Delegate to upstream machinery so the install is registered in
    # whatever layout this camoufox version uses.
    try:
        fetcher = CamoufoxFetcher()
        fetcher.install(replace=force)
    except TypeError:
        # Older camoufox without the replace kwarg
        fetcher = CamoufoxFetcher()
        fetcher.install()

    if profile == "mini":
        removed = _trim_fonts(profile, quiet=quiet)
        if not removed and not quiet:
            say("Note: no bundled font files found to trim.")

    say("Camoufox browser installed successfully.")
    return camoufox_browser_installed()


def missing_browser_hint() -> str:
    """User-facing hint printed when the camoufox browser is absent."""
    return (
        "Camoufox stealth browser is not installed.\n"
        "  Install trimmed (~330 MB):  intelliscrape --install-browser\n"
        "  Install full (~930 MB):     intelliscrape --install-browser full\n"
        "  Or via camoufox itself:     camoufox fetch"
    )
