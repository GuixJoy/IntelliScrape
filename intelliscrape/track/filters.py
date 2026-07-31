"""URL include / exclude filter patterns.

Ported from HTTrack's ``fa_strjoker()`` in htsfilters.c.

Supports wildcard patterns like ``*.pdf``, ``/admin/*``, ``+*.html``.
"""

from __future__ import annotations

import fnmatch
import re
from urllib.parse import urlparse


class URLFilter:
    """Decide whether a URL matches a set of include/exclude patterns.

    Patterns use simple shell-style wildcards applied to the URL's path:

    * ``*.pdf``       – any path ending in ``.pdf``
    * ``/admin/*``    – anything under ``/admin/``
    * ``-*.zip``      – exclude zip files (``-`` prefix is the exclude marker)
    * ``+*.html``     – include html files (``+`` prefix is the include marker)

    Patterns without a prefix are treated as exclude patterns.

    The last matching pattern wins (consistent with HTTrack).
    """

    def __init__(
        self,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> None:
        self._includes = [_compile(p) for p in (include or [])]
        self._excludes = [_compile(p) for p in (exclude or [])]

    def matches(self, url: str) -> bool:
        """Return True if *url* passes the filter (i.e. should be fetched)."""
        path = urlparse(url).path

        # Apply excludes first
        for pat in self._excludes:
            if pat.match(path):
                return False

        # If there are includes, the URL must match at least one
        if self._includes:
            for pat in self._includes:
                if pat.match(path):
                    return True
            return False

        return True

    def add_include(self, pattern: str) -> None:
        self._includes.append(_compile(pattern))

    def add_exclude(self, pattern: str) -> None:
        self._excludes.append(_compile(pattern))

    @classmethod
    def from_strings(cls, patterns: list[str]) -> URLFilter:
        """Build a filter from HTTrack-style command-line patterns.

        Each pattern may start with ``+`` (include) or ``-`` (exclude).
        A bare pattern is treated as exclude.
        """
        inc: list[str] = []
        exc: list[str] = []
        for p in patterns:
            if p.startswith("+"):
                inc.append(p[1:])
            elif p.startswith("-"):
                exc.append(p[1:])
            else:
                exc.append(p)
        return cls(include=inc, exclude=exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compile(pattern: str) -> re.Pattern[str]:
    """Compile a wildcard pattern into a regex.

    Handles ``*`` (any chars), ``?`` (one char), and ``**`` (any path depth).
    """
    # Strip leading +/- marker
    if pattern and pattern[0] in "+-":
        pattern = pattern[1:]

    # Convert shell globs to regex
    regex = fnmatch.translate(pattern)
    return re.compile(regex, re.IGNORECASE)
