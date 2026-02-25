"""Utilities for securely downloading HTML resources for IntelliScrape."""

from __future__ import annotations

from typing import Mapping, MutableMapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlsplit

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

from .exceptions import DownloadError

DEFAULT_HEADERS: MutableMapping[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_DEFAULT_STATUS_FORCELIST = (429, 500, 502, 503, 504)
_DEFAULT_ALLOWED_METHODS = ("HEAD", "GET", "OPTIONS")
_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 20.0)
_ALLOWED_SCHEMES = {"http", "https"}

TimeoutType = Union[float, Tuple[float, float]]


def create_session(
    *,
    retries: int = 3,
    backoff_factor: float = 0.6,
    status_forcelist: Sequence[int] = _DEFAULT_STATUS_FORCELIST,
    allowed_methods: Sequence[str] = _DEFAULT_ALLOWED_METHODS,
    pool_connections: int = 10,
    pool_maxsize: int = 20,
) -> Session:
    """Create a hardened :class:`requests.Session` with sane defaults.

    Parameters
    ----------
    retries:
        Maximum number of retry attempts for transient errors.
    backoff_factor:
        Base factor for exponential backoff between retries.
    status_forcelist:
        HTTP status codes that should trigger a retry.
    allowed_methods:
        HTTP methods eligible for retry. Defaults to idempotent verbs.
    pool_connections:
        Minimum number of connection pools to keep.
    pool_maxsize:
        Maximum pool size per host.
    """

    retry_strategy = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(method.upper() for method in allowed_methods),
        raise_on_status=False,
        raise_on_redirect=True,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
    )

    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    session.trust_env = False  # avoid inheriting potentially unsafe proxy settings
    session.max_redirects = 5

    return session


def _ensure_safe_url(url: str) -> None:
    """Validate that ``url`` uses an allowed scheme."""

    parsed = urlsplit(url)
    if not parsed.scheme or parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise DownloadError(f"Unsupported or unsafe URL scheme for '{url}'.")


def _merge_headers(custom: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    """Merge user-provided headers with hardened defaults."""

    if not custom:
        return DEFAULT_HEADERS
    merged: MutableMapping[str, str] = {**DEFAULT_HEADERS}
    merged.update({k: v for k, v in custom.items() if v is not None})
    return merged


def _normalize_timeout(timeout: Optional[TimeoutType]) -> TimeoutType:
    """Normalize timeout inputs to ``requests`` accepted formats."""

    if timeout is None:
        return _DEFAULT_TIMEOUT
    if isinstance(timeout, (int, float)):
        if timeout <= 0:
            raise DownloadError("Timeout must be positive.")
        return float(timeout)
    if (
        isinstance(timeout, tuple)
        and len(timeout) == 2
        and all(isinstance(value, (int, float)) and value > 0 for value in timeout)
    ):
        return float(timeout[0]), float(timeout[1])
    raise DownloadError("Timeout must be a positive number or a (connect, read) tuple.")


def download_html(
    url: str,
    *,
    session: Optional[Session] = None,
    timeout: Optional[TimeoutType] = None,
    headers: Optional[Mapping[str, str]] = None,
    allow_redirects: bool = False,
    return_response: bool = False,
) -> Union[str, Response]:
    """Download HTML for ``url`` with hardened defaults.

    Parameters
    ----------
    url:
        Target resource URL. Schemes are restricted to ``http`` and ``https``.
    session:
        Optional pre-configured session. A secure session is created if omitted.
    timeout:
        ``requests`` timeout parameter. Defaults to ``(_DEFAULT_TIMEOUT)``.
    headers:
        Optional headers merged atop :data:`DEFAULT_HEADERS`.
    allow_redirects:
        Whether redirects are followed. Disabled by default to avoid open
        redirect abuse; if enabled, redirect targets are revalidated.
    return_response:
        When ``True`` the raw :class:`requests.Response` is returned instead of
        ``response.text``.

    Returns
    -------
    str
        HTML payload from the response body.
    """

    _ensure_safe_url(url)
    normalized_timeout = _normalize_timeout(timeout)
    prepared_headers = _merge_headers(headers)

    close_session = False
    active_session = session
    if active_session is None:
        active_session = create_session()
        close_session = True

    try:
        response: Response = active_session.get(
            url,
            timeout=normalized_timeout,
            headers=prepared_headers,
            allow_redirects=allow_redirects,
        )
        if allow_redirects:
            _ensure_safe_url(response.url)
        response.raise_for_status()

        if not response.encoding:
            response.encoding = response.apparent_encoding or "utf-8"

        if return_response:
            return response

        return response.text
    except RequestException as exc:
        raise DownloadError(f"Error while downloading '{url}': {exc}") from exc
    finally:
        if close_session:
            active_session.close()