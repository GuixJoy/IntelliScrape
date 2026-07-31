"""Website mirroring for IntelliScrape.

Mirrors complete websites (HTML, CSS, JS, images, fonts, etc.) for offline
browsing, with URL rewriting, robots.txt compliance, and ZIP packaging.

Quick usage::

    from intelliscrape.track import mirror

    # Mirror a site to disk
    result = mirror("https://example.com", max_depth=3)

    # Mirror and create a ZIP
    result = mirror("https://example.com", save_zip="site.zip")

Advanced usage::

    from intelliscrape.track import SiteMirror, MirrorConfig

    config = MirrorConfig(
        url="https://example.com",
        max_depth=4,
        output_dir="./my-mirror",
        exclude_patterns=["*.pdf", "/admin/*"],
        engine="playwright",  # use anti-detection engine
    )

    m = SiteMirror(config)
    result = m.run(save_zip="mirror.zip")
"""

from .config import MirrorConfig
from .mirror import SiteMirror, MirrorResult, mirror
from .parser import AssetDiscovery, DiscoveredAsset
from .rewriter import URLRewriter
from .cache import MirrorCache, CacheEntry
from .robots import RobotsParser
from .filters import URLFilter
from .naming import SaveNamer

__all__ = [
    "MirrorConfig",
    "SiteMirror",
    "MirrorResult",
    "mirror",
    "AssetDiscovery",
    "DiscoveredAsset",
    "URLRewriter",
    "MirrorCache",
    "CacheEntry",
    "RobotsParser",
    "URLFilter",
    "SaveNamer",
]
