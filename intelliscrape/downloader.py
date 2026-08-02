"""File download utilities for IntelliScrape."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Mapping, MutableMapping, Sequence, Tuple, Union
from urllib.parse import unquote, urlparse

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

from .exceptions import DownloadError


# Original downloader functions (preserved for compatibility)

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
    """Create a hardened :class:`requests.Session` with sane defaults."""

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
    session.trust_env = False
    session.max_redirects = 5

    return session


def _ensure_safe_url(url: str) -> None:
    """Validate that ``url`` uses an allowed scheme."""
    parsed = urlparse(url)
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
    """Download HTML for ``url`` with hardened defaults."""

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


# New file download utilities


@dataclass
class DownloadResult:
    """Result of a file download."""
    url: str
    file_path: str
    file_name: str
    file_size: int
    content_type: str
    success: bool
    error: str = ""


class Downloader:
    """Download files from URLs."""
    
    # Common file extensions
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp"}
    DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"}
    ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz"}
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".aac"}
    
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        })
    
    def download(
        self,
        url: str,
        output_dir: str = "downloads",
        filename: Optional[str] = None,
        *,
        timeout: int = 60,
        chunk_size: int = 8192,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DownloadResult:
        """Download a file.
        
        Parameters
        ----------
        url : str
            URL to download.
        output_dir : str
            Output directory.
        filename : str, optional
            Custom filename. If None, uses URL filename.
        timeout : int
            Request timeout.
        chunk_size : int
            Download chunk size.
        progress_callback : callable, optional
            Callback with (downloaded, total) bytes.
            
        Returns
        -------
        DownloadResult
            Download result.
        """
        try:
            # Create output directory
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Get filename
            if not filename:
                filename = self._get_filename(url)
            
            # Full file path
            file_path = os.path.join(output_dir, filename)
            
            # Download
            response = self.session.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Get file size
            total_size = int(response.headers.get("content-length", 0))
            
            # Get content type
            content_type = response.headers.get("content-type", "application/octet-stream")
            
            # Save file
            downloaded = 0
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            return DownloadResult(
                url=url,
                file_path=file_path,
                file_name=filename,
                file_size=downloaded,
                content_type=content_type,
                success=True,
            )
            
        except Exception as e:
            return DownloadResult(
                url=url,
                file_path="",
                file_name=filename or "",
                file_size=0,
                content_type="",
                success=False,
                error=str(e),
            )
    
    def download_images(
        self,
        html: str,
        base_url: str,
        output_dir: str = "downloads/images",
        *,
        timeout: int = 60,
    ) -> List[DownloadResult]:
        """Download all images from HTML.
        
        Parameters
        ----------
        html : str
            HTML content.
        base_url : str
            Base URL for resolving relative URLs.
        output_dir : str
            Output directory.
        timeout : int
            Request timeout.
            
        Returns
        -------
        list of DownloadResult
            Download results.
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, "html.parser")
        image_urls = set()
        
        # Find all images
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                from urllib.parse import urljoin
                full_url = urljoin(base_url, src)
                image_urls.add(full_url)
        
        # Download all images
        results = []
        for url in image_urls:
            result = self.download(url, output_dir, timeout=timeout)
            results.append(result)
        
        return results
    
    def download_links(
        self,
        html: str,
        base_url: str,
        output_dir: str = "downloads/files",
        *,
        extensions: Optional[set] = None,
        timeout: int = 60,
    ) -> List[DownloadResult]:
        """Download all linked files from HTML.
        
        Parameters
        ----------
        html : str
            HTML content.
        base_url : str
            Base URL for resolving relative URLs.
        output_dir : str
            Output directory.
        extensions : set, optional
            File extensions to download. If None, downloads all.
        timeout : int
            Request timeout.
            
        Returns
        -------
        list of DownloadResult
            Download results.
        """
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        soup = BeautifulSoup(html, "html.parser")
        file_urls = set()
        
        # Find all links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_url, href)
            
            # Check extension
            if extensions:
                parsed = urlparse(full_url)
                path = unquote(parsed.path)
                ext = os.path.splitext(path)[1].lower()
                if ext in extensions:
                    file_urls.add(full_url)
            else:
                file_urls.add(full_url)
        
        # Download all files
        results = []
        for url in file_urls:
            result = self.download(url, output_dir, timeout=timeout)
            results.append(result)
        
        return results
    
    def _get_filename(self, url: str) -> str:
        """Extract filename from URL."""
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        # Get filename from path
        filename = os.path.basename(path)
        
        # If no filename, use hash
        if not filename or "." not in filename:
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"download_{url_hash}"
        
        return filename
