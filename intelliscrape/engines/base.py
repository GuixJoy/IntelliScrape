"""Base engine interface for IntelliScrape."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ScrapeResult:
    """Result from a scraping engine."""
    url: str
    html: str
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    engine: str = "unknown"
    success: bool = True
    error: Optional[str] = None
    redirect_url: Optional[str] = None


class BaseEngine(ABC):
    """Base class for scraping engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name."""
        ...

    @abstractmethod
    def fetch(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        **kwargs,
    ) -> ScrapeResult:
        """Fetch a URL and return the result.

        Parameters
        ----------
        url : str
            Target URL.
        headers : dict, optional
            Custom headers.
        cookies : dict, optional
            Custom cookies.
        timeout : float
            Request timeout in seconds.

        Returns
        -------
        ScrapeResult
            The scraping result.
        """
        ...

    def is_available(self) -> bool:
        """Check if this engine's dependencies are installed."""
        return True
