"""Disk-based cache for mirror resume support.

Ported from HTTrack's ``cache_back`` (htscache.c).

Stores metadata about downloaded URLs so that a subsequent ``--update`` run
can skip already-fetched resources.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class CacheEntry:
    """Metadata for one cached download."""

    url: str
    save_path: str
    status_code: int = 200
    content_type: str = ""
    content_length: int = 0
    content_hash: str = ""  # SHA-256 of the body
    etag: str | None = None
    last_modified: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    depth: int = 0


class MirrorCache:
    """Simple JSON-file-backed cache for a mirror project.

    The cache lives at ``<output_dir>/.track-cache.json`` and maps URLs
    to their download metadata.
    """

    _CACHE_FILE = ".track-cache.json"

    def __init__(self, output_dir: str | Path) -> None:
        self._dir = Path(output_dir)
        self._path = self._dir / self._CACHE_FILE
        self._entries: dict[str, CacheEntry] = {}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load cache from disk (no-op if file doesn't exist)."""
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for url, blob in data.items():
                self._entries[url] = CacheEntry(**blob)
        except Exception:
            self._entries = {}

    def save(self) -> None:
        """Persist the cache to disk."""
        self._dir.mkdir(parents=True, exist_ok=True)
        data = {url: asdict(e) for url, e in self._entries.items()}
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Read / write
    # ------------------------------------------------------------------

    def get(self, url: str) -> CacheEntry | None:
        return self._entries.get(url)

    def has(self, url: str) -> bool:
        return url in self._entries

    def set(
        self,
        url: str,
        save_path: str,
        status_code: int = 200,
        content_type: str = "",
        content_length: int = 0,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        depth: int = 0,
    ) -> CacheEntry:
        """Create or update a cache entry."""
        content_hash = ""
        if body:
            content_hash = hashlib.sha256(body).hexdigest()

        entry = CacheEntry(
            url=url,
            save_path=save_path,
            status_code=status_code,
            content_type=content_type,
            content_length=content_length,
            content_hash=content_hash,
            etag=headers.get("etag") if headers else None,
            last_modified=headers.get("last-modified") if headers else None,
            headers=headers or {},
            timestamp=time.time(),
            depth=depth,
        )
        self._entries[url] = entry
        return entry

    def remove(self, url: str) -> bool:
        """Remove a URL from the cache. Returns True if it existed."""
        return self._entries.pop(url, None) is not None

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_fresh(self, url: str, max_age: float = 86400) -> bool:
        """Return True if the cached copy is newer than *max_age* seconds."""
        entry = self._entries.get(url)
        if entry is None:
            return False
        return (time.time() - entry.timestamp) < max_age

    def needs_update(
        self,
        url: str,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> bool:
        """Return True if the server version differs from the cache.

        Uses ETag / Last-Modified validators when available, falling back
        to a simple age check.
        """
        entry = self._entries.get(url)
        if entry is None:
            return True

        # If we have validators, compare
        if etag and entry.etag and etag == entry.etag:
            return False
        if last_modified and entry.last_modified and last_modified == entry.last_modified:
            return False

        # Fallback: stale after 24 h
        return not self.is_fresh(url)

    @property
    def entries(self) -> dict[str, CacheEntry]:
        return dict(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()
