"""URL → local filesystem path mapping.

Ported from HTTrack's ``url_savename()`` in htsname.c.

The naming module converts a remote URL into a deterministic local save path
that mirrors the original site's directory structure.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse, parse_qs, urlencode, unquote

from .config import MirrorConfig

# Characters that are unsafe in file/path names
_UNSAFE_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_MULTI_SLASHES = re.compile(r"/{2,}")
_DOTS = re.compile(r"/\.{1,2}(/|$)")


class SaveNamer:
    """Compute a local save path for a remote URL.

    By default the original directory structure is preserved::

        https://example.com/dir/page.html  →  example.com/dir/page.html
        https://example.com/img/logo.png   →  example.com/img/logo.png
    """

    def __init__(self, config: MirrorConfig) -> None:
        self.config = config
        self._seen: dict[str, str] = {}  # url → save_path (dedup)

    def compute_path(self, url: str) -> str:
        """Return the mirror-relative path where *url* should be saved.

        The returned path always uses forward slashes and is relative to the
        mirror's output directory.
        """
        if url in self._seen:
            return self._seen[url]

        path = self._url_to_path(url)
        path = self._dedup(path)
        self._seen[url] = path
        return path

    # ------------------------------------------------------------------
    # Core conversion
    # ------------------------------------------------------------------

    def _url_to_path(self, url: str) -> str:
        parsed = urlparse(url)
        host = (parsed.hostname or "localhost").lower()
        raw_path = unquote(parsed.path)

        # Normalise slashes and dot-segments
        raw_path = _MULTI_SLASHES.sub("/", raw_path)
        raw_path = _DOTS.sub("/", raw_path)

        if not raw_path or raw_path == "/":
            raw_path = "/index.html"

        # Ensure it looks like a file (has an extension)
        if "." not in raw_path.split("/")[-1]:
            raw_path = raw_path.rstrip("/") + "/index.html"

        # Sanitise each path component
        parts: list[str] = []
        for part in raw_path.split("/"):
            if not part:
                continue
            part = _UNSAFE_CHARS.sub("_", part)
            # Truncate very long names
            if len(part) > 200:
                name, ext = _split_ext(part)
                part = name[:190] + ext
            parts.append(part)

        # Build: host/path/to/file.html
        save_path = host + "/" + "/".join(parts)

        # Append query string as a hash (to avoid collisions)
        if parsed.query:
            qs_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
            name, ext = _split_ext(save_path)
            save_path = f"{name}_{qs_hash}{ext}"

        return save_path

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _dedup(self, path: str) -> str:
        """Ensure *path* is unique in the seen-map."""
        if path not in self._seen.values():
            return path

        name, ext = _split_ext(path)
        counter = 2
        while True:
            candidate = f"{name}_{counter}{ext}"
            if candidate not in self._seen.values():
                return candidate
            counter += 1

    # ------------------------------------------------------------------
    # Query-string handling
    # ------------------------------------------------------------------

    def _query_to_suffix(self, query: str, max_len: int = 60) -> str:
        """Convert a query string to a filesystem-safe suffix."""
        if not query:
            return ""
        qs_hash = hashlib.md5(query.encode()).hexdigest()[:12]
        return f"__{qs_hash}"


def _split_ext(path: str) -> tuple[str, str]:
    """Split *path* into (name, extension).

    ``/foo/bar.css`` → ``("/foo/bar", ".css")``
    ``/foo/bar``     → ``("/foo/bar", "")``
    """
    last_slash = path.rfind("/")
    last_dot = path.rfind(".")

    if last_dot > last_slash:
        return path[:last_dot], path[last_dot:]
    return path, ""


def normalise_url(url: str) -> str:
    """Lightweight URL normalisation (cf. HTTrack's ``urlhack`` mode)."""
    parsed = urlparse(url)

    host = (parsed.hostname or "").lower()
    # Strip leading www. for dedup
    if host.startswith("www."):
        host = host[4:]

    path = _MULTI_SLASHES.sub("/", parsed.path)
    path = _DOTS.sub("/", path)

    # Sort query parameters for determinism
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        sorted_qs = urlencode(sorted(qs.items()), doseq=True)
    else:
        sorted_qs = ""

    return f"{parsed.scheme}://{host}{path}" + (f"?{sorted_qs}" if sorted_qs else "")
